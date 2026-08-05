-- ============================================================================
-- TIDE · demo_reset.sql
-- Resets the database to a pristine demo-ready state.
--
-- Run as TIDE_ADMIN (the role used by deploy.py) against the canonical account.
-- DO NOT run against a schema that has live customer data.
--
-- Updated 2026-08-05 to cover all tables added in WS-C/D:
--   DECISION.DECISIONS, EXECUTION.RESOLUTION_REQUESTS, EXECUTION.CASE_REPORTS
--   — none of these existed in the 27 Jul original.
--
-- Usage:
--   snow sql -c tide -f scripts/demo_reset.sql
-- Then re-seed:
--   snow sql -c tide -f sql/seed/seed_retail.sql
--   snow sql -c tide -f sql/seed/seed_decision.sql
--   snow sql -c tide -f sql/seed/seed_demo_customer.sql
-- ============================================================================

USE ROLE TIDE_ADMIN;
USE DATABASE TIDE;
USE WAREHOUSE TIDE_WH_APP;

-- ---------------------------------------------------------------------------
-- 1. Truncate all mutable case-state tables (append-only in production, but
--    reset is the one legitimate TRUNCATE context for demo resets).
-- ---------------------------------------------------------------------------
TRUNCATE TABLE TIDE.TRIAGE.CASES;
TRUNCATE TABLE TIDE.TRIAGE.CASE_EVENTS;
TRUNCATE TABLE TIDE.TRIAGE.CHAT;

TRUNCATE TABLE TIDE.INVESTIGATION.EVIDENCE_BUNDLES;
TRUNCATE TABLE TIDE.INVESTIGATION.PROOF_FILES;

TRUNCATE TABLE TIDE.DECISION.DECISIONS;

TRUNCATE TABLE TIDE.EXECUTION.RESOLUTION_REQUESTS;
TRUNCATE TABLE TIDE.EXECUTION.CASE_REPORTS;
TRUNCATE TABLE TIDE.EXECUTION.PIPELINE_LOG;

-- ---------------------------------------------------------------------------
-- 2. Reset the case reference sequence back to 1.
-- ---------------------------------------------------------------------------
ALTER SEQUENCE TIDE.TRIAGE.CASE_SEQ RESTART;

-- ---------------------------------------------------------------------------
-- 3. Clear proof stage (images live on stage, not in tables).
-- ---------------------------------------------------------------------------
REMOVE @TIDE.INVESTIGATION.PROOF_STAGE;

-- ---------------------------------------------------------------------------
-- 4. Verify (optional — comment out for non-interactive runs).
-- ---------------------------------------------------------------------------
-- SELECT 'cases'              AS tbl, COUNT(*) AS rows FROM TIDE.TRIAGE.CASES
-- UNION ALL SELECT 'case_events', COUNT(*) FROM TIDE.TRIAGE.CASE_EVENTS
-- UNION ALL SELECT 'chat',        COUNT(*) FROM TIDE.TRIAGE.CHAT
-- UNION ALL SELECT 'decisions',   COUNT(*) FROM TIDE.DECISION.DECISIONS
-- UNION ALL SELECT 'requests',    COUNT(*) FROM TIDE.EXECUTION.RESOLUTION_REQUESTS
-- UNION ALL SELECT 'pipeline',    COUNT(*) FROM TIDE.EXECUTION.PIPELINE_LOG;
