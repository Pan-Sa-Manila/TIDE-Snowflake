"""TRIAGE.TIMEOUT_SWEEP — Snowpark stored procedure wrapper.

Cron task (*/5 * * * *) that closes idle cases in pending_triage
that have exceeded INACTIVITY_TIMEOUT_MIN without customer activity.
"""

# TODO: Implement when WS-C (Agents & Orchestration) begins
#
# Signature:
#   TIMEOUT_SWEEP(session) -> VARIANT
#
# Steps:
#   1. Read INACTIVITY_TIMEOUT_MIN from DECISION.RULE_CONSTANTS
#   2. Query TRIAGE.V_CASE_CURRENT for cases WHERE:
#      - current_status = 'pending_triage'
#      - DATEDIFF('minute', status_changed_at, CURRENT_TIMESTAMP()) > timeout
#   3. For each stale case:
#      a. Insert status_changed event (pending_triage → closed)
#      b. Insert closed event (closed_by='timeout', close_reason='unresponsive')
#   4. Log sweep results to EXECUTION.PIPELINE_LOG
#   5. Return count of closed cases
#
# Constraints:
#   - Plain SQL, no AI needed
#   - TASK_AUTO_RETRY_ATTEMPTS = 2
#   - Runs on TIDE_WH_TASKS warehouse
