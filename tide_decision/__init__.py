"""TIDE Decision Engine — pure Python, zero Snowflake imports.

This package implements the deterministic adjudication logic for TIDE.
It receives a plain-dict evidence bundle and returns a Decision.

No LLM. No database. No network. Testable locally with pytest.
"""

from tide_decision.adjudicate import adjudicate
from tide_decision.types import Decision, CaseStatus, DisputeSubtype, ResolutionType

__all__ = ["adjudicate", "Decision", "CaseStatus", "DisputeSubtype", "ResolutionType"]
