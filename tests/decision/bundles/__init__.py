"""Evidence-bundle builders for decision-engine tests.

The engine's entire input is a plain dict (SCHEMA.md §5), so fixtures are built
here rather than loaded from a database. `make_bundle()` returns a *clean* case
— payment confirmed, delivered inside the return window, no prior refunds,
stock on hand, and (for proof-required subtypes) supporting proof — so that no
guardrail fires unless a test deliberately makes one fire.

The engine has no clock: every timestamp is relative to `AS_OF`.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from tide_decision.types import PROOF_SIGNAL_BY_SUBTYPE

# The bundle's evaluation timestamp. Everything else is derived from it.
AS_OF = "2026-08-01T12:00:00+00:00"

# Subtypes whose routing turns on tracking state rather than the return window.
DELIVERY_SUBTYPES = {"non_receipt", "delayed", "exception", "lost"}

DEFAULT_SKU = "SKU-KETTLE-01"
DEFAULT_ITEM_ID = "IT-0001"


class _Unset:
    """Sentinel so `delivered_days_ago=None` can mean 'never delivered'."""

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return "UNSET"


UNSET = _Unset()


def days_before(n: float, base: str = AS_OF) -> str:
    """ISO timestamp `n` days before `base`."""
    return (datetime.fromisoformat(base) - timedelta(days=n)).isoformat()


def days_after(n: float, base: str = AS_OF) -> str:
    """ISO timestamp `n` days after `base`."""
    return (datetime.fromisoformat(base) + timedelta(days=n)).isoformat()


def tracking_event(event_type: str, days_ago: float = 1, location: str = "Cebu Hub") -> dict:
    """A single RETAIL.TRACKING_EVENTS row as it appears in a bundle."""
    return {
        "event_type": event_type,
        "location": location,
        "occurred_at": days_before(days_ago),
    }


def default_proof(subtype: str) -> dict:
    """Proof that *supports* the claim, for proof-required subtypes only."""
    signal_key = PROOF_SIGNAL_BY_SUBTYPE.get(subtype)
    if not signal_key:
        return {"present": False, "analysis_status": None, "signals": {}}
    return {
        "present": True,
        "analysis_status": "completed",
        "signals": {signal_key: True},
        "notes": "Photo clearly shows the reported issue.",
    }


def make_bundle(
    subtype: str,
    preference: str = "",
    *,
    amount: float = 40.00,
    total_amount: float | None = None,
    shipping_fee: float = 4.99,
    qty: int = 1,
    order_status: str | None = None,
    payment_status: str = "confirmed",
    delivered_days_ago: float | None = UNSET,
    estimated_delivery: str | None = None,
    stock_available: int | None = 5,
    tracking_events: list | None = None,
    refund_history: list | None = None,
    proof: dict | None = None,
    as_of: str = AS_OF,
    **overrides,
) -> dict:
    """Build a clean evidence bundle, then apply overrides.

    Args:
        amount: Unit price of the affected line item → drives `affected_amount`.
        total_amount: Order total → drives `total_order_amount`. Defaults to
            `amount * qty` so simple cases need only one number.
        delivered_days_ago: Sets `shipment.delivered_at`. Omitted, it defaults
            to 2 days (inside the return window) for non-delivery subtypes and
            to undelivered for delivery subtypes. Pass None to force
            "no delivery timestamp anywhere".
        stock_available: Units on hand for the affected SKU. `None` omits the
            SKU from the inventory feed entirely (unknown availability).
        **overrides: Replace any top-level bundle key outright.
    """
    is_delivery = subtype in DELIVERY_SUBTYPES

    if delivered_days_ago is UNSET:
        delivered_days_ago = None if is_delivery else 2
    if order_status is None:
        order_status = "placed" if is_delivery else "fulfilled"
    if total_amount is None:
        total_amount = amount * qty

    delivered_at = (
        days_before(delivered_days_ago) if delivered_days_ago is not None else None
    )

    line_item = {
        "item_id": DEFAULT_ITEM_ID,
        "sku": DEFAULT_SKU,
        "name": "Stovetop Kettle 1.5L",
        "qty": qty,
        "unit_price": amount,
    }

    inventory = []
    if stock_available is not None:
        inventory = [{
            "sku": DEFAULT_SKU,
            "quantity_available": stock_available,
            "quantity_ordered": qty,
        }]

    bundle = {
        "as_of": as_of,
        "dispute_subtype": subtype,
        "resolution_preference": preference,
        "order": {
            "order_id": "ORD-0001",
            "status": order_status,
            "total_amount": total_amount,
            "shipping_fee": shipping_fee,
            "placed_at": days_before(10),
            "fulfilled_at": days_before(6),
            "delivered_at": None,
            "estimated_delivery": estimated_delivery,
        },
        "items": [line_item],
        "affected_items": [dict(line_item)],
        "payment": {
            "status": payment_status,
            "amount": total_amount,
            "method": "card",
        },
        "refund_history": list(refund_history or []),
        "shipment": {
            "carrier": "SwiftPost",
            "estimated_delivery": estimated_delivery,
            "delivered_at": delivered_at,
        },
        "tracking_events": list(tracking_events or []),
        "inventory": inventory,
        "proof": proof if proof is not None else default_proof(subtype),
        "assembly": {"status": "complete", "sources": ["orders", "payments"], "failures": []},
    }

    bundle.update(overrides)
    return bundle
