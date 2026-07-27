"""Tests for decision engine routing (R-01 through R-53)."""

from tide_decision import adjudicate
from tide_decision.types import CaseStatus, ResolutionType

def test_r01_duplicate_charge_autonomous():
    """R-01: Duplicate charge ≤ autonomous limit is auto-approved."""
    bundle = {
        "dispute_subtype": "duplicate_charge",
        "resolution_preference": "refund",
        "order": {"total_amount": 40.00},
        "payment": {"status": "confirmed"},
    }
    decision = adjudicate(bundle, constants={"AUTONOMOUS_LIMIT_USD": 50.00})
    
    assert decision.path_id == "R-01"
    assert decision.target_status == CaseStatus.APPROVED_EXECUTING
    assert decision.resolution_type == ResolutionType.REFUND
    assert decision.eligible_amount == 40.00

# TODO: WS-B — implement tests for R-02 through R-53
