"""INVESTIGATION.ANALYZE_PROOF — Snowpark stored procedure wrapper.

Runs AI_COMPLETE vision model on uploaded proof images to extract
subtype-relevant signals (damage, wrong item, missing item, etc.).
"""

# TODO: Implement when WS-C (Agents & Orchestration) begins
#
# Signature:
#   ANALYZE_PROOF(session, case_id VARCHAR, proof_id VARCHAR) -> VARIANT
#
# Steps:
#   1. Load proof metadata from INVESTIGATION.PROOF_FILES
#   2. Read image from @INVESTIGATION.PROOF_STAGE via GET_PRESIGNED_URL
#   3. Call AI_COMPLETE with vision model + structured output schema:
#      { damage_detected, wrong_item_signals, missing_item_signals,
#        not_as_described_signals, matches_product, description, confidence }
#   4. Update PROOF_FILES.analysis and analysis_status
#   5. Insert case event (proof_analyzed)
#   6. Log to EXECUTION.PIPELINE_LOG
#
# Constraints:
#   - Read vision model name from DECISION.RULE_CONSTANTS
#   - Temperature 0, structured output with TRY_PARSE_JSON
#   - NULL parse → one retry → analysis_status='failed'
