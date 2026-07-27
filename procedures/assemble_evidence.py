"""INVESTIGATION.ASSEMBLE_EVIDENCE — Snowpark stored procedure wrapper.

Invokes the Cortex Agent (INVESTIGATOR) to assemble an evidence bundle
from enterprise data sources. The agent selects tools based on dispute type.

This is a thin wrapper; the agent does the heavy lifting.
"""

# TODO: Implement when WS-C (Agents & Orchestration) begins
#
# Signature:
#   ASSEMBLE_EVIDENCE(session, case_id VARCHAR) -> VARIANT
#
# Steps:
#   1. Load case from TRIAGE.V_CASE_CURRENT
#   2. Invoke INVESTIGATOR agent via DATA_AGENT_RUN with case context
#   3. Parse agent response into evidence bundle shape (SCHEMA.md §5)
#   4. Insert bundle into INVESTIGATION.EVIDENCE_BUNDLES
#   5. Insert case event (evidence_assembled)
#   6. Log to EXECUTION.PIPELINE_LOG
#   7. Return bundle for downstream adjudication
#
# Constraints:
#   - Agent budget: 60 seconds, 24,000 tokens
#   - Failure or invalid shape: one retry, then assembly_status='failed'
#   - Failed assembly routes to escalation (adjudicator handles this)
