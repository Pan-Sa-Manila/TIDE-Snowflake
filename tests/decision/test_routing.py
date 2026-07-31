"""Routing tests — DETAILS.md §11 and the §13 path enumeration (R-01 … R-53).

One test per terminal path. `AUTO` = approved_executing, `APPR` = awaiting_approval,
`ESC` = escalated_human_required, `ACD` = awaiting_customer_decision.

Amount convention: 40.00 sits below the $50 autonomous limit, 180.00 above it.
Where a path's eligible amount could plausibly come from more than one field,
the fixture makes the fields differ so the assertion pins the right one.
"""

from tide_decision import adjudicate
from tide_decision.fact_derivation import derive_facts
from tide_decision.routing import route
from tide_decision.types import CaseStatus, InvalidReasonCode, ResolutionType

from .bundles import confirmed_payments, make_bundle, tracking_event

UNDER = 40.00
OVER = 180.00


# ===========================================================================
# duplicate_charge — R-01 / R-02 (refund of total_order_amount)
# ===========================================================================
def test_r01_duplicate_charge_under_limit_is_autonomous():
    """R-01: refunds the *order total*, not the affected-item subtotal."""
    bundle = make_bundle(
        "duplicate_charge",
        "refund",
        amount=10.00,
        total_amount=UNDER,
        payments=confirmed_payments(2, UNDER),  # two charges, or G-10 fires first
    )
    decision = adjudicate(bundle)

    assert decision.path_id == "R-01"
    assert decision.target_status == CaseStatus.APPROVED_EXECUTING
    assert decision.resolution_type == ResolutionType.REFUND
    assert decision.eligible_amount == UNDER


def test_r02_duplicate_charge_over_limit_needs_approval():
    bundle = make_bundle(
        "duplicate_charge",
        "refund",
        amount=10.00,
        total_amount=OVER,
        payments=confirmed_payments(2, OVER),  # two charges, or G-10 fires first
    )
    decision = adjudicate(bundle)

    assert decision.path_id == "R-02"
    assert decision.target_status == CaseStatus.AWAITING_APPROVAL
    assert decision.resolution_type == ResolutionType.REFUND
    assert decision.eligible_amount == OVER


# ===========================================================================
# not_as_described — R-03 … R-08
# ===========================================================================
def test_r03_not_as_described_replacement_infeasible():
    bundle = make_bundle("not_as_described", "replacement", stock_available=0)
    decision = adjudicate(bundle)

    assert decision.path_id == "R-03"
    assert decision.target_status == CaseStatus.AWAITING_CUSTOMER_DECISION
    assert decision.invalid_reason_code == InvalidReasonCode.INSUFFICIENT_INVENTORY
    assert "Stovetop Kettle" in decision.reason


def test_r04_not_as_described_replacement_under_limit():
    bundle = make_bundle("not_as_described", "replacement", amount=UNDER)
    decision = adjudicate(bundle)

    assert decision.path_id == "R-04"
    assert decision.target_status == CaseStatus.APPROVED_EXECUTING
    assert decision.resolution_type == ResolutionType.REPLACEMENT
    assert decision.eligible_amount == UNDER
    assert decision.replacement_items
    assert decision.affected_item_ids == ["IT-0001"]


def test_r05_not_as_described_replacement_over_limit():
    bundle = make_bundle("not_as_described", "replacement", amount=OVER)
    decision = adjudicate(bundle)

    assert decision.path_id == "R-05"
    assert decision.target_status == CaseStatus.AWAITING_APPROVAL
    assert decision.resolution_type == ResolutionType.REPLACEMENT


def test_r06_not_as_described_refund_outside_window():
    bundle = make_bundle("not_as_described", "refund", delivered_days_ago=30)
    decision = adjudicate(bundle)

    assert decision.path_id == "R-06"
    assert decision.target_status == CaseStatus.AWAITING_CUSTOMER_DECISION
    assert decision.invalid_reason_code == InvalidReasonCode.OUTSIDE_RETURN_WINDOW


def test_r07_not_as_described_refund_under_limit():
    """Refunds the affected-item subtotal, not the whole order."""
    bundle = make_bundle("not_as_described", "refund", amount=UNDER, total_amount=500.00)
    decision = adjudicate(bundle)

    assert decision.path_id == "R-07"
    assert decision.target_status == CaseStatus.APPROVED_EXECUTING
    assert decision.resolution_type == ResolutionType.REFUND
    assert decision.eligible_amount == UNDER


def test_r08_not_as_described_refund_over_limit():
    bundle = make_bundle("not_as_described", "refund", amount=OVER)
    decision = adjudicate(bundle)

    assert decision.path_id == "R-08"
    assert decision.target_status == CaseStatus.AWAITING_APPROVAL
    assert decision.eligible_amount == OVER


# ===========================================================================
# damaged_goods — R-09 … R-14
# ===========================================================================
def test_r09_damaged_goods_replacement_infeasible():
    decision = adjudicate(make_bundle("damaged_goods", "replacement", stock_available=0))

    assert decision.path_id == "R-09"
    assert decision.invalid_reason_code == InvalidReasonCode.INSUFFICIENT_INVENTORY


def test_r10_damaged_goods_replacement_under_limit():
    decision = adjudicate(make_bundle("damaged_goods", "replacement", amount=UNDER))

    assert decision.path_id == "R-10"
    assert decision.target_status == CaseStatus.APPROVED_EXECUTING
    assert decision.resolution_type == ResolutionType.REPLACEMENT


def test_r11_damaged_goods_replacement_over_limit():
    decision = adjudicate(make_bundle("damaged_goods", "replacement", amount=OVER))

    assert decision.path_id == "R-11"
    assert decision.target_status == CaseStatus.AWAITING_APPROVAL


def test_r12_damaged_goods_refund_outside_window():
    decision = adjudicate(make_bundle("damaged_goods", "refund", delivered_days_ago=30))

    assert decision.path_id == "R-12"
    assert decision.invalid_reason_code == InvalidReasonCode.OUTSIDE_RETURN_WINDOW


def test_r13_damaged_goods_refund_under_limit():
    """The headline demo case: a small damaged-goods claim resolves itself."""
    decision = adjudicate(make_bundle("damaged_goods", "refund", amount=12.00))

    assert decision.path_id == "R-13"
    assert decision.target_status == CaseStatus.APPROVED_EXECUTING
    assert decision.resolution_type == ResolutionType.REFUND
    assert decision.eligible_amount == 12.00


def test_r14_damaged_goods_refund_over_limit():
    decision = adjudicate(make_bundle("damaged_goods", "refund", amount=OVER))

    assert decision.path_id == "R-14"
    assert decision.target_status == CaseStatus.AWAITING_APPROVAL


# ===========================================================================
# wrong_item — R-15 … R-20
# ===========================================================================
def test_r15_wrong_item_replacement_infeasible():
    decision = adjudicate(make_bundle("wrong_item", "replacement", stock_available=0))

    assert decision.path_id == "R-15"
    assert decision.invalid_reason_code == InvalidReasonCode.INSUFFICIENT_INVENTORY


def test_r16_wrong_item_replacement_under_limit():
    decision = adjudicate(make_bundle("wrong_item", "replacement", amount=UNDER))

    assert decision.path_id == "R-16"
    assert decision.target_status == CaseStatus.APPROVED_EXECUTING
    assert decision.resolution_type == ResolutionType.REPLACEMENT


def test_r17_wrong_item_replacement_over_limit():
    decision = adjudicate(make_bundle("wrong_item", "replacement", amount=OVER))

    assert decision.path_id == "R-17"
    assert decision.target_status == CaseStatus.AWAITING_APPROVAL


def test_r18_wrong_item_refund_outside_window():
    decision = adjudicate(make_bundle("wrong_item", "refund", delivered_days_ago=30))

    assert decision.path_id == "R-18"
    assert decision.invalid_reason_code == InvalidReasonCode.OUTSIDE_RETURN_WINDOW


def test_r19_wrong_item_refund_under_limit():
    decision = adjudicate(make_bundle("wrong_item", "refund", amount=UNDER))

    assert decision.path_id == "R-19"
    assert decision.target_status == CaseStatus.APPROVED_EXECUTING


def test_r20_wrong_item_refund_over_limit():
    decision = adjudicate(make_bundle("wrong_item", "refund", amount=OVER))

    assert decision.path_id == "R-20"
    assert decision.target_status == CaseStatus.AWAITING_APPROVAL


# ===========================================================================
# partial_fulfillment — R-21
# ===========================================================================
def test_r21_partial_fulfillment_always_escalates():
    """Multi-item shortfalls need a human even when the money is trivial."""
    decision = adjudicate(make_bundle("partial_fulfillment", "refund", amount=20.00))

    assert decision.path_id == "R-21"
    assert decision.target_status == CaseStatus.ESCALATED_HUMAN_REQUIRED
    assert decision.eligible_amount == 20.00


# ===========================================================================
# return_request — R-22 … R-24
# ===========================================================================
def test_r22_return_request_non_returnable_order():
    bundle = make_bundle("return_request", "return", order_status="cancelled")
    decision = adjudicate(bundle)

    assert decision.path_id == "R-22"
    assert decision.target_status == CaseStatus.AWAITING_CUSTOMER_DECISION
    assert decision.invalid_reason_code == InvalidReasonCode.NON_RETURNABLE_ITEM


def test_r23_return_request_outside_window():
    bundle = make_bundle("return_request", "return", delivered_days_ago=30)
    decision = adjudicate(bundle)

    assert decision.path_id == "R-23"
    assert decision.invalid_reason_code == InvalidReasonCode.OUTSIDE_RETURN_WINDOW


def test_r24_return_request_is_never_autonomous():
    """Even a $30 return waits for a human — DETAILS.md §11."""
    bundle = make_bundle("return_request", "return", amount=30.00, total_amount=30.00)
    decision = adjudicate(bundle)

    assert decision.path_id == "R-24"
    assert decision.target_status == CaseStatus.AWAITING_APPROVAL
    assert decision.resolution_type == ResolutionType.RETURN
    assert decision.eligible_amount == 30.00


# ===========================================================================
# changed_mind — R-25 … R-27
# ===========================================================================
def test_r25_changed_mind_non_returnable_order():
    bundle = make_bundle("changed_mind", "return", order_status="cancelled")
    decision = adjudicate(bundle)

    assert decision.path_id == "R-25"
    assert decision.invalid_reason_code == InvalidReasonCode.NON_RETURNABLE_ITEM


def test_r26_changed_mind_outside_window():
    bundle = make_bundle("changed_mind", "return", delivered_days_ago=30)
    decision = adjudicate(bundle)

    assert decision.path_id == "R-26"
    assert decision.invalid_reason_code == InvalidReasonCode.OUTSIDE_RETURN_WINDOW


def test_r27_changed_mind_is_never_autonomous():
    bundle = make_bundle("changed_mind", "return", amount=25.00, total_amount=25.00)
    decision = adjudicate(bundle)

    assert decision.path_id == "R-27"
    assert decision.target_status == CaseStatus.AWAITING_APPROVAL
    assert decision.resolution_type == ResolutionType.RETURN


# ===========================================================================
# other — R-28
# ===========================================================================
def test_r28_other_always_escalates():
    decision = adjudicate(make_bundle("other", "refund"))

    assert decision.path_id == "R-28"
    assert decision.target_status == CaseStatus.ESCALATED_HUMAN_REQUIRED


# ===========================================================================
# non_receipt — R-29 … R-37
# ===========================================================================
def test_r29_non_receipt_replacement_infeasible():
    decision = adjudicate(make_bundle("non_receipt", "replacement", stock_available=0))

    assert decision.path_id == "R-29"
    assert decision.invalid_reason_code == InvalidReasonCode.INSUFFICIENT_INVENTORY


def test_r30_non_receipt_replacement_is_never_autonomous():
    decision = adjudicate(make_bundle("non_receipt", "replacement", amount=UNDER))

    assert decision.path_id == "R-30"
    assert decision.target_status == CaseStatus.AWAITING_APPROVAL
    assert decision.resolution_type == ResolutionType.REPLACEMENT
    assert decision.eligible_amount == UNDER


def test_r31_non_receipt_refund_no_tracking_under_limit():
    decision = adjudicate(make_bundle("non_receipt", "refund", amount=UNDER))

    assert decision.path_id == "R-31"
    assert decision.target_status == CaseStatus.APPROVED_EXECUTING
    assert decision.resolution_type == ResolutionType.REFUND


def test_r32_non_receipt_refund_no_tracking_over_limit():
    decision = adjudicate(make_bundle("non_receipt", "refund", amount=OVER))

    assert decision.path_id == "R-32"
    assert decision.target_status == CaseStatus.AWAITING_APPROVAL


def test_r33_non_receipt_refund_carrier_exception_under_limit():
    bundle = make_bundle(
        "non_receipt", "refund", amount=UNDER,
        tracking_events=[tracking_event("exception", days_ago=2, location="Mandaue Depot")],
    )
    decision = adjudicate(bundle)

    assert decision.path_id == "R-33"
    assert decision.target_status == CaseStatus.APPROVED_EXECUTING
    assert decision.tracking_evidence.startswith("Exception at Mandaue Depot on")


def test_r34_non_receipt_refund_carrier_exception_over_limit():
    bundle = make_bundle(
        "non_receipt", "refund", amount=OVER,
        tracking_events=[tracking_event("exception", days_ago=2)],
    )
    decision = adjudicate(bundle)

    assert decision.path_id == "R-34"
    assert decision.target_status == CaseStatus.AWAITING_APPROVAL


def test_r35_non_receipt_refund_stale_transit_under_limit():
    bundle = make_bundle(
        "non_receipt", "refund", amount=UNDER,
        tracking_events=[tracking_event("in_transit", days_ago=10)],
    )
    decision = adjudicate(bundle)

    assert decision.path_id == "R-35"
    assert decision.target_status == CaseStatus.APPROVED_EXECUTING
    assert decision.tracking_evidence.startswith("Last movement at")


def test_r36_non_receipt_refund_stale_transit_over_limit():
    bundle = make_bundle(
        "non_receipt", "refund", amount=OVER,
        tracking_events=[tracking_event("in_transit", days_ago=10)],
    )
    decision = adjudicate(bundle)

    assert decision.path_id == "R-36"
    assert decision.target_status == CaseStatus.AWAITING_APPROVAL


def test_r37_non_receipt_refund_ambiguous_tracking_escalates():
    """A carrier 'lost' scan on a non-receipt claim is not a clean payout."""
    bundle = make_bundle(
        "non_receipt", "refund", amount=UNDER,
        tracking_events=[tracking_event("lost", days_ago=2)],
    )
    decision = adjudicate(bundle)

    assert decision.path_id == "R-37"
    assert decision.target_status == CaseStatus.ESCALATED_HUMAN_REQUIRED


# ===========================================================================
# delayed — R-38 … R-44
# ===========================================================================
def test_r38_delayed_sla_breach_refunds_shipping_only():
    """Late but delivered → the customer gets the shipping fee back, not the goods."""
    from .bundles import days_before

    bundle = make_bundle(
        "delayed", "refund", amount=OVER, shipping_fee=4.99,
        delivered_days_ago=1, estimated_delivery=days_before(6),
    )
    decision = adjudicate(bundle)

    assert decision.path_id == "R-38"
    assert decision.target_status == CaseStatus.APPROVED_EXECUTING
    assert decision.shipping_fee_only is True
    assert decision.eligible_amount == 4.99


def test_r39_delayed_sla_breach_shipping_over_limit():
    from .bundles import days_before

    bundle = make_bundle(
        "delayed", "refund", shipping_fee=75.00,
        delivered_days_ago=1, estimated_delivery=days_before(6),
    )
    decision = adjudicate(bundle)

    assert decision.path_id == "R-39"
    assert decision.target_status == CaseStatus.AWAITING_APPROVAL
    assert decision.shipping_fee_only is True
    assert decision.eligible_amount == 75.00


def test_r40_delayed_carrier_exception_under_limit():
    bundle = make_bundle(
        "delayed", "refund", amount=UNDER,
        tracking_events=[tracking_event("exception", days_ago=2)],
    )
    decision = adjudicate(bundle)

    assert decision.path_id == "R-40"
    assert decision.target_status == CaseStatus.APPROVED_EXECUTING
    assert decision.eligible_amount == UNDER


def test_r41_delayed_carrier_exception_over_limit():
    bundle = make_bundle(
        "delayed", "refund", amount=OVER,
        tracking_events=[tracking_event("exception", days_ago=2)],
    )
    decision = adjudicate(bundle)

    assert decision.path_id == "R-41"
    assert decision.target_status == CaseStatus.AWAITING_APPROVAL


def test_r42_delayed_stale_transit_under_limit():
    bundle = make_bundle(
        "delayed", "refund", amount=UNDER,
        tracking_events=[tracking_event("in_transit", days_ago=10)],
    )
    decision = adjudicate(bundle)

    assert decision.path_id == "R-42"
    assert decision.target_status == CaseStatus.APPROVED_EXECUTING


def test_r43_delayed_stale_transit_over_limit():
    bundle = make_bundle(
        "delayed", "refund", amount=OVER,
        tracking_events=[tracking_event("in_transit", days_ago=10)],
    )
    decision = adjudicate(bundle)

    assert decision.path_id == "R-43"
    assert decision.target_status == CaseStatus.AWAITING_APPROVAL


def test_r44_delayed_without_evidence_escalates():
    decision = adjudicate(make_bundle("delayed", "refund"))

    assert decision.path_id == "R-44"
    assert decision.target_status == CaseStatus.ESCALATED_HUMAN_REQUIRED


# ===========================================================================
# exception — R-45 … R-47
# ===========================================================================
def test_r45_exception_event_under_limit():
    bundle = make_bundle(
        "exception", "refund", amount=UNDER,
        tracking_events=[tracking_event("exception", days_ago=2, location="Toledo Sort")],
    )
    decision = adjudicate(bundle)

    assert decision.path_id == "R-45"
    assert decision.target_status == CaseStatus.APPROVED_EXECUTING
    assert decision.tracking_evidence.startswith("Exception at Toledo Sort on")


def test_r46_exception_event_over_limit():
    bundle = make_bundle(
        "exception", "refund", amount=OVER,
        tracking_events=[tracking_event("exception", days_ago=2)],
    )
    decision = adjudicate(bundle)

    assert decision.path_id == "R-46"
    assert decision.target_status == CaseStatus.AWAITING_APPROVAL


def test_r47_exception_without_event_escalates():
    decision = adjudicate(make_bundle("exception", "refund"))

    assert decision.path_id == "R-47"
    assert decision.target_status == CaseStatus.ESCALATED_HUMAN_REQUIRED


# ===========================================================================
# lost — R-48 … R-52
# ===========================================================================
def test_r48_lost_replacement_infeasible():
    decision = adjudicate(make_bundle("lost", "replacement", stock_available=0))

    assert decision.path_id == "R-48"
    assert decision.invalid_reason_code == InvalidReasonCode.INSUFFICIENT_INVENTORY


def test_r49_lost_replacement_is_never_autonomous():
    decision = adjudicate(make_bundle("lost", "replacement", amount=UNDER))

    assert decision.path_id == "R-49"
    assert decision.target_status == CaseStatus.AWAITING_APPROVAL
    assert decision.resolution_type == ResolutionType.REPLACEMENT


def test_r50_lost_refund_under_limit():
    bundle = make_bundle(
        "lost", "refund", amount=UNDER,
        tracking_events=[tracking_event("lost", days_ago=2, location="Danao Transfer")],
    )
    decision = adjudicate(bundle)

    assert decision.path_id == "R-50"
    assert decision.target_status == CaseStatus.APPROVED_EXECUTING
    assert decision.tracking_evidence.startswith("Lost at Danao Transfer on")


def test_r51_lost_refund_over_limit():
    bundle = make_bundle(
        "lost", "refund", amount=OVER,
        tracking_events=[tracking_event("lost", days_ago=2)],
    )
    decision = adjudicate(bundle)

    assert decision.path_id == "R-51"
    assert decision.target_status == CaseStatus.AWAITING_APPROVAL


def test_r52_lost_without_carrier_event_escalates():
    decision = adjudicate(make_bundle("lost", "refund"))

    assert decision.path_id == "R-52"
    assert decision.target_status == CaseStatus.ESCALATED_HUMAN_REQUIRED


# ===========================================================================
# R-53 — defence in depth behind G-01
# ===========================================================================
def test_r53_unknown_subtype_reaching_routing_escalates():
    """Unreachable through adjudicate() by design — G-01 catches it first.

    This asserts the routing layer is still safe if it is ever called directly
    (as the stored-procedure wrapper could), which is the whole point of a
    defence-in-depth branch.
    """
    bundle = make_bundle("subtype_from_the_future")

    assert route(bundle, derive_facts(bundle)).path_id == "R-53"
    assert adjudicate(bundle).path_id == "G-01"
