"""Tests for decision engine guardrails (G-01 through G-09)."""

from tide_decision import adjudicate
from tide_decision.types import CaseStatus, InvalidReasonCode

def test_g01_unknown_subtype():
    """G-01: Unknown dispute subtype routes to escalation."""
    bundle = {
        "dispute_subtype": "random_nonsense",
        "resolution_preference": "refund",
    }
    decision = adjudicate(bundle)
    
    assert decision.path_id == "G-01"
    assert decision.target_status == CaseStatus.ESCALATED_HUMAN_REQUIRED
    assert "Unknown dispute subtype" in decision.reason

# TODO: WS-B — implement tests for G-02 through G-09
