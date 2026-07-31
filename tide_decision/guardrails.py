"""Guardrails: ordered checks that run before routing.

G-01 through G-10 — first match returns a Decision.
See DETAILS.md §10 for the complete guardrail specification.

The order is load-bearing. Never reorder, never fall through.

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
    resolve_type,
)


def check_guardrails(bundle: dict, facts: DerivedFacts) -> Optional[Decision]:
    """Run guardrails G-01 through G-10 in order. First match returns.

    Args:
        bundle: The evidence bundle dict. `resolution_preference` must be the
            **raw** customer preference — G-02 exists to catch a preference the
            subtype does not allow, so it must not have been defaulted away.
        facts: Derived facts from fact_derivation.

    Returns:
        A Decision if a guardrail fires, or None to proceed to routing.
    """
    subtype = bundle.get("dispute_subtype", "")
    preference = bundle.get("resolution_preference", "")
    meta = SUBTYPE_META.get(subtype)

    # G-01: subtype missing or unknown after normalisation
    if not meta:
        label = subtype or "(none)"
        return Decision(
            path_id="G-01",
            target_status=CaseStatus.ESCALATED_HUMAN_REQUIRED,
            reason=f"Unknown dispute subtype '{label}' — manual review required",
        )

    # G-02: requested type is not in the allowed set for this subtype
    allowed = meta["allowed"]
    if preference and preference not in allowed:
        return Decision(
            path_id="G-02",
            target_status=CaseStatus.AWAITING_CUSTOMER_DECISION,
            invalid_reason_code=InvalidReasonCode.UNSUPPORTED_RESOLUTION_TYPE,
            reason=(
                f"Resolution type '{preference}' is not available for "
                f"'{subtype}'. Allowed: {', '.join(allowed)}"
            ),
        )

    # G-03: refund with prior refunds on the order → duplicate-refund risk
    if resolve_type(preference, subtype) == "refund" and facts.prior_refund_count > 0:
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
                f"'{payment.get('status') or 'unknown'}'"
            ),
        )

    # G-05: non_receipt / lost claimed, but tracking shows delivery
    if subtype in ("non_receipt", "lost") and facts.delivered_event:
        loc = facts.delivered_event.get("location", "unknown")
        when = facts.delivered_event.get("occurred_at", "unknown")
        return Decision(
            path_id="G-05",
            target_status=CaseStatus.ESCALATED_HUMAN_REQUIRED,
            tracking_evidence=f"Delivered at {loc} on {when}",
            reason=(
                f"Claimed {subtype} but tracking shows delivery at "
                f"{loc} on {when}"
            ),
        )

    # G-06 … G-09 apply only to proof-required subtypes
    if meta.get("proof", False):
        # G-06: proof required but not present
        if not facts.proof_present:
            return Decision(
                path_id="G-06",
                target_status=CaseStatus.AWAITING_CUSTOMER_DECISION,
                invalid_reason_code=InvalidReasonCode.INSUFFICIENT_PROOF,
                reason="Proof is required for this dispute type but was not provided",
            )

        # G-07: proof analysis failed
        if facts.proof_analysis_failed:
            return Decision(
                path_id="G-07",
                target_status=CaseStatus.ESCALATED_HUMAN_REQUIRED,
                reason="Proof analysis failed — manual review required",
            )

        # G-08: proof explicitly contradicts the claim
        if facts.proof_contradicts:
            return Decision(
                path_id="G-08",
                target_status=CaseStatus.AWAITING_CUSTOMER_DECISION,
                invalid_reason_code=InvalidReasonCode.PROOF_CONTRADICTS_CLAIM,
                reason=f"Uploaded proof contradicts the '{subtype}' claim",
            )

        # G-09: proof present but does not support the claim
        if not facts.proof_supports:
            return Decision(
                path_id="G-09",
                target_status=CaseStatus.AWAITING_CUSTOMER_DECISION,
                invalid_reason_code=InvalidReasonCode.INSUFFICIENT_PROOF,
                reason=f"Uploaded proof does not support the '{subtype}' claim",
            )

    # G-10: duplicate charge claimed, but the records show fewer than two charges.
    # Subtype-conditioned rather than global, following the precedent of G-05.
    # Sits after G-03 and G-04 so a duplicate-refund risk or an unconfirmed
    # payment still escalates first. DETAILS.md §10.
    if subtype == "duplicate_charge" and facts.confirmed_payment_count < 2:
        return Decision(
            path_id="G-10",
            target_status=CaseStatus.AWAITING_CUSTOMER_DECISION,
            invalid_reason_code=InvalidReasonCode.INSUFFICIENT_EVIDENCE,
            reason=(
                f"Duplicate charge claimed but payment records show "
                f"{facts.confirmed_payment_count} confirmed charge(s) for this order"
            ),
        )

    # No guardrail fired — proceed to routing
    return None
