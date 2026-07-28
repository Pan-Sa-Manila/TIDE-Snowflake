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
