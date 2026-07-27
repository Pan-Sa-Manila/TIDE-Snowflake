-- ============================================================================
-- TIDE · 03_decision_ddl.sql
-- DECISION schema: rule constants, policies, reason copy, decisions
-- Idempotent: safe to re-run
-- ============================================================================

USE DATABASE TIDE;

CREATE SCHEMA IF NOT EXISTS DECISION
    COMMENT = 'Adjudicator, rule constants, policies, reason copy, decision log';

USE SCHEMA DECISION;

-- ---------------------------------------------------------------------------
-- RULE_CONSTANTS — single source of truth for business thresholds
-- Read by procedures and UI; never hardcoded elsewhere
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS RULE_CONSTANTS (
    key         VARCHAR(50)   NOT NULL,
    value       VARIANT       NOT NULL,
    description VARCHAR,
    brl_ref     VARCHAR(20),                           -- reference to DETAILS.md section

    CONSTRAINT pk_rule_constants PRIMARY KEY (key)
);

-- ---------------------------------------------------------------------------
-- POLICIES — policy documents for Cortex Search and rejection citations
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS POLICIES (
    policy_id   VARCHAR(36)   DEFAULT UUID_STRING() NOT NULL,
    slug        VARCHAR(50)   NOT NULL,
    category    VARCHAR(20)   NOT NULL,                -- store | payment | return | delivery | sla
    title       VARCHAR       NOT NULL,
    body        VARCHAR       NOT NULL,
    active      BOOLEAN       DEFAULT TRUE,

    CONSTRAINT pk_policies PRIMARY KEY (policy_id),
    CONSTRAINT uq_policies_slug UNIQUE (slug)
);

-- ---------------------------------------------------------------------------
-- REASON_COPY — customer-facing text for invalid-reason codes
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS REASON_COPY (
    invalid_reason_code VARCHAR(40)  NOT NULL,
    customer_copy       VARCHAR      NOT NULL,
    appeal_priority     VARCHAR(10)  DEFAULT 'normal',  -- high | normal

    CONSTRAINT pk_reason_copy PRIMARY KEY (invalid_reason_code)
);

-- ---------------------------------------------------------------------------
-- DECISIONS — immutable log of every adjudication decision
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS DECISIONS (
    decision_id       VARCHAR(36)   DEFAULT UUID_STRING() NOT NULL,
    case_id           VARCHAR(36)   NOT NULL,
    path_id           VARCHAR(10)   NOT NULL,           -- G-xx / R-xx
    target_status     VARCHAR(30)   NOT NULL,
    resolution_type   VARCHAR(20),                      -- refund | return | replacement | null
    eligible_amount   NUMBER(10,2),
    shipping_fee_only BOOLEAN       DEFAULT FALSE,
    invalid_reason_code VARCHAR(40),
    reason            VARCHAR,
    input_snapshot    VARIANT,                           -- full evidence bundle at decision time
    decided_at        TIMESTAMP_TZ  DEFAULT CURRENT_TIMESTAMP(),

    CONSTRAINT pk_decisions PRIMARY KEY (decision_id)
);

-- ---------------------------------------------------------------------------
-- Grants
-- ---------------------------------------------------------------------------
GRANT USAGE ON SCHEMA DECISION TO ROLE TIDE_CUSTOMER;
GRANT USAGE ON SCHEMA DECISION TO ROLE TIDE_APPROVER;
GRANT USAGE ON SCHEMA DECISION TO ROLE TIDE_ESCALATION;

GRANT SELECT ON TABLE RULE_CONSTANTS TO ROLE TIDE_CUSTOMER;
GRANT SELECT ON TABLE RULE_CONSTANTS TO ROLE TIDE_APPROVER;
GRANT SELECT ON TABLE RULE_CONSTANTS TO ROLE TIDE_ESCALATION;

GRANT SELECT ON TABLE POLICIES TO ROLE TIDE_APPROVER;
GRANT SELECT ON TABLE POLICIES TO ROLE TIDE_ESCALATION;

GRANT SELECT ON TABLE REASON_COPY TO ROLE TIDE_CUSTOMER;
