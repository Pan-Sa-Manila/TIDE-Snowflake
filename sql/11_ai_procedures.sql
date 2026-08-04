-- ============================================================================
-- TIDE · 11_ai_procedures.sql
-- The AI_COMPLETE call sites (TASKS.md C-2).
--
-- Every AI call in TIDE goes through ONE wrapper, DECISION.AI_JSON, which reads
-- the model name from DECISION.RULE_CONSTANTS. Nothing here names a model
-- literally: when a model changes it is a row update, not a code change
-- (AGENTS.md §8.2).
--
-- Every call site has a deterministic fallback and takes it when the model is
-- unavailable, returns malformed JSON, or answers outside the closed set. That
-- is required behaviour under DETAILS.md failure handling, not scaffolding —
-- the pipeline stays demonstrable with the AI switched off.
--
-- The fallbacks are cheap because the customer already told us what we need:
-- OPEN_CASE captured the subtype and resolution preference from the picker
-- before any model was consulted.
--
-- Idempotent: safe to re-run
-- ============================================================================

USE DATABASE TIDE;
USE SCHEMA DECISION;

-- ---------------------------------------------------------------------------
-- AI_JSON — the single AI entry point.
--
-- Returns the parsed object, or NULL. NULL is the caller's signal to take its
-- fallback; no caller is allowed to treat NULL as an exception.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE PROCEDURE AI_JSON(MODEL_KEY VARCHAR, PROMPT VARCHAR, SCHEMA VARIANT)
RETURNS VARIANT
LANGUAGE SQL
COMMENT = 'Internal. The only AI_COMPLETE call site in TIDE. Reads the model from RULE_CONSTANTS by key (MODEL_TEXT | MODEL_VISION | MODEL_AGENT), runs the prompt with constrained decoding at temperature 0, and returns the parsed object or NULL. NULL means take your fallback.'
EXECUTE AS OWNER
AS
$$
DECLARE
    model VARCHAR;
    raw   VARIANT;
    out   VARIANT;
BEGIN
    SELECT rk.value::VARCHAR INTO :model
    FROM TIDE.DECISION.RULE_CONSTANTS rk WHERE rk.key = :MODEL_KEY;

    IF (model IS NULL) THEN
        RETURN NULL;
    END IF;

    SELECT AI_COMPLETE(
        model            => :model,
        prompt           => :PROMPT,
        response_format  => OBJECT_CONSTRUCT('type', 'json', 'schema', :SCHEMA),
        model_parameters => OBJECT_CONSTRUCT('temperature', 0)
    ) INTO :raw;

    -- AI_COMPLETE may hand back an object or a JSON string depending on model.
    SELECT IFF(TYPEOF(:raw) = 'VARCHAR', TRY_PARSE_JSON(:raw::VARCHAR), :raw) INTO :out;

    RETURN :out;
EXCEPTION
    WHEN OTHER THEN
        -- An AI failure is a routed branch, never an exception. DETAILS.md §14.
        RETURN NULL;
END;
$$;

USE SCHEMA TRIAGE;

-- ---------------------------------------------------------------------------
-- NORMALISE_SUBTYPE — intake aliases, DETAILS.md §7.2.
-- Applied before anything else; an unknown subtype after this is G-01's problem.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION NORMALISE_SUBTYPE(RAW VARCHAR)
RETURNS VARCHAR
COMMENT = 'Map an intake alias to its canonical subtype (DETAILS.md section 7.2). Unrecognised input is returned unchanged.'
AS
$$
    COALESCE(
        CASE LOWER(TRIM(COALESCE(RAW, '')))
            WHEN 'package_never_arrived'   THEN 'non_receipt'
            WHEN 'delivery_late'           THEN 'delayed'
            WHEN 'wrong_delivery_address'  THEN 'exception'
            WHEN 'quality_issue'           THEN 'not_as_described'
            WHEN 'return_for_refund'       THEN 'return_request'
            ELSE LOWER(TRIM(COALESCE(RAW, '')))
        END, '')
$$;

-- ---------------------------------------------------------------------------
-- INTAKE_TURN — one customer message, and the pipeline it may start.
--
-- This is the orchestrator: ARCHITECTURE.md §6.1 is
--   INTAKE_TURN -> ASSEMBLE_EVIDENCE -> ADJUDICATE -> EXECUTE_RESOLUTION
-- and this procedure owns the first three hops.
--
-- The model only decides whether it still needs to ask something. It never
-- decides the outcome; adjudication is deterministic and downstream.
--
-- Fallback: if the model is unavailable, malformed, or answers with a subtype
-- outside the closed set, intake proceeds with what the customer already chose
-- when they opened the case. Nothing is blocked on AI.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE PROCEDURE INTAKE_TURN(CASE_ID VARCHAR, MESSAGE VARCHAR)
RETURNS VARIANT
LANGUAGE SQL
COMMENT = 'Process one customer message during intake. Input: case_id, message text. Records the message, may ask one clarifying question (bounded by MAX_FOLLOWUP_QUESTIONS), and otherwise runs evidence assembly and adjudication. Returns the assistant reply and, when the case was decided, the decision.'
EXECUTE AS OWNER
AS
$$
DECLARE
    v_status     VARCHAR;
    v_subtype    VARCHAR;
    v_preference VARCHAR;
    v_summary    VARCHAR;
    asked        NUMBER DEFAULT 0;
    max_followup NUMBER;
    ai           VARIANT;
    ai_subtype   VARCHAR;
    action       VARCHAR;
    reply        VARCHAR;
    prompt       VARCHAR;
    schema_def   VARIANT;
    decision     VARIANT;
    bundle       VARIANT;
    err          VARCHAR;
BEGIN
    SELECT v.current_status, v.dispute_subtype, v.resolution_preference, v.intake_summary
      INTO :v_status, :v_subtype, :v_preference, :v_summary
    FROM TIDE.TRIAGE.V_CASE_CURRENT v
    WHERE v.case_id = :CASE_ID;

    IF (v_status IS NULL) THEN
        RETURN OBJECT_CONSTRUCT('success', FALSE, 'error', 'Case not found.');
    END IF;

    IF (v_status IN ('closed', 'resolved')) THEN
        RETURN OBJECT_CONSTRUCT('success', FALSE, 'error', 'This case is closed.');
    END IF;

    -- The customer's turn is recorded before anything can fail, so the
    -- transcript is never missing a message the customer can see they sent.
    CALL TIDE.TRIAGE.POST_MESSAGE(:CASE_ID, 'customer', CURRENT_USER(), :MESSAGE, NULL);

    -- A case waiting on proof stays waiting; talking does not unblock it.
    IF (v_status = 'awaiting_customer_proof') THEN
        CALL TIDE.TRIAGE.POST_MESSAGE(
            :CASE_ID, 'assistant', 'TIDE',
            'Thanks — I still need a photo before I can look into this. Please upload one above.',
            NULL);
        RETURN OBJECT_CONSTRUCT('success', TRUE, 'action', 'awaiting_proof');
    END IF;

    SELECT rk.value::NUMBER INTO :max_followup
    FROM TIDE.DECISION.RULE_CONSTANTS rk WHERE rk.key = 'MAX_FOLLOWUP_QUESTIONS';

    SELECT COUNT(*) INTO :asked
    FROM TIDE.TRIAGE.CASE_EVENTS e
    WHERE e.case_id = :CASE_ID AND e.event_type = 'followup_asked';

    -- ---- the one AI call on this path -------------------------------------
    schema_def := OBJECT_CONSTRUCT(
        'type', 'object',
        'properties', OBJECT_CONSTRUCT(
            'action',   OBJECT_CONSTRUCT('type', 'string',
                            'description', 'ask_followup if one more fact is genuinely needed, otherwise ready'),
            'subtype',  OBJECT_CONSTRUCT('type', 'string',
                            'description', 'One of the 12 canonical dispute subtypes, or the empty string if unchanged'),
            'reply',    OBJECT_CONSTRUCT('type', 'string',
                            'description', 'One short sentence to the customer. Plain and specific, never vague reassurance'),
            'summary',  OBJECT_CONSTRUCT('type', 'string',
                            'description', 'One line summarising the complaint for a human reviewer')),
        'required', ARRAY_CONSTRUCT('action', 'subtype', 'reply', 'summary'),
        'additionalProperties', FALSE);

    prompt := 'You are triaging a retail dispute. The customer already selected subtype "'
        || COALESCE(:v_subtype, '') || '" and preferred resolution "'
        || COALESCE(:v_preference, '') || '" when opening the case. '
        || 'Their message: "' || COALESCE(:MESSAGE, '') || '". '
        || 'You have already asked ' || :asked || ' of a maximum ' || :max_followup
        || ' follow-up questions. Ask another only if a fact you genuinely lack would change '
        || 'the outcome; otherwise answer ready. Do not promise any refund or outcome. '
        || 'Respond in JSON.';

    CALL TIDE.DECISION.AI_JSON('MODEL_TEXT', :prompt, :schema_def) INTO :ai;

    IF (ai IS NULL) THEN
        -- Fallback: the customer already told us the subtype at OPEN_CASE.
        action := 'ready';
        reply  := 'Thanks — I have what I need. Looking into this now.';
    ELSE
        action     := COALESCE(ai['action']::VARCHAR, 'ready');
        reply      := COALESCE(ai['reply']::VARCHAR, 'Thanks — looking into this now.');
        ai_subtype := TIDE.TRIAGE.NORMALISE_SUBTYPE(ai['subtype']::VARCHAR);

        -- Only accept a subtype inside the closed set. A model answering
        -- "missing_parcel" is not a reason to invent a 13th subtype.
        IF (ai_subtype <> '' AND TIDE.TRIAGE.IS_KNOWN_SUBTYPE(:ai_subtype)
            AND ai_subtype <> v_subtype) THEN
            UPDATE TIDE.TRIAGE.CASES c
            SET c.dispute_subtype = :ai_subtype
            WHERE c.case_id = :CASE_ID;

            INSERT INTO TIDE.TRIAGE.CASE_EVENTS (case_id, event_type, actor_type, actor_id, payload)
            SELECT :CASE_ID, 'intake_classified', 'assistant', 'TIDE',
                   OBJECT_CONSTRUCT('from', :v_subtype, 'to', :ai_subtype);

            v_subtype := ai_subtype;
        END IF;

        IF (ai['summary']::VARCHAR IS NOT NULL AND v_summary IS NULL) THEN
            UPDATE TIDE.TRIAGE.CASES c
            SET c.intake_summary = :ai['summary']::VARCHAR
            WHERE c.case_id = :CASE_ID;
        END IF;
    END IF;

    -- The follow-up budget is a hard stop, whatever the model wants.
    IF (action = 'ask_followup' AND asked >= max_followup) THEN
        action := 'ready';
    END IF;

    CALL TIDE.TRIAGE.POST_MESSAGE(:CASE_ID, 'assistant', 'TIDE', :reply, NULL);

    IF (action = 'ask_followup') THEN
        INSERT INTO TIDE.TRIAGE.CASE_EVENTS (case_id, event_type, actor_type, actor_id, payload)
        SELECT :CASE_ID, 'followup_asked', 'assistant', 'TIDE',
               OBJECT_CONSTRUCT('question', :reply, 'asked_count', :asked + 1);

        INSERT INTO TIDE.EXECUTION.PIPELINE_LOG (case_id, component, status, detail)
        SELECT :CASE_ID, 'INTAKE_TURN', 'completed',
               OBJECT_CONSTRUCT('action', 'ask_followup', 'asked_count', :asked + 1,
                                'ai', IFF(:ai IS NULL, 'fallback', 'model'));

        RETURN OBJECT_CONSTRUCT('success', TRUE, 'action', 'ask_followup', 'reply', :reply);
    END IF;

    -- ---- ready: run the rest of the synchronous chain ----------------------
    CALL TIDE.INVESTIGATION.ASSEMBLE_EVIDENCE(:CASE_ID) INTO :bundle;

    IF (bundle IS NULL OR bundle['error'] IS NOT NULL) THEN
        INSERT INTO TIDE.EXECUTION.PIPELINE_LOG (case_id, component, status, detail)
        SELECT :CASE_ID, 'INTAKE_TURN', 'failed',
               OBJECT_CONSTRUCT('stage', 'assemble_evidence', 'detail', :bundle);
        RETURN OBJECT_CONSTRUCT('success', FALSE, 'error', 'Evidence assembly failed.');
    END IF;

    CALL TIDE.DECISION.ADJUDICATE(:CASE_ID) INTO :decision;

    INSERT INTO TIDE.EXECUTION.PIPELINE_LOG (case_id, component, status, detail)
    SELECT :CASE_ID, 'INTAKE_TURN', 'completed',
           OBJECT_CONSTRUCT('action', 'adjudicated',
                            'path_id', :decision['path_id'],
                            'ai', IFF(:ai IS NULL, 'fallback', 'model'));

    RETURN OBJECT_CONSTRUCT(
        'success', TRUE, 'action', 'adjudicated',
        'reply', :reply, 'decision', :decision);
EXCEPTION
    WHEN OTHER THEN
        err := SQLERRM;
        INSERT INTO TIDE.EXECUTION.PIPELINE_LOG (case_id, component, status, detail)
        SELECT :CASE_ID, 'INTAKE_TURN', 'failed', OBJECT_CONSTRUCT('error', :err);
        RETURN OBJECT_CONSTRUCT('success', FALSE, 'error', :err);
END;
$$;

USE SCHEMA EXECUTION;

-- ---------------------------------------------------------------------------
-- SUMMARIZE_ESCALATION — the human handoff summary.
--
-- Writes to PIPELINE_LOG as component 'T_SUMMARIZE' with the text under
-- detail.summary, because that is exactly what 3_Escalation.py already reads
-- as its fallback source. Matching the UI's existing contract rather than
-- inventing a table it would have to be taught about.
--
-- Fallback: a templated digest assembled from the same facts. A specialist
-- picking up a case gets a usable handover whether or not the model answered.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE PROCEDURE SUMMARIZE_ESCALATION(CASE_ID VARCHAR)
RETURNS VARIANT
LANGUAGE SQL
COMMENT = 'Generate the escalation handoff summary for a case and record it for the escalation console. Input: case_id. Falls back to a templated digest when the model is unavailable.'
EXECUTE AS OWNER
AS
$$
DECLARE
    v_ref      VARCHAR;
    v_subtype  VARCHAR;
    v_status   VARCHAR;
    v_path     VARCHAR;
    v_reason   VARCHAR;
    v_amount   VARCHAR;
    transcript VARCHAR;
    ai         VARIANT;
    summary    VARCHAR;
    prompt     VARCHAR;
    schema_def VARIANT;
    err        VARCHAR;
BEGIN
    SELECT v.reference_number, v.dispute_subtype, v.current_status,
           COALESCE(v.path_id, 'n/a'), COALESCE(v.eligible_amount::VARCHAR, '0')
      INTO :v_ref, :v_subtype, :v_status, :v_path, :v_amount
    FROM TIDE.TRIAGE.V_CASE_CURRENT v WHERE v.case_id = :CASE_ID;

    IF (v_ref IS NULL) THEN
        RETURN OBJECT_CONSTRUCT('success', FALSE, 'error', 'Case not found.');
    END IF;

    SELECT d.reason INTO :v_reason
    FROM TIDE.DECISION.DECISIONS d
    WHERE d.case_id = :CASE_ID ORDER BY d.decided_at DESC LIMIT 1;

    SELECT LISTAGG(ch.sender_type || ': ' || ch.content, '\n')
             WITHIN GROUP (ORDER BY ch.created_at)
      INTO :transcript
    FROM TIDE.TRIAGE.CHAT ch WHERE ch.case_id = :CASE_ID;

    -- The templated digest is built first, so it is always available.
    summary := 'Case ' || :v_ref || ' (' || :v_subtype || ') is at ' || :v_status
        || '. Decision path ' || :v_path || ', eligible amount ' || :v_amount || '. '
        || COALESCE(:v_reason, 'No decision recorded yet.');

    schema_def := OBJECT_CONSTRUCT(
        'type', 'object',
        'properties', OBJECT_CONSTRUCT(
            'summary', OBJECT_CONSTRUCT('type', 'string',
                'description', 'Three sentences maximum for the specialist picking this up: what the customer wants, what the records show, and what needs deciding')),
        'required', ARRAY_CONSTRUCT('summary'),
        'additionalProperties', FALSE);

    prompt := 'Summarise this dispute for the human specialist taking it over. '
        || 'Reference ' || :v_ref || ', subtype ' || :v_subtype || ', status ' || :v_status
        || ', decision path ' || :v_path || ', eligible amount ' || :v_amount || '. '
        || 'Engine reason: ' || COALESCE(:v_reason, 'none') || '. '
        || 'Transcript:\n' || COALESCE(:transcript, '(no messages)') || '\n'
        || 'State facts only. Do not recommend an outcome. Respond in JSON.';

    CALL TIDE.DECISION.AI_JSON('MODEL_TEXT', :prompt, :schema_def) INTO :ai;

    IF (ai IS NOT NULL AND ai['summary']::VARCHAR IS NOT NULL) THEN
        summary := ai['summary']::VARCHAR;
    END IF;

    INSERT INTO TIDE.EXECUTION.PIPELINE_LOG (case_id, component, status, detail)
    SELECT :CASE_ID, 'T_SUMMARIZE', 'completed',
           OBJECT_CONSTRUCT('summary', :summary, 'ai', IFF(:ai IS NULL, 'fallback', 'model'));

    INSERT INTO TIDE.TRIAGE.CASE_EVENTS (case_id, event_type, actor_type, actor_id, payload)
    SELECT :CASE_ID, 'summarized', 'system', CURRENT_USER(),
           OBJECT_CONSTRUCT('summary', :summary);

    RETURN OBJECT_CONSTRUCT('success', TRUE, 'summary', :summary);
EXCEPTION
    WHEN OTHER THEN
        err := SQLERRM;
        INSERT INTO TIDE.EXECUTION.PIPELINE_LOG (case_id, component, status, detail)
        SELECT :CASE_ID, 'T_SUMMARIZE', 'failed', OBJECT_CONSTRUCT('error', :err);
        RETURN OBJECT_CONSTRUCT('success', FALSE, 'error', :err);
END;
$$;

-- ---------------------------------------------------------------------------
-- GENERATE_REPORT — the case report written on close.
--
-- One row per case in CASE_REPORTS, which both the customer page and the
-- escalation console read. The audit trail is the product, so this is assembled
-- from recorded facts (decision path, policies, event timeline) rather than
-- narrated by the model; the model only writes the prose summary on top.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE PROCEDURE GENERATE_REPORT(CASE_ID VARCHAR)
RETURNS VARIANT
LANGUAGE SQL
COMMENT = 'Generate the final case report on close. Input: case_id. Writes one CASE_REPORTS row with the outcome summary, decision path, rules applied and event timeline. Falls back to a templated summary without the model.'
EXECUTE AS OWNER
AS
$$
DECLARE
    v_ref      VARCHAR;
    v_subtype  VARCHAR;
    v_status   VARCHAR;
    v_path     VARCHAR;
    v_reason   VARCHAR;
    v_close    VARCHAR;
    timeline   VARIANT;
    policies   ARRAY;
    ai         VARIANT;
    summary    VARCHAR;
    prompt     VARCHAR;
    schema_def VARIANT;
    err        VARCHAR;
BEGIN
    SELECT v.reference_number, v.dispute_subtype, v.current_status,
           COALESCE(v.path_id, 'n/a'), COALESCE(v.close_reason, 'n/a')
      INTO :v_ref, :v_subtype, :v_status, :v_path, :v_close
    FROM TIDE.TRIAGE.V_CASE_CURRENT v WHERE v.case_id = :CASE_ID;

    IF (v_ref IS NULL) THEN
        RETURN OBJECT_CONSTRUCT('success', FALSE, 'error', 'Case not found.');
    END IF;

    SELECT d.reason INTO :v_reason
    FROM TIDE.DECISION.DECISIONS d
    WHERE d.case_id = :CASE_ID ORDER BY d.decided_at DESC LIMIT 1;

    SELECT ARRAY_AGG(OBJECT_CONSTRUCT(
               'event_type', e.event_type,
               'actor', e.actor_type,
               'at', TIDE.INVESTIGATION.ISO_UTC(e.occurred_at)))
             WITHIN GROUP (ORDER BY e.occurred_at)
      INTO :timeline
    FROM TIDE.TRIAGE.CASE_EVENTS e WHERE e.case_id = :CASE_ID;

    SELECT COALESCE(ARRAY_AGG(DISTINCT ce.payload['citations'][0]::VARCHAR), ARRAY_CONSTRUCT())
      INTO :policies
    FROM TIDE.TRIAGE.CASE_EVENTS ce
    WHERE ce.case_id = :CASE_ID AND ce.event_type = 'rejected';

    summary := 'Case ' || :v_ref || ' (' || :v_subtype || ') closed as ' || :v_close
        || ' via decision path ' || :v_path || '. ' || COALESCE(:v_reason, '');

    schema_def := OBJECT_CONSTRUCT(
        'type', 'object',
        'properties', OBJECT_CONSTRUCT(
            'summary', OBJECT_CONSTRUCT('type', 'string',
                'description', 'Two or three sentences of plain factual record: what was claimed, what was decided, and why')),
        'required', ARRAY_CONSTRUCT('summary'),
        'additionalProperties', FALSE);

    prompt := 'Write the closing record for dispute ' || :v_ref || '. Subtype ' || :v_subtype
        || ', closed as ' || :v_close || ', decision path ' || :v_path
        || ', engine reason: ' || COALESCE(:v_reason, 'none')
        || '. Factual and past tense. No apology, no marketing. Respond in JSON.';

    CALL TIDE.DECISION.AI_JSON('MODEL_TEXT', :prompt, :schema_def) INTO :ai;

    IF (ai IS NOT NULL AND ai['summary']::VARCHAR IS NOT NULL) THEN
        summary := ai['summary']::VARCHAR;
    END IF;

    DELETE FROM TIDE.EXECUTION.CASE_REPORTS cr WHERE cr.case_id = :CASE_ID;

    INSERT INTO TIDE.EXECUTION.CASE_REPORTS
        (case_id, outcome_summary, resolution_path, rules_applied, policies_cited, timeline)
    SELECT :CASE_ID, :summary, :v_path,
           ARRAY_CONSTRUCT(:v_path), :policies, :timeline;

    INSERT INTO TIDE.EXECUTION.PIPELINE_LOG (case_id, component, status, detail)
    SELECT :CASE_ID, 'T_REPORT', 'completed',
           OBJECT_CONSTRUCT('path_id', :v_path, 'ai', IFF(:ai IS NULL, 'fallback', 'model'));

    INSERT INTO TIDE.TRIAGE.CASE_EVENTS (case_id, event_type, actor_type, actor_id, payload)
    SELECT :CASE_ID, 'reported', 'system', CURRENT_USER(),
           OBJECT_CONSTRUCT('path_id', :v_path);

    RETURN OBJECT_CONSTRUCT('success', TRUE, 'summary', :summary);
EXCEPTION
    WHEN OTHER THEN
        err := SQLERRM;
        INSERT INTO TIDE.EXECUTION.PIPELINE_LOG (case_id, component, status, detail)
        SELECT :CASE_ID, 'T_REPORT', 'failed', OBJECT_CONSTRUCT('error', :err);
        RETURN OBJECT_CONSTRUCT('success', FALSE, 'error', :err);
END;
$$;

USE SCHEMA INVESTIGATION;

-- ---------------------------------------------------------------------------
-- ANALYZE_PROOF — the vision call. DETAILS.md §9 proof signals.
--
-- Called by the customer page immediately after a file lands on PROOF_STAGE.
-- It registers the file (the UI never writes PROOF_FILES itself), asks the
-- vision model about the four signals the engine reads, and stores the answer.
-- It does not decide anything: guardrails G-06 to G-09 do, downstream.
--
-- Why this calls AI_COMPLETE directly rather than DECISION.AI_JSON: the wrapper
-- takes a VARCHAR prompt, and a multimodal call needs PROMPT(...) with
-- TO_FILE(...), which is a different type. Changing AI_JSON's signature would
-- break its existing callers, so the rule that matters is honoured instead —
-- the model name is read from RULE_CONSTANTS and never hardcoded.
--
-- Failure is 'failed', not 'unverified'. DETAILS.md §10 G-07 routes a failed
-- analysis to a human. Recording "no signals" instead would reach G-09 and tell
-- the customer their proof does not support the claim, when the truth is that
-- nobody looked at it.
--
-- Signal keys match tide_decision PROOF_SIGNAL_BY_SUBTYPE exactly. The engine
-- reads only the key relevant to the case's subtype; `true` supports the claim,
-- `false` contradicts it (G-08), and a missing key is merely unsupportive.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE PROCEDURE ANALYZE_PROOF(CASE_ID VARCHAR, RELATIVE_PATH VARCHAR)
RETURNS VARIANT
LANGUAGE SQL
COMMENT = 'Register a staged proof image and analyse it with the vision model. Input: case_id, stage-relative path. Writes signals to PROOF_FILES.analysis and sets analysis_status to completed or failed. Returns {success, analysis_status, signals} or {success:false, error}. Reports signals only; it never classifies the case.'
EXECUTE AS OWNER
AS
$$
DECLARE
    reg      VARIANT;
    subtype  VARCHAR;
    model    VARCHAR;
    raw      VARIANT;
    parsed   VARIANT;
    err      VARCHAR;
BEGIN
    -- 1. Register first. This enforces the upload cap, rejects a duplicate
    -- image and confirms the file is actually on the stage.
    CALL TIDE.INVESTIGATION.REGISTER_PROOF(:CASE_ID, :RELATIVE_PATH) INTO :reg;

    IF (NOT COALESCE(:reg['success']::BOOLEAN, FALSE)) THEN
        INSERT INTO TIDE.EXECUTION.PIPELINE_LOG (case_id, component, status, detail)
        SELECT :CASE_ID, 'ANALYZE_PROOF', 'failed', :reg;
        RETURN :reg;
    END IF;

    SELECT v.dispute_subtype INTO :subtype
    FROM TIDE.TRIAGE.V_CASE_CURRENT v WHERE v.case_id = :CASE_ID;

    SELECT rk.value::VARCHAR INTO :model
    FROM TIDE.DECISION.RULE_CONSTANTS rk WHERE rk.key = 'MODEL_VISION';

    -- 2. Ask the model. Constrained decoding at temperature 0 so the same image
    -- yields the same signals on a re-run, which the demo depends on.
    SELECT AI_COMPLETE(
        model  => :model,
        prompt => PROMPT(
            'You are inspecting a customer''s proof photograph for an online '
            || 'retail dispute. The customer claims: ' || COALESCE(:subtype, 'unknown')
            || '. Report only what is visible. Do not decide the outcome. {0}',
            TO_FILE('@TIDE.INVESTIGATION.PROOF_STAGE', :RELATIVE_PATH)),
        response_format => OBJECT_CONSTRUCT(
            'type', 'json',
            'schema', OBJECT_CONSTRUCT(
                'type', 'object',
                'properties', OBJECT_CONSTRUCT(
                    'damage_detected', OBJECT_CONSTRUCT(
                        'type', 'boolean',
                        'description', 'True only if visible physical damage is present: breakage, cracks, tears, dents, stains or spillage.'),
                    'wrong_item_signals', OBJECT_CONSTRUCT(
                        'type', 'boolean',
                        'description', 'True only if the item shown appears to be a different product from what a customer would have ordered.'),
                    'not_as_described_signals', OBJECT_CONSTRUCT(
                        'type', 'boolean',
                        'description', 'True only if the item is intact but visibly differs from a normal description: wrong colour, wrong size, wrong material.'),
                    'missing_item_signals', OBJECT_CONSTRUCT(
                        'type', 'boolean',
                        'description', 'True only if the photograph shows a package or order with contents visibly absent.'),
                    'notes', OBJECT_CONSTRUCT(
                        'type', 'string',
                        'description', 'One sentence describing what is visible. No opinion on the dispute.')),
                'required', ARRAY_CONSTRUCT(
                    'damage_detected', 'wrong_item_signals',
                    'not_as_described_signals', 'missing_item_signals', 'notes'))),
        model_parameters => OBJECT_CONSTRUCT('temperature', 0)
    ) INTO :raw;

    SELECT IFF(TYPEOF(:raw) = 'VARCHAR', TRY_PARSE_JSON(:raw::VARCHAR), :raw) INTO :parsed;

    IF (parsed IS NULL) THEN
        UPDATE TIDE.INVESTIGATION.PROOF_FILES
        SET analysis_status = 'failed',
            analysis = OBJECT_CONSTRUCT('error', 'Vision model returned nothing')
        WHERE case_id = :CASE_ID AND relative_path = :RELATIVE_PATH;

        INSERT INTO TIDE.EXECUTION.PIPELINE_LOG (case_id, component, status, detail)
        SELECT :CASE_ID, 'ANALYZE_PROOF', 'failed',
               OBJECT_CONSTRUCT('relative_path', :RELATIVE_PATH, 'ai', 'fallback');

        RETURN OBJECT_CONSTRUCT(
            'success', TRUE, 'analysis_status', 'failed',
            'note', 'Analysis unavailable; the case will be routed to a person.');
    END IF;

    -- 3. Store signals and prose separately: the engine reads the first, the
    -- escalation console shows the second.
    UPDATE TIDE.INVESTIGATION.PROOF_FILES
    SET analysis_status = 'completed',
        analysis = OBJECT_CONSTRUCT(
            'signals', OBJECT_CONSTRUCT(
                'damage_detected',          :parsed['damage_detected']::BOOLEAN,
                'wrong_item_signals',       :parsed['wrong_item_signals']::BOOLEAN,
                'not_as_described_signals', :parsed['not_as_described_signals']::BOOLEAN,
                'missing_item_signals',     :parsed['missing_item_signals']::BOOLEAN),
            'notes', :parsed['notes']::VARCHAR,
            'model', :model)
    WHERE case_id = :CASE_ID AND relative_path = :RELATIVE_PATH;

    INSERT INTO TIDE.EXECUTION.PIPELINE_LOG (case_id, component, status, detail)
    SELECT :CASE_ID, 'ANALYZE_PROOF', 'completed',
           OBJECT_CONSTRUCT('relative_path', :RELATIVE_PATH, 'ai', 'model',
                            'subtype', :subtype);

    RETURN OBJECT_CONSTRUCT(
        'success', TRUE,
        'analysis_status', 'completed',
        'signals', OBJECT_CONSTRUCT(
            'damage_detected',          :parsed['damage_detected']::BOOLEAN,
            'wrong_item_signals',       :parsed['wrong_item_signals']::BOOLEAN,
            'not_as_described_signals', :parsed['not_as_described_signals']::BOOLEAN,
            'missing_item_signals',     :parsed['missing_item_signals']::BOOLEAN),
        'notes', :parsed['notes']::VARCHAR);
EXCEPTION
    WHEN OTHER THEN
        err := SQLERRM;
        UPDATE TIDE.INVESTIGATION.PROOF_FILES
        SET analysis_status = 'failed',
            analysis = OBJECT_CONSTRUCT('error', :err)
        WHERE case_id = :CASE_ID AND relative_path = :RELATIVE_PATH;

        INSERT INTO TIDE.EXECUTION.PIPELINE_LOG (case_id, component, status, detail)
        SELECT :CASE_ID, 'ANALYZE_PROOF', 'failed', OBJECT_CONSTRUCT('error', :err);

        RETURN OBJECT_CONSTRUCT('success', FALSE, 'error', :err);
END;
$$;

-- ---------------------------------------------------------------------------
-- Grants
-- ---------------------------------------------------------------------------
GRANT USAGE ON FUNCTION TIDE.TRIAGE.NORMALISE_SUBTYPE(VARCHAR)            TO ROLE TIDE_ADMIN;
GRANT USAGE ON PROCEDURE TIDE.DECISION.AI_JSON(VARCHAR, VARCHAR, VARIANT) TO ROLE TIDE_ADMIN;
GRANT USAGE ON PROCEDURE TIDE.TRIAGE.INTAKE_TURN(VARCHAR, VARCHAR)        TO ROLE TIDE_CUSTOMER;
GRANT USAGE ON PROCEDURE TIDE.EXECUTION.SUMMARIZE_ESCALATION(VARCHAR)     TO ROLE TIDE_ADMIN;
GRANT USAGE ON PROCEDURE TIDE.EXECUTION.GENERATE_REPORT(VARCHAR)          TO ROLE TIDE_ADMIN;
GRANT USAGE ON PROCEDURE TIDE.INVESTIGATION.ANALYZE_PROOF(VARCHAR, VARCHAR) TO ROLE TIDE_CUSTOMER;
