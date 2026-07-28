"""Fact derivation: evidence bundle → DerivedFacts.

Transforms raw evidence data into the intermediate facts consumed by
guardrails and routing. See DETAILS.md §9 for derivation rules.

No Snowflake imports. No clock — uses bundle['as_of'].
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from tide_decision.types import (
    DerivedFacts,
    PROOF_SIGNAL_BY_SUBTYPE,
    constant,
)

# Payment statuses that count as confirmed — DETAILS.md §9
CONFIRMED_PAYMENT_STATUSES = {
    "confirmed", "completed", "paid", "success", "succeeded",
}

# Order statuses from which a return is possible — DETAILS.md §9
RETURNABLE_ORDER_STATUSES = {"fulfilled", "returned"}

# Sorts before any real timestamp; used so unparseable dates never win "latest".
_EPOCH = datetime.min.replace(tzinfo=timezone.utc)


def _parse_ts(value: Optional[str]) -> Optional[datetime]:
    """Parse an ISO timestamp string, returning None on failure.

    Naive timestamps are assumed UTC so aware/naive values remain comparable.
    """
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _days_between(a: Optional[str], b: Optional[str]) -> Optional[float]:
    """Return days from `a` to `b` (b − a) as a float, or None."""
    dt_a = _parse_ts(a)
    dt_b = _parse_ts(b)
    if dt_a is None or dt_b is None:
        return None
    return (dt_b - dt_a).total_seconds() / 86400


def _latest_event(events: list, *event_types: str) -> Optional[dict]:
    """Return the latest tracking event matching any of `event_types`.

    DETAILS.md §9 specifies "latest tracking event of that type" — bundle order
    is not guaranteed, so this sorts by `occurred_at` rather than trusting it.
    """
    matching = [
        e for e in events
        if (e.get("event_type") or "").lower() in event_types
    ]
    if not matching:
        return None
    return max(matching, key=lambda e: _parse_ts(e.get("occurred_at")) or _EPOCH)


def _qty_of(item: dict) -> float:
    """Ordered quantity for a bundle item ("qty", tolerating "quantity")."""
    qty = item.get("qty")
    if qty is None:
        qty = item.get("quantity", 1)
    return qty or 0


def derive_facts(bundle: dict, constants: Optional[dict] = None) -> DerivedFacts:
    """Derive intermediate facts from the evidence bundle.

    Args:
        bundle: Plain-dict evidence bundle (see SCHEMA.md §5). `dispute_subtype`
            is expected to be already normalised (see adjudicate.py).
        constants: Business constants; falls back to DETAILS.md §6 defaults.

    Returns:
        DerivedFacts populated from the bundle.
    """
    return_window_days = constant("RETURN_WINDOW_DAYS", constants)
    delivery_sla_breach_days = constant("DELIVERY_SLA_BREACH_DAYS", constants)
    stale_transit_days = constant("STALE_TRANSIT_DAYS", constants)

    facts = DerivedFacts()
    as_of = bundle.get("as_of")
    subtype = bundle.get("dispute_subtype", "")

    # --- Payment ---
    payment = bundle.get("payment") or {}
    payment_status = (payment.get("status") or "").lower()
    facts.payment_confirmed = payment_status in CONFIRMED_PAYMENT_STATUSES

    # --- Order ---
    order = bundle.get("order") or {}
    order_status = (order.get("status") or "").lower()
    facts.order_returnable = order_status in RETURNABLE_ORDER_STATUSES

    # Total order amount: refund-transaction amount ?? order total
    #                     ?? payment amount ?? 0
    refund_history = bundle.get("refund_history") or []
    refund_amount = refund_history[0].get("amount", 0) if refund_history else 0
    facts.total_order_amount = (
        refund_amount
        or order.get("total_amount", 0)
        or payment.get("amount", 0)
        or 0
    )

    facts.shipping_fee = order.get("shipping_fee") or 0

    # --- Affected items ---
    # Σ(qty × unit price) over selected items; fallback all items; fallback total
    affected_items = bundle.get("affected_items") or []
    items = bundle.get("items") or []

    if affected_items:
        facts.affected_amount = sum(
            _qty_of(i) * (i.get("unit_price") or 0) for i in affected_items
        )
    elif items:
        facts.affected_amount = sum(
            _qty_of(i) * (i.get("unit_price") or 0) for i in items
        )
    else:
        facts.affected_amount = facts.total_order_amount

    facts.replacement_amount = (
        facts.affected_amount if facts.affected_amount > 0
        else facts.total_order_amount
    )

    # --- Tracking events (latest of each type) ---
    shipment = bundle.get("shipment") or {}
    tracking_events = bundle.get("tracking_events") or []

    facts.delivered_event = _latest_event(tracking_events, "delivered")
    facts.lost_event = _latest_event(tracking_events, "lost")
    # "exception falls back to `delayed` event" — prefer a true exception
    facts.exception_event = (
        _latest_event(tracking_events, "exception")
        or _latest_event(tracking_events, "delayed")
    )
    facts.in_transit_event = _latest_event(tracking_events, "in_transit")

    # --- Return window ---
    # First non-null of: shipment delivered_at, order delivered_at,
    # order fulfilled_at, order placed_at, delivered tracking event time
    facts.window_basis_date = (
        shipment.get("delivered_at")
        or order.get("delivered_at")
        or order.get("fulfilled_at")
        or order.get("placed_at")
        or (facts.delivered_event.get("occurred_at")
            if facts.delivered_event else None)
    )

    if facts.window_basis_date and as_of:
        days = _days_between(facts.window_basis_date, as_of)
        facts.within_return_window = (
            days is not None and 0 <= days <= return_window_days
        )

    # --- Stale in transit ---
    if facts.in_transit_event and not facts.delivered_event:
        days_since = _days_between(
            facts.in_transit_event.get("occurred_at"), as_of
        )
        facts.stale_in_transit = (
            days_since is not None and days_since > stale_transit_days
        )

    # --- SLA breach ---
    # Delivered ∧ days(delivered_at − estimated_delivery) > threshold.
    # "Delivered" is taken from whichever source carries the timestamp.
    delivered_at = (
        shipment.get("delivered_at")
        or order.get("delivered_at")
        or (facts.delivered_event.get("occurred_at")
            if facts.delivered_event else None)
    )
    estimated_delivery = (
        shipment.get("estimated_delivery") or order.get("estimated_delivery")
    )
    if delivered_at and estimated_delivery:
        days_late = _days_between(estimated_delivery, delivered_at)
        facts.sla_breached = (
            days_late is not None and days_late > delivery_sla_breach_days
        )

    # --- Prior refunds ---
    facts.prior_refund_count = len(refund_history)
    facts.prior_refund_total = sum((r.get("amount") or 0) for r in refund_history)

    # --- Inventory ---
    # False if the item list is empty, any item has unknown availability, or
    # available < ordered. The reason names the blocked products.
    inventory = bundle.get("inventory") or []
    check_items = affected_items or items

    if not check_items:
        facts.inventory_feasible = False
        facts.inventory_block_reason = "no items to check"
    else:
        blocked = []
        for item in check_items:
            sku = item.get("sku")
            label = item.get("name") or sku or "unknown item"
            stock_entry = next(
                (inv for inv in inventory if inv.get("sku") == sku), None
            )
            if stock_entry is None:
                blocked.append(f"{label}: unknown availability")
                continue
            # Prefer the ordered qty the inventory feed reports; fall back to
            # the qty on the line item.
            needed = stock_entry.get("quantity_ordered")
            if needed is None:
                needed = _qty_of(item)
            available = stock_entry.get("quantity_available") or 0
            if available < needed:
                blocked.append(f"{label}: need {needed}, have {available}")
        facts.inventory_feasible = not blocked
        facts.inventory_block_reason = "; ".join(blocked)

    # --- Proof ---
    # proof_contradicts = the subtype-relevant signal is explicitly false while
    # proof exists. A *missing* signal is not a contradiction — it is merely
    # unsupportive (G-09), which is why `is False` is load-bearing below.
    proof = bundle.get("proof") or {}
    facts.proof_present = bool(proof.get("present", False))
    facts.proof_analysis_failed = (
        (proof.get("analysis_status") or "").lower() == "failed"
    )

    if facts.proof_present and not facts.proof_analysis_failed:
        signals = proof.get("signals") or {}
        signal_key = PROOF_SIGNAL_BY_SUBTYPE.get(subtype)
        if signal_key:
            signal = signals.get(signal_key)
            facts.proof_supports = signal is True
            facts.proof_contradicts = signal is False

    return facts
