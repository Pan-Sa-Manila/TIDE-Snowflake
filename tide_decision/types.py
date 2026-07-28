"""Core types for the TIDE decision engine.

All enums, dataclasses, and constants live here.
No Snowflake imports. No external dependencies beyond the stdlib.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


# ---------------------------------------------------------------------------
# Case status lifecycle (9 states) — DETAILS.md §8
# ---------------------------------------------------------------------------
class CaseStatus(str, Enum):
    PENDING_TRIAGE = "pending_triage"
    AWAITING_CUSTOMER_PROOF = "awaiting_customer_proof"
    AWAITING_CUSTOMER_DECISION = "awaiting_customer_decision"
    AWAITING_APPROVAL = "awaiting_approval"
    APPROVED_EXECUTING = "approved_executing"
    REJECTED_HUMAN_REQUIRED = "rejected_human_required"
    ESCALATED_HUMAN_REQUIRED = "escalated_human_required"
    RESOLVED = "resolved"
    CLOSED = "closed"


# ---------------------------------------------------------------------------
# Dispute types
# ---------------------------------------------------------------------------
class DisputeType(str, Enum):
    REFUND = "refund"
    DELIVERY = "delivery"


# ---------------------------------------------------------------------------
# 12 canonical subtypes — DETAILS.md §7.1
# ---------------------------------------------------------------------------
class DisputeSubtype(str, Enum):
    DUPLICATE_CHARGE = "duplicate_charge"
    NOT_AS_DESCRIBED = "not_as_described"
    DAMAGED_GOODS = "damaged_goods"
    WRONG_ITEM = "wrong_item"
    PARTIAL_FULFILLMENT = "partial_fulfillment"
    RETURN_REQUEST = "return_request"
    CHANGED_MIND = "changed_mind"
    OTHER = "other"
    NON_RECEIPT = "non_receipt"
    DELAYED = "delayed"
    EXCEPTION = "exception"
    LOST = "lost"


# ---------------------------------------------------------------------------
# Resolution types
# ---------------------------------------------------------------------------
class ResolutionType(str, Enum):
    REFUND = "refund"
    REPLACEMENT = "replacement"
    RETURN = "return"


# ---------------------------------------------------------------------------
# Invalid reason codes — DETAILS.md §12 (closed set)
# ---------------------------------------------------------------------------
class InvalidReasonCode(str, Enum):
    INSUFFICIENT_PROOF = "insufficient_proof"
    PROOF_CONTRADICTS_CLAIM = "proof_contradicts_claim"
    OUTSIDE_RETURN_WINDOW = "outside_return_window"
    NON_RETURNABLE_ITEM = "non_returnable_item"
    INSUFFICIENT_INVENTORY = "insufficient_inventory"
    UNSUPPORTED_RESOLUTION_TYPE = "unsupported_resolution_type"
    DUPLICATE_CASE = "duplicate_case"
    ORDER_NOT_FOUND = "order_not_found"
    INELIGIBLE_ORDER_STATE = "ineligible_order_state"
    POLICY_EXCLUSION = "policy_exclusion"


# ---------------------------------------------------------------------------
# Subtype metadata — DETAILS.md §7.1
# ---------------------------------------------------------------------------
# Maps subtype → (dispute_type, proof_required, allowed_resolutions, default_resolution)
SUBTYPE_META: dict[str, dict] = {
    "duplicate_charge":    {"type": "refund",   "proof": False, "allowed": ["refund"],                "default": "refund"},
    "not_as_described":    {"type": "refund",   "proof": True,  "allowed": ["refund", "replacement"], "default": "refund"},
    "damaged_goods":       {"type": "refund",   "proof": True,  "allowed": ["refund", "replacement"], "default": "refund"},
    "wrong_item":          {"type": "refund",   "proof": True,  "allowed": ["refund", "replacement"], "default": "refund"},
    "partial_fulfillment": {"type": "refund",   "proof": True,  "allowed": ["refund"],                "default": "refund"},
    "return_request":      {"type": "refund",   "proof": False, "allowed": ["return"],                "default": "return"},
    "changed_mind":        {"type": "refund",   "proof": False, "allowed": ["return"],                "default": "return"},
    "other":               {"type": "refund",   "proof": False, "allowed": ["refund"],                "default": "refund"},
    "non_receipt":         {"type": "delivery", "proof": False, "allowed": ["refund", "replacement"], "default": "refund"},
    "delayed":             {"type": "delivery", "proof": False, "allowed": ["refund"],                "default": "refund"},
    "exception":           {"type": "delivery", "proof": False, "allowed": ["refund"],                "default": "refund"},
    "lost":                {"type": "delivery", "proof": False, "allowed": ["refund", "replacement"], "default": "refund"},
}

# Intake aliases — DETAILS.md §7.2
INTAKE_ALIASES: dict[str, str] = {
    "package_never_arrived": "non_receipt",
    "delivery_late": "delayed",
    "wrong_delivery_address": "exception",
    "quality_issue": "not_as_described",
    "return_for_refund": "return_request",
}

# Which proof signal is relevant to which subtype — DETAILS.md §9
# (`proof_supports` / `proof_contradicts` are "the subtype-relevant signal")
PROOF_SIGNAL_BY_SUBTYPE: dict[str, str] = {
    "damaged_goods": "damage_detected",
    "wrong_item": "wrong_item_signals",
    "not_as_described": "not_as_described_signals",
    "partial_fulfillment": "missing_item_signals",
}


# ---------------------------------------------------------------------------
# Business constants — DETAILS.md §6
# ---------------------------------------------------------------------------
# Mirrored in DECISION.RULE_CONSTANTS. At runtime the stored procedure reads
# that table and passes the values in; these are the documented defaults so the
# engine stays runnable (and testable) without a database. Nothing else in the
# engine may hardcode a threshold — read it through `constant()`.
DEFAULT_CONSTANTS: dict[str, object] = {
    "AUTONOMOUS_LIMIT_USD": 50.00,
    "RETURN_WINDOW_DAYS": 7,
    "DELIVERY_SLA_BREACH_DAYS": 3,
    "STALE_TRANSIT_DAYS": 7,
    "INACTIVITY_TIMEOUT_MIN": 15,
    "MIN_REJECTION_CHARS": 50,
    "MIN_REJECTION_CITATIONS": 1,
    "MAX_PROOF_UPLOADS": 2,
    "MAX_PROOF_BYTES": 5 * 1024 * 1024,
    "MAX_FOLLOWUP_QUESTIONS": 3,
    "CURRENCY": "USD",
}


def constant(key: str, constants: Optional[dict] = None):
    """Read a business constant, preferring a caller-supplied override.

    Raises KeyError for an unknown key — a typo'd threshold must fail loudly
    rather than silently defaulting to zero.
    """
    if constants and constants.get(key) is not None:
        return constants[key]
    return DEFAULT_CONSTANTS[key]


def resolve_type(preference: str, subtype: str) -> str:
    """Resolve the effective resolution type — DETAILS.md §7.3.

    Customer preference if allowed for the subtype; else the subtype default.
    A preference outside the allowed set does **not** silently downgrade here —
    G-02 fires first, on the raw preference, before this is ever consulted.
    """
    meta = SUBTYPE_META.get(subtype)
    if not meta:
        return preference or "refund"
    if preference in meta["allowed"]:
        return preference
    return meta["default"]


# ---------------------------------------------------------------------------
# Path IDs — complete enumeration per DETAILS.md §13
# ---------------------------------------------------------------------------
GUARDRAIL_PATH_IDS = [f"G-{i:02d}" for i in range(1, 10)]  # G-01..G-09

ROUTING_PATH_IDS = [f"R-{i:02d}" for i in range(1, 54)]     # R-01..R-53

ALL_PATH_IDS = GUARDRAIL_PATH_IDS + ROUTING_PATH_IDS         # 62 total


# ---------------------------------------------------------------------------
# Decision — the output of adjudicate()
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Decision:
    """Immutable decision returned by the adjudication engine."""

    path_id: str                                        # G-xx or R-xx
    target_status: CaseStatus
    resolution_type: Optional[ResolutionType] = None
    eligible_amount: float = 0.0
    shipping_fee_only: bool = False
    invalid_reason_code: Optional[InvalidReasonCode] = None
    reason: str = ""
    tracking_evidence: Optional[str] = None             # e.g. "Delivered at <loc> on <time>"
    replacement_items: list = field(default_factory=list)
    affected_item_ids: list = field(default_factory=list)


# ---------------------------------------------------------------------------
# Derived facts — intermediate computation between bundle and decision
# ---------------------------------------------------------------------------
@dataclass
class DerivedFacts:
    """Facts derived from the evidence bundle — input to guardrails and routing."""

    payment_confirmed: bool = False
    order_returnable: bool = False
    total_order_amount: float = 0.0
    affected_amount: float = 0.0
    replacement_amount: float = 0.0
    shipping_fee: float = 0.0
    window_basis_date: Optional[str] = None
    within_return_window: bool = False
    delivered_event: Optional[dict] = None
    lost_event: Optional[dict] = None
    exception_event: Optional[dict] = None
    in_transit_event: Optional[dict] = None
    stale_in_transit: bool = False
    sla_breached: bool = False
    inventory_feasible: bool = False
    inventory_block_reason: str = ""
    prior_refund_count: int = 0
    prior_refund_total: float = 0.0
    proof_present: bool = False
    proof_supports: bool = False
    proof_contradicts: bool = False
    proof_analysis_failed: bool = False
