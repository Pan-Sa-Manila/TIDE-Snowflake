"""Guardrail tests — DETAILS.md §10 (G-01 … G-09).

Guardrails run before routing, in order, first match returns. Each test below
pins one terminal path; the ordering tests at the bottom pin the *sequence*,
which is load-bearing (a case can satisfy several guardrails at once).
"""

from tide_decision import adjudicate
from tide_decision.types import CaseStatus, InvalidReasonCode

from .bundles import make_bundle, tracking_event


# ---------------------------------------------------------------------------
# G-01 — unknown subtype
# ---------------------------------------------------------------------------
def test_g01_unknown_subtype_escalates():
    """G-01: a subtype that survives normalisation unrecognised → escalation."""
    bundle = make_bundle("teleporter_malfunction")
    decision = adjudicate(bundle)

    assert decision.path_id == "G-01"
    assert decision.target_status == CaseStatus.ESCALATED_HUMAN_REQUIRED
    assert decision.resolution_type is None
    assert "manual review" in decision.reason.lower()


def test_g01_empty_subtype_escalates():
    """G-01: a missing subtype is as unknown as a wrong one."""
    decision = adjudicate(make_bundle(""))

    assert decision.path_id == "G-01"
    assert decision.target_status == CaseStatus.ESCALATED_HUMAN_REQUIRED


# ---------------------------------------------------------------------------
# G-02 — resolution type not allowed for the subtype
# ---------------------------------------------------------------------------
def test_g02_unsupported_resolution_type():
    """G-02: replacement is not offered for a duplicate charge."""
    bundle = make_bundle("duplicate_charge", preference="replacement")
    decision = adjudicate(bundle)

    assert decision.path_id == "G-02"
    assert decision.target_status == CaseStatus.AWAITING_CUSTOMER_DECISION
    assert decision.invalid_reason_code == InvalidReasonCode.UNSUPPORTED_RESOLUTION_TYPE


def test_g02_preference_does_not_silently_downgrade():
    """G-02: an unsupported preference must not be quietly defaulted away.

    DETAILS.md §7.3 is explicit that this asks the customer rather than
    substituting the subtype default behind their back.
    """
    decision = adjudicate(make_bundle("return_request", preference="refund"))

    assert decision.path_id == "G-02"
    assert decision.target_status == CaseStatus.AWAITING_CUSTOMER_DECISION


def test_g02_does_not_fire_without_a_preference():
    """No stated preference is not an unsupported preference."""
    decision = adjudicate(make_bundle("duplicate_charge", preference=""))

    assert decision.path_id != "G-02"


def test_g02_does_not_fire_for_an_allowed_preference():
    decision = adjudicate(make_bundle("damaged_goods", preference="replacement"))

    assert decision.path_id != "G-02"


# ---------------------------------------------------------------------------
# G-03 — duplicate refund risk
# ---------------------------------------------------------------------------
def test_g03_prior_refund_blocks_payout():
    """G-03: money already went out for this order — a human looks first."""
    bundle = make_bundle(
        "duplicate_charge",
        preference="refund",
        refund_history=[{"amount": 47.50, "processed_at": "2026-07-20T10:00:00+00:00"}],
    )
    decision = adjudicate(bundle)

    assert decision.path_id == "G-03"
    assert decision.target_status == CaseStatus.ESCALATED_HUMAN_REQUIRED
    assert decision.eligible_amount == 0.0
    assert "47.50" in decision.reason


def test_g03_does_not_fire_for_non_refund_types():
    """A return is not a payout, so prior refunds do not gate it."""
    bundle = make_bundle(
        "return_request",
        preference="return",
        refund_history=[{"amount": 10.00}],
    )
    decision = adjudicate(bundle)

    assert decision.path_id != "G-03"


# ---------------------------------------------------------------------------
# G-04 — payment not confirmed
# ---------------------------------------------------------------------------
def test_g04_unconfirmed_payment_escalates():
    """G-04: never refund money the account never received."""
    bundle = make_bundle("duplicate_charge", preference="refund", payment_status="pending")
    decision = adjudicate(bundle)

    assert decision.path_id == "G-04"
    assert decision.target_status == CaseStatus.ESCALATED_HUMAN_REQUIRED
    assert "pending" in decision.reason


def test_g04_accepts_every_confirmed_synonym():
    """DETAILS.md §9 lists five statuses that all mean 'the money arrived'."""
    for status in ("confirmed", "completed", "paid", "success", "succeeded"):
        decision = adjudicate(
            make_bundle("duplicate_charge", preference="refund", payment_status=status)
        )
        assert decision.path_id != "G-04", f"{status} should count as confirmed"


# ---------------------------------------------------------------------------
# G-05 — claimed non-delivery, but tracking says delivered
# ---------------------------------------------------------------------------
def test_g05_delivered_but_disputed():
    """G-05: non_receipt contradicted by a delivery scan."""
    bundle = make_bundle(
        "non_receipt",
        preference="refund",
        tracking_events=[tracking_event("delivered", days_ago=3, location="Lapu-Lapu City")],
    )
    decision = adjudicate(bundle)

    assert decision.path_id == "G-05"
    assert decision.target_status == CaseStatus.ESCALATED_HUMAN_REQUIRED
    assert decision.tracking_evidence is not None
    assert decision.tracking_evidence.startswith("Delivered at Lapu-Lapu City on")


def test_g05_applies_to_lost_claims_too():
    bundle = make_bundle(
        "lost",
        preference="refund",
        tracking_events=[tracking_event("delivered", days_ago=1)],
    )
    decision = adjudicate(bundle)

    assert decision.path_id == "G-05"


# ---------------------------------------------------------------------------
# G-06 — proof required, none supplied
# ---------------------------------------------------------------------------
def test_g06_missing_proof():
    bundle = make_bundle("damaged_goods", preference="refund", proof={"present": False})
    decision = adjudicate(bundle)

    assert decision.path_id == "G-06"
    assert decision.target_status == CaseStatus.AWAITING_CUSTOMER_DECISION
    assert decision.invalid_reason_code == InvalidReasonCode.INSUFFICIENT_PROOF


# ---------------------------------------------------------------------------
# G-07 — proof analysis failed
# ---------------------------------------------------------------------------
def test_g07_proof_analysis_failure_escalates():
    """An AI failure is a routed branch, not a silent default (DETAILS.md §F2.4)."""
    bundle = make_bundle(
        "damaged_goods",
        preference="refund",
        proof={"present": True, "analysis_status": "failed", "signals": {}},
    )
    decision = adjudicate(bundle)

    assert decision.path_id == "G-07"
    assert decision.target_status == CaseStatus.ESCALATED_HUMAN_REQUIRED


# ---------------------------------------------------------------------------
# G-08 — proof contradicts the claim
# ---------------------------------------------------------------------------
def test_g08_proof_contradicts_claim():
    """The photo shows an undamaged product on a damaged-goods claim."""
    bundle = make_bundle(
        "damaged_goods",
        preference="refund",
        proof={
            "present": True,
            "analysis_status": "completed",
            "signals": {"damage_detected": False},
        },
    )
    decision = adjudicate(bundle)

    assert decision.path_id == "G-08"
    assert decision.target_status == CaseStatus.AWAITING_CUSTOMER_DECISION
    assert decision.invalid_reason_code == InvalidReasonCode.PROOF_CONTRADICTS_CLAIM


# ---------------------------------------------------------------------------
# G-09 — proof present but unsupportive
# ---------------------------------------------------------------------------
def test_g09_proof_does_not_support_claim():
    """A *missing* signal is unsupportive (G-09), not a contradiction (G-08).

    DETAILS.md §9: `proof_contradicts` requires the signal to be explicitly
    false. Here the relevant signal is simply absent.
    """
    bundle = make_bundle(
        "damaged_goods",
        preference="refund",
        proof={
            "present": True,
            "analysis_status": "completed",
            "signals": {"wrong_item_signals": True},
        },
    )
    decision = adjudicate(bundle)

    assert decision.path_id == "G-09"
    assert decision.target_status == CaseStatus.AWAITING_CUSTOMER_DECISION
    assert decision.invalid_reason_code == InvalidReasonCode.INSUFFICIENT_PROOF


def test_g09_reads_the_subtype_relevant_signal():
    """Damage on a wrong-item claim proves nothing about the wrong item."""
    bundle = make_bundle(
        "wrong_item",
        preference="refund",
        proof={
            "present": True,
            "analysis_status": "completed",
            "signals": {"damage_detected": True},
        },
    )
    decision = adjudicate(bundle)

    assert decision.path_id == "G-09"


# ---------------------------------------------------------------------------
# Ordering — the sequence itself is a requirement
# ---------------------------------------------------------------------------
def test_g01_precedes_g02():
    """An unknown subtype has no allowed set to violate."""
    decision = adjudicate(make_bundle("nonsense_subtype", preference="replacement"))

    assert decision.path_id == "G-01"


def test_g02_precedes_g03():
    bundle = make_bundle(
        "duplicate_charge",
        preference="replacement",
        refund_history=[{"amount": 20.00}],
    )

    assert adjudicate(bundle).path_id == "G-02"


def test_g03_precedes_g04():
    """Duplicate-refund risk outranks an unconfirmed payment."""
    bundle = make_bundle(
        "duplicate_charge",
        preference="refund",
        payment_status="pending",
        refund_history=[{"amount": 20.00}],
    )

    assert adjudicate(bundle).path_id == "G-03"


def test_g04_precedes_g05():
    bundle = make_bundle(
        "non_receipt",
        preference="refund",
        payment_status="failed",
        tracking_events=[tracking_event("delivered", days_ago=2)],
    )

    assert adjudicate(bundle).path_id == "G-04"


def test_g06_precedes_g07():
    """No proof at all is a G-06, even if the analysis record says failed."""
    bundle = make_bundle(
        "damaged_goods",
        preference="refund",
        proof={"present": False, "analysis_status": "failed", "signals": {}},
    )

    assert adjudicate(bundle).path_id == "G-06"
