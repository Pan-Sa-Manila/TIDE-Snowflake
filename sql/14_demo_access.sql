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
-- SETTLED: the enrolment step is accepted, and this policy is NOT applied.
--
-- `MFA_ENROLLMENT = OPTIONAL` does not take. Created and described on canonical,
-- the stored value came back as
--
--   MFA_ENROLLMENT = REQUIRED_SNOWFLAKE_UI_PASSWORD_ONLY
--
-- which is precisely the path a judge uses — Snowsight, password, browser.
-- Silent coercion rather than an error, and no account-level authentication
-- policy is set (`SHOW PARAMETERS LIKE '%AUTHENTICATION%' IN ACCOUNT` returns
-- nothing), so this is Snowflake's platform floor for `TYPE = PERSON` users
-- rather than anything configured here. No policy will go below it.
--
-- The decision is therefore to let the evaluator enrol their own device on first
-- login. The consequence that matters is in the account notes below: the judge
-- account must be left UNENROLLED, because an account enrolled against a team
-- member's device demands that device at the judge's login.
--
-- The policy object is still created because it is harmless and documents the
-- attempt. The attach statements stay commented: applying a policy that still
-- demands enrolment changes nothing except making this look handled.
--
-- Untried alternative, if enrolment proves too much friction for evaluators:
-- `TYPE = LEGACY_SERVICE` is exempt from the MFA mandate and retains password
-- auth, but may be barred from Snowsight — test before relying on it.
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
-- credentials published with the submission cannot run ad-hoc SQL. Confirmed
-- non-blocking: a login succeeded with the restriction in force, and MFA
-- enrolment completed under it too. The earlier worry that STREAMLIT-only might
-- bar the Snowsight page hosting the app is closed.
--
-- **DO NOT LOG IN AS TIDE_JUDGE.** MFA enrolment binds to the enrolling device,
-- so any login by a team member makes the judge's login demand *our* phone. The
-- account was dropped and recreated on 2 Aug precisely to clear an accidental
-- enrolment; it must reach the evaluator with has_mfa = false so they enrol
-- their own. Verify with: SHOW USERS LIKE 'TIDE_JUDGE' -> has_mfa.
--
-- The three demo persona accounts are enrolled to Keith, which is correct —
-- they exist to record the demo video.
--
-- Customer-facing views filter on CURRENT_USER(), so any account that needs a
-- populated customer page must also own orders — see
-- sql/seed/seed_demo_customer.sql, which seeds per username.
-- ---------------------------------------------------------------------------

-- ---------------------------------------------------------------------------
-- Persona resolution — who is the viewer, and what may they do?
--
-- Streamlit in Snowflake runs with **owner's rights**. Every query and every
-- procedure call in the app executes as TIDE_ADMIN regardless of who is signed
-- in, which was confirmed by a customer account rendering V_QUEUE_APPROVAL and
-- EVIDENCE_BUNDLES — neither of which TIDE_CUSTOMER is granted. CURRENT_USER()
-- correctly returns the viewer, but privileges do not follow the persona.
--
-- So the persona roles above are real and correctly granted, but they are not
-- what the app runs as. Anything that must be restricted has to check the
-- caller explicitly, and this table plus HAS_PERSONA is how it does that.
--
-- Why a table rather than reading the grants: SHOW GRANTS TO USER needs
-- privileges TIDE_ADMIN may not hold, and SNOWFLAKE.ACCOUNT_USAGE.GRANTS_TO_USERS
-- lags by up to two hours — unusable when a judge creates a session and acts in
-- the same minute. This mirrors the GRANT ROLE statements above; change both or
-- neither.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS TIDE.TRIAGE.USER_PERSONA (
    username    VARCHAR(100) NOT NULL,
    persona     VARCHAR(20)  NOT NULL,
    CONSTRAINT pk_user_persona PRIMARY KEY (username, persona)
) COMMENT = 'Maps a Snowflake user to the TIDE personas they may act as. Mirrors the role grants in this file; Streamlit runs with owner rights so procedures cannot infer the caller from CURRENT_ROLE().';

DELETE FROM TIDE.TRIAGE.USER_PERSONA
WHERE username IN ('TIDE_DEMO_CUSTOMER', 'TIDE_DEMO_APPROVER',
                   'TIDE_DEMO_ESCALATION', 'TIDE_JUDGE');

INSERT INTO TIDE.TRIAGE.USER_PERSONA (username, persona)
SELECT * FROM VALUES
    ('TIDE_DEMO_CUSTOMER',   'customer'),
    ('TIDE_DEMO_APPROVER',   'approver'),
    ('TIDE_DEMO_ESCALATION', 'escalation'),
    -- The judge walks all three personas from one login.
    ('TIDE_JUDGE',           'customer'),
    ('TIDE_JUDGE',           'approver'),
    ('TIDE_JUDGE',           'escalation')
AS t(username, persona);

-- ---------------------------------------------------------------------------
-- HAS_PERSONA — the check every gated procedure calls.
--
-- An unmapped user is treated as fully privileged, NOT as denied. That is
-- deliberate: TIDE_ADMIN deploys, seeds and runs scripts/run_matrix.py, which
-- drives these procedures directly. Denying the unmapped would turn the matrix
-- red and break every maintenance path, while gaining nothing — a user who can
-- already call the procedure as owner is not the threat this guards against.
-- The threat is a *demo persona* reaching an action belonging to another
-- persona, and those users are all mapped.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION TIDE.TRIAGE.HAS_PERSONA(USERNAME VARCHAR, PERSONA VARCHAR)
RETURNS BOOLEAN
COMMENT = 'True if USERNAME may act as PERSONA (customer|approver|escalation). A user absent from USER_PERSONA is unrestricted, so admin and deploy paths keep working.'
AS
$$
    NOT EXISTS (
        SELECT 1 FROM TIDE.TRIAGE.USER_PERSONA up WHERE up.username = USERNAME
    )
    OR EXISTS (
        SELECT 1 FROM TIDE.TRIAGE.USER_PERSONA up
        WHERE up.username = USERNAME AND up.persona = PERSONA
    )
$$;

GRANT SELECT ON TABLE TIDE.TRIAGE.USER_PERSONA TO ROLE TIDE_CUSTOMER;
GRANT SELECT ON TABLE TIDE.TRIAGE.USER_PERSONA TO ROLE TIDE_APPROVER;
GRANT SELECT ON TABLE TIDE.TRIAGE.USER_PERSONA TO ROLE TIDE_ESCALATION;
GRANT USAGE ON FUNCTION TIDE.TRIAGE.HAS_PERSONA(VARCHAR, VARCHAR) TO ROLE TIDE_CUSTOMER;
GRANT USAGE ON FUNCTION TIDE.TRIAGE.HAS_PERSONA(VARCHAR, VARCHAR) TO ROLE TIDE_APPROVER;
GRANT USAGE ON FUNCTION TIDE.TRIAGE.HAS_PERSONA(VARCHAR, VARCHAR) TO ROLE TIDE_ESCALATION;

-- ---------------------------------------------------------------------------
-- Streamlit app grant
--
-- The app is deployed by `snow streamlit deploy` from streamlit/snowflake.yml,
-- driven by scripts/deploy.py step 4. It lives in TIDE.TRIAGE because the three
-- persona roles already hold USAGE on that schema, so only the app object
-- itself needs granting.
--
-- Ordering note: this file runs before the app is created on a from-zero
-- deploy, so the grants are guarded. A missing Streamlit reads as "object does
-- not exist", which would abort the whole file — see the grant/identifier
-- gotcha in CLAUDE.md. deploy.py re-runs this file after step 4 so the grants
-- land on a cold build too.
-- ---------------------------------------------------------------------------
EXECUTE IMMEDIATE $$
DECLARE
    app_missing BOOLEAN DEFAULT FALSE;
BEGIN
    SHOW STREAMLITS LIKE 'TIDE_APP' IN SCHEMA TIDE.TRIAGE;
    SELECT COUNT(*) = 0 INTO :app_missing
    FROM TABLE(RESULT_SCAN(LAST_QUERY_ID()));

    IF (app_missing) THEN
        RETURN 'TIDE_APP not deployed yet; grants skipped. deploy.py step 4 creates it, then re-runs this file.';
    END IF;

    GRANT USAGE ON STREAMLIT TIDE.TRIAGE.TIDE_APP TO ROLE TIDE_CUSTOMER;
    GRANT USAGE ON STREAMLIT TIDE.TRIAGE.TIDE_APP TO ROLE TIDE_APPROVER;
    GRANT USAGE ON STREAMLIT TIDE.TRIAGE.TIDE_APP TO ROLE TIDE_ESCALATION;
    GRANT USAGE ON STREAMLIT TIDE.TRIAGE.TIDE_APP TO ROLE TIDE_JUDGE;
    RETURN 'TIDE_APP granted to the three personas and the judge role.';
END;
$$;
