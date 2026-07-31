-- ============================================================================
-- TIDE · sql/procedures/adjudicate.sql
-- DECISION.ADJUDICATE — the deterministic decision engine, in Snowflake.
--
-- NOT in sql/*.sql on purpose. This procedure IMPORTS tide_decision.zip from
-- DECISION.CODE_STAGE, and Snowflake resolves IMPORTS at CREATE time, so the
-- module has to be on the stage first. scripts/deploy.py step 3 zips
-- tide_decision/, uploads it, then runs this file.
--
-- No business logic lives here. The wrapper loads the bundle, reads
-- RULE_CONSTANTS, calls the pure function, and writes down what came back.
-- Money is decided by tide_decision and nothing else — ARCHITECTURE.md §7.4.
--
-- Idempotent: safe to re-run
-- ============================================================================

USE DATABASE TIDE;
USE SCHEMA DECISION;

CREATE OR REPLACE PROCEDURE ADJUDICATE(CASE_ID VARCHAR)
RETURNS VARIANT
LANGUAGE PYTHON
RUNTIME_VERSION = '3.11'
PACKAGES = ('snowflake-snowpark-python')
IMPORTS = ('@TIDE.DECISION.CODE_STAGE/tide_decision.zip')
HANDLER = 'run'
COMMENT = 'Adjudicate a case against its latest evidence bundle using the deterministic engine. Input: case_id. Writes the decision, the decision_made event and any resolution request, transitions the case, and returns the decision.'
EXECUTE AS OWNER
AS
$$
import json

from tide_decision import adjudicate


def _constants(session):
    """Business thresholds come from the table, never from the engine defaults.

    DETAILS.md §6 is mirrored in DECISION.RULE_CONSTANTS; the engine's
    DEFAULT_CONSTANTS exist so the module stays runnable without a database and
    are a fallback, not the source of truth (TASKS.md B-4).
    """
    rows = session.sql(
        "SELECT key, value FROM TIDE.DECISION.RULE_CONSTANTS"
    ).collect()
    out = {}
    for r in rows:
        raw = r["VALUE"]
        try:
            out[r["KEY"]] = json.loads(raw) if isinstance(raw, str) else raw
        except (TypeError, ValueError):
            out[r["KEY"]] = raw
    return out


def _log(session, case_id, status, detail):
    session.sql(
        """
        INSERT INTO TIDE.EXECUTION.PIPELINE_LOG (case_id, component, status, detail)
        SELECT ?, 'ADJUDICATE', ?, PARSE_JSON(?)
        """,
        params=[case_id, status, json.dumps(detail)],
    ).collect()


def run(session, case_id):
    try:
        rows = session.sql(
            """
            SELECT bundle_id, bundle
            FROM TIDE.INVESTIGATION.EVIDENCE_BUNDLES
            WHERE case_id = ? AND assembly_status = 'complete'
            ORDER BY assembled_at DESC
            LIMIT 1
            """,
            params=[case_id],
        ).collect()

        if not rows:
            _log(session, case_id, "failed", {"error": "no complete evidence bundle"})
            return {"error": "No complete evidence bundle for this case."}

        bundle_id = rows[0]["BUNDLE_ID"]
        bundle = rows[0]["BUNDLE"]
        if isinstance(bundle, str):
            bundle = json.loads(bundle)

        decision = adjudicate(bundle, _constants(session))

        # The decision row, the resolution request and the state transition are
        # one fact about the case. Writing them without a transaction once left
        # a case with an R-01 decision recorded but still sitting in
        # pending_triage, because the middle write failed. All or nothing.
        session.sql("BEGIN").collect()

        # Enums are str-valued, but be explicit rather than relying on it.
        target_status = getattr(decision.target_status, "value", decision.target_status)
        resolution_type = getattr(decision.resolution_type, "value", decision.resolution_type)
        reason_code = getattr(
            decision.invalid_reason_code, "value", decision.invalid_reason_code
        )

        payload = {
            "path_id": decision.path_id,
            "target_status": target_status,
            "resolution_type": resolution_type,
            "eligible_amount": float(decision.eligible_amount),
            "shipping_fee_only": bool(decision.shipping_fee_only),
            "invalid_reason_code": reason_code,
            "reason": decision.reason,
            "tracking_evidence": decision.tracking_evidence,
            "replacement_items": list(decision.replacement_items),
            "affected_item_ids": list(decision.affected_item_ids),
            "bundle_id": bundle_id,
        }

        session.sql(
            """
            INSERT INTO TIDE.DECISION.DECISIONS
                (case_id, path_id, target_status, resolution_type, eligible_amount,
                 shipping_fee_only, invalid_reason_code, reason, input_snapshot)
            SELECT ?, ?, ?, ?, ?, ?, ?, ?, PARSE_JSON(?)
            """,
            params=[
                case_id, decision.path_id, target_status, resolution_type,
                float(decision.eligible_amount), bool(decision.shipping_fee_only),
                reason_code, decision.reason, json.dumps(bundle, default=str),
            ],
        ).collect()

        # The event carries the full decision plus the bundle it was made from,
        # so the audit trail can be replayed without joining anything.
        session.sql(
            """
            INSERT INTO TIDE.TRIAGE.CASE_EVENTS
                (case_id, event_type, actor_type, actor_id, payload)
            SELECT ?, 'decision_made', 'system', CURRENT_USER(), PARSE_JSON(?)
            """,
            params=[case_id, json.dumps(payload, default=str)],
        ).collect()

        # A decision that grants something needs a request row: it is what the
        # approver queue reads, and what EXECUTE_RESOLUTION acts on.
        request_id = None
        if resolution_type and target_status in (
            "awaiting_approval",
            "approved_executing",
        ):
            # item_ids is an ARRAY column. A Python list cannot be bound to a
            # placeholder — the connector raises "list index out of range" —
            # so it goes over as JSON text and is parsed back on arrival.
            session.sql(
                """
                INSERT INTO TIDE.EXECUTION.RESOLUTION_REQUESTS
                    (case_id, request_type, status, amount, item_ids, detail)
                SELECT ?, ?, 'pending', ?, PARSE_JSON(?)::ARRAY, PARSE_JSON(?)
                """,
                params=[
                    case_id, resolution_type, float(decision.eligible_amount),
                    json.dumps(list(decision.affected_item_ids)),
                    json.dumps(
                        {
                            "path_id": decision.path_id,
                            "shipping_fee_only": bool(decision.shipping_fee_only),
                            "replacement_items": list(decision.replacement_items),
                        }
                    ),
                ],
            ).collect()
            got = session.sql(
                """
                SELECT request_id FROM TIDE.EXECUTION.RESOLUTION_REQUESTS
                WHERE case_id = ? ORDER BY created_at DESC LIMIT 1
                """,
                params=[case_id],
            ).collect()
            request_id = got[0]["REQUEST_ID"] if got else None

        # Transition last: legality is enforced in TRANSITION_STATE, and an
        # illegal move must not leave a decision row pointing at a state the
        # case never reached.
        session.sql(
            "CALL TIDE.TRIAGE.TRANSITION_STATE(?, ?, 'system', CURRENT_USER(), ?)",
            params=[case_id, target_status, f"{decision.path_id}: {decision.reason}"],
        ).collect()

        session.sql("COMMIT").collect()

        _log(
            session,
            case_id,
            "completed",
            {
                "path_id": decision.path_id,
                "target_status": target_status,
                "eligible_amount": float(decision.eligible_amount),
                "request_id": request_id,
            },
        )

        result = dict(payload)
        result["request_id"] = request_id
        result["success"] = True
        return result

    except Exception as exc:  # noqa: BLE001 - failure is a routed branch, not a crash
        try:
            session.sql("ROLLBACK").collect()
        except Exception:  # noqa: BLE001 - nothing to roll back if we never began
            pass
        # Logged outside the transaction on purpose: a failure that rolled back
        # its own writes still has to leave a trace.
        _log(session, case_id, "failed", {"error": str(exc)})
        return {"success": False, "error": str(exc)}
$$;

GRANT USAGE ON PROCEDURE TIDE.DECISION.ADJUDICATE(VARCHAR) TO ROLE TIDE_ADMIN;
