-- ============================================================================
-- TIDE · 00_account.sql
-- Account-level objects: warehouses, roles, database, role hierarchy & grants
-- Idempotent: safe to re-run from zero
--
-- REQUIRES: ACCOUNTADMIN
-- Warehouses and roles are account-level objects, so this file cannot run as
-- TIDE_ADMIN. scripts/deploy.py detects the marker above and passes
-- --role ACCOUNTADMIN for this file only; every later file runs under the
-- connection's own role so TIDE_ADMIN owns the schema objects it creates.
-- ============================================================================

-- ---------------------------------------------------------------------------
-- Warehouses
-- ---------------------------------------------------------------------------
CREATE WAREHOUSE IF NOT EXISTS TIDE_WH_APP
    WAREHOUSE_SIZE = 'XSMALL'
    AUTO_SUSPEND = 300
    AUTO_RESUME = TRUE
    INITIALLY_SUSPENDED = TRUE
    COMMENT = 'TIDE interactive workloads (Streamlit, procedures)';

CREATE WAREHOUSE IF NOT EXISTS TIDE_WH_TASKS
    WAREHOUSE_SIZE = 'XSMALL'
    AUTO_SUSPEND = 60
    AUTO_RESUME = TRUE
    INITIALLY_SUSPENDED = TRUE
    COMMENT = 'TIDE async tasks (summariser, reporter, sweeper)';

-- ---------------------------------------------------------------------------
-- Database
-- ---------------------------------------------------------------------------
CREATE DATABASE IF NOT EXISTS TIDE
    COMMENT = 'TIDE — Triage · Investigation · Decision · Execution';

-- ---------------------------------------------------------------------------
-- Roles
-- ---------------------------------------------------------------------------
CREATE ROLE IF NOT EXISTS TIDE_ADMIN
    COMMENT = 'Owns TIDE objects, deploys';

CREATE ROLE IF NOT EXISTS TIDE_CUSTOMER
    COMMENT = 'Customer persona — intake, upload, close, appeal';

CREATE ROLE IF NOT EXISTS TIDE_APPROVER
    COMMENT = 'Approver persona — queue review, approve/reject';

CREATE ROLE IF NOT EXISTS TIDE_ESCALATION
    COMMENT = 'Escalation persona — claim, chat, manual actions';

-- ---------------------------------------------------------------------------
-- Role hierarchy: all persona roles inherit from TIDE_ADMIN
-- TIDE_ADMIN inherits from SYSADMIN (standard Snowflake practice)
-- ---------------------------------------------------------------------------
GRANT ROLE TIDE_CUSTOMER   TO ROLE TIDE_ADMIN;
GRANT ROLE TIDE_APPROVER   TO ROLE TIDE_ADMIN;
GRANT ROLE TIDE_ESCALATION TO ROLE TIDE_ADMIN;
GRANT ROLE TIDE_ADMIN      TO ROLE SYSADMIN;

-- ---------------------------------------------------------------------------
-- Database grants
-- ---------------------------------------------------------------------------
-- TIDE_ADMIN needs database-level ALL: each DDL file opens with
-- CREATE SCHEMA IF NOT EXISTS, and Snowflake checks the privilege before the
-- IF NOT EXISTS short-circuits, so USAGE alone fails even when the schema
-- already exists.
GRANT ALL PRIVILEGES ON DATABASE TIDE TO ROLE TIDE_ADMIN;
GRANT USAGE ON DATABASE TIDE TO ROLE TIDE_ADMIN;
GRANT USAGE ON DATABASE TIDE TO ROLE TIDE_CUSTOMER;
GRANT USAGE ON DATABASE TIDE TO ROLE TIDE_APPROVER;
GRANT USAGE ON DATABASE TIDE TO ROLE TIDE_ESCALATION;

-- ---------------------------------------------------------------------------
-- Warehouse grants
-- ---------------------------------------------------------------------------
GRANT USAGE ON WAREHOUSE TIDE_WH_APP TO ROLE TIDE_ADMIN;
GRANT USAGE ON WAREHOUSE TIDE_WH_APP TO ROLE TIDE_CUSTOMER;
GRANT USAGE ON WAREHOUSE TIDE_WH_APP TO ROLE TIDE_APPROVER;
GRANT USAGE ON WAREHOUSE TIDE_WH_APP TO ROLE TIDE_ESCALATION;

GRANT USAGE ON WAREHOUSE TIDE_WH_TASKS TO ROLE TIDE_ADMIN;

-- ---------------------------------------------------------------------------
-- Build privileges for TIDE_ADMIN
--
-- TIDE_ADMIN owns and deploys every object (ARCHITECTURE.md §4). Schema-level
-- USAGE alone is not enough: the newer Cortex object types need their own
-- CREATE privilege, and without them a deploy run as TIDE_ADMIN fails with
-- "Insufficient privileges to operate on schema" even though the account has
-- the Cortex entitlement. Verified on the canonical account: CREATE AGENT was
-- the first to fail.
--
-- Granted per schema rather than via a database-wide FUTURE grant so the set
-- stays explicit and greppable.
-- ---------------------------------------------------------------------------
GRANT ALL PRIVILEGES ON SCHEMA TIDE.TRIAGE        TO ROLE TIDE_ADMIN;
GRANT ALL PRIVILEGES ON SCHEMA TIDE.INVESTIGATION TO ROLE TIDE_ADMIN;
GRANT ALL PRIVILEGES ON SCHEMA TIDE.DECISION      TO ROLE TIDE_ADMIN;
GRANT ALL PRIVILEGES ON SCHEMA TIDE.EXECUTION     TO ROLE TIDE_ADMIN;
GRANT ALL PRIVILEGES ON SCHEMA TIDE.RETAIL        TO ROLE TIDE_ADMIN;

-- Cortex object types, called out explicitly: ALL PRIVILEGES covers these on
-- current Snowflake versions, but naming them documents the dependency and
-- keeps the file honest if ALL ever stops including a newer object type.
GRANT CREATE AGENT                 ON SCHEMA TIDE.INVESTIGATION TO ROLE TIDE_ADMIN;
GRANT CREATE CORTEX SEARCH SERVICE ON SCHEMA TIDE.DECISION      TO ROLE TIDE_ADMIN;
GRANT CREATE SEMANTIC VIEW         ON SCHEMA TIDE.RETAIL        TO ROLE TIDE_ADMIN;

-- ---------------------------------------------------------------------------
-- Table privileges for TIDE_ADMIN.
--
-- ALL PRIVILEGES on a schema does NOT cascade to the tables in it. The
-- lifecycle procedures are EXECUTE AS OWNER, so every INSERT they make runs as
-- TIDE_ADMIN and fails with "Insufficient privileges to operate on table"
-- without this. First seen on EXECUTION.PIPELINE_LOG.
--
-- Both forms are needed and neither is redundant: FUTURE covers a deploy on a
-- fresh account where the tables do not exist yet when this file runs, ALL
-- covers every account where they already do. deploy.py re-runs this file on
-- every deploy, so the pair converges either way.
-- ---------------------------------------------------------------------------
GRANT ALL PRIVILEGES ON FUTURE TABLES IN SCHEMA TIDE.TRIAGE        TO ROLE TIDE_ADMIN;
GRANT ALL PRIVILEGES ON FUTURE TABLES IN SCHEMA TIDE.INVESTIGATION TO ROLE TIDE_ADMIN;
GRANT ALL PRIVILEGES ON FUTURE TABLES IN SCHEMA TIDE.DECISION      TO ROLE TIDE_ADMIN;
GRANT ALL PRIVILEGES ON FUTURE TABLES IN SCHEMA TIDE.EXECUTION     TO ROLE TIDE_ADMIN;
GRANT ALL PRIVILEGES ON FUTURE TABLES IN SCHEMA TIDE.RETAIL        TO ROLE TIDE_ADMIN;

GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA TIDE.TRIAGE        TO ROLE TIDE_ADMIN;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA TIDE.INVESTIGATION TO ROLE TIDE_ADMIN;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA TIDE.DECISION      TO ROLE TIDE_ADMIN;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA TIDE.EXECUTION     TO ROLE TIDE_ADMIN;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA TIDE.RETAIL        TO ROLE TIDE_ADMIN;

-- Views and the proof stage, same reasoning.
GRANT SELECT ON ALL VIEWS    IN SCHEMA TIDE.TRIAGE TO ROLE TIDE_ADMIN;
GRANT SELECT ON FUTURE VIEWS IN SCHEMA TIDE.TRIAGE TO ROLE TIDE_ADMIN;
GRANT READ, WRITE ON ALL STAGES    IN SCHEMA TIDE.INVESTIGATION TO ROLE TIDE_ADMIN;
GRANT READ, WRITE ON FUTURE STAGES IN SCHEMA TIDE.INVESTIGATION TO ROLE TIDE_ADMIN;

-- Sequences. CASE_SEQ produces the TIDE-%05d reference number in OPEN_CASE.
-- Without USAGE, Snowflake reports the sequence as
-- "invalid identifier 'TIDE.TRIAGE.CASE_SEQ.NEXTVAL'" rather than as a
-- permission error, which reads like a syntax problem and sends you looking in
-- the wrong place.
GRANT USAGE ON ALL SEQUENCES    IN SCHEMA TIDE.TRIAGE TO ROLE TIDE_ADMIN;
GRANT USAGE ON FUTURE SEQUENCES IN SCHEMA TIDE.TRIAGE TO ROLE TIDE_ADMIN;

-- ---------------------------------------------------------------------------
-- Task execution
--
-- Serverless tasks need EXECUTE MANAGED TASK on the *owner* role; the ordinary
-- EXECUTE TASK privilege is not enough and is not implied by ownership.
--
-- Without this the tasks are created and resumed happily and then fail on every
-- single run with
--
--   091089: Cannot execute task, EXECUTE MANAGED TASK privilege must be granted
--
-- until Snowflake auto-suspends them after ten consecutive failures. Nothing in
-- the deploy output says so, because the failure happens later, on the task's
-- own schedule. That is exactly what happened here: T_SUMMARIZE and T_REPORT
-- sat suspended and the whole asynchronous half of the system — escalation
-- summaries, case reports, timeout sweeping — silently never ran.
--
-- Check with:
--   SELECT name, state, error_message FROM TABLE(
--     INFORMATION_SCHEMA.TASK_HISTORY(SCHEDULED_TIME_RANGE_START =>
--       DATEADD('hour', -24, CURRENT_TIMESTAMP())));
-- ---------------------------------------------------------------------------
GRANT EXECUTE TASK         ON ACCOUNT TO ROLE TIDE_ADMIN;
GRANT EXECUTE MANAGED TASK ON ACCOUNT TO ROLE TIDE_ADMIN;

-- ---------------------------------------------------------------------------
-- Streams
--
-- Streams need their own ON ALL and ON FUTURE grant, exactly like tables,
-- views, stages and sequences. They were the one object type missing from that
-- list, and the tasks are owned by TIDE_ADMIN while the streams were created
-- under ACCOUNTADMIN — so the task could not see them.
--
-- The symptom is the trap this project keeps meeting: a missing grant does not
-- say "permission denied". It says
--
--   Invalid value ['TIDE.EXECUTION.S_ESCALATIONS'] for function
--   'SYSTEM$STREAM_HAS_DATA', parameter 1: must be a valid stream name
--
-- which reads as a typo in the stream name. The stream existed, was not stale,
-- and was named correctly. Suspect grants before syntax.
-- ---------------------------------------------------------------------------
GRANT SELECT ON ALL STREAMS    IN SCHEMA TIDE.EXECUTION TO ROLE TIDE_ADMIN;
GRANT SELECT ON FUTURE STREAMS IN SCHEMA TIDE.EXECUTION TO ROLE TIDE_ADMIN;
GRANT SELECT ON ALL STREAMS    IN SCHEMA TIDE.TRIAGE    TO ROLE TIDE_ADMIN;
GRANT SELECT ON FUTURE STREAMS IN SCHEMA TIDE.TRIAGE    TO ROLE TIDE_ADMIN;
