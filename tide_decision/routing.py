"""Routing: subtype-specific decision logic after guardrails pass.

R-01 through R-53 — dispatches by subtype, then by resolution type.
See DETAILS.md §11 for the complete routing specification.

No Snowflake imports.
"""

from __future__ import annotations

from tide_decision.types import (
    CaseStatus,
    Decision,
    DerivedFacts,
    InvalidReasonCode,
    ResolutionType,
    constant,
    resolve_type,
)


def _auto_or_approval(
    path_auto: str,
    path_approval: str,
    amount: float,
    limit: float,
    resolution_type: ResolutionType,
    reason: str,
    tracking_evidence: str | None = None,
    shipping_fee_only: bool = False,
    replacement_items: list | None = None,
    affected_item_ids: list | None = None,
) -> Decision:
    """Return AUTO if amount ≤ limit, APPROVAL otherwise."""
    if amount <= limit:
        return Decision(
            path_id=path_auto,
            target_status=CaseStatus.APPROVED_EXECUTING,
            resolution_type=resolution_type,
            eligible_amount=amount,
            shipping_fee_only=shipping_fee_only,
            reason=reason,
            tracking_evidence=tracking_evidence,
            replacement_items=replacement_items or [],
            affected_item_ids=affected_item_ids or [],
        )
    return Decision(
        path_id=path_approval,
        target_status=CaseStatus.AWAITING_APPROVAL,
        resolution_type=resolution_type,
        eligible_amount=amount,
        shipping_fee_only=shipping_fee_only,
        reason=reason,
        tracking_evidence=tracking_evidence,
        replacement_items=replacement_items or [],
        affected_item_ids=affected_item_ids or [],
    )


def route(
    bundle: dict,
    facts: DerivedFacts,
    autonomous_limit: float | None = None,
) -> Decision:
    """Route the case to its terminal decision based on subtype.

    Args:
        bundle: The evidence bundle dict.
        facts: Derived facts from fact_derivation.
        autonomous_limit: AUTONOMOUS_LIMIT_USD; defaults to DETAILS.md §6.

    Returns:
        A Decision with path_id R-01..R-53.
    """
    if autonomous_limit is None:
        autonomous_limit = constant("AUTONOMOUS_LIMIT_USD")
    subtype = bundle.get("dispute_subtype", "")
    preference = bundle.get("resolution_preference", "")

    # DETAILS.md §7.3 — preference if allowed for the subtype, else the default.
    # An unsupported preference never reaches here; G-02 catches it first.
    resolved_type = resolve_type(preference, subtype)

    # ── duplicate_charge ──────────────────────────────────────────────
    if subtype == "duplicate_charge":
        return _auto_or_approval(
            "R-01", "R-02",
            facts.total_order_amount, autonomous_limit,
            ResolutionType.REFUND,
            f"Duplicate charge refund of ${facts.total_order_amount:.2f}",
        )

    # ── not_as_described / damaged_goods / wrong_item ─────────────────
    if subtype in ("not_as_described", "damaged_goods", "wrong_item"):
        # Offset for path IDs: not_as_described=0, damaged_goods=1, wrong_item=2
        offsets = {"not_as_described": 0, "damaged_goods": 6, "wrong_item": 12}
        base = 3 + offsets[subtype]

        if resolved_type == "replacement":
            if not facts.inventory_feasible:
                return Decision(
                    path_id=f"R-{base:02d}",
                    target_status=CaseStatus.AWAITING_CUSTOMER_DECISION,
                    invalid_reason_code=InvalidReasonCode.INSUFFICIENT_INVENTORY,
                    reason=f"Replacement not available: {facts.inventory_block_reason}",
                )
            return _auto_or_approval(
                f"R-{base + 1:02d}", f"R-{base + 2:02d}",
                facts.replacement_amount, autonomous_limit,
                ResolutionType.REPLACEMENT,
                f"Replacement for {subtype} — ${facts.replacement_amount:.2f}",
                replacement_items=bundle.get("affected_items", []),
                affected_item_ids=[i.get("item_id") for i in bundle.get("affected_items", [])],
            )
        else:  # refund
            if not facts.within_return_window:
                window_basis = facts.window_basis_date or "unknown"
                return Decision(
                    path_id=f"R-{base + 3:02d}",
                    target_status=CaseStatus.AWAITING_CUSTOMER_DECISION,
                    invalid_reason_code=InvalidReasonCode.OUTSIDE_RETURN_WINDOW,
                    reason=f"Outside return window (basis: {window_basis})",
                )
            return _auto_or_approval(
                f"R-{base + 4:02d}", f"R-{base + 5:02d}",
                facts.affected_amount, autonomous_limit,
                ResolutionType.REFUND,
                f"Refund for {subtype} — ${facts.affected_amount:.2f}",
            )

    # ── partial_fulfillment ───────────────────────────────────────────
    if subtype == "partial_fulfillment":
        return Decision(
            path_id="R-21",
            target_status=CaseStatus.ESCALATED_HUMAN_REQUIRED,
            resolution_type=ResolutionType.REFUND,
            eligible_amount=facts.affected_amount,
            reason=f"Partial fulfillment — escalated for human review (${facts.affected_amount:.2f})",
        )

    # ── return_request / changed_mind ─────────────────────────────────
    if subtype in ("return_request", "changed_mind"):
        base = 22 if subtype == "return_request" else 25

        if not facts.order_returnable:
            order_status = (bundle.get("order") or {}).get("status") or "unknown"
            return Decision(
                path_id=f"R-{base:02d}",
                target_status=CaseStatus.AWAITING_CUSTOMER_DECISION,
                invalid_reason_code=InvalidReasonCode.NON_RETURNABLE_ITEM,
                reason=f"Order is not in a returnable state (status: {order_status})",
            )

        if not facts.within_return_window:
            return Decision(
                path_id=f"R-{base + 1:02d}",
                target_status=CaseStatus.AWAITING_CUSTOMER_DECISION,
                invalid_reason_code=InvalidReasonCode.OUTSIDE_RETURN_WINDOW,
                reason=f"Outside return window (basis: {facts.window_basis_date or 'unknown'})",
            )

        # Returns are never autonomous — always approval
        return Decision(
            path_id=f"R-{base + 2:02d}",
            target_status=CaseStatus.AWAITING_APPROVAL,
            resolution_type=ResolutionType.RETURN,
            eligible_amount=facts.total_order_amount,
            reason=f"Return request — ${facts.total_order_amount:.2f} pending approval",
        )

    # ── other ─────────────────────────────────────────────────────────
    if subtype == "other":
        return Decision(
            path_id="R-28",
            target_status=CaseStatus.ESCALATED_HUMAN_REQUIRED,
            reason="Dispute type 'other' — escalated for human review",
        )

    # ── non_receipt ───────────────────────────────────────────────────
    if subtype == "non_receipt":
        if resolved_type == "replacement":
            if not facts.inventory_feasible:
                return Decision(
                    path_id="R-29",
                    target_status=CaseStatus.AWAITING_CUSTOMER_DECISION,
                    invalid_reason_code=InvalidReasonCode.INSUFFICIENT_INVENTORY,
                    reason=f"Replacement not available: {facts.inventory_block_reason}",
                )
            # Non-receipt replacement is never autonomous
            return Decision(
                path_id="R-30",
                target_status=CaseStatus.AWAITING_APPROVAL,
                resolution_type=ResolutionType.REPLACEMENT,
                eligible_amount=facts.replacement_amount,
                reason=f"Non-receipt replacement — ${facts.replacement_amount:.2f} pending approval",
                replacement_items=bundle.get("affected_items", []),
            )
        else:  # refund
            # DETAILS.md §13 names R-31/32 the "no-event" pair, so the specific
            # tracking states (exception, stale) are tested first and the plain
            # no-event refund is the fallback. Reading §11's clause order
            # literally would make R-33..R-36 unreachable.
            if not facts.delivered_event and not facts.lost_event:
                if facts.exception_event:
                    te = facts.exception_event
                    evidence = f"Exception at {te.get('location', '?')} on {te.get('occurred_at', '?')}"
                    return _auto_or_approval(
                        "R-33", "R-34",
                        facts.affected_amount, autonomous_limit,
                        ResolutionType.REFUND,
                        f"Non-receipt with carrier exception — ${facts.affected_amount:.2f}",
                        tracking_evidence=evidence,
                    )
                if facts.stale_in_transit:
                    te = facts.in_transit_event or {}
                    evidence = f"Last movement at {te.get('location', '?')} on {te.get('occurred_at', '?')}"
                    return _auto_or_approval(
                        "R-35", "R-36",
                        facts.affected_amount, autonomous_limit,
                        ResolutionType.REFUND,
                        f"Non-receipt — stale in transit — ${facts.affected_amount:.2f}",
                        tracking_evidence=evidence,
                    )
                return _auto_or_approval(
                    "R-31", "R-32",
                    facts.affected_amount, autonomous_limit,
                    ResolutionType.REFUND,
                    f"Non-receipt refund — ${facts.affected_amount:.2f}",
                )
            # Fallthrough: delivered (caught by G-05) or unclear
            return Decision(
                path_id="R-37",
                target_status=CaseStatus.ESCALATED_HUMAN_REQUIRED,
                resolution_type=ResolutionType.REFUND,
                eligible_amount=facts.affected_amount,
                reason="Non-receipt — ambiguous tracking state, escalated",
            )

    # ── delayed ───────────────────────────────────────────────────────
    if subtype == "delayed":
        if facts.sla_breached:
            return _auto_or_approval(
                "R-38", "R-39",
                facts.shipping_fee, autonomous_limit,
                ResolutionType.REFUND,
                f"SLA breach — shipping fee refund ${facts.shipping_fee:.2f}",
                shipping_fee_only=True,
            )
        if facts.exception_event and not facts.delivered_event:
            te = facts.exception_event
            evidence = f"Exception at {te.get('location', '?')} on {te.get('occurred_at', '?')}"
            return _auto_or_approval(
                "R-40", "R-41",
                facts.affected_amount, autonomous_limit,
                ResolutionType.REFUND,
                f"Delayed with carrier exception — ${facts.affected_amount:.2f}",
                tracking_evidence=evidence,
            )
        if facts.stale_in_transit:
            te = facts.in_transit_event or {}
            evidence = f"Last movement at {te.get('location', '?')} on {te.get('occurred_at', '?')}"
            return _auto_or_approval(
                "R-42", "R-43",
                facts.affected_amount, autonomous_limit,
                ResolutionType.REFUND,
                f"Delayed — stale in transit — ${facts.affected_amount:.2f}",
                tracking_evidence=evidence,
            )
        return Decision(
            path_id="R-44",
            target_status=CaseStatus.ESCALATED_HUMAN_REQUIRED,
            resolution_type=ResolutionType.REFUND,
            eligible_amount=facts.affected_amount,
            reason="Delayed — no clear delivery issue, escalated",
        )

    # ── exception ─────────────────────────────────────────────────────
    if subtype == "exception":
        if facts.exception_event and not facts.delivered_event:
            te = facts.exception_event
            evidence = f"Exception at {te.get('location', '?')} on {te.get('occurred_at', '?')}"
            return _auto_or_approval(
                "R-45", "R-46",
                facts.affected_amount, autonomous_limit,
                ResolutionType.REFUND,
                f"Carrier exception — ${facts.affected_amount:.2f}",
                tracking_evidence=evidence,
            )
        return Decision(
            path_id="R-47",
            target_status=CaseStatus.ESCALATED_HUMAN_REQUIRED,
            resolution_type=ResolutionType.REFUND,
            eligible_amount=facts.affected_amount,
            reason="Exception — no carrier exception event found, escalated",
        )

    # ── lost ──────────────────────────────────────────────────────────
    if subtype == "lost":
        if resolved_type == "replacement":
            if not facts.inventory_feasible:
                return Decision(
                    path_id="R-48",
                    target_status=CaseStatus.AWAITING_CUSTOMER_DECISION,
                    invalid_reason_code=InvalidReasonCode.INSUFFICIENT_INVENTORY,
                    reason=f"Replacement not available: {facts.inventory_block_reason}",
                )
            return Decision(
                path_id="R-49",
                target_status=CaseStatus.AWAITING_APPROVAL,
                resolution_type=ResolutionType.REPLACEMENT,
                eligible_amount=facts.replacement_amount,
                reason=f"Lost — replacement pending approval (${facts.replacement_amount:.2f})",
                replacement_items=bundle.get("affected_items", []),
            )
        else:  # refund
            if facts.lost_event and not facts.delivered_event:
                te = facts.lost_event
                evidence = f"Lost at {te.get('location', '?')} on {te.get('occurred_at', '?')}"
                return _auto_or_approval(
                    "R-50", "R-51",
                    facts.affected_amount, autonomous_limit,
                    ResolutionType.REFUND,
                    f"Lost — carrier confirmed — ${facts.affected_amount:.2f}",
                    tracking_evidence=evidence,
                )
            return Decision(
                path_id="R-52",
                target_status=CaseStatus.ESCALATED_HUMAN_REQUIRED,
                resolution_type=ResolutionType.REFUND,
                eligible_amount=facts.affected_amount,
                reason="Lost — no carrier lost event found, escalated",
            )

    # ── R-53: defence in depth behind G-01 ────────────────────────────
    return Decision(
        path_id="R-53",
        target_status=CaseStatus.ESCALATED_HUMAN_REQUIRED,
        reason=f"Unknown subtype '{subtype}' reached routing — escalated (defence in depth)",
    )
