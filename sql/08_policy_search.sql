-- ============================================================================
-- TIDE · 08_policy_search.sql
-- DECISION.POLICY_SEARCH — Cortex Search service over DECISION.POLICIES
-- (docs/SCHEMA.md §3).
--
-- Two callers:
--   1. The Investigator agent, when policy scope is unclear and it needs to
--      cite a policy for the decision rationale (agents/investigator.yaml).
--   2. The approver rejection form's citation picker — a rejection needs at
--      least MIN_REJECTION_CITATIONS policy citations (DETAILS.md §14).
--
-- BLOCKED: cortex-trial
-- CREATE CORTEX SEARCH SERVICE fails on this account with:
--   399258 (0A000): AI function EMBED_TEXT_768 is not available for trial
--   accounts.
-- The service builds a vector index, so creation itself needs an embedding
-- model — unlike CREATE AGENT, which succeeds and only fails when run. This is
-- the same account entitlement documented in docs/CAPABILITIES.md §C, not a
-- syntax problem. The DDL below is correct and unchanged; it will create the
-- service as written once entitlements land.
--
-- Deploy impact: scripts/deploy.py exits on the first failing SQL file, so
-- while the block holds this file aborts the deploy before the seed step.
-- Needs a team decision (skip-list, or move blocked DDL after seed) — see the
-- handover note rather than assuming deploy.py still runs end to end.
--
-- Idempotent: safe to re-run
-- ============================================================================

USE DATABASE TIDE;
USE SCHEMA DECISION;

-- ---------------------------------------------------------------------------
-- Cortex Search requires change tracking on the source table so it can pick up
-- incremental edits. Setting it explicitly keeps this file self-sufficient
-- rather than relying on Snowflake enabling it as a side effect of CREATE.
-- ---------------------------------------------------------------------------
ALTER TABLE POLICIES SET CHANGE_TRACKING = TRUE;

-- ---------------------------------------------------------------------------
-- POLICY_SEARCH
--
-- Indexes `body`, the full policy text. slug / category / title are ATTRIBUTES,
-- meaning they can be filtered on at query time: the citation picker narrows by
-- category, the agent looks a known policy up by slug. policy_id is carried in
-- the source query so results can be keyed back to the row, but it is not a
-- filter dimension.
--
-- Only active policies are indexed. A retired policy must not be citable on a
-- rejection.
--
-- Warehouse: TIDE_WH_TASKS. Indexing is background refresh work, not
-- interactive, and that warehouse auto-suspends after 60s.
-- TARGET_LAG is an hour because the corpus is static seed data; it exists to
-- pick up policy edits during the build, not to track a live feed.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE CORTEX SEARCH SERVICE POLICY_SEARCH
    ON body
    ATTRIBUTES slug, category, title
    WAREHOUSE = TIDE_WH_TASKS
    TARGET_LAG = '1 hour'
    COMMENT = 'Search dispute resolution policies by topic. Use when you need to cite a specific policy for a decision rationale, or to check whether a scenario is covered by existing policy. Returns policy title, slug, category and full text. Filter by category (store, payment, return, delivery, sla) when the dispute type is known.'
AS
    SELECT
        policy_id,
        slug,
        category,
        title,
        body
    FROM POLICIES
    WHERE active;

-- ---------------------------------------------------------------------------
-- Grants
-- The Investigator agent reaches the service inside EXECUTE AS OWNER
-- procedures. TIDE_APPROVER is granted directly because the rejection form's
-- citation picker is an approver-persona read (AGENTS.md §10.1).
-- ---------------------------------------------------------------------------
GRANT USAGE ON CORTEX SEARCH SERVICE POLICY_SEARCH TO ROLE TIDE_ADMIN;
GRANT USAGE ON CORTEX SEARCH SERVICE POLICY_SEARCH TO ROLE TIDE_APPROVER;

-- ---------------------------------------------------------------------------
-- Cost control
--
-- A Cortex Search service bills on index size multiplied by how long the index
-- persists, so it costs money while idle, not only while queried. The corpus
-- here is 14 static policies, but suspend it between demo runs anyway.
-- Uncomment and run when the account is idle; RESUME before a demo, and allow
-- time for the index to come back before querying.
-- ---------------------------------------------------------------------------
-- ALTER CORTEX SEARCH SERVICE POLICY_SEARCH SUSPEND;
-- ALTER CORTEX SEARCH SERVICE POLICY_SEARCH RESUME;
