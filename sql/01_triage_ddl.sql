-- ============================================================================
-- TIDE · 01_triage_ddl.sql
-- TRIAGE schema: cases, case events, chat, sequence, views
-- Idempotent: safe to re-run
-- ============================================================================

USE DATABASE TIDE;

CREATE SCHEMA IF NOT EXISTS TRIAGE
    COMMENT = 'Cases, chat, events, intake procedure, sweeper';

USE SCHEMA TRIAGE;

-- ---------------------------------------------------------------------------
-- Sequence for human-readable reference numbers
-- ---------------------------------------------------------------------------
CREATE SEQUENCE IF NOT EXISTS CASE_SEQ START = 1 INCREMENT = 1;

-- ---------------------------------------------------------------------------
-- CASES — immutable core; mutable state lives in CASE_EVENTS
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS CASES (
    case_id              VARCHAR(36)   DEFAULT UUID_STRING() NOT NULL,
    reference_number     VARCHAR(20)   NOT NULL,
    order_id             VARCHAR(36)   NOT NULL,
    customer_id          VARCHAR(100)  NOT NULL,
    dispute_type         VARCHAR(20)   NOT NULL,       -- refund | delivery
    dispute_subtype      VARCHAR(30)   NOT NULL,       -- 12 canonical subtypes
    resolution_preference VARCHAR(20)  NOT NULL,       -- refund | replacement | return
    intake_summary       VARCHAR,
    proof_required       BOOLEAN       DEFAULT FALSE,
    created_at           TIMESTAMP_TZ  DEFAULT CURRENT_TIMESTAMP(),

    CONSTRAINT pk_cases PRIMARY KEY (case_id)
);

-- ---------------------------------------------------------------------------
-- CASE_EVENTS — append-only; the spine of the system
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS CASE_EVENTS (
    event_id    VARCHAR(36)   DEFAULT UUID_STRING() NOT NULL,
    case_id     VARCHAR(36)   NOT NULL,
    event_key   VARCHAR(100),                          -- idempotency key
    event_type  VARCHAR(30)   NOT NULL,
    actor_type  VARCHAR(20)   NOT NULL,                -- customer | assistant | agent | system
    actor_id    VARCHAR(100),
    payload     VARIANT,
    occurred_at TIMESTAMP_TZ  DEFAULT CURRENT_TIMESTAMP(),

    CONSTRAINT pk_case_events PRIMARY KEY (event_id),
    CONSTRAINT uq_case_events_key UNIQUE (event_key)
);

-- ---------------------------------------------------------------------------
-- CHAT — append-only messages
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS CHAT (
    message_id  VARCHAR(36)   DEFAULT UUID_STRING() NOT NULL,
    case_id     VARCHAR(36)   NOT NULL,
    sender_type VARCHAR(20)   NOT NULL,                -- customer | assistant | agent | system
    sender_id   VARCHAR(100),
    content     VARCHAR,
    metadata    VARIANT,
    created_at  TIMESTAMP_TZ  DEFAULT CURRENT_TIMESTAMP(),

    CONSTRAINT pk_chat PRIMARY KEY (message_id)
);

-- ---------------------------------------------------------------------------
-- V_CASE_CURRENT — the only way the app reads case state
-- Derives current status from the latest status_changed event
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW V_CASE_CURRENT AS
SELECT
    c.case_id,
    c.reference_number,
    c.order_id,
    c.customer_id,
    c.dispute_type,
    c.dispute_subtype,
    c.resolution_preference,
    c.intake_summary,
    c.proof_required,
    c.created_at,
    -- Current status from latest status_changed event
    COALESCE(se.current_status, 'pending_triage')       AS current_status,
    se.status_changed_at,
    -- Assignment (for escalation)
    ae.assigned_to,
    ae.assigned_at,
    -- Close info
    ce.closed_by,
    ce.close_reason,
    ce.closed_at,
    -- Decision info
    de.path_id,
    de.resolution_type,
    de.eligible_amount
FROM CASES c
-- Latest status
LEFT JOIN (
    SELECT
        case_id,
        payload:to::VARCHAR       AS current_status,
        occurred_at               AS status_changed_at,
        ROW_NUMBER() OVER (
            PARTITION BY case_id
            ORDER BY occurred_at DESC
        ) AS rn
    FROM CASE_EVENTS
    WHERE event_type = 'status_changed'
) se ON se.case_id = c.case_id AND se.rn = 1
-- Assignment
LEFT JOIN (
    SELECT
        case_id,
        actor_id                  AS assigned_to,
        occurred_at               AS assigned_at,
        ROW_NUMBER() OVER (
            PARTITION BY case_id
            ORDER BY occurred_at DESC
        ) AS rn
    FROM CASE_EVENTS
    WHERE event_type = 'claimed'
) ae ON ae.case_id = c.case_id AND ae.rn = 1
-- Close
LEFT JOIN (
    SELECT
        case_id,
        actor_id                  AS closed_by,
        payload:reason::VARCHAR   AS close_reason,
        occurred_at               AS closed_at,
        ROW_NUMBER() OVER (
            PARTITION BY case_id
            ORDER BY occurred_at DESC
        ) AS rn
    FROM CASE_EVENTS
    WHERE event_type = 'closed'
) ce ON ce.case_id = c.case_id AND ce.rn = 1
-- Decision
LEFT JOIN (
    SELECT
        case_id,
        payload:path_id::VARCHAR          AS path_id,
        payload:resolution_type::VARCHAR  AS resolution_type,
        payload:eligible_amount::NUMBER(10,2) AS eligible_amount,
        ROW_NUMBER() OVER (
            PARTITION BY case_id
            ORDER BY occurred_at DESC
        ) AS rn
    FROM CASE_EVENTS
    WHERE event_type = 'decision_made'
) de ON de.case_id = c.case_id AND de.rn = 1;

-- ---------------------------------------------------------------------------
-- V_MY_CASES — secure view filtered by CURRENT_USER()
-- ---------------------------------------------------------------------------
CREATE OR REPLACE SECURE VIEW V_MY_CASES AS
SELECT * FROM V_CASE_CURRENT
WHERE customer_id = CURRENT_USER();

-- ---------------------------------------------------------------------------
-- V_MY_ORDERS — secure view filtered by CURRENT_USER()
--
-- Exists so TIDE_CUSTOMER never needs a base-table grant on RETAIL. Per
-- ARCHITECTURE.md §4 the customer role gets own-case views only; the intake
-- order-picker reads this instead of RETAIL.ORDERS.
--
-- Reports facts, not judgements. `status` and the latest-case columns are the
-- state a caller needs to mark an order non-disputable, but this view does not
-- decide that: `ineligible_order_state` and `duplicate_case` are DETAILS.md §12
-- rules and belong to the intake procedure, not to the UI or to this view.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE SECURE VIEW V_MY_ORDERS AS
SELECT
    o.order_id,
    o.status,
    o.total_amount,
    o.shipping_fee,
    o.placed_at,
    o.fulfilled_at,
    o.delivered_at,
    o.estimated_delivery,
    COALESCE(it.item_count, 0)     AS item_count,
    it.item_summary,
    COALESCE(cs.case_count, 0)     AS case_count,
    cs.latest_case_reference,
    cs.latest_case_status,
    cs.latest_case_created_at
FROM TIDE.RETAIL.ORDERS o
-- Item rollup, so the picker can label an order without a second query
LEFT JOIN (
    SELECT
        order_id,
        COUNT(*) AS item_count,
        LISTAGG(product_name, ', ') WITHIN GROUP (ORDER BY item_id) AS item_summary
    FROM TIDE.RETAIL.ORDER_ITEMS
    GROUP BY order_id
) it ON it.order_id = o.order_id
-- Existing cases on this order. case_id breaks the created_at tie so the
-- "latest" case is deterministic.
LEFT JOIN (
    SELECT
        order_id,
        COUNT(*) OVER (PARTITION BY order_id) AS case_count,
        reference_number                      AS latest_case_reference,
        current_status                        AS latest_case_status,
        created_at                            AS latest_case_created_at
    FROM V_CASE_CURRENT
    QUALIFY ROW_NUMBER() OVER (
        PARTITION BY order_id ORDER BY created_at DESC, case_id DESC) = 1
) cs ON cs.order_id = o.order_id
WHERE o.customer_id = CURRENT_USER();

-- ---------------------------------------------------------------------------
-- V_MY_ORDER_ITEMS — secure view filtered by CURRENT_USER()
--
-- Exists so TIDE_CUSTOMER never needs a base-table grant on RETAIL. Backs the
-- affected-items picker, which drives `affected_amount` in DETAILS.md §9;
-- `line_amount` is that per-item arithmetic, precomputed for display only.
-- Items are reachable only through an order the current user owns.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE SECURE VIEW V_MY_ORDER_ITEMS AS
SELECT
    oi.item_id,
    oi.order_id,
    oi.sku,
    oi.product_name,
    oi.quantity,
    oi.unit_price,
    oi.quantity * oi.unit_price AS line_amount
FROM TIDE.RETAIL.ORDER_ITEMS oi
JOIN TIDE.RETAIL.ORDERS o ON o.order_id = oi.order_id
WHERE o.customer_id = CURRENT_USER();

-- ---------------------------------------------------------------------------
-- V_QUEUE_APPROVAL — approver persona queue
-- ---------------------------------------------------------------------------
CREATE OR REPLACE SECURE VIEW V_QUEUE_APPROVAL AS
SELECT
    vc.*,
    DATEDIFF('minute', vc.status_changed_at, CURRENT_TIMESTAMP()) AS age_minutes,
    CASE
        WHEN DATEDIFF('minute', vc.status_changed_at, CURRENT_TIMESTAMP()) < 15  THEN 'fresh'
        WHEN DATEDIFF('minute', vc.status_changed_at, CURRENT_TIMESTAMP()) < 60  THEN 'aging'
        ELSE 'urgent'
    END AS age_bucket
FROM V_CASE_CURRENT vc
WHERE vc.current_status = 'awaiting_approval';

-- ---------------------------------------------------------------------------
-- V_QUEUE_ESCALATION — escalation persona queue
-- ---------------------------------------------------------------------------
CREATE OR REPLACE SECURE VIEW V_QUEUE_ESCALATION AS
SELECT
    vc.*,
    DATEDIFF('minute', vc.status_changed_at, CURRENT_TIMESTAMP()) AS age_minutes,
    CASE
        WHEN DATEDIFF('minute', vc.status_changed_at, CURRENT_TIMESTAMP()) < 15  THEN 'fresh'
        WHEN DATEDIFF('minute', vc.status_changed_at, CURRENT_TIMESTAMP()) < 60  THEN 'aging'
        ELSE 'urgent'
    END AS age_bucket
FROM V_CASE_CURRENT vc
WHERE vc.current_status IN ('escalated_human_required', 'rejected_human_required');

-- ---------------------------------------------------------------------------
-- Grants
-- ---------------------------------------------------------------------------
GRANT USAGE ON SCHEMA TRIAGE TO ROLE TIDE_CUSTOMER;
GRANT USAGE ON SCHEMA TRIAGE TO ROLE TIDE_APPROVER;
GRANT USAGE ON SCHEMA TRIAGE TO ROLE TIDE_ESCALATION;

GRANT SELECT ON VIEW V_MY_CASES TO ROLE TIDE_CUSTOMER;
GRANT SELECT ON VIEW V_QUEUE_APPROVAL TO ROLE TIDE_APPROVER;
GRANT SELECT ON VIEW V_QUEUE_ESCALATION TO ROLE TIDE_ESCALATION;

-- The customer's route to order data. These replace the base-table access that
-- RETAIL currently grants TIDE_CUSTOMER via GRANT SELECT ON ALL TABLES, which
-- contradicts ARCHITECTURE.md §4. That grant is intentionally still in place:
-- the revoke happens once WS-D reads these views instead.
GRANT SELECT ON VIEW V_MY_ORDERS      TO ROLE TIDE_CUSTOMER;
GRANT SELECT ON VIEW V_MY_ORDER_ITEMS TO ROLE TIDE_CUSTOMER;

-- V_CASE_CURRENT is the `cases` logical table of RETAIL.DISPUTES_SV, so anyone
-- querying that semantic view needs to read it directly. The secure queue views
-- above work under owner's rights and never needed this.
--
-- Approver and escalation only. This view is NOT filtered by customer, and
-- TIDE_CUSTOMER must reach case state solely through V_MY_CASES, which is
-- secure and filtered on CURRENT_USER(). Granting it here would let any
-- customer read every case.
--
-- Deliberately no GRANT ... ON ALL/FUTURE VIEWS in TRIAGE: no persona role
-- holds a table grant in this schema, and a blanket view grant would hand
-- V_CASE_CURRENT to TIDE_CUSTOMER. Views here are granted one at a time, on
-- purpose.
GRANT SELECT ON VIEW V_CASE_CURRENT TO ROLE TIDE_APPROVER;
GRANT SELECT ON VIEW V_CASE_CURRENT TO ROLE TIDE_ESCALATION;
