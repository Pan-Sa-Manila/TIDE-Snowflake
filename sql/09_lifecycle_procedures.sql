-- ============================================================================
-- TIDE · 09_lifecycle_procedures.sql
-- Case lifecycle procedures (TASKS.md C-5).
--
-- These are the procedures the Streamlit UI already calls. Names, arities and
-- return shapes are taken from the existing call sites in streamlit/pages/*.py
-- rather than from the original spec — see docs/DECISIONS.md. Two consequences
-- that look odd until you know why:
--
--   * Return keys are LOWERCASE. ui/db.py::call_proc() hands the VARIANT back
--     as a dict and callers read result.get("case_id") / result.get("success").
--   * CLOSE_CASE has two arities: (case_id, closed_by) from the customer page
--     and (case_id, closed_by, close_reason) from the escalation console.
--
-- Actor identity is never passed in. The UI sends no agent or approver id, so
-- every procedure resolves it from CURRENT_USER().
--
-- UI-facing procedures return {"error": ...} rather than raising: call_proc()
-- turns an exception into a red banner and a null result, which loses the
-- reason. TRANSITION_STATE is the exception — it raises, because an illegal
-- transition must write nothing (DETAILS.md §8).
--
-- Every procedure here is a pipeline step, so each writes one PIPELINE_LOG row
-- (CLAUDE.md definition of done). The read-only agent tools in
-- 06_investigation_tools.sql deliberately do not.
--
-- Pure SQL over existing tables: unaffected by any Cortex entitlement block.
--
-- Idempotent: safe to re-run
-- ============================================================================

USE DATABASE TIDE;
USE SCHEMA TRIAGE;

-- ---------------------------------------------------------------------------
-- IS_LEGAL_TRANSITION — the DETAILS.md §8 state machine, in one place.
--
-- Self-transition is always legal (idempotent retries). `closed` is terminal.
-- An unknown/absent from-status is treated as "(new)", which may only open into
-- pending_triage or awaiting_customer_proof.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION IS_LEGAL_TRANSITION(FROM_STATUS VARCHAR, TO_STATUS VARCHAR)
RETURNS BOOLEAN
COMMENT = 'True if a case may move from FROM_STATUS to TO_STATUS per DETAILS.md section 8.'
AS
$$
    FROM_STATUS = TO_STATUS
    OR ARRAY_CONTAINS(
        TO_STATUS::VARIANT,
        CASE FROM_STATUS
            WHEN 'pending_triage' THEN ARRAY_CONSTRUCT(
                'awaiting_customer_proof', 'awaiting_customer_decision',
                'awaiting_approval', 'approved_executing',
                'escalated_human_required', 'closed')
            WHEN 'awaiting_customer_proof'    THEN ARRAY_CONSTRUCT('pending_triage', 'closed')
            WHEN 'awaiting_customer_decision' THEN ARRAY_CONSTRUCT('escalated_human_required', 'closed')
            WHEN 'awaiting_approval'          THEN ARRAY_CONSTRUCT('approved_executing', 'rejected_human_required', 'closed')
            WHEN 'approved_executing'         THEN ARRAY_CONSTRUCT('resolved', 'closed')
            WHEN 'rejected_human_required'    THEN ARRAY_CONSTRUCT('resolved', 'closed')
            WHEN 'escalated_human_required'   THEN ARRAY_CONSTRUCT('resolved', 'closed')
            WHEN 'resolved'                   THEN ARRAY_CONSTRUCT('closed')
            WHEN 'closed'                     THEN ARRAY_CONSTRUCT()
            ELSE ARRAY_CONSTRUCT('pending_triage', 'awaiting_customer_proof')
        END)
$$;

-- ---------------------------------------------------------------------------
-- REQUIRES_PROOF — DETAILS.md §7.1. Which subtypes gate on a photo.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION REQUIRES_PROOF(SUBTYPE VARCHAR)
RETURNS BOOLEAN
COMMENT = 'True if the dispute subtype requires photo proof before triage (DETAILS.md section 7.1).'
AS
$$
    ARRAY_CONTAINS(
        SUBTYPE::VARIANT,
        ARRAY_CONSTRUCT('not_as_described', 'damaged_goods', 'wrong_item', 'partial_fulfillment'))
$$;

-- ---------------------------------------------------------------------------
-- IS_KNOWN_SUBTYPE — the 12 canonical subtypes, DETAILS.md §7.1.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION IS_KNOWN_SUBTYPE(SUBTYPE VARCHAR)
RETURNS BOOLEAN
COMMENT = 'True if the subtype is one of the 12 canonical values (DETAILS.md section 7.1).'
AS
$$
    ARRAY_CONTAINS(
        SUBTYPE::VARIANT,
        ARRAY_CONSTRUCT(
            'duplicate_charge', 'not_as_described', 'damaged_goods', 'wrong_item',
            'partial_fulfillment', 'return_request', 'changed_mind', 'other',
            'non_receipt', 'delayed', 'exception', 'lost'))
$$;

-- ---------------------------------------------------------------------------
-- TRANSITION_STATE — the only writer of status_changed events.
--
-- Raises on an illegal transition and writes nothing. Every procedure below
-- goes through here rather than inserting the event itself, so §8 legality is
-- enforced in exactly one place.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE PROCEDURE TRANSITION_STATE(
    CASE_ID VARCHAR, TO_STATUS VARCHAR, ACTOR_TYPE VARCHAR,
    ACTOR_ID VARCHAR, REASON VARCHAR)
RETURNS VARIANT
LANGUAGE SQL
COMMENT = 'Internal. Validate a case state transition against DETAILS.md section 8 and append the status_changed event. Raises and writes nothing if the transition is illegal.'
EXECUTE AS OWNER
AS
$$
DECLARE
    from_status VARCHAR;
    illegal_transition EXCEPTION (-20001, 'Illegal state transition');
    case_not_found     EXCEPTION (-20002, 'Case not found');
BEGIN
    SELECT v.current_status INTO :from_status
    FROM TIDE.TRIAGE.V_CASE_CURRENT v
    WHERE v.case_id = :CASE_ID;

    IF (from_status IS NULL) THEN
        RAISE case_not_found;
    END IF;

    IF (NOT TIDE.TRIAGE.IS_LEGAL_TRANSITION(:from_status, :TO_STATUS)) THEN
        RAISE illegal_transition;
    END IF;

    INSERT INTO TIDE.TRIAGE.CASE_EVENTS (case_id, event_type, actor_type, actor_id, payload)
    SELECT :CASE_ID, 'status_changed', :ACTOR_TYPE, :ACTOR_ID,
           OBJECT_CONSTRUCT('from', :from_status, 'to', :TO_STATUS, 'reason', :REASON);

    RETURN OBJECT_CONSTRUCT('success', TRUE, 'from', :from_status, 'to', :TO_STATUS);
END;
$$;

-- ---------------------------------------------------------------------------
-- POST_MESSAGE — append-only CHAT insert.
--
-- Idempotent when an event key is supplied: a retried write with the same key
-- is a no-op, so a double-submit from the UI cannot duplicate a message.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE PROCEDURE POST_MESSAGE(
    CASE_ID VARCHAR, SENDER_TYPE VARCHAR, SENDER_ID VARCHAR,
    CONTENT VARCHAR, EVENT_KEY VARCHAR)
RETURNS VARIANT
LANGUAGE SQL
COMMENT = 'Internal. Append one message to TRIAGE.CHAT. Pass an event key to make a retry a no-op.'
EXECUTE AS OWNER
AS
$$
DECLARE
    existing VARCHAR;
BEGIN
    IF (EVENT_KEY IS NOT NULL) THEN
        SELECT c.message_id INTO :existing
        FROM TIDE.TRIAGE.CHAT c
        WHERE c.case_id = :CASE_ID AND c.metadata:event_key::VARCHAR = :EVENT_KEY
        LIMIT 1;

        IF (existing IS NOT NULL) THEN
            RETURN OBJECT_CONSTRUCT('success', TRUE, 'message_id', :existing, 'deduped', TRUE);
        END IF;
    END IF;

    INSERT INTO TIDE.TRIAGE.CHAT (case_id, sender_type, sender_id, content, metadata)
    SELECT :CASE_ID, :SENDER_TYPE, :SENDER_ID, :CONTENT,
           OBJECT_CONSTRUCT_KEEP_NULL('event_key', :EVENT_KEY);

    RETURN OBJECT_CONSTRUCT('success', TRUE, 'deduped', FALSE);
END;
$$;

-- ---------------------------------------------------------------------------
-- OPEN_CASE — customer starts a dispute.
--
-- The only procedure whose success is signalled by `case_id` rather than
-- `success`; 1_Customer.py reads result.get("case_id").
-- ---------------------------------------------------------------------------
CREATE OR REPLACE PROCEDURE OPEN_CASE(ORDER_ID VARCHAR, SUBTYPE VARCHAR, RESOLUTION VARCHAR)
RETURNS VARIANT
LANGUAGE SQL
COMMENT = 'Open a dispute case for one of the caller''s orders. Input: order_id, dispute subtype, resolution preference. Returns {case_id, reference_number, status} or {error}. One open case per order; a proof-required subtype starts in awaiting_customer_proof.'
EXECUTE AS OWNER
AS
$$
DECLARE
    customer   VARCHAR DEFAULT CURRENT_USER();
    order_ok   VARCHAR;
    open_case  VARCHAR;
    new_case   VARCHAR;
    ref_no     VARCHAR;
    start_at   VARCHAR;
    err        VARCHAR;
BEGIN
    IF (NOT TIDE.TRIAGE.IS_KNOWN_SUBTYPE(:SUBTYPE)) THEN
        RETURN OBJECT_CONSTRUCT('error', 'Unknown dispute subtype: ' || :SUBTYPE);
    END IF;

    -- The order must exist and belong to the caller. Scoping here rather than
    -- trusting the UI keeps the check on the owner's side of the boundary.
    -- Aliased throughout: the parameter names shadow the column names.
    SELECT o.order_id INTO :order_ok
    FROM TIDE.RETAIL.ORDERS o
    WHERE o.order_id = :ORDER_ID AND o.customer_id = :customer;

    IF (order_ok IS NULL) THEN
        RETURN OBJECT_CONSTRUCT('error', 'Order not found for this customer.');
    END IF;

    -- Order must be in a disputable state — DETAILS.md §12 ineligible_order_state.
    -- Cancelled and returned orders cannot be disputed; any other status is fine.
    DECLARE
        order_status VARCHAR;
    BEGIN
        SELECT o.status INTO :order_status
        FROM TIDE.RETAIL.ORDERS o
        WHERE o.order_id = :ORDER_ID;

        IF (order_status IN ('cancelled', 'returned')) THEN
            RETURN OBJECT_CONSTRUCT(
                'error', 'ineligible_order_state',
                'detail', 'This order is not in a state that supports a dispute (status: ' || :order_status || ').');
        END IF;
    END;

    -- One open case per order — DETAILS.md §12 duplicate_case.
    SELECT v.case_id INTO :open_case
    FROM TIDE.TRIAGE.V_CASE_CURRENT v
    WHERE v.order_id = :ORDER_ID
      AND v.customer_id = :customer
      AND v.current_status NOT IN ('closed', 'resolved')
    LIMIT 1;

    IF (open_case IS NOT NULL) THEN
        RETURN OBJECT_CONSTRUCT(
            'error', 'This order already has an open case.',
            'case_id', :open_case);
    END IF;

    new_case := UUID_STRING();
    start_at := IFF(TIDE.TRIAGE.REQUIRES_PROOF(:SUBTYPE), 'awaiting_customer_proof', 'pending_triage');

    -- NEXTVAL is taken inline in the INSERT. Snowflake Scripting cannot resolve
    -- a dotted sequence reference in a `SELECT ... INTO`, so the reference
    -- number is read back afterwards rather than computed into a variable.
    INSERT INTO TIDE.TRIAGE.CASES
        (case_id, reference_number, order_id, customer_id, dispute_type,
         dispute_subtype, resolution_preference, proof_required)
    SELECT :new_case,
           'TIDE-' || LPAD(TIDE.TRIAGE.CASE_SEQ.NEXTVAL::VARCHAR, 5, '0'),
           :ORDER_ID, :customer,
           IFF(:SUBTYPE IN ('non_receipt', 'delayed', 'exception', 'lost'),
               'delivery', 'refund'),
           :SUBTYPE, :RESOLUTION, TIDE.TRIAGE.REQUIRES_PROOF(:SUBTYPE);

    SELECT c.reference_number INTO :ref_no
    FROM TIDE.TRIAGE.CASES c WHERE c.case_id = :new_case;

    INSERT INTO TIDE.TRIAGE.CASE_EVENTS (case_id, event_type, actor_type, actor_id, payload)
    SELECT :new_case, 'case_created', 'customer', :customer,
           OBJECT_CONSTRUCT('order_id', :ORDER_ID, 'subtype', :SUBTYPE,
                            'resolution_preference', :RESOLUTION);

    CALL TIDE.TRIAGE.TRANSITION_STATE(
        :new_case, :start_at, 'system', :customer, 'Case opened');

    INSERT INTO TIDE.EXECUTION.PIPELINE_LOG (case_id, component, status, detail)
    SELECT :new_case, 'OPEN_CASE', 'completed',
           OBJECT_CONSTRUCT('order_id', :ORDER_ID, 'subtype', :SUBTYPE, 'status', :start_at);

    RETURN OBJECT_CONSTRUCT(
        'case_id', :new_case, 'reference_number', :ref_no, 'status', :start_at);
EXCEPTION
    WHEN OTHER THEN
        err := SQLERRM;
        INSERT INTO TIDE.EXECUTION.PIPELINE_LOG (case_id, component, status, detail)
        SELECT NULL, 'OPEN_CASE', 'failed', OBJECT_CONSTRUCT('error', :err);
        RETURN OBJECT_CONSTRUCT('error', :err);
END;
$$;

-- ---------------------------------------------------------------------------
-- CLOSE_CASE — two arities. The customer page passes ('customer'); the
-- escalation console passes ('agent', <reason text>).
-- Close reasons per DETAILS.md §14: resolved | unresponsive | duplicate.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE PROCEDURE CLOSE_CASE(CASE_ID VARCHAR, CLOSED_BY VARCHAR, CLOSE_REASON VARCHAR)
RETURNS VARIANT
LANGUAGE SQL
COMMENT = 'Close a case. Input: case_id, who closed it (customer|agent|timeout), and the close reason. Returns {success} or {success:false, error}. Closed is terminal.'
EXECUTE AS OWNER
AS
$$
DECLARE
    err VARCHAR;
BEGIN
    CALL TIDE.TRIAGE.TRANSITION_STATE(
        :CASE_ID, 'closed', :CLOSED_BY, CURRENT_USER(), :CLOSE_REASON);

    INSERT INTO TIDE.TRIAGE.CASE_EVENTS (case_id, event_type, actor_type, actor_id, payload)
    SELECT :CASE_ID, 'closed', :CLOSED_BY, CURRENT_USER(),
           OBJECT_CONSTRUCT('reason', :CLOSE_REASON, 'closed_by', :CLOSED_BY);

    INSERT INTO TIDE.EXECUTION.PIPELINE_LOG (case_id, component, status, detail)
    SELECT :CASE_ID, 'CLOSE_CASE', 'completed',
           OBJECT_CONSTRUCT('closed_by', :CLOSED_BY, 'reason', :CLOSE_REASON);

    RETURN OBJECT_CONSTRUCT('success', TRUE);
EXCEPTION
    WHEN OTHER THEN
        err := SQLERRM;
        INSERT INTO TIDE.EXECUTION.PIPELINE_LOG (case_id, component, status, detail)
        SELECT :CASE_ID, 'CLOSE_CASE', 'failed', OBJECT_CONSTRUCT('error', :err);
        RETURN OBJECT_CONSTRUCT('success', FALSE, 'error', :err);
END;
$$;

CREATE OR REPLACE PROCEDURE CLOSE_CASE(CASE_ID VARCHAR, CLOSED_BY VARCHAR)
RETURNS VARIANT
LANGUAGE SQL
COMMENT = 'Close a case with the default reason "resolved". Input: case_id, who closed it. Returns {success} or {success:false, error}.'
EXECUTE AS OWNER
AS
$$
DECLARE
    res VARIANT;
BEGIN
    CALL TIDE.TRIAGE.CLOSE_CASE(:CASE_ID, :CLOSED_BY, 'resolved') INTO :res;
    RETURN :res;
END;
$$;

-- ---------------------------------------------------------------------------
-- CLAIM_CASE — opening an unassigned escalated case claims it.
-- A case assigned to someone else is read-only to everyone else (DETAILS.md §14).
-- ---------------------------------------------------------------------------
CREATE OR REPLACE PROCEDURE CLAIM_CASE(CASE_ID VARCHAR)
RETURNS VARIANT
LANGUAGE SQL
COMMENT = 'Claim an unassigned escalated case for the calling agent. Input: case_id. Re-claiming your own case is a no-op; a case held by another agent is refused.'
EXECUTE AS OWNER
AS
$$
DECLARE
    agent      VARCHAR DEFAULT CURRENT_USER();
    holder     VARCHAR;
    found_case VARCHAR;
    err        VARCHAR;
BEGIN
    -- Streamlit in Snowflake runs with owner's rights, so this procedure
    -- cannot infer the caller from CURRENT_ROLE() — every call arrives as
    -- TIDE_ADMIN. The caller is checked explicitly instead. A user absent
    -- from USER_PERSONA is unrestricted, which keeps admin and deploy
    -- paths (including scripts/run_matrix.py) working.
    IF (NOT TIDE.TRIAGE.HAS_PERSONA(:agent, 'escalation')) THEN
        RETURN OBJECT_CONSTRUCT('success', FALSE,
            'error', 'This action is limited to the escalation agent role.');
    END IF;

    SELECT v.case_id, v.assigned_to INTO :found_case, :holder
    FROM TIDE.TRIAGE.V_CASE_CURRENT v
    WHERE v.case_id = :CASE_ID;

    IF (found_case IS NULL) THEN
        RETURN OBJECT_CONSTRUCT('success', FALSE, 'error', 'Case not found.');
    END IF;

    IF (holder IS NOT NULL AND holder <> agent) THEN
        RETURN OBJECT_CONSTRUCT(
            'success', FALSE,
            'error', 'Case is already assigned to ' || :holder || '.');
    END IF;

    IF (holder = agent) THEN
        RETURN OBJECT_CONSTRUCT('success', TRUE, 'assigned_to', :agent, 'claimed', FALSE);
    END IF;

    INSERT INTO TIDE.TRIAGE.CASE_EVENTS (case_id, event_type, actor_type, actor_id, payload)
    SELECT :CASE_ID, 'claimed', 'agent', :agent, OBJECT_CONSTRUCT('assigned_to', :agent);

    INSERT INTO TIDE.EXECUTION.PIPELINE_LOG (case_id, component, status, detail)
    SELECT :CASE_ID, 'CLAIM_CASE', 'completed', OBJECT_CONSTRUCT('assigned_to', :agent);

    RETURN OBJECT_CONSTRUCT('success', TRUE, 'assigned_to', :agent, 'claimed', TRUE);
EXCEPTION
    WHEN OTHER THEN
        err := SQLERRM;
        INSERT INTO TIDE.EXECUTION.PIPELINE_LOG (case_id, component, status, detail)
        SELECT :CASE_ID, 'CLAIM_CASE', 'failed', OBJECT_CONSTRUCT('error', :err);
        RETURN OBJECT_CONSTRUCT('success', FALSE, 'error', :err);
END;
$$;

-- ---------------------------------------------------------------------------
-- APPEAL_CASE — customer appeals an awaiting_customer_decision outcome.
-- Priority comes from REASON_COPY keyed on the decision's invalid reason code
-- (DETAILS.md §12), never hardcoded here.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE PROCEDURE APPEAL_CASE(CASE_ID VARCHAR)
RETURNS VARIANT
LANGUAGE SQL
COMMENT = 'Appeal a decision that closed a path to the customer. Input: case_id. Moves the case to escalated_human_required and records the appeal priority from REASON_COPY.'
EXECUTE AS OWNER
AS
$$
DECLARE
    code     VARCHAR;
    priority VARCHAR DEFAULT 'normal';
    err      VARCHAR;
BEGIN
    SELECT e.payload:invalid_reason_code::VARCHAR INTO :code
    FROM TIDE.TRIAGE.CASE_EVENTS e
    WHERE e.case_id = :CASE_ID AND e.event_type = 'decision_made'
    ORDER BY e.occurred_at DESC
    LIMIT 1;

    IF (code IS NOT NULL) THEN
        SELECT rc.appeal_priority INTO :priority
        FROM TIDE.DECISION.REASON_COPY rc
        WHERE rc.invalid_reason_code = :code;
    END IF;

    CALL TIDE.TRIAGE.TRANSITION_STATE(
        :CASE_ID, 'escalated_human_required', 'customer', CURRENT_USER(),
        'Customer appealed');

    INSERT INTO TIDE.TRIAGE.CASE_EVENTS (case_id, event_type, actor_type, actor_id, payload)
    SELECT :CASE_ID, 'appealed', 'customer', CURRENT_USER(),
           OBJECT_CONSTRUCT_KEEP_NULL('invalid_reason_code', :code, 'priority', :priority);

    INSERT INTO TIDE.EXECUTION.PIPELINE_LOG (case_id, component, status, detail)
    SELECT :CASE_ID, 'APPEAL_CASE', 'completed',
           OBJECT_CONSTRUCT_KEEP_NULL('invalid_reason_code', :code, 'priority', :priority);

    RETURN OBJECT_CONSTRUCT('success', TRUE, 'priority', :priority);
EXCEPTION
    WHEN OTHER THEN
        err := SQLERRM;
        INSERT INTO TIDE.EXECUTION.PIPELINE_LOG (case_id, component, status, detail)
        SELECT :CASE_ID, 'APPEAL_CASE', 'failed', OBJECT_CONSTRUCT('error', :err);
        RETURN OBJECT_CONSTRUCT('success', FALSE, 'error', :err);
END;
$$;

-- ---------------------------------------------------------------------------
-- RESUME_INTAKE — awaiting_customer_proof → pending_triage once a proof exists.
-- The composer stays locked until at least one upload (DETAILS.md §14).
-- ---------------------------------------------------------------------------
CREATE OR REPLACE PROCEDURE RESUME_INTAKE(CASE_ID VARCHAR)
RETURNS VARIANT
LANGUAGE SQL
COMMENT = 'Move a case waiting on proof back into triage once at least one proof file is registered. Input: case_id. Refused if no proof exists yet.'
EXECUTE AS OWNER
AS
$$
DECLARE
    proof_count NUMBER DEFAULT 0;
    err         VARCHAR;
BEGIN
    SELECT COUNT(*) INTO :proof_count
    FROM TIDE.INVESTIGATION.PROOF_FILES pf
    WHERE pf.case_id = :CASE_ID;

    IF (proof_count = 0) THEN
        RETURN OBJECT_CONSTRUCT(
            'success', FALSE, 'error', 'No proof uploaded for this case yet.');
    END IF;

    CALL TIDE.TRIAGE.TRANSITION_STATE(
        :CASE_ID, 'pending_triage', 'system', CURRENT_USER(), 'Proof received');

    INSERT INTO TIDE.EXECUTION.PIPELINE_LOG (case_id, component, status, detail)
    SELECT :CASE_ID, 'RESUME_INTAKE', 'completed', OBJECT_CONSTRUCT('proof_count', :proof_count);

    RETURN OBJECT_CONSTRUCT('success', TRUE, 'proof_count', :proof_count);
EXCEPTION
    WHEN OTHER THEN
        err := SQLERRM;
        INSERT INTO TIDE.EXECUTION.PIPELINE_LOG (case_id, component, status, detail)
        SELECT :CASE_ID, 'RESUME_INTAKE', 'failed', OBJECT_CONSTRUCT('error', :err);
        RETURN OBJECT_CONSTRUCT('success', FALSE, 'error', :err);
END;
$$;

-- ---------------------------------------------------------------------------
-- AGENT_MESSAGE — escalation agent chat turn.
-- Only the assigned agent may speak on a claimed case.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE PROCEDURE AGENT_MESSAGE(CASE_ID VARCHAR, CONTENT VARCHAR)
RETURNS VARIANT
LANGUAGE SQL
COMMENT = 'Post an escalation agent message to the case chat. Input: case_id, message text. Only the agent the case is assigned to may post.'
EXECUTE AS OWNER
AS
$$
DECLARE
    agent  VARCHAR DEFAULT CURRENT_USER();
    holder VARCHAR;
    err    VARCHAR;
BEGIN
    -- Streamlit in Snowflake runs with owner's rights, so this procedure
    -- cannot infer the caller from CURRENT_ROLE() — every call arrives as
    -- TIDE_ADMIN. The caller is checked explicitly instead. A user absent
    -- from USER_PERSONA is unrestricted, which keeps admin and deploy
    -- paths (including scripts/run_matrix.py) working.
    IF (NOT TIDE.TRIAGE.HAS_PERSONA(:agent, 'escalation')) THEN
        RETURN OBJECT_CONSTRUCT('success', FALSE,
            'error', 'This action is limited to the escalation agent role.');
    END IF;

    SELECT v.assigned_to INTO :holder
    FROM TIDE.TRIAGE.V_CASE_CURRENT v
    WHERE v.case_id = :CASE_ID;

    IF (holder IS NOT NULL AND holder <> agent) THEN
        RETURN OBJECT_CONSTRUCT(
            'success', FALSE,
            'error', 'Case is assigned to ' || :holder || '.');
    END IF;

    CALL TIDE.TRIAGE.POST_MESSAGE(:CASE_ID, 'agent', :agent, :CONTENT, NULL);

    INSERT INTO TIDE.EXECUTION.PIPELINE_LOG (case_id, component, status, detail)
    SELECT :CASE_ID, 'AGENT_MESSAGE', 'completed', OBJECT_CONSTRUCT('sender_id', :agent);

    RETURN OBJECT_CONSTRUCT('success', TRUE);
EXCEPTION
    WHEN OTHER THEN
        err := SQLERRM;
        INSERT INTO TIDE.EXECUTION.PIPELINE_LOG (case_id, component, status, detail)
        SELECT :CASE_ID, 'AGENT_MESSAGE', 'failed', OBJECT_CONSTRUCT('error', :err);
        RETURN OBJECT_CONSTRUCT('success', FALSE, 'error', :err);
END;
$$;

-- ---------------------------------------------------------------------------
-- ESCALATION_RESOLVE — human specialist resolves a case manually.
-- Writes the structured resolution record; the audit trail is the product.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE PROCEDURE ESCALATION_RESOLVE(
    CASE_ID VARCHAR, RESOLVE_TYPE VARCHAR, AMOUNT FLOAT, NOTE VARCHAR)
RETURNS VARIANT
LANGUAGE SQL
COMMENT = 'Resolve an escalated case manually. Input: case_id, resolution type (refund|replacement), amount, and a note. Writes a completed resolution record and resolves the case.'
EXECUTE AS OWNER
AS
$$
DECLARE
    agent   VARCHAR DEFAULT CURRENT_USER();
    holder  VARCHAR;
    req     VARCHAR;
    err     VARCHAR;
BEGIN
    -- Streamlit in Snowflake runs with owner's rights, so this procedure
    -- cannot infer the caller from CURRENT_ROLE() — every call arrives as
    -- TIDE_ADMIN. The caller is checked explicitly instead. A user absent
    -- from USER_PERSONA is unrestricted, which keeps admin and deploy
    -- paths (including scripts/run_matrix.py) working.
    IF (NOT TIDE.TRIAGE.HAS_PERSONA(:agent, 'escalation')) THEN
        RETURN OBJECT_CONSTRUCT('success', FALSE,
            'error', 'This action is limited to the escalation agent role.');
    END IF;

    SELECT v.assigned_to INTO :holder
    FROM TIDE.TRIAGE.V_CASE_CURRENT v
    WHERE v.case_id = :CASE_ID;

    IF (holder IS NOT NULL AND holder <> agent) THEN
        RETURN OBJECT_CONSTRUCT(
            'success', FALSE,
            'error', 'Case is assigned to ' || :holder || '.');
    END IF;

    req := UUID_STRING();

    INSERT INTO TIDE.EXECUTION.RESOLUTION_REQUESTS
        (request_id, case_id, request_type, status, amount, detail, decided_by)
    SELECT :req, :CASE_ID, :RESOLVE_TYPE, 'completed', :AMOUNT,
           OBJECT_CONSTRUCT('source', 'escalation_manual', 'note', :NOTE), :agent;

    INSERT INTO TIDE.TRIAGE.CASE_EVENTS (case_id, event_type, actor_type, actor_id, payload)
    SELECT :CASE_ID, 'resolution_executed', 'agent', :agent,
           OBJECT_CONSTRUCT('request_id', :req, 'resolution_type', :RESOLVE_TYPE,
                            'amount', :AMOUNT, 'note', :NOTE);

    CALL TIDE.TRIAGE.TRANSITION_STATE(
        :CASE_ID, 'resolved', 'agent', :agent, 'Resolved by escalation agent');

    INSERT INTO TIDE.EXECUTION.PIPELINE_LOG (case_id, component, status, detail)
    SELECT :CASE_ID, 'ESCALATION_RESOLVE', 'completed',
           OBJECT_CONSTRUCT('request_id', :req, 'resolution_type', :RESOLVE_TYPE, 'amount', :AMOUNT);

    RETURN OBJECT_CONSTRUCT('success', TRUE, 'request_id', :req);
EXCEPTION
    WHEN OTHER THEN
        err := SQLERRM;
        INSERT INTO TIDE.EXECUTION.PIPELINE_LOG (case_id, component, status, detail)
        SELECT :CASE_ID, 'ESCALATION_RESOLVE', 'failed', OBJECT_CONSTRUCT('error', :err);
        RETURN OBJECT_CONSTRUCT('success', FALSE, 'error', :err);
END;
$$;

-- ---------------------------------------------------------------------------
-- EXECUTION procedures
-- ---------------------------------------------------------------------------
USE SCHEMA EXECUTION;

-- EXECUTE_RESOLUTION — approver approves; approving executes and resolves
-- (DETAILS.md §14).
CREATE OR REPLACE PROCEDURE EXECUTE_RESOLUTION(CASE_ID VARCHAR, REQUEST_ID VARCHAR)
RETURNS VARIANT
LANGUAGE SQL
COMMENT = 'Approve and execute a pending resolution request. Input: case_id, request_id. Approving executes the resolution and resolves the case in one step.'
EXECUTE AS OWNER
AS
$$
DECLARE
    approver VARCHAR DEFAULT CURRENT_USER();
    req_state VARCHAR;
    err VARCHAR;
BEGIN
    -- Streamlit in Snowflake runs with owner's rights, so this procedure
    -- cannot infer the caller from CURRENT_ROLE() — every call arrives as
    -- TIDE_ADMIN. The caller is checked explicitly instead. A user absent
    -- from USER_PERSONA is unrestricted, which keeps admin and deploy
    -- paths (including scripts/run_matrix.py) working.
    IF (NOT TIDE.TRIAGE.HAS_PERSONA(:approver, 'approver')) THEN
        RETURN OBJECT_CONSTRUCT('success', FALSE,
            'error', 'This action is limited to the approver role.');
    END IF;

    SELECT r.status INTO :req_state
    FROM TIDE.EXECUTION.RESOLUTION_REQUESTS r
    WHERE r.request_id = :REQUEST_ID AND r.case_id = :CASE_ID;

    IF (req_state IS NULL) THEN
        RETURN OBJECT_CONSTRUCT('success', FALSE, 'error', 'Resolution request not found.');
    END IF;

    IF (req_state <> 'pending') THEN
        RETURN OBJECT_CONSTRUCT(
            'success', FALSE,
            'error', 'Request is already ' || :req_state || '.');
    END IF;

    CALL TIDE.TRIAGE.TRANSITION_STATE(
        :CASE_ID, 'approved_executing', 'approver', :approver, 'Approved');

    UPDATE TIDE.EXECUTION.RESOLUTION_REQUESTS
    SET status = 'completed', decided_by = :approver, updated_at = CURRENT_TIMESTAMP()
    WHERE request_id = :REQUEST_ID;

    INSERT INTO TIDE.TRIAGE.CASE_EVENTS (case_id, event_type, actor_type, actor_id, payload)
    SELECT :CASE_ID, 'approved', 'approver', :approver,
           OBJECT_CONSTRUCT('request_id', :REQUEST_ID);

    INSERT INTO TIDE.TRIAGE.CASE_EVENTS (case_id, event_type, actor_type, actor_id, payload)
    SELECT :CASE_ID, 'resolution_executed', 'system', :approver,
           OBJECT_CONSTRUCT('request_id', :REQUEST_ID);

    CALL TIDE.TRIAGE.TRANSITION_STATE(
        :CASE_ID, 'resolved', 'system', :approver, 'Resolution executed');

    INSERT INTO TIDE.EXECUTION.PIPELINE_LOG (case_id, component, status, detail)
    SELECT :CASE_ID, 'EXECUTE_RESOLUTION', 'completed',
           OBJECT_CONSTRUCT('request_id', :REQUEST_ID, 'decided_by', :approver);

    RETURN OBJECT_CONSTRUCT('success', TRUE, 'request_id', :REQUEST_ID);
EXCEPTION
    WHEN OTHER THEN
        err := SQLERRM;
        INSERT INTO TIDE.EXECUTION.PIPELINE_LOG (case_id, component, status, detail)
        SELECT :CASE_ID, 'EXECUTE_RESOLUTION', 'failed', OBJECT_CONSTRUCT('error', :err);
        RETURN OBJECT_CONSTRUCT('success', FALSE, 'error', :err);
END;
$$;

-- REJECT_RESOLUTION — rejection rigor. Minimums come from RULE_CONSTANTS, never
-- hardcoded: DETAILS.md §14 and §6.
CREATE OR REPLACE PROCEDURE REJECT_RESOLUTION(
    CASE_ID VARCHAR, REQUEST_ID VARCHAR, REASON VARCHAR, CITATIONS ARRAY)
RETURNS VARIANT
LANGUAGE SQL
COMMENT = 'Reject a pending resolution request. Input: case_id, request_id, written reason, array of policy ids. The reason length and citation count minimums are read from DECISION.RULE_CONSTANTS and enforced here, not in the UI.'
EXECUTE AS OWNER
AS
$$
DECLARE
    approver  VARCHAR DEFAULT CURRENT_USER();
    req_state VARCHAR;
    min_chars NUMBER;
    min_cites NUMBER;
    err       VARCHAR;
BEGIN
    -- Streamlit in Snowflake runs with owner's rights, so this procedure
    -- cannot infer the caller from CURRENT_ROLE() — every call arrives as
    -- TIDE_ADMIN. The caller is checked explicitly instead. A user absent
    -- from USER_PERSONA is unrestricted, which keeps admin and deploy
    -- paths (including scripts/run_matrix.py) working.
    IF (NOT TIDE.TRIAGE.HAS_PERSONA(:approver, 'approver')) THEN
        RETURN OBJECT_CONSTRUCT('success', FALSE,
            'error', 'This action is limited to the approver role.');
    END IF;

    SELECT rk.value::NUMBER INTO :min_chars
    FROM TIDE.DECISION.RULE_CONSTANTS rk WHERE rk.key = 'MIN_REJECTION_CHARS';

    SELECT rk.value::NUMBER INTO :min_cites
    FROM TIDE.DECISION.RULE_CONSTANTS rk WHERE rk.key = 'MIN_REJECTION_CITATIONS';

    IF (LENGTH(COALESCE(:REASON, '')) < :min_chars) THEN
        RETURN OBJECT_CONSTRUCT(
            'success', FALSE,
            'error', 'Rejection reason must be at least ' || :min_chars || ' characters.');
    END IF;

    IF (ARRAY_SIZE(COALESCE(:CITATIONS, ARRAY_CONSTRUCT())) < :min_cites) THEN
        RETURN OBJECT_CONSTRUCT(
            'success', FALSE,
            'error', 'At least ' || :min_cites || ' policy citation(s) required.');
    END IF;

    SELECT r.status INTO :req_state
    FROM TIDE.EXECUTION.RESOLUTION_REQUESTS r
    WHERE r.request_id = :REQUEST_ID AND r.case_id = :CASE_ID;

    IF (req_state IS NULL) THEN
        RETURN OBJECT_CONSTRUCT('success', FALSE, 'error', 'Resolution request not found.');
    END IF;

    IF (req_state <> 'pending') THEN
        RETURN OBJECT_CONSTRUCT(
            'success', FALSE,
            'error', 'Request is already ' || :req_state || '.');
    END IF;

    CALL TIDE.TRIAGE.TRANSITION_STATE(
        :CASE_ID, 'rejected_human_required', 'approver', :approver, 'Rejected by approver');

    UPDATE TIDE.EXECUTION.RESOLUTION_REQUESTS
    SET status = 'rejected', decided_by = :approver, updated_at = CURRENT_TIMESTAMP()
    WHERE request_id = :REQUEST_ID;

    INSERT INTO TIDE.TRIAGE.CASE_EVENTS (case_id, event_type, actor_type, actor_id, payload)
    SELECT :CASE_ID, 'rejected', 'approver', :approver,
           OBJECT_CONSTRUCT('request_id', :REQUEST_ID, 'reason', :REASON,
                            'citations', :CITATIONS);

    INSERT INTO TIDE.EXECUTION.PIPELINE_LOG (case_id, component, status, detail)
    SELECT :CASE_ID, 'REJECT_RESOLUTION', 'completed',
           OBJECT_CONSTRUCT('request_id', :REQUEST_ID, 'decided_by', :approver,
                            'citation_count', ARRAY_SIZE(:CITATIONS));

    RETURN OBJECT_CONSTRUCT('success', TRUE, 'request_id', :REQUEST_ID);
EXCEPTION
    WHEN OTHER THEN
        err := SQLERRM;
        INSERT INTO TIDE.EXECUTION.PIPELINE_LOG (case_id, component, status, detail)
        SELECT :CASE_ID, 'REJECT_RESOLUTION', 'failed', OBJECT_CONSTRUCT('error', :err);
        RETURN OBJECT_CONSTRUCT('success', FALSE, 'error', :err);
END;
$$;

-- ---------------------------------------------------------------------------
-- INVESTIGATION procedures
-- ---------------------------------------------------------------------------
USE SCHEMA INVESTIGATION;

-- REGISTER_PROOF — record a staged proof image.
--
-- The UI never inserts PROOF_FILES itself: it PUTs to PROOF_STAGE, refreshes
-- the directory table, then calls ANALYZE_PROOF, which calls this.
--
-- Hash note: the directory table exposes MD5, not SHA-256, and pure SQL cannot
-- digest a staged file. MD5 is used as the dedupe key until ANALYZE_PROOF (C-2,
-- Snowpark) reads the bytes for vision and can overwrite the column with a real
-- SHA-256. Dedupe behaviour is correct either way; only the algorithm differs
-- from the column name.
CREATE OR REPLACE PROCEDURE REGISTER_PROOF(CASE_ID VARCHAR, RELATIVE_PATH VARCHAR)
RETURNS VARIANT
LANGUAGE SQL
COMMENT = 'Internal. Record a proof image already staged on PROOF_STAGE. Input: case_id, stage-relative path. Rejects a duplicate image and enforces the per-case upload cap from RULE_CONSTANTS.'
EXECUTE AS OWNER
AS
$$
DECLARE
    max_uploads NUMBER;
    existing    NUMBER DEFAULT 0;
    dup         NUMBER DEFAULT 0;
    file_hash   VARCHAR;
    file_size   NUMBER;
    err         VARCHAR;
BEGIN
    SELECT rk.value::NUMBER INTO :max_uploads
    FROM TIDE.DECISION.RULE_CONSTANTS rk WHERE rk.key = 'MAX_PROOF_UPLOADS';

    SELECT COUNT(*) INTO :existing
    FROM TIDE.INVESTIGATION.PROOF_FILES pf WHERE pf.case_id = :CASE_ID;

    IF (existing >= max_uploads) THEN
        RETURN OBJECT_CONSTRUCT(
            'success', FALSE,
            'error', 'Upload cap reached (' || :max_uploads || ' per case).');
    END IF;

    SELECT MD5, SIZE INTO :file_hash, :file_size
    FROM DIRECTORY(@TIDE.INVESTIGATION.PROOF_STAGE)
    WHERE RELATIVE_PATH = :RELATIVE_PATH;

    IF (file_hash IS NULL) THEN
        RETURN OBJECT_CONSTRUCT(
            'success', FALSE,
            'error', 'File not found on stage. Run ALTER STAGE PROOF_STAGE REFRESH first.');
    END IF;

    SELECT COUNT(*) INTO :dup
    FROM TIDE.INVESTIGATION.PROOF_FILES pf
    WHERE pf.case_id = :CASE_ID AND pf.sha256 = :file_hash;

    IF (dup > 0) THEN
        RETURN OBJECT_CONSTRUCT('success', FALSE, 'error', 'This image was already uploaded.');
    END IF;

    INSERT INTO TIDE.INVESTIGATION.PROOF_FILES
        (case_id, relative_path, content_type, byte_size, sha256, analysis_status)
    SELECT :CASE_ID, :RELATIVE_PATH,
           CASE
               WHEN LOWER(:RELATIVE_PATH) LIKE '%.png'  THEN 'image/png'
               WHEN LOWER(:RELATIVE_PATH) LIKE '%.webp' THEN 'image/webp'
               ELSE 'image/jpeg'
           END,
           :file_size, :file_hash, 'pending';

    INSERT INTO TIDE.TRIAGE.CASE_EVENTS (case_id, event_type, actor_type, actor_id, payload)
    SELECT :CASE_ID, 'proof_uploaded', 'customer', CURRENT_USER(),
           OBJECT_CONSTRUCT('relative_path', :RELATIVE_PATH, 'byte_size', :file_size);

    RETURN OBJECT_CONSTRUCT('success', TRUE, 'relative_path', :RELATIVE_PATH);
EXCEPTION
    WHEN OTHER THEN
        err := SQLERRM;
        RETURN OBJECT_CONSTRUCT('success', FALSE, 'error', :err);
END;
$$;

-- ---------------------------------------------------------------------------
-- Grants — scoped to the persona that actually calls each procedure.
-- ---------------------------------------------------------------------------
GRANT USAGE ON FUNCTION TIDE.TRIAGE.IS_LEGAL_TRANSITION(VARCHAR, VARCHAR) TO ROLE TIDE_ADMIN;
GRANT USAGE ON FUNCTION TIDE.TRIAGE.REQUIRES_PROOF(VARCHAR)               TO ROLE TIDE_ADMIN;
GRANT USAGE ON FUNCTION TIDE.TRIAGE.IS_KNOWN_SUBTYPE(VARCHAR)             TO ROLE TIDE_ADMIN;

-- Customer
GRANT USAGE ON PROCEDURE TIDE.TRIAGE.OPEN_CASE(VARCHAR, VARCHAR, VARCHAR) TO ROLE TIDE_CUSTOMER;
GRANT USAGE ON PROCEDURE TIDE.TRIAGE.CLOSE_CASE(VARCHAR, VARCHAR)         TO ROLE TIDE_CUSTOMER;
GRANT USAGE ON PROCEDURE TIDE.TRIAGE.APPEAL_CASE(VARCHAR)                 TO ROLE TIDE_CUSTOMER;
GRANT USAGE ON PROCEDURE TIDE.TRIAGE.RESUME_INTAKE(VARCHAR)               TO ROLE TIDE_CUSTOMER;

-- Approver
GRANT USAGE ON PROCEDURE TIDE.EXECUTION.EXECUTE_RESOLUTION(VARCHAR, VARCHAR)              TO ROLE TIDE_APPROVER;
GRANT USAGE ON PROCEDURE TIDE.EXECUTION.REJECT_RESOLUTION(VARCHAR, VARCHAR, VARCHAR, ARRAY) TO ROLE TIDE_APPROVER;

-- Escalation
GRANT USAGE ON PROCEDURE TIDE.TRIAGE.CLAIM_CASE(VARCHAR)                            TO ROLE TIDE_ESCALATION;
GRANT USAGE ON PROCEDURE TIDE.TRIAGE.AGENT_MESSAGE(VARCHAR, VARCHAR)                TO ROLE TIDE_ESCALATION;
GRANT USAGE ON PROCEDURE TIDE.TRIAGE.ESCALATION_RESOLVE(VARCHAR, VARCHAR, FLOAT, VARCHAR) TO ROLE TIDE_ESCALATION;
GRANT USAGE ON PROCEDURE TIDE.TRIAGE.CLOSE_CASE(VARCHAR, VARCHAR, VARCHAR)          TO ROLE TIDE_ESCALATION;
