"""Fact-derivation and constants tests — DETAILS.md §6, §7.2, §7.3, §9.

Routing and guardrail tests pin the *decisions*; these pin the derivations they
stand on, so a subtle regression in (say) which tracking event counts as the
latest fails here with a readable message instead of somewhere in the matrix.
"""

import pytest

from tide_decision import adjudicate
from tide_decision.fact_derivation import derive_facts
from tide_decision.types import (
    DEFAULT_CONSTANTS,
    INTAKE_ALIASES,
    SUBTYPE_META,
    constant,
    resolve_type,
)

from .bundles import confirmed_payments, days_before, make_bundle, tracking_event


# ---------------------------------------------------------------------------
# §6 — constants
# ---------------------------------------------------------------------------
def test_default_constants_match_the_brl():
    """These mirror DECISION.RULE_CONSTANTS; drift here is a spec violation."""
    assert DEFAULT_CONSTANTS["AUTONOMOUS_LIMIT_USD"] == 50.00
    assert DEFAULT_CONSTANTS["RETURN_WINDOW_DAYS"] == 7
    assert DEFAULT_CONSTANTS["DELIVERY_SLA_BREACH_DAYS"] == 3
    assert DEFAULT_CONSTANTS["STALE_TRANSIT_DAYS"] == 7
    assert DEFAULT_CONSTANTS["INACTIVITY_TIMEOUT_MIN"] == 15
    assert DEFAULT_CONSTANTS["MIN_REJECTION_CHARS"] == 50
    assert DEFAULT_CONSTANTS["MIN_REJECTION_CITATIONS"] == 1
    assert DEFAULT_CONSTANTS["MAX_PROOF_UPLOADS"] == 2
    assert DEFAULT_CONSTANTS["MAX_FOLLOWUP_QUESTIONS"] == 3
    assert DEFAULT_CONSTANTS["CURRENCY"] == "USD"


def test_constant_prefers_the_supplied_override():
    assert constant("AUTONOMOUS_LIMIT_USD", {"AUTONOMOUS_LIMIT_USD": 125.00}) == 125.00
    assert constant("AUTONOMOUS_LIMIT_USD", {}) == 50.00
    assert constant("AUTONOMOUS_LIMIT_USD", None) == 50.00


def test_unknown_constant_fails_loudly():
    with pytest.raises(KeyError):
        constant("NOT_A_REAL_CONSTANT")


def test_autonomous_limit_is_read_not_hardcoded():
    """Raising the limit must move the same case from approval to autonomous."""
    bundle = make_bundle(
        "duplicate_charge",
        "refund",
        total_amount=120.00,
        payments=confirmed_payments(2, 120.00),  # two charges, or G-10 fires first
    )

    assert adjudicate(bundle).path_id == "R-02"
    assert adjudicate(bundle, {"AUTONOMOUS_LIMIT_USD": 200.00}).path_id == "R-01"


def test_return_window_is_read_not_hardcoded():
    bundle = make_bundle("damaged_goods", "refund", delivered_days_ago=10)

    assert adjudicate(bundle).path_id == "R-12"  # outside the 7-day window
    assert adjudicate(bundle, {"RETURN_WINDOW_DAYS": 30}).path_id == "R-13"


def test_stale_transit_days_is_read_not_hardcoded():
    bundle = make_bundle(
        "non_receipt", "refund",
        tracking_events=[tracking_event("in_transit", days_ago=10)],
    )

    assert adjudicate(bundle).path_id == "R-35"  # stale at >7 days
    assert adjudicate(bundle, {"STALE_TRANSIT_DAYS": 20}).path_id == "R-31"


# ---------------------------------------------------------------------------
# §7.1 / §7.2 / §7.3 — taxonomy, aliases, resolution type
# ---------------------------------------------------------------------------
def test_twelve_canonical_subtypes():
    assert len(SUBTYPE_META) == 12


def test_intake_aliases_normalise_before_anything_else():
    """An alias must behave exactly like its canonical subtype."""
    aliased = adjudicate(make_bundle("package_never_arrived", "refund"))
    canonical = adjudicate(make_bundle("non_receipt", "refund"))

    assert aliased.path_id == canonical.path_id == "R-31"


def test_every_alias_maps_to_a_canonical_subtype():
    for alias, target in INTAKE_ALIASES.items():
        assert target in SUBTYPE_META, f"{alias} maps to unknown subtype {target}"


def test_subtype_is_case_and_whitespace_insensitive():
    bundle = make_bundle(
        "damaged_goods", "refund", dispute_subtype="  DAMAGED_GOODS  "
    )

    assert adjudicate(bundle).path_id == "R-13"


def test_resolve_type_prefers_an_allowed_preference():
    assert resolve_type("replacement", "damaged_goods") == "replacement"


def test_resolve_type_falls_back_to_the_subtype_default():
    assert resolve_type("", "damaged_goods") == "refund"
    assert resolve_type("", "return_request") == "return"


# ---------------------------------------------------------------------------
# §9 — derived facts
# ---------------------------------------------------------------------------
def test_latest_tracking_event_wins_regardless_of_bundle_order():
    """DETAILS.md §9 says 'latest', and bundle ordering is not guaranteed."""
    bundle = make_bundle(
        "non_receipt", "refund",
        tracking_events=[
            tracking_event("in_transit", days_ago=2, location="Recent Hub"),
            tracking_event("in_transit", days_ago=9, location="Old Hub"),
        ],
    )
    facts = derive_facts(bundle)

    assert facts.in_transit_event["location"] == "Recent Hub"
    assert facts.stale_in_transit is False  # latest movement was 2 days ago


def test_exception_event_falls_back_to_a_delayed_event():
    bundle = make_bundle(
        "exception", "refund",
        tracking_events=[tracking_event("delayed", days_ago=2)],
    )
    facts = derive_facts(bundle)

    assert facts.exception_event is not None
    assert facts.exception_event["event_type"] == "delayed"


def test_a_true_exception_outranks_a_delayed_event():
    bundle = make_bundle(
        "exception", "refund",
        tracking_events=[
            tracking_event("delayed", days_ago=1, location="Delayed Scan"),
            tracking_event("exception", days_ago=4, location="Exception Scan"),
        ],
    )
    facts = derive_facts(bundle)

    assert facts.exception_event["location"] == "Exception Scan"


def test_window_basis_prefers_shipment_delivery_date():
    bundle = make_bundle("damaged_goods", "refund", delivered_days_ago=3)
    facts = derive_facts(bundle)

    assert facts.window_basis_date == days_before(3)
    assert facts.within_return_window is True


def test_window_basis_falls_back_through_the_order_dates():
    """No delivery timestamp anywhere → fall back to fulfilled_at."""
    bundle = make_bundle("damaged_goods", "refund", delivered_days_ago=None)
    facts = derive_facts(bundle)

    assert facts.window_basis_date == days_before(6)  # order.fulfilled_at


def test_sla_breach_uses_the_shipment_delivery_date():
    """A late delivery with no tracking rows must still breach the SLA."""
    bundle = make_bundle(
        "delayed", "refund",
        delivered_days_ago=1, estimated_delivery=days_before(6),
    )
    facts = derive_facts(bundle)

    assert facts.sla_breached is True


def test_sla_not_breached_inside_the_grace_window():
    bundle = make_bundle(
        "delayed", "refund",
        delivered_days_ago=4, estimated_delivery=days_before(6),
    )
    facts = derive_facts(bundle)

    assert facts.sla_breached is False  # 2 days late, threshold is 3


def test_affected_amount_falls_back_to_all_items():
    bundle = make_bundle("damaged_goods", "refund", amount=30.00, affected_items=[])
    facts = derive_facts(bundle)

    assert facts.affected_amount == 30.00


def test_affected_amount_sums_quantity_times_price():
    bundle = make_bundle("damaged_goods", "refund", amount=12.50, qty=4)
    facts = derive_facts(bundle)

    assert facts.affected_amount == 50.00


def test_inventory_unknown_sku_is_not_feasible():
    """An item missing from the feed is unknown availability, not availability."""
    bundle = make_bundle("damaged_goods", "replacement", stock_available=None)
    facts = derive_facts(bundle)

    assert facts.inventory_feasible is False
    assert "unknown availability" in facts.inventory_block_reason


def test_inventory_block_reason_names_the_product():
    bundle = make_bundle("damaged_goods", "replacement", stock_available=0)
    facts = derive_facts(bundle)

    assert facts.inventory_feasible is False
    assert "Stovetop Kettle 1.5L" in facts.inventory_block_reason


def test_prior_refunds_are_counted_and_totalled():
    bundle = make_bundle(
        "damaged_goods", "refund",
        refund_history=[{"amount": 10.00}, {"amount": 15.50}],
    )
    facts = derive_facts(bundle)

    assert facts.prior_refund_count == 2
    assert facts.prior_refund_total == 25.50


def test_proof_signal_is_read_per_subtype():
    supporting = derive_facts(make_bundle("damaged_goods", "refund"))
    assert supporting.proof_supports is True
    assert supporting.proof_contradicts is False

    contradicting = derive_facts(make_bundle(
        "damaged_goods", "refund",
        proof={"present": True, "analysis_status": "completed",
               "signals": {"damage_detected": False}},
    ))
    assert contradicting.proof_supports is False
    assert contradicting.proof_contradicts is True


def test_the_engine_has_no_clock():
    """`as_of` drives every date comparison — same bundle, different verdict."""
    recent = make_bundle("damaged_goods", "refund", delivered_days_ago=2)
    stale = make_bundle("damaged_goods", "refund", delivered_days_ago=2,
                        as_of=days_before(-30))  # evaluated 30 days later

    assert adjudicate(recent).path_id == "R-13"
    assert adjudicate(stale).path_id == "R-12"


def test_adjudicate_is_pure():
    """Same bundle in, same decision out — and the input is not mutated."""
    bundle = make_bundle("damaged_goods", "refund", amount=12.00)
    snapshot = repr(bundle)

    first = adjudicate(bundle)
    second = adjudicate(bundle)

    assert first == second
    assert repr(bundle) == snapshot
