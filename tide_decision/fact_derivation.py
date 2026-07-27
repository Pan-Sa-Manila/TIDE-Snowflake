"""Fact derivation: evidence bundle → DerivedFacts.

Transforms raw evidence data into the intermediate facts consumed by
guardrails and routing. See DETAILS.md §9 for derivation rules.

No Snowflake imports. No clock — uses bundle['as_of'].
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from tide_decision.types import DerivedFacts


def _parse_ts(value: Optional[str]) -> Optional[datetime]:
    """Parse an ISO timestamp string, returning None on failure."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


def _days_between(a: Optional[str], b: Optional[str]) -> Optional[float]:
    """Return days between two ISO timestamp strings, or None."""
    dt_a = _parse_ts(a)
    dt_b = _parse_ts(b)
    if dt_a is None or dt_b is None:
        return None
    return (dt_b - dt_a).total_seconds() / 86400


def derive_facts(bundle: dict, constants: Optional[dict] = None) -> DerivedFacts:
    """Derive intermediate facts from the evidence bundle.

    Args:
        bundle: Plain-dict evidence bundle (see SCHEMA.md §5).
        constants: Override thresholds (for testing). Defaults to BRL values.

    Returns:
        DerivedFacts populated from the bundle.
    """
    # Defaults per DETAILS.md §6
    c = constants or {}
    return_window_days = c.get("RETURN_WINDOW_DAYS", 7)
    delivery_sla_breach_days = c.get("DELIVERY_SLA_BREACH_DAYS", 3)
    stale_transit_days = c.get("STALE_TRANSIT_DAYS", 7)

    facts = DerivedFacts()
    as_of = bundle.get("as_of")

    # --- Payment ---
    payment = bundle.get("payment") or {}
    payment_status = (payment.get("status") or "").lower()
    facts.payment_confirmed = payment_status in {
        "confirmed", "completed", "paid", "success", "succeeded"
    }

    # --- Order ---
    order = bundle.get("order") or {}
    order_status = (order.get("status") or "").lower()
    facts.order_returnable = order_status in {"fulfilled", "returned"}

    # Total order amount: refund amount ?? order total ?? payment amount ?? 0
    refund_history = bundle.get("refund_history") or []
    refund_amount = refund_history[0].get("amount", 0) if refund_history else 0
    facts.total_order_amount = (
        refund_amount
        or order.get("total_amount", 0)
        or payment.get("amount", 0)
        or 0
    )

    # Shipping fee
    facts.shipping_fee = order.get("shipping_fee") or 0

    # --- Affected items ---
    affected_items = bundle.get("affected_items") or []
    items = bundle.get("items") or []

    if affected_items:
        facts.affected_amount = sum(
            (i.get("qty", 1) * i.get("unit_price", 0)) for i in affected_items
        )
    elif items:
        facts.affected_amount = sum(
            (i.get("qty", i.get("quantity", 1)) * i.get("unit_price", 0))
            for i in items
        )
    else:
        facts.affected_amount = facts.total_order_amount

    facts.replacement_amount = (
        facts.affected_amount if facts.affected_amount > 0
        else facts.total_order_amount
    )

    # --- Return window ---
    # window_basis_date: first non-null of shipment.delivered_at, order.delivered_at,
    # order.fulfilled_at, order.placed_at, delivered tracking event time
    shipment = bundle.get("shipment") or {}
    tracking_events = bundle.get("tracking_events") or []

    delivered_tracking = None
    for te in tracking_events:
        if (te.get("event_type") or "").lower() == "delivered":
            delivered_tracking = te
            break

    facts.window_basis_date = (
        shipment.get("delivered_at")
        or order.get("delivered_at")
        or order.get("fulfilled_at")
        or order.get("placed_at")
        or (delivered_tracking.get("occurred_at") if delivered_tracking else None)
    )

    if facts.window_basis_date and as_of:
        days = _days_between(facts.window_basis_date, as_of)
        facts.within_return_window = (
            days is not None and 0 <= days <= return_window_days
        )

    # --- Tracking events ---
    for te in tracking_events:
        et = (te.get("event_type") or "").lower()
        if et == "delivered" and facts.delivered_event is None:
            facts.delivered_event = te
        elif et == "lost" and facts.lost_event is None:
            facts.lost_event = te
        elif et in ("exception", "delayed") and facts.exception_event is None:
            facts.exception_event = te
        elif et == "in_transit":
            # Keep the latest in_transit event
            facts.in_transit_event = te

    # Stale in transit
    if facts.in_transit_event and not facts.delivered_event:
        days_since = _days_between(
            facts.in_transit_event.get("occurred_at"), as_of
        )
        facts.stale_in_transit = (
            days_since is not None and days_since > stale_transit_days
        )

    # SLA breached
    if facts.delivered_event:
        est = shipment.get("estimated_delivery") or order.get("estimated_delivery")
        delivered_at = facts.delivered_event.get("occurred_at")
        if est and delivered_at:
            days_late = _days_between(est, delivered_at)
            facts.sla_breached = (
                days_late is not None and days_late > delivery_sla_breach_days
            )

    # --- Prior refunds ---
    facts.prior_refund_count = len(refund_history)
    facts.prior_refund_total = sum(r.get("amount", 0) for r in refund_history)

    # --- Inventory ---
    inventory = bundle.get("inventory") or []
    if not affected_items and not items:
        facts.inventory_feasible = False
        facts.inventory_block_reason = "no items to check"
    elif not inventory:
        facts.inventory_feasible = False
        facts.inventory_block_reason = "inventory data unavailable"
    else:
        check_items = affected_items or items
        feasible = True
        blocked = []
        for item in check_items:
            sku = item.get("sku")
            qty_needed = item.get("qty", item.get("quantity", 1))
            stock_entry = next(
                (inv for inv in inventory if inv.get("sku") == sku), None
            )
            if stock_entry is None:
                feasible = False
                blocked.append(f"{sku}: unknown availability")
            elif stock_entry.get("quantity_available", 0) < qty_needed:
                feasible = False
                blocked.append(
                    f"{sku}: need {qty_needed}, have "
                    f"{stock_entry.get('quantity_available', 0)}"
                )
        facts.inventory_feasible = feasible
        facts.inventory_block_reason = "; ".join(blocked)

    # --- Proof ---
    proof = bundle.get("proof") or {}
    facts.proof_present = proof.get("present", False)

    analysis_status = (proof.get("analysis_status") or "").lower()
    facts.proof_analysis_failed = analysis_status == "failed"

    signals = proof.get("signals") or {}
    # proof_supports and proof_contradicts are subtype-dependent;
    # the caller sets the subtype context. Here we derive raw signals.
    # The guardrails module applies subtype-specific interpretation.
    facts.proof_supports = False
    facts.proof_contradicts = False

    if facts.proof_present and not facts.proof_analysis_failed:
        # Store raw signals; guardrails.py interprets per subtype
        facts._raw_proof_signals = signals  # type: ignore[attr-defined]

    return facts
