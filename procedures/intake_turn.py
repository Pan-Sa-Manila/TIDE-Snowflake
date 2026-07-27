"""TRIAGE.INTAKE_TURN — Snowpark stored procedure wrapper.

Processes a single customer message during intake. Loads case + chat + order
snapshot, calls AI_COMPLETE with structured output for intent classification,
and returns the assistant reply.

This is a thin wrapper; business logic lives in tide_decision/.
"""

# TODO: Implement when WS-C (Agents & Orchestration) begins
#
# Signature:
#   INTAKE_TURN(session, case_id VARCHAR, message VARCHAR) -> VARIANT
#
# Steps:
#   1. Load case from TRIAGE.V_CASE_CURRENT
#   2. Load chat history from TRIAGE.CHAT
#   3. Load order snapshot from RETAIL.ORDERS + ORDER_ITEMS
#   4. Call AI_COMPLETE with structured output schema:
#      { action, subtype, followup, choices, affected_items, confidence, reply }
#   5. Enforce follow-up limit (≤ MAX_FOLLOWUP_QUESTIONS)
#   6. Insert assistant message into TRIAGE.CHAT
#   7. Insert case event (intake_classified / followup_asked)
#   8. Log to EXECUTION.PIPELINE_LOG
#   9. Return structured response for Streamlit
#
# Constraints:
#   - Read MAX_FOLLOWUP_QUESTIONS from DECISION.RULE_CONSTANTS
#   - Read model name from DECISION.RULE_CONSTANTS
#   - All SQL parameterised with bind variables
#   - Validate input with Pydantic before processing
