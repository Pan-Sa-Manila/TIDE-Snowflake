-- ============================================================================
-- TIDE · 02_investigation_ddl.sql
-- INVESTIGATION schema: evidence bundles, proof files, proof stage
-- Idempotent: safe to re-run
-- ============================================================================

USE DATABASE TIDE;

CREATE SCHEMA IF NOT EXISTS INVESTIGATION
    COMMENT = 'Evidence bundles, proof files + stage, investigator agent, vision';

USE SCHEMA INVESTIGATION;

-- ---------------------------------------------------------------------------
-- EVIDENCE_BUNDLES — one row per assembly attempt; latest wins
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS EVIDENCE_BUNDLES (
    bundle_id       VARCHAR(36)   DEFAULT UUID_STRING() NOT NULL,
    case_id         VARCHAR(36)   NOT NULL,
    assembly_status VARCHAR(20)   NOT NULL,             -- complete | partial | failed
    bundle          VARIANT       NOT NULL,             -- structured evidence (see SCHEMA.md §5)
    sources_queried ARRAY,
    agent_citations VARIANT,
    assembled_at    TIMESTAMP_TZ  DEFAULT CURRENT_TIMESTAMP(),

    CONSTRAINT pk_evidence_bundles PRIMARY KEY (bundle_id)
);

-- ---------------------------------------------------------------------------
-- PROOF_FILES — metadata for uploaded proof images (bytes on stage, not here)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS PROOF_FILES (
    proof_id        VARCHAR(36)   DEFAULT UUID_STRING() NOT NULL,
    case_id         VARCHAR(36)   NOT NULL,
    relative_path   VARCHAR       NOT NULL,             -- <case_id>/<uuid>.<ext>
    content_type    VARCHAR(20)   NOT NULL,             -- image/jpeg | image/png | image/webp
    byte_size       NUMBER        NOT NULL,
    sha256          VARCHAR(64)   NOT NULL,
    width           NUMBER,
    height          NUMBER,
    analysis        VARIANT,                            -- vision model output
    analysis_status VARCHAR(20)   DEFAULT 'pending',    -- pending | completed | failed
    uploaded_at     TIMESTAMP_TZ  DEFAULT CURRENT_TIMESTAMP(),

    CONSTRAINT pk_proof_files PRIMARY KEY (proof_id)
);

-- ---------------------------------------------------------------------------
-- PROOF_STAGE — internal stage for proof images
-- SNOWFLAKE_SSE encryption, directory table enabled for listing
-- ---------------------------------------------------------------------------
CREATE STAGE IF NOT EXISTS PROOF_STAGE
    DIRECTORY = (ENABLE = TRUE)
    ENCRYPTION = (TYPE = 'SNOWFLAKE_SSE')
    COMMENT = 'Proof images uploaded by customers — no image bytes in tables';

-- ---------------------------------------------------------------------------
-- Grants
-- ---------------------------------------------------------------------------
GRANT USAGE ON SCHEMA INVESTIGATION TO ROLE TIDE_CUSTOMER;
GRANT USAGE ON SCHEMA INVESTIGATION TO ROLE TIDE_APPROVER;
GRANT USAGE ON SCHEMA INVESTIGATION TO ROLE TIDE_ESCALATION;

-- Deliberately no table or ALL/FUTURE VIEWS grants here. No persona role reads
-- INVESTIGATION directly: evidence bundles and proof analysis are reached
-- through EXECUTE AS OWNER procedures. Grant individual objects if that ever
-- changes, rather than opening the schema.
