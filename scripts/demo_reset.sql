-- ============================================================================
-- TIDE · demo_reset.sql
-- Resets the database to a pristine state for demo runs.
-- DO NOT RUN IN PRODUCTION (if this ever became production).
-- ============================================================================

USE DATABASE TIDE;

-- 1. Truncate all mutable state tables
TRUNCATE TABLE TIDE.TRIAGE.CASES;
TRUNCATE TABLE TIDE.TRIAGE.CASE_EVENTS;
TRUNCATE TABLE TIDE.TRIAGE.CHAT;
TRUNCATE TABLE TIDE.INVESTIGATION.EVIDENCE_BUNDLES;
TRUNCATE TABLE TIDE.INVESTIGATION.PROOF_FILES;
TRUNCATE TABLE TIDE.DECISION.DECISIONS;
TRUNCATE TABLE TIDE.EXECUTION.RESOLUTION_REQUESTS;
TRUNCATE TABLE TIDE.EXECUTION.CASE_REPORTS;
TRUNCATE TABLE TIDE.EXECUTION.PIPELINE_LOG;

-- 2. Reset sequences
ALTER SEQUENCE TIDE.TRIAGE.CASE_SEQ SET DATA_TYPE = NUMBER(38,0), START = 1;

-- 3. Clear proof stage
REMOVE @TIDE.INVESTIGATION.PROOF_STAGE;

-- 4. Re-seed base data (invoked via scripts/deploy.py during setup, or manually here)
-- Source: sql/seed/*.sql
