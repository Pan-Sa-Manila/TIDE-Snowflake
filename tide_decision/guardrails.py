"""Guardrails: ordered checks that run before routing.

G-01 through G-09 — first match returns a Decision.
See DETAILS.md §10 for the complete guardrail specification.

No Snowflake imports.
"""

from __future__ import annotations

from typing import Optional

from tide_decision.types import (
    CaseStatus,
    Decision,
    DerivedFacts,
    InvalidReasonCode,
    SUBTYPE_META,
)


def _resolve_proof_signals(
    subtype: str, facts: DerivedFacts
) -> tuple[bool, bool]:
    """Interpret raw proof signals in the context of a specific subtype.

    Returns:
        (proof_supports, proof_contradicts)
    """
    signals = getattr(facts, "_raw_proof_signals", {})
    if not signals:
        return False, False

    if subtype == "damaged_goods":
        supports = signals.get("damage_detected", False)
        contradicts = signals.get("damage_detected") is False
    elif subtype == "wrong_item":
        supports = signals.get("wrong_item_signals", False)
        contradicts = signals.get("wrong_item_signals") is False
    elif subtype == "not_as_described":
        supports = signals.get("not_as_described_signals", False)
        contradicts = signals.get("not_as_described_signals") is False
    elif subtype == "partial_fulfillment":
        supports = signals.get("missing_item_signals", False)
        contradicts = signals.get("missing_item_signals") is False
    else:
        supports = False
        contradicts = False

    return supports, contradicts


def check_guardrails(
    bundle: dict,
    facts: DerivedFacts,
    autonomous_limit: float = 50.0,
) -> Optional[Decision]:
    """Run guardrails G-01 through G-09 in order. First match returns.

    Args:
        bundle: The evidence bundle dict.
        facts: Derived facts from fact_derivation.
        autonomous_limit: AUTONOMOUS_LIMIT_USD from constants.

    Returns:
        A Decision if a guardrail fires, or None to proceed to routing.
    """
    subtype = bundle.get("dispute_subtype", "")
    resolution_preference = bundle.get("resolution_preference", "")
    meta = SUBTYPE_META.get(subtype)

    # G-01: subtype missing or unknown after normalisation
    if not meta:
        return Decision(
            path_id="G-01",
            target_status=CaseStatus.ESCALATED_HUMAN_REQUIRED,
            reason=f"Unknown dispute subtype '{subtype}' — manual review required",
        )

    # G-02: resolved type not in allowed set for subtype
    allowed = meta["allowed"]
    if resolution_preference and resolution_preference not in allowed:
        return Decision(
            path_id="G-02",
            target_status=CaseStatus.AWAITING_CUSTOMER_DECISION,
            invalid_reason_code=InvalidReasonCode.UNSUPPORTED_RESOLUTION_TYPE,
            reason=(
                f"Resolution type '{resolution_preference}' is not available for "
                f"'{subtype}'. Allowed: {', '.join(allowed)}"
            ),
        )

    # G-03: refund type with prior refunds → duplicate refund risk
    resolved_type = resolution_preference if resolution_preference in allowed else meta["default"]
    if resolved_type == "refund" and facts.prior_refund_count > 0:
        return Decision(
            path_id="G-03",
            target_status=CaseStatus.ESCALATED_HUMAN_REQUIRED,
            eligible_amount=0.0,
            reason=(
                f"Duplicate refund risk: {facts.prior_refund_count} prior "
                f"refund(s) totalling ${facts.prior_refund_total:.2f} "
                f"already exist for this order"
            ),
        )

    # G-04: payment not confirmed
    if not facts.payment_confirmed:
        payment = bundle.get("payment") or {}
        return Decision(
            path_id="G-04",
            target_status=CaseStatus.ESCALATED_HUMAN_REQUIRED,
            reason=(
                f"Payment not confirmed — current status: "
                f"'{payment.get('status', 'unknown')}'"
            ),
        )

    # G-05: non_receipt or lost, but delivered event exists
    if subtype in ("non_receipt", "lost") and facts.delivered_event:
        loc = facts.delivered_event.get("location", "unknown")
        time = facts.delivered_event.get("occurred_at", "unknown")
        return Decision(
            path_id="G-05",
            target_status=CaseStatus.ESCALATED_HUMAN_REQUIRED,
            tracking_evidence=f"Delivered at {loc} on {time}",
            reason=(
                f"Claimed {subtype} but tracking shows delivery at "
                f"{loc} on {time}"
            ),
        )

    # G-06 through G-09: proof-related guardrails
    proof_required = meta.get("proof", False)

    if proof_required:
        # G-06: proof required but not present
        if not facts.proof_present:
            return Decision(
                path_id="G-06",
                target_status=CaseStatus.AWAITING_CUSTOMER_DECISION,
                invalid_reason_code=InvalidReasonCode.INSUFFICIENT_PROOF,
                reason="Proof is required for this dispute type but was not provided",
            )

        # G-07: proof required, analysis failed
        if facts.proof_analysis_failed:
            return Decision(
                path_id="G-07",
                target_status=CaseStatus.ESCALATED_HUMAN_REQUIRED,
                reason="Proof analysis failed — manual review required",
            )

        # Interpret proof signals for this subtype
        proof_supports, proof_contradicts = _resolve_proof_signals(subtype, facts)

        # G-08: proof contradicts claim
        if proof_contradicts:
            return Decision(
                path_id="G-08",
                target_status=CaseStatus.AWAITING_CUSTOMER_DECISION,
                invalid_reason_code=InvalidReasonCode.PROOF_CONTRADICTS_CLAIM,
                reason=(
                    f"Uploaded proof contradicts the '{subtype}' claim"
                ),
            )

        # G-09: proof present but does not support claim
        if not proof_supports:
            return Decision(
                path_id="G-09",
                target_status=CaseStatus.AWAITING_CUSTOMER_DECISION,
                invalid_reason_code=InvalidReasonCode.INSUFFICIENT_PROOF,
                reason=(
                    f"Uploaded proof does not support the '{subtype}' claim"
                ),
            )

    # No guardrail fired — proceed to routing
    return None
