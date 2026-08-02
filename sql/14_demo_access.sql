-- ============================================================================
-- TIDE · 14_demo_access.sql
-- Access model for demo and judging (docs/SUBMISSION.md).
--
-- REQUIRES: ACCOUNTADMIN
--
-- Two things live here: the TIDE_JUDGE role, and the grants that let the
-- persona roles reach the Streamlit app.
--
-- USERS ARE NOT CREATED HERE, DELIBERATELY. Creating a user requires setting a
-- password, and there are no secrets in this repository (AGENTS.md §10.2).
-- The four demo/judge users are created out of band; this file gives their
-- roles everything those roles need, so user creation is only
-- CREATE USER ... DEFAULT_ROLE = <role>. The account list is documented at the
-- bottom.
--
-- Idempotent: safe to re-run
-- ============================================================================

USE DATABASE TIDE;

-- ---------------------------------------------------------------------------
-- TIDE_JUDGE — one login that can walk all three personas.
--
-- Built by role inheritance rather than by duplicating grants. A role granted
-- to another role passes its privileges up, so TIDE_JUDGE is exactly the union
-- of the three personas and stays that way automatically as their grants
-- change. Duplicating the grant list here would drift the first time someone
-- edits a persona.
--
-- Why one judge account and not three: Home.py routes personas with buttons,
-- not with a role check — any authenticated viewer can open any of the three
-- pages, and the role only decides which SQL succeeds underneath. Three judge
-- logins would mean two extra sign-ins for an evaluator and no extra proof.
-- Role separation is still demonstrated by the three single-persona demo
-- accounts.
-- ---------------------------------------------------------------------------
CREATE ROLE IF NOT EXISTS TIDE_JUDGE
    COMMENT = 'Hackathon evaluator: union of the three personas, read-mostly, Streamlit only';

GRANT ROLE TIDE_CUSTOMER   TO ROLE TIDE_JUDGE;
GRANT ROLE TIDE_APPROVER   TO ROLE TIDE_JUDGE;
GRANT ROLE TIDE_ESCALATION TO ROLE TIDE_JUDGE;

-- TIDE_ADMIN sits above it so the role stays manageable without ACCOUNTADMIN.
GRANT ROLE TIDE_JUDGE TO ROLE TIDE_ADMIN;

-- The inherited persona roles already carry database, schema, view and
-- procedure privileges. Warehouse usage is granted directly as well, so the
-- role works even if a persona's warehouse grant is ever narrowed.
GRANT USAGE ON WAREHOUSE TIDE_WH_APP TO ROLE TIDE_JUDGE;
GRANT USAGE ON DATABASE  TIDE        TO ROLE TIDE_JUDGE;

-- ---------------------------------------------------------------------------
-- Authentication policy for the demo and judge accounts
--
-- This account enforces MFA on password logins, which is why the team's own
-- programmatic access uses a PAT. Verified behaviour for a fresh demo user:
--
--   250001 (08001): Multi-factor authentication is required for this account.
--                   Log in to Snowsight to enroll.
--
-- The password is accepted and then the login is refused pending enrolment. An
-- evaluator handed these credentials with the submission would hit an MFA
-- enrolment screen — asking a judge to bind an authenticator app to a throwaway
-- account is how a submission goes unreviewed.
--
-- A user-level authentication policy overrides the account-level one, so the
-- blast radius below is these four demo logins and nothing else. The accounts
-- hold no production data, are seeded from sql/seed/, and are disposable after
-- judging.
--
-- UNRESOLVED — DO NOT ASSUME THIS WORKS. The policy object below was created
-- and described on canonical. `MFA_ENROLLMENT = OPTIONAL` did NOT take: the
-- stored value came back as
--
--   MFA_ENROLLMENT = REQUIRED_SNOWFLAKE_UI_PASSWORD_ONLY
--
-- which is precisely the path a judge uses — Snowsight, password, browser. So
-- creating this policy is not by itself the fix, and the ALTER USER attach
-- statements are deliberately left commented out rather than shipped looking
-- like a solution.
--
-- Whoever picks this up: confirm whether OPTIONAL is rejected because the
-- account enforces a floor, or because the keyword is no longer honoured, then
-- either fix the policy or take one of the fallbacks in docs/TASKS.md E-4.
-- Attaching a policy that still demands enrolment would leave the judge exactly
-- where they started, with the added cost of looking handled.
-- ---------------------------------------------------------------------------
CREATE AUTHENTICATION POLICY IF NOT EXISTS TIDE.TRIAGE.DEMO_AUTH_POLICY
    AUTHENTICATION_METHODS = ('PASSWORD')
    MFA_ENROLLMENT = OPTIONAL
    COMMENT = 'Demo and judge accounts: password without MFA enrolment. Disposable accounts, no production data.';

-- Intentionally not applied. See the note above before uncommenting, and verify
-- an actual login afterwards rather than trusting the statement's success.
--   ALTER USER TIDE_DEMO_CUSTOMER   SET AUTHENTICATION POLICY TIDE.TRIAGE.DEMO_AUTH_POLICY;
--   ALTER USER TIDE_DEMO_APPROVER   SET AUTHENTICATION POLICY TIDE.TRIAGE.DEMO_AUTH_POLICY;
--   ALTER USER TIDE_DEMO_ESCALATION SET AUTHENTICATION POLICY TIDE.TRIAGE.DEMO_AUTH_POLICY;
--   ALTER USER TIDE_JUDGE           SET AUTHENTICATION POLICY TIDE.TRIAGE.DEMO_AUTH_POLICY;

-- ---------------------------------------------------------------------------
-- The demo and judge accounts
--
-- Created out of band, without passwords in this repo. Each is
--   CREATE USER <name>
--     PASSWORD = '<generated>'
--     DEFAULT_ROLE = <role>
--     DEFAULT_WAREHOUSE = TIDE_WH_APP
--     DEFAULT_NAMESPACE = TIDE.TRIAGE
--     MUST_CHANGE_PASSWORD = FALSE;
--
--   TIDE_DEMO_CUSTOMER    -> TIDE_CUSTOMER     three single-persona accounts,
--   TIDE_DEMO_APPROVER    -> TIDE_APPROVER     used for the demo video so role
--   TIDE_DEMO_ESCALATION  -> TIDE_ESCALATION   separation is visible on camera
--   TIDE_JUDGE            -> TIDE_JUDGE        one evaluator login, all three
--
-- All four exist on canonical as of 2 Aug 2026, with the roles above granted
-- and verified. MUST_CHANGE_PASSWORD is FALSE on all four: a forced
-- password-change screen on first login is exactly how an evaluator bounces off
-- the submission.
--
-- The judge account additionally carries ALLOWED_INTERFACES = ('STREAMLIT') so
-- credentials published with the submission cannot run ad-hoc SQL. Applied and
-- confirmed present via DESCRIBE USER.
--
-- CAVEAT, untested: whether STREAMLIT-only still admits the Snowsight page that
-- *hosts* a Streamlit app. If it does not, the judge is locked out of the very
-- thing the account exists for. This cannot be tested until the app is deployed
-- (deploy.py step 4 is a stub), and both must be checked together. If it turns
-- out to block, widen to ('ALL') — the account is disposable and read-mostly,
-- so the restriction is defence in depth, not the thing keeping it safe.
--
-- Customer-facing views filter on CURRENT_USER(), so any account that needs a
-- populated customer page must also own orders — see
-- sql/seed/seed_demo_customer.sql, which seeds per username.
-- ---------------------------------------------------------------------------

-- ---------------------------------------------------------------------------
-- Streamlit app grant
--
-- The app object does not exist yet (scripts/deploy.py step 4 is a stub), so
-- this cannot be granted here. When the app is deployed, add:
--
--   GRANT USAGE ON STREAMLIT TIDE.<schema>.<app> TO ROLE TIDE_CUSTOMER;
--   GRANT USAGE ON STREAMLIT TIDE.<schema>.<app> TO ROLE TIDE_APPROVER;
--   GRANT USAGE ON STREAMLIT TIDE.<schema>.<app> TO ROLE TIDE_ESCALATION;
--   GRANT USAGE ON STREAMLIT TIDE.<schema>.<app> TO ROLE TIDE_JUDGE;
--
-- Until then the accounts authenticate but have nothing to open. This is the
-- step that gates judge-access testing (docs/TASKS.md E-4).
-- ---------------------------------------------------------------------------
