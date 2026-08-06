-- ============================================================================
-- TIDE · 12_streams_tasks.sql
-- The asynchronous half of the architecture (TASKS.md C-3).
--
-- ARCHITECTURE.md §6.2: only genuinely detached work is a task. Triggered tasks
-- have a ~30 second floor, which is unusable inside a chat turn — that latency
-- constraint is what drew the sync/async line, not preference. Everything a
-- person waits on stays a synchronous procedure call.
--
--   S_ESCALATIONS -> T_SUMMARIZE  writes the specialist handoff summary
--   S_CLOSURES    -> T_REPORT     writes the final case report
--   T_TIMEOUT_SWEEP (cron)        closes cases idle in pending_triage
--
-- The streams already exist (04_execution_ddl.sql). They are APPEND_ONLY over
-- CASE_EVENTS, which is safe because that table is append-only by rule.
--
-- Tasks are created SUSPENDED by Snowflake and resumed at the bottom of this
-- file. Serverless, with TASK_AUTO_RETRY_ATTEMPTS = 2 per SCHEMA.md §8.
--
-- Idempotent: safe to re-run
-- ============================================================================

USE DATABASE TIDE;
USE SCHEMA EXECUTION;

-- ---------------------------------------------------------------------------
-- The stream consumers.
--
-- The work lives in procedures and the tasks are one-line CALLs. A task body
-- containing a Snowflake Scripting block is not dollar-quoted, so the CLI's
-- statement splitter cuts it at the first internal semicolon and the file fails
-- to deploy. Procedures are dollar-quoted and immune.
--
-- Each consumer drains its stream into a temp table first. Reading a stream in
-- a DML statement is what advances its offset — without that the task re-fires
-- on the same events forever, including events its filter does not even match.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE PROCEDURE RUN_SUMMARIZE_STREAM()
RETURNS VARIANT
LANGUAGE SQL
COMMENT = 'Internal. Drain S_ESCALATIONS and summarise every case that entered escalation.'
EXECUTE AS OWNER
AS
$$
DECLARE
    done NUMBER DEFAULT 0;
    res  VARIANT;
    -- A cursor field cannot be passed straight into CALL: `rec.case_id`
    -- fails to resolve there with `invalid identifier 'REC.CASE_ID'`,
    -- even though the same reference works in an expression. Assign it to
    -- a declared variable and bind that instead.
    cid  VARCHAR;
    c CURSOR FOR
        SELECT DISTINCT d.case_id AS case_id FROM DRAINED d
        WHERE d.event_type = 'status_changed'
          AND d.payload['to']::VARCHAR = 'escalated_human_required';
    err VARCHAR;
BEGIN
    CREATE OR REPLACE TEMPORARY TABLE DRAINED AS
        SELECT s.case_id, s.event_type, s.payload FROM TIDE.EXECUTION.S_ESCALATIONS s;

    FOR rec IN c DO
        cid := rec.case_id;
        CALL TIDE.EXECUTION.SUMMARIZE_ESCALATION(:cid) INTO :res;
        done := done + 1;
    END FOR;

    RETURN OBJECT_CONSTRUCT('success', TRUE, 'summarized', :done);
EXCEPTION
    WHEN OTHER THEN
        err := SQLERRM;
        INSERT INTO TIDE.EXECUTION.PIPELINE_LOG (case_id, component, status, detail)
        SELECT NULL, 'T_SUMMARIZE', 'failed', OBJECT_CONSTRUCT('error', :err);
        RETURN OBJECT_CONSTRUCT('success', FALSE, 'error', :err);
END;
$$;

CREATE OR REPLACE PROCEDURE RUN_REPORT_STREAM()
RETURNS VARIANT
LANGUAGE SQL
COMMENT = 'Internal. Drain S_CLOSURES and write the final report for every closed case.'
EXECUTE AS OWNER
AS
$$
DECLARE
    done NUMBER DEFAULT 0;
    res  VARIANT;
    -- A cursor field cannot be passed straight into CALL: `rec.case_id`
    -- fails to resolve there with `invalid identifier 'REC.CASE_ID'`,
    -- even though the same reference works in an expression. Assign it to
    -- a declared variable and bind that instead.
    cid  VARCHAR;
    c CURSOR FOR
        SELECT DISTINCT d.case_id AS case_id FROM DRAINED d WHERE d.event_type = 'closed';
    err VARCHAR;
BEGIN
    CREATE OR REPLACE TEMPORARY TABLE DRAINED AS
        SELECT s.case_id, s.event_type FROM TIDE.EXECUTION.S_CLOSURES s;

    FOR rec IN c DO
        cid := rec.case_id;
        CALL TIDE.EXECUTION.GENERATE_REPORT(:cid) INTO :res;
        done := done + 1;
    END FOR;

    RETURN OBJECT_CONSTRUCT('success', TRUE, 'reported', :done);
EXCEPTION
    WHEN OTHER THEN
        err := SQLERRM;
        INSERT INTO TIDE.EXECUTION.PIPELINE_LOG (case_id, component, status, detail)
        SELECT NULL, 'T_REPORT', 'failed', OBJECT_CONSTRUCT('error', :err);
        RETURN OBJECT_CONSTRUCT('success', FALSE, 'error', :err);
END;
$$;

-- TARGET_COMPLETION_INTERVAL is mandatory on a serverless triggered task —
-- it will not resume without one. Five minutes is well inside what a human
-- handoff tolerates, and nobody is watching this in real time by design.
CREATE OR REPLACE TASK T_SUMMARIZE
    USER_TASK_MANAGED_INITIAL_WAREHOUSE_SIZE = 'XSMALL'
    TARGET_COMPLETION_INTERVAL = '5 MINUTES'
    TASK_AUTO_RETRY_ATTEMPTS = 2
    COMMENT = 'On escalation, generate the specialist handoff summary'
    WHEN SYSTEM$STREAM_HAS_DATA('TIDE.EXECUTION.S_ESCALATIONS')
AS
    CALL TIDE.EXECUTION.RUN_SUMMARIZE_STREAM();

CREATE OR REPLACE TASK T_REPORT
    USER_TASK_MANAGED_INITIAL_WAREHOUSE_SIZE = 'XSMALL'
    TARGET_COMPLETION_INTERVAL = '5 MINUTES'
    TASK_AUTO_RETRY_ATTEMPTS = 2
    COMMENT = 'On case close, generate the final case report'
    WHEN SYSTEM$STREAM_HAS_DATA('TIDE.EXECUTION.S_CLOSURES')
AS
    CALL TIDE.EXECUTION.RUN_REPORT_STREAM();

USE SCHEMA TRIAGE;

-- ---------------------------------------------------------------------------
-- TIMEOUT_SWEEP — close cases the customer walked away from.
--
-- DETAILS.md §14: idle in pending_triage beyond INACTIVITY_TIMEOUT_MIN closes
-- with closed_by = timeout, close_reason = unresponsive. Idle is measured from
-- the last activity on the case, not from creation, so a customer mid-
-- conversation is never swept.
--
-- Goes through CLOSE_CASE like every other closure, so the state machine is
-- enforced in one place and the sweep leaves the same audit trail a human would.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE PROCEDURE TIMEOUT_SWEEP()
RETURNS VARIANT
LANGUAGE SQL
COMMENT = 'Close cases idle in pending_triage beyond INACTIVITY_TIMEOUT_MIN, per DETAILS.md section 14. Returns the number swept.'
EXECUTE AS OWNER
AS
$$
DECLARE
    idle_min NUMBER;
    swept    NUMBER DEFAULT 0;
    res      VARIANT;
    -- The threshold is read inside the cursor query rather than bound in: a
    -- FOR loop takes no USING clause. Still sourced from RULE_CONSTANTS, so
    -- nothing here hardcodes a business constant.
    c CURSOR FOR
        SELECT v.case_id AS case_id
        FROM TIDE.TRIAGE.V_CASE_CURRENT v
        WHERE v.current_status = 'pending_triage'
          AND DATEDIFF('minute',
                COALESCE(
                    (SELECT MAX(e.occurred_at) FROM TIDE.TRIAGE.CASE_EVENTS e
                      WHERE e.case_id = v.case_id),
                    v.created_at),
                CURRENT_TIMESTAMP())
              > (SELECT rk.value::NUMBER FROM TIDE.DECISION.RULE_CONSTANTS rk
                  WHERE rk.key = 'INACTIVITY_TIMEOUT_MIN');
    err VARCHAR;
BEGIN
    SELECT rk.value::NUMBER INTO :idle_min
    FROM TIDE.DECISION.RULE_CONSTANTS rk WHERE rk.key = 'INACTIVITY_TIMEOUT_MIN';

    FOR rec IN c DO
        CALL TIDE.TRIAGE.CLOSE_CASE(rec.case_id, 'timeout', 'unresponsive') INTO :res;
        swept := swept + 1;
    END FOR;

    INSERT INTO TIDE.EXECUTION.PIPELINE_LOG (case_id, component, status, detail)
    SELECT NULL, 'T_TIMEOUT_SWEEP', 'completed',
           OBJECT_CONSTRUCT('swept', :swept, 'idle_minutes', :idle_min);

    RETURN OBJECT_CONSTRUCT('success', TRUE, 'swept', :swept);
EXCEPTION
    WHEN OTHER THEN
        err := SQLERRM;
        INSERT INTO TIDE.EXECUTION.PIPELINE_LOG (case_id, component, status, detail)
        SELECT NULL, 'T_TIMEOUT_SWEEP', 'failed', OBJECT_CONSTRUCT('error', :err);
        RETURN OBJECT_CONSTRUCT('success', FALSE, 'error', :err);
END;
$$;

CREATE OR REPLACE TASK T_TIMEOUT_SWEEP
    USER_TASK_MANAGED_INITIAL_WAREHOUSE_SIZE = 'XSMALL'
    TASK_AUTO_RETRY_ATTEMPTS = 2
    SCHEDULE = 'USING CRON */5 * * * * UTC'
    COMMENT = 'Every 5 minutes, close idle pending_triage cases (DETAILS.md section 14)'
AS
    CALL TIDE.TRIAGE.TIMEOUT_SWEEP();

-- ---------------------------------------------------------------------------
-- Resume. Tasks are created suspended; nothing runs until this.
--
-- Cost note: the sweeper wakes every 5 minutes. Suspend it between demo runs
-- with  ALTER TASK TIDE.TRIAGE.T_TIMEOUT_SWEEP SUSPEND;
-- ---------------------------------------------------------------------------
ALTER TASK TIDE.EXECUTION.T_SUMMARIZE     RESUME;
ALTER TASK TIDE.EXECUTION.T_REPORT        RESUME;
ALTER TASK TIDE.TRIAGE.T_TIMEOUT_SWEEP    RESUME;

GRANT USAGE ON PROCEDURE TIDE.TRIAGE.TIMEOUT_SWEEP() TO ROLE TIDE_ADMIN;
