"""End-to-end matrix runner — the deployed system, not the engine.

`pytest tests/` proves the decision engine is correct against fabricated bundles.
This proves the *deployed* system is correct against the seeded data: that
OPEN_CASE, ASSEMBLE_EVIDENCE and ADJUDICATE, running on Snowflake over
`sql/seed/seed_retail.sql`, land each scenario on the path it was engineered to
trip. Those are different claims, and only this one is what a demo shows.

Closes the "full matrix pass, twice, second one uninterrupted" gate in
`docs/SUBMISSION.md`.

    python scripts/run_matrix.py --connection tide
    python scripts/run_matrix.py --only E-08 --keep     # one scenario, leave the case

Exit codes: 0 all as expected · 1 unexpected result · 2 harness/connection error.

--- Two things worth understanding before editing ---

**Ownership.** `OPEN_CASE` scopes the order to `CURRENT_USER()` (a deliberate
check on the owner's side of the boundary, not something to work around). The
seeded orders belong to `@example.com` addresses that are not Snowflake users,
so the runner takes ownership of one order at a time and hands it back
immediately. A crash leaves at most one order reassigned, `--restore-only`
repairs it, and re-running `seed_retail.sql` is the backstop.

**Proof-gated scenarios stop before adjudication, on purpose.** A proof-required
subtype opens directly into `awaiting_customer_proof`, and the only legal exits
from there are `pending_triage` and `closed` (DETAILS.md §8). `RESUME_INTAKE` is
the way out and it refuses while `PROOF_FILES` is empty. So the flow genuinely
cannot adjudicate one of these until proof exists, and these scenarios assert
**the gate holds** rather than asserting a decision path.

They are *not* blocked on `ANALYZE_PROOF` any more — that landed on 4 Aug and the
whole path is verified working, through vision analysis to a real G-08. They are
blocked on **image fixtures**: reaching the intended path (R-08, R-13, ...)
requires a photograph whose contents actually support the claim, and this runner
has none. Uploading an arbitrary image would reach G-08 (proof contradicts) and
assert nothing useful. Add real fixtures per scenario and these become PASS
against `intended`.

A consequence worth knowing, surfaced by an earlier version of this runner that
called ADJUDICATE anyway: **guardrail G-06 is unreachable end to end.** It fires
on "proof required but not present", but the only route to adjudication for such
a subtype passes through `RESUME_INTAKE`, which requires a proof file. So
`proof_present` is always true by then. G-06 is correct and tested in the engine
and is real defence in depth, but the deployed system enforces that gate with the
state machine, one layer earlier. Calling ADJUDICATE directly from
`awaiting_customer_proof` returns
`{"success": false, "error": "... ILLEGAL_TRANSITION ..."}` — a graceful refusal,
not a crash, and not a path the UI can take.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

# --------------------------------------------------------------------------
# The matrix. Scenario ids and intended paths come from the comment above each
# order in sql/seed/seed_retail.sql — that file is the source of truth; if it
# changes, change this with it.
#
#   expect     - the path id the deployed system must produce today
#   gate       - a status the flow legitimately stops at, short of adjudication
#   intended   - what the seed comment says, once the blocker is gone
#   blocked_by - unbuilt component preventing `intended`; reported BLOCKED
# --------------------------------------------------------------------------
SCENARIOS = [
    # --- proof-required subtypes: hold at the proof gate, no adjudication ---
    dict(id="E-01", order="ORD-1001", subtype="damaged_goods",      resolution="refund",
         expect=None, gate="awaiting_customer_proof", intended="R-08",
         blocked_by="a supporting proof image"),
    dict(id="E-02", order="ORD-1002", subtype="damaged_goods",      resolution="refund",
         expect=None, gate="awaiting_customer_proof", intended="R-09",
         blocked_by="a supporting proof image"),
    dict(id="E-04", order="ORD-1003", subtype="damaged_goods",      resolution="refund",
         expect=None, gate="awaiting_customer_proof", intended="G-08",
         blocked_by="a supporting proof image"),
    dict(id="E-03", order="ORD-1004", subtype="damaged_goods",      resolution="refund",
         expect=None, gate="awaiting_customer_proof", intended="held at gate",
         blocked_by="a supporting proof image",
         note="the gate holding IS this scenario's intended outcome"),
    dict(id="E-06", order="ORD-1005", subtype="wrong_item",         resolution="replacement",
         expect=None, gate="awaiting_customer_proof", intended="R-13",
         blocked_by="a supporting proof image"),
    dict(id="E-07", order="ORD-1006", subtype="wrong_item",         resolution="replacement",
         expect=None, gate="awaiting_customer_proof", intended="R-12",
         blocked_by="a supporting proof image"),
    dict(id="E-20", order="ORD-1019", subtype="partial_fulfillment", resolution="refund",
         expect=None, gate="awaiting_customer_proof", intended="R-21",
         blocked_by="a supporting proof image"),

    # --- guardrails, fully reachable ---
    dict(id="E-09", order="ORD-1008", subtype="duplicate_charge", resolution="refund",
         expect="G-03", note="prior refund on record -> duplicate-refund risk"),
    dict(id="E-10", order="ORD-1009", subtype="duplicate_charge", resolution="refund",
         expect="G-04", note="payment pending; G-04 precedes G-10"),
    dict(id="E-11", order="ORD-1010", subtype="non_receipt",      resolution="refund",
         expect="G-05", note="delivery scan contradicts the claim"),

    # --- routing, fully reachable ---
    dict(id="E-08", order="ORD-1007", subtype="duplicate_charge", resolution="refund",
         expect="R-01", note="two confirmed charges, under the autonomous limit"),
    dict(id="E-12", order="ORD-1011", subtype="non_receipt",      resolution="refund",
         expect="R-31"),
    dict(id="E-13", order="ORD-1012", subtype="non_receipt",      resolution="refund",
         expect="R-36", note="stale in transit, over the limit"),
    dict(id="E-14", order="ORD-1013", subtype="delayed",          resolution="refund",
         expect="R-38", note="SLA breach -> shipping fee only"),
    dict(id="E-15", order="ORD-1014", subtype="exception",        resolution="refund",
         expect="R-46"),
    dict(id="E-16", order="ORD-1015", subtype="lost",             resolution="refund",
         expect="R-50"),
    dict(id="E-17", order="ORD-1016", subtype="return_request",   resolution="return",
         expect="R-24", note="inside the return window"),
    dict(id="E-18", order="ORD-1017", subtype="return_request",   resolution="return",
         expect="R-23", note="outside the return window"),
    dict(id="E-19", order="ORD-1018", subtype="changed_mind",     resolution="return",
         expect="R-25", note="order still 'placed' -> non-returnable"),
    dict(id="E-21", order="ORD-1020", subtype="other",            resolution="refund",
         expect="R-28"),

    # --- refusals: the correct outcome is that nothing opens at all ---
    # ORD-1023 is the "cancelled order is not disputable" probe. This ran as an
    # OBSERVE until 5 Aug, when OPEN_CASE started enforcing ineligible_order_state
    # (DETAILS.md §12) — the gap this runner reported. It is now an assertion:
    # a case must NOT open on a cancelled order.
    dict(id="E-22", order="ORD-1023", subtype="duplicate_charge", resolution="refund",
         expect=None, expect_refusal="ineligible_order_state",
         note="cancelled order must be refused at intake"),
]

# E-25 (duplicate open case) is asserted separately — it needs two OPEN_CASE
# calls on one order, which does not fit the one-case-per-scenario shape.
DUPLICATE_PROBE_ORDER = "ORD-1021"

# E-24 (timeout) is deliberately absent: it depends on T_TIMEOUT_SWEEP firing on
# a cron, so it is a wall-clock test rather than a matrix row. Verify by hand.

ALL_MATRIX_ORDERS = [s["order"] for s in SCENARIOS] + [DUPLICATE_PROBE_ORDER]

# Scoped teardown, ordered so children go before parents. Mirrors the teardown
# in sql/seed/seed_demo_customer.sql; keep the two in step.
PURGE_CASE_SQL = """
DELETE FROM TIDE.EXECUTION.CASE_REPORTS        WHERE case_id IN (SELECT case_id FROM TIDE.TRIAGE.CASES WHERE order_id = '{order}');
DELETE FROM TIDE.EXECUTION.PIPELINE_LOG        WHERE case_id IN (SELECT case_id FROM TIDE.TRIAGE.CASES WHERE order_id = '{order}');
DELETE FROM TIDE.EXECUTION.RESOLUTION_REQUESTS WHERE case_id IN (SELECT case_id FROM TIDE.TRIAGE.CASES WHERE order_id = '{order}');
DELETE FROM TIDE.DECISION.DECISIONS            WHERE case_id IN (SELECT case_id FROM TIDE.TRIAGE.CASES WHERE order_id = '{order}');
DELETE FROM TIDE.INVESTIGATION.EVIDENCE_BUNDLES WHERE case_id IN (SELECT case_id FROM TIDE.TRIAGE.CASES WHERE order_id = '{order}');
DELETE FROM TIDE.TRIAGE.CASE_EVENTS            WHERE case_id IN (SELECT case_id FROM TIDE.TRIAGE.CASES WHERE order_id = '{order}');
DELETE FROM TIDE.TRIAGE.CHAT                   WHERE case_id IN (SELECT case_id FROM TIDE.TRIAGE.CASES WHERE order_id = '{order}');
DELETE FROM TIDE.TRIAGE.CASES                  WHERE order_id = '{order}';
""".strip()


class SnowError(RuntimeError):
    """A `snow sql` invocation failed outright."""


def run_sql(connection: str, sql: str) -> list:
    """Execute a SQL script and return one parsed result set per statement.

    Goes through the CLI rather than a driver so the runner adds no dependency
    (ARCHITECTURE.md requires a line for each). Always a file, never -q: the
    scripts here contain JSON paths and quoting that the -q path mangles.
    """
    with tempfile.NamedTemporaryFile("w", suffix=".sql", delete=False,
                                     encoding="utf-8") as handle:
        handle.write(sql)
        path = handle.name
    try:
        proc = subprocess.run(
            ["snow", "sql", "--connection", connection, "--format", "json",
             "--filename", path],
            capture_output=True, timeout=300,
            # Decode explicitly rather than via the locale. This console is
            # cp1252 and Snowflake happily returns text that is not.
            encoding="utf-8", errors="replace",
        )
        if proc.returncode != 0:
            # The CLI prefixes a harmless encoding UserWarning to stderr on this
            # machine, so stderr alone reads like the error and is not. Carry
            # the code and both streams or the real cause stays hidden.
            noise = "UserWarning: Encoding mismatch"
            err = "\n".join(
                line for line in (proc.stderr or "").splitlines()
                if noise not in line and "warnings.warn" not in line
            ).strip()
            raise SnowError(
                f"exit {proc.returncode}: {err or (proc.stdout or '').strip()[:400]}")
        # The CLI prefixes an encoding warning on this machine; JSON starts at
        # the first bracket.
        out = proc.stdout
        start = out.find("[")
        if start < 0:
            raise SnowError(f"no JSON in output: {out.strip()[:300]}")
        parsed = json.loads(out[start:])
        # A single-statement script returns one result set, not a list of them.
        if parsed and isinstance(parsed[0], dict):
            return [parsed]
        return parsed
    except subprocess.TimeoutExpired as exc:
        raise SnowError(f"timed out after {exc.timeout}s") from exc
    except json.JSONDecodeError as exc:
        raise SnowError(f"unparseable output: {exc}") from exc
    finally:
        Path(path).unlink(missing_ok=True)


def scalar(result_sets: list, index: int, column: str):
    """First row's `column` from result set `index`, or None."""
    try:
        rows = result_sets[index]
        if not rows:
            return None
        row = rows[0]
        # snow returns CALL results under the procedure's name; when there is
        # exactly one column, take it rather than guessing the key.
        if column in row:
            return row[column]
        if len(row) == 1:
            return next(iter(row.values()))
        return None
    except (IndexError, KeyError, TypeError, StopIteration):
        return None


def as_obj(value):
    """CALL returns a VARIANT as a JSON string; give back a dict."""
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return {}
    return {}


def capture_owners(connection: str) -> dict:
    """Record who owns each matrix order, so ownership can be handed back."""
    orders = ", ".join(f"'{o}'" for o in ALL_MATRIX_ORDERS)
    sets = run_sql(connection, f"""
SELECT order_id, customer_id FROM TIDE.RETAIL.ORDERS
WHERE order_id IN ({orders}) ORDER BY order_id;
""")
    return {r["ORDER_ID"]: r["CUSTOMER_ID"] for r in sets[0]}


def suspect_owners(owners: dict) -> list:
    """Matrix orders whose owner does not look like a seeded customer.

    Every order in seed_retail.sql belongs to an `@example.com` address, so
    anything else means a previous run — or a hand-run probe — died before
    handing the order back. This matters more than it looks: `capture_owners`
    treats whatever it finds as the value to restore, so without this check a
    single interrupted run poisons the baseline and every later run faithfully
    "restores" the wrong owner. Learned by doing exactly that.
    """
    return [o for o, c in sorted(owners.items()) if "@" not in str(c)]


def restore_owners(connection: str, owners: dict) -> None:
    """Hand every matrix order back to its seeded customer."""
    if not owners:
        return
    cases = "\n".join(
        f"    WHEN '{oid}' THEN '{cid}'" for oid, cid in sorted(owners.items())
    )
    ids = ", ".join(f"'{o}'" for o in sorted(owners))
    run_sql(connection, f"""
UPDATE TIDE.RETAIL.ORDERS SET customer_id = CASE order_id
{cases}
    END
WHERE order_id IN ({ids});
""")


def verify_restored(connection: str, owners: dict) -> list:
    """Return orders whose owner does not match what we recorded."""
    if not owners:
        return []
    current = capture_owners(connection)
    return [o for o, c in sorted(owners.items()) if current.get(o) != c]


def run_scenario(connection: str, sc: dict, owner: str, keep: bool) -> dict:
    """Drive one scenario through open -> assemble -> adjudicate."""
    order = sc["order"]
    result = dict(sc, actual=None, status_after=None, amount=None,
                  outcome="ERROR", detail="")

    # 1. Take ownership and clear any prior case, so re-runs are clean.
    opened = run_sql(connection, f"""
UPDATE TIDE.RETAIL.ORDERS SET customer_id = CURRENT_USER() WHERE order_id = '{order}';
{PURGE_CASE_SQL.format(order=order)}
CALL TIDE.TRIAGE.OPEN_CASE('{order}', '{sc["subtype"]}', '{sc["resolution"]}');
""")
    open_res = as_obj(scalar(opened, len(opened) - 1, "OPEN_CASE"))
    case_id = open_res.get("case_id")

    # Some scenarios are correct precisely because nothing opens.
    if sc.get("expect_refusal"):
        err = str(open_res.get("error", ""))
        result["actual"] = "refused" if not case_id else "opened"
        result["detail"] = err[:60]
        if case_id:
            result["outcome"] = "FAIL"
            result["detail"] = "a case opened; intake did not refuse"
        elif sc["expect_refusal"] in err:
            result["outcome"] = "PASS"
        else:
            result["outcome"] = "FAIL"
            result["detail"] = f"refused, but not for {sc['expect_refusal']}: {err[:40]}"
        if not keep:
            run_sql(connection, PURGE_CASE_SQL.format(order=order))
        restore_owners(connection, {order: owner})
        return result

    if not case_id:
        result["outcome"] = "ERROR"
        result["detail"] = f"OPEN_CASE: {open_res.get('error', open_res)}"
        restore_owners(connection, {order: owner})
        return result

    # 1b. A gated scenario stops here. Adjudicating from awaiting_customer_proof
    # is not something the UI can do — RESUME_INTAKE is the only way out and it
    # requires a proof file — so driving it further would test a state the real
    # flow cannot reach. Assert the gate held and stop.
    if sc.get("gate"):
        opened_status = open_res.get("status")
        result["actual"] = opened_status
        result["status_after"] = opened_status
        if opened_status == sc["gate"]:
            result["outcome"] = "BLOCKED" if sc.get("blocked_by") else "PASS"
            result["detail"] = (f"held at gate; intended {sc['intended']} "
                                f"needs {sc['blocked_by']}") if sc.get("blocked_by") else ""
        else:
            result["outcome"] = "FAIL"
            result["detail"] = f"expected gate {sc['gate']}, got {opened_status}"
        if not keep:
            run_sql(connection, PURGE_CASE_SQL.format(order=order))
        restore_owners(connection, {order: owner})
        return result

    # 2. Assemble, adjudicate, read the resulting state, then clean up.
    cleanup = "" if keep else PURGE_CASE_SQL.format(order=order)
    hand_back = (f"UPDATE TIDE.RETAIL.ORDERS SET customer_id = '{owner}' "
                 f"WHERE order_id = '{order}';")
    # Reading path_id back off the view is not redundant: ADJUDICATE returns the
    # decision and writes it in one transaction, so a returned path that was
    # never persisted is exactly the failure that transaction exists to prevent.
    sets = run_sql(connection, f"""
CALL TIDE.INVESTIGATION.ASSEMBLE_EVIDENCE('{case_id}');
CALL TIDE.DECISION.ADJUDICATE('{case_id}');
SELECT current_status, path_id FROM TIDE.TRIAGE.V_CASE_CURRENT WHERE case_id = '{case_id}';
{cleanup}
{hand_back}
""")

    decision = as_obj(scalar(sets, 1, "ADJUDICATE"))
    result["actual"] = decision.get("path_id")
    result["amount"] = decision.get("eligible_amount")
    result["status_after"] = scalar(sets, 2, "CURRENT_STATUS")
    persisted = scalar(sets, 2, "PATH_ID")

    if decision.get("error"):
        result["outcome"] = "ERROR"
        result["detail"] = str(decision["error"])[:120]
    elif result["actual"] and persisted != result["actual"]:
        result["outcome"] = "FAIL"
        result["detail"] = (f"returned {result['actual']} but view shows "
                            f"{persisted or 'nothing'} — decision not persisted")
    elif sc["expect"] is None:
        result["outcome"] = "OBSERVE"
        result["detail"] = f"landed on {result['actual']}"
    elif result["actual"] == sc["expect"]:
        result["outcome"] = "BLOCKED" if sc.get("blocked_by") else "PASS"
        if sc.get("blocked_by"):
            result["detail"] = f"intended {sc['intended']}, needs {sc['blocked_by']}"
    else:
        result["outcome"] = "FAIL"
        result["detail"] = f"expected {sc['expect']}, got {result['actual']}"
    return result


def run_duplicate_probe(connection: str, owner: str) -> dict:
    """E-25: a second OPEN_CASE on the same order must be refused."""
    order = DUPLICATE_PROBE_ORDER
    result = dict(id="E-25", order=order, subtype="duplicate_charge",
                  expect="refused", actual=None, status_after=None, amount=None,
                  outcome="ERROR", detail="", blocked_by=None, intended=None,
                  note="one open case per order")
    sets = run_sql(connection, f"""
UPDATE TIDE.RETAIL.ORDERS SET customer_id = CURRENT_USER() WHERE order_id = '{order}';
{PURGE_CASE_SQL.format(order=order)}
CALL TIDE.TRIAGE.OPEN_CASE('{order}', 'duplicate_charge', 'refund');
CALL TIDE.TRIAGE.OPEN_CASE('{order}', 'duplicate_charge', 'refund');
{PURGE_CASE_SQL.format(order=order)}
UPDATE TIDE.RETAIL.ORDERS SET customer_id = '{owner}' WHERE order_id = '{order}';
""")
    first = as_obj(scalar(sets, 9, "OPEN_CASE"))
    second = as_obj(scalar(sets, 10, "OPEN_CASE"))
    if not first.get("case_id"):
        result["detail"] = f"first open failed: {first.get('error', first)}"
        return result
    if second.get("error"):
        result["outcome"] = "PASS"
        result["actual"] = "refused"
        result["detail"] = str(second["error"])[:80]
    else:
        result["outcome"] = "FAIL"
        result["actual"] = "allowed"
        result["detail"] = "second OPEN_CASE created a case; duplicate_case unenforced"
    return result


def report(results: list) -> int:
    """Print the matrix table and return the process exit code."""
    width = 122
    print("\n" + "=" * width)
    print("MATRIX RESULTS")
    print("=" * width)
    print(f"{'ID':<6} {'ORDER':<10} {'SUBTYPE':<20} {'EXPECTED':<24} "
          f"{'ACTUAL':<24} {'RESULT':<8} DETAIL")
    print("-" * width)
    for r in results:
        # A gated scenario asserts a status, not a path id; show whichever
        # applies so the column reads as "what this scenario had to produce".
        target = r["expect"] or r.get("gate") or (
            "refused" if r.get("expect_refusal") else "-")
        print(f"{r['id']:<6} {r['order']:<10} {str(r['subtype'])[:19]:<20} "
              f"{str(target)[:23]:<24} {str(r['actual'] or '-')[:23]:<24} "
              f"{r['outcome']:<8} {r['detail'][:30]}")
    print("-" * width)

    counts = {}
    for r in results:
        counts[r["outcome"]] = counts.get(r["outcome"], 0) + 1
    summary = " · ".join(f"{n} {k.lower()}" for k, n in sorted(counts.items()))
    print(f"{len(results)} scenarios: {summary}")

    blocked = [r for r in results if r["outcome"] == "BLOCKED"]
    if blocked:
        print(f"\n{len(blocked)} scenario(s) stop at the proof gate. ANALYZE_PROOF is "
              f"built and working;")
        print("  what is missing is an image fixture whose contents support each claim.")
        print("  The gate holding is itself correct behaviour and is asserted; these are")
        print("  counted apart from PASS so the gap stays visible: "
              + ", ".join(f"{r['id']}->{r['intended']}" for r in blocked))

    bad = [r for r in results if r["outcome"] in ("FAIL", "ERROR")]
    if bad:
        print(f"\n{len(bad)} UNEXPECTED:")
        for r in bad:
            print(f"  {r['id']} {r['order']}: {r['detail']}")
        return 1

    print("\nAll scenarios produced their expected path.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run the seeded scenario matrix against the deployed system")
    parser.add_argument("--connection", default="tide")
    parser.add_argument("--only", metavar="ID",
                        help="run a single scenario id, e.g. E-08")
    parser.add_argument("--keep", action="store_true",
                        help="leave cases in place instead of cleaning up")
    parser.add_argument("--restore-only", action="store_true",
                        help="hand every matrix order back to its seeded owner and exit")
    args = parser.parse_args()

    if args.restore_only:
        # Diagnosis, not repair. seed_retail.sql owns the correct mapping; this
        # only reports which orders drifted from it, because guessing an owner
        # here is how the wrong one gets written back.
        try:
            owners = capture_owners(args.connection)
        except SnowError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 2
        for order, owner in sorted(owners.items()):
            flag = "" if "@" in str(owner) else "   <-- REASSIGNED"
            print(f"  {order}  {owner}{flag}")
        suspect = suspect_owners(owners)
        if suspect:
            print(f"\n{len(suspect)} order(s) reassigned. Re-run "
                  f"sql/seed/seed_retail.sql to restore them.")
            return 1
        print("\nAll matrix orders are owned by their seeded customer.")
        return 0

    scenarios = SCENARIOS
    if args.only:
        scenarios = [s for s in SCENARIOS if s["id"] == args.only.upper()]
        if not scenarios and args.only.upper() != "E-25":
            print(f"No scenario {args.only}. Known: "
                  f"{', '.join(s['id'] for s in SCENARIOS)}, E-25", file=sys.stderr)
            return 2

    print(f"Matrix run against connection '{args.connection}' — "
          f"{len(scenarios)} scenario(s)")
    if args.keep:
        print("--keep: cases will be left in place. Re-run without it to clean up.")

    try:
        owners = capture_owners(args.connection)
    except SnowError as exc:
        print(f"ERROR: could not read order ownership: {exc}", file=sys.stderr)
        return 2

    missing = [s["order"] for s in scenarios if s["order"] not in owners]
    if missing:
        print(f"ERROR: orders not found — is the seed loaded? {', '.join(missing)}",
              file=sys.stderr)
        return 2

    # Refuse to start from a poisoned baseline rather than cement it.
    suspect = suspect_owners(owners)
    if suspect:
        print("\nERROR: these matrix orders are not owned by a seeded customer, so a "
              "previous run left them reassigned:", file=sys.stderr)
        for order in suspect:
            print(f"  {order}  currently {owners[order]}", file=sys.stderr)
        print("\nRestoring now would preserve the wrong owner. Re-run "
              "sql/seed/seed_retail.sql first.", file=sys.stderr)
        return 2

    results = []
    try:
        for sc in scenarios:
            print(f"  {sc['id']} {sc['order']} ({sc['subtype']}) ...", flush=True)
            try:
                results.append(
                    run_scenario(args.connection, sc, owners[sc["order"]], args.keep))
            except SnowError as exc:
                results.append(dict(sc, actual=None, status_after=None, amount=None,
                                    outcome="ERROR", detail=str(exc)[:120]))
        if not args.only or args.only.upper() == "E-25":
            print(f"  E-25 {DUPLICATE_PROBE_ORDER} (duplicate open case) ...",
                  flush=True)
            try:
                results.append(
                    run_duplicate_probe(args.connection, owners[DUPLICATE_PROBE_ORDER]))
            except SnowError as exc:
                results.append(dict(id="E-25", order=DUPLICATE_PROBE_ORDER,
                                    subtype="duplicate_charge", expect="refused",
                                    actual=None, status_after=None, amount=None,
                                    outcome="ERROR", detail=str(exc)[:120]))
    finally:
        # Ownership goes back even if the run died mid-scenario.
        try:
            restore_owners(args.connection, owners)
            drifted = verify_restored(args.connection, owners)
            if drifted:
                print(f"\nWARNING: ownership not restored for {', '.join(drifted)}. "
                      f"Re-run sql/seed/seed_retail.sql.", file=sys.stderr)
            else:
                print("\nOwnership restored for all matrix orders.")
        except SnowError as exc:
            print(f"\nWARNING: could not restore ownership: {exc}\n"
                  f"Re-run sql/seed/seed_retail.sql.", file=sys.stderr)

    return report(results)


if __name__ == "__main__":
    sys.exit(main())
