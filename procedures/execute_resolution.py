"""EXECUTION.EXECUTE_RESOLUTION — Snowpark stored procedure wrapper.

Executes the approved resolution: creates refund/return/replacement records,
updates resolution request status, transitions case to resolved,
and generates the customer-facing resolution plan text.
"""

# TODO: Implement when WS-D (Interface) begins
#
# Signature:
#   EXECUTE_RESOLUTION(session, case_id VARCHAR, request_id VARCHAR) -> VARIANT
#
# Steps:
#   1. Load resolution request from EXECUTION.RESOLUTION_REQUESTS
#   2. Validate request status is 'approved' or 'pending' (for autonomous)
#   3. Execute: insert into RETAIL.REFUNDS / update RETAIL.STOCK etc.
#   4. Call AI_COMPLETE for customer-facing resolution plan text
#   5. Update RESOLUTION_REQUESTS.status to 'completed'
#   6. Insert case events (resolution_executed, status_changed → resolved)
#   7. Insert assistant message into TRIAGE.CHAT with resolution plan
#   8. Log to EXECUTION.PIPELINE_LOG
#
# Constraints:
#   - Validate state transition legality before writing
#   - Parameterised SQL only
