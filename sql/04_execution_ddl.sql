-- ============================================================================
-- TIDE · 04_execution_ddl.sql
-- EXECUTION schema: resolution requests, case reports, pipeline log, streams
-- Idempotent: safe to re-run
-- ============================================================================

USE DATABASE TIDE;

CREATE SCHEMA IF NOT EXISTS EXECUTION
    COMMENT = 'Resolution requests/records, case reports, pipeline log';

USE SCHEMA EXECUTION;

-- ---------------------------------------------------------------------------
-- RESOLUTION_REQUESTS — tracks approval/execution lifecycle
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS RESOLUTION_REQUESTS (
    request_id  VARCHAR(36)   DEFAULT UUID_STRING() NOT NULL,
    case_id     VARCHAR(36)   NOT NULL,
    request_type VARCHAR(20)  NOT NULL,                -- refund | return | replacement
    status      VARCHAR(20)   DEFAULT 'pending',       -- pending | approved | rejected | executing | completed | cancelled | failed
    amount      NUMBER(10,2),
    item_ids    ARRAY,
    detail      VARIANT,                               -- replacement items, partial flags, shipping_fee_only
    decided_by  VARCHAR(100),
    created_at  TIMESTAMP_TZ  DEFAULT CURRENT_TIMESTAMP(),
    updated_at  TIMESTAMP_TZ  DEFAULT CURRENT_TIMESTAMP(),

    CONSTRAINT pk_resolution_requests PRIMARY KEY (request_id)
);

-- ---------------------------------------------------------------------------
-- CASE_REPORTS — generated on case close (one per case)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS CASE_REPORTS (
    case_id          VARCHAR(36)   NOT NULL,
    outcome_summary  VARCHAR,
    resolution_path  VARCHAR,
    rules_applied    ARRAY,
    policies_cited   ARRAY,
    sources_queried  ARRAY,
    proof_summary    VARIANT,
    timeline         VARIANT,
    generated_at     TIMESTAMP_TZ  DEFAULT CURRENT_TIMESTAMP(),

    CONSTRAINT pk_case_reports PRIMARY KEY (case_id)
);

-- ---------------------------------------------------------------------------
-- PIPELINE_LOG — every procedure/task/agent call writes one row
-- The ops debugging surface AND demo-day progress feed
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS PIPELINE_LOG (
    log_id      VARCHAR(36)   DEFAULT UUID_STRING() NOT NULL,
    case_id     VARCHAR(36),
    component   VARCHAR(50)   NOT NULL,                -- procedure/task/agent name
    status      VARCHAR(20)   NOT NULL,                -- started | completed | failed
    elapsed_ms  NUMBER,
    detail      VARIANT,
    logged_at   TIMESTAMP_TZ  DEFAULT CURRENT_TIMESTAMP(),

    CONSTRAINT pk_pipeline_log PRIMARY KEY (log_id)
);

-- ---------------------------------------------------------------------------
-- Streams — feed async tasks
-- ---------------------------------------------------------------------------

-- Stream for escalation events → triggers T_SUMMARIZE
CREATE STREAM IF NOT EXISTS S_ESCALATIONS
    ON TABLE TIDE.TRIAGE.CASE_EVENTS
    APPEND_ONLY = TRUE
    COMMENT = 'Feeds T_SUMMARIZE on escalation status changes';

-- Stream for close events → triggers T_REPORT
CREATE STREAM IF NOT EXISTS S_CLOSURES
    ON TABLE TIDE.TRIAGE.CASE_EVENTS
    APPEND_ONLY = TRUE
    COMMENT = 'Feeds T_REPORT on case close events';

-- ---------------------------------------------------------------------------
-- Grants
-- ---------------------------------------------------------------------------
GRANT USAGE ON SCHEMA EXECUTION TO ROLE TIDE_APPROVER;
GRANT USAGE ON SCHEMA EXECUTION TO ROLE TIDE_ESCALATION;
GRANT USAGE ON SCHEMA EXECUTION TO ROLE TIDE_CUSTOMER;

GRANT SELECT ON TABLE CASE_REPORTS TO ROLE TIDE_CUSTOMER;
GRANT SELECT ON TABLE RESOLUTION_REQUESTS TO ROLE TIDE_APPROVER;
GRANT SELECT ON TABLE RESOLUTION_REQUESTS TO ROLE TIDE_ESCALATION;
GRANT SELECT ON TABLE PIPELINE_LOG TO ROLE TIDE_CUSTOMER;
GRANT SELECT ON TABLE PIPELINE_LOG TO ROLE TIDE_APPROVER;
GRANT SELECT ON TABLE PIPELINE_LOG TO ROLE TIDE_ESCALATION;

-- Views, present and future. A missing view grant surfaces as "object does not
-- exist" rather than a permission error, so it fails silently and looks like a
-- deploy bug. Scoped to the roles that already hold table grants in this
-- schema; this widens nothing.
GRANT SELECT ON ALL VIEWS IN SCHEMA EXECUTION TO ROLE TIDE_CUSTOMER;
GRANT SELECT ON ALL VIEWS IN SCHEMA EXECUTION TO ROLE TIDE_APPROVER;
GRANT SELECT ON ALL VIEWS IN SCHEMA EXECUTION TO ROLE TIDE_ESCALATION;

GRANT SELECT ON FUTURE VIEWS IN SCHEMA EXECUTION TO ROLE TIDE_CUSTOMER;
GRANT SELECT ON FUTURE VIEWS IN SCHEMA EXECUTION TO ROLE TIDE_APPROVER;
GRANT SELECT ON FUTURE VIEWS IN SCHEMA EXECUTION TO ROLE TIDE_ESCALATION;
