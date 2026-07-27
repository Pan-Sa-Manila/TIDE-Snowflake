-- ============================================================================
-- TIDE · 00_account.sql
-- Account-level objects: warehouses, roles, database, role hierarchy & grants
-- Idempotent: safe to re-run from zero
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
