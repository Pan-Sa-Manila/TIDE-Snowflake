-- ============================================================================
-- TIDE · 06_investigation_tools.sql
-- INVESTIGATION schema: the four custom tool procedures the Investigator
-- Cortex Agent calls (agents/investigator.yaml).
--
-- Contract: each procedure returns a VARIANT object whose keys drop straight
-- into the evidence bundle (docs/SCHEMA.md §5). The fields returned are
-- exactly those read by fact derivation (docs/DETAILS.md §9) — nothing more.
--
-- These tools report facts. They never classify, threshold, or judge:
-- no business constants appear here. Thresholds such as STALE_TRANSIT_DAYS
-- live in DECISION.RULE_CONSTANTS and are applied by the decision engine.
--
-- Every procedure returns a well-formed object even when there is no data,
-- so "no record exists" (found = false) is distinguishable from a tool failure.
--
-- Idempotent: safe to re-run
-- ============================================================================

USE DATABASE TIDE;

CREATE SCHEMA IF NOT EXISTS INVESTIGATION
    COMMENT = 'Evidence bundles, proof files + stage, investigator agent, vision';

USE SCHEMA INVESTIGATION;

-- ---------------------------------------------------------------------------
-- ISO_UTC — render a TIMESTAMP_TZ as the UTC ISO-8601 string the bundle uses.
-- The decision engine parses these; it never sees a Snowflake timestamp type.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION ISO_UTC(TS TIMESTAMP_TZ)
RETURNS VARCHAR
COMMENT = 'TIMESTAMP_TZ to UTC ISO-8601 string (YYYY-MM-DDTHH:MM:SSZ). NULL in, NULL out.'
AS
$$
    TO_CHAR(CONVERT_TIMEZONE('UTC', TS), 'YYYY-MM-DD"T"HH24:MI:SS"Z"')
$$;

-- ---------------------------------------------------------------------------
-- GET_SHIPMENT_TIMELINE
-- Feeds bundle.shipment and bundle.tracking_events.
-- DETAILS.md §9 reads: window_basis_date (shipment delivered_at, delivered
-- event time), delivered/lost/exception/in_transit_event (latest of each type),
-- stale_in_transit (in_transit occurred_at), sla_breached (delivered_at vs
-- estimated_delivery). G-05 quotes the delivered event's location and time.
--
-- An order may carry more than one shipment row; the bundle contract is
-- singular, so the most recently completed or scheduled one is chosen and only
-- its events are returned. Mixing events across shipments would corrupt the
-- "latest event of type X" derivation.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE PROCEDURE GET_SHIPMENT_TIMELINE(ORDER_ID VARCHAR)
RETURNS VARIANT
LANGUAGE SQL
COMMENT = 'Shipment and full tracking history for one order. Call this for any delivery dispute (non_receipt, delayed, exception, lost) or when you need delivery dates or proof of delivery. Input: order_id. Returns carrier, estimated_delivery, delivered_at, and every tracking event (event_type, location, occurred_at) oldest first. If the order has no shipment, found is false, shipment is null and tracking_events is empty: that means never shipped, not a failed lookup.'
EXECUTE AS OWNER
AS
$$
DECLARE
    res VARIANT;
BEGIN
    WITH anchor AS (SELECT 1 AS x),
    sh AS (
        SELECT s.shipment_id, s.carrier, s.estimated_delivery, s.delivered_at
        FROM TIDE.RETAIL.SHIPMENTS s
        WHERE s.order_id = :ORDER_ID
        QUALIFY ROW_NUMBER() OVER (
            ORDER BY COALESCE(s.delivered_at, s.estimated_delivery) DESC NULLS LAST,
                     s.shipment_id DESC) = 1
    ),
    ev AS (
        SELECT ARRAY_AGG(OBJECT_CONSTRUCT_KEEP_NULL(
                   'event_type',  t.event_type,
                   'location',    t.location,
                   'occurred_at', ISO_UTC(t.occurred_at)))
                 WITHIN GROUP (ORDER BY t.occurred_at, t.event_id) AS events
        FROM TIDE.RETAIL.TRACKING_EVENTS t
        JOIN sh ON t.shipment_id = sh.shipment_id
    )
    SELECT OBJECT_CONSTRUCT_KEEP_NULL(
        'order_id', :ORDER_ID,
        'found',    sh.shipment_id IS NOT NULL,
        'shipment', IFF(sh.shipment_id IS NULL, NULL, OBJECT_CONSTRUCT_KEEP_NULL(
            'carrier',            sh.carrier,
            'estimated_delivery', ISO_UTC(sh.estimated_delivery),
            'delivered_at',       ISO_UTC(sh.delivered_at))),
        'tracking_events', COALESCE(ev.events, ARRAY_CONSTRUCT())
    )
    INTO :res
    FROM anchor a
    LEFT JOIN sh ON TRUE
    LEFT JOIN ev ON TRUE;

    RETURN :res;
END;
$$;

-- ---------------------------------------------------------------------------
-- GET_PAYMENT_STATUS
-- Feeds bundle.payment.
-- DETAILS.md §9 reads: payment_confirmed (payment.status), total_order_amount
-- (payment.amount as last fallback). G-04 quotes the actual status string.
--
-- The bundle's payment is singular but an order can hold several payment rows —
-- that is the duplicate-charge evidence. The singular object is taken from the
-- most recent row (paid_at descending, unpaid rows last, payment_id as
-- tiebreak) and every row is also returned under `payments` so multiplicity is
-- visible. Status strings are passed through verbatim: deciding which of them
-- counts as confirmed is DETAILS.md §9, not this tool.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE PROCEDURE GET_PAYMENT_STATUS(ORDER_ID VARCHAR)
RETURNS VARIANT
LANGUAGE SQL
COMMENT = 'Payment records for one order. Call this first for every dispute: an unconfirmed payment changes the outcome. Input: order_id. Returns payment (the most recent record: status, amount, method) and payments (every record oldest first, with paid_at) so you can see if the order was charged more than once. If the order has no payment record at all, found is false and payment is null.'
EXECUTE AS OWNER
AS
$$
DECLARE
    res VARIANT;
BEGIN
    WITH anchor AS (SELECT 1 AS x),
    latest AS (
        SELECT p.payment_id, p.status, p.amount, p.method
        FROM TIDE.RETAIL.PAYMENTS p
        WHERE p.order_id = :ORDER_ID
        QUALIFY ROW_NUMBER() OVER (
            ORDER BY p.paid_at DESC NULLS LAST, p.payment_id DESC) = 1
    ),
    all_rows AS (
        SELECT ARRAY_AGG(OBJECT_CONSTRUCT_KEEP_NULL(
                   'status',  p.status,
                   'amount',  p.amount,
                   'method',  p.method,
                   'paid_at', ISO_UTC(p.paid_at)))
                 WITHIN GROUP (ORDER BY p.paid_at NULLS LAST, p.payment_id) AS rows_json
        FROM TIDE.RETAIL.PAYMENTS p
        WHERE p.order_id = :ORDER_ID
    )
    SELECT OBJECT_CONSTRUCT_KEEP_NULL(
        'order_id', :ORDER_ID,
        'found',    latest.payment_id IS NOT NULL,
        'payment',  IFF(latest.payment_id IS NULL, NULL, OBJECT_CONSTRUCT_KEEP_NULL(
            'status', latest.status,
            'amount', latest.amount,
            'method', latest.method)),
        'payments', COALESCE(all_rows.rows_json, ARRAY_CONSTRUCT())
    )
    INTO :res
    FROM anchor a
    LEFT JOIN latest ON TRUE
    LEFT JOIN all_rows ON TRUE;

    RETURN :res;
END;
$$;

-- ---------------------------------------------------------------------------
-- GET_REFUND_HISTORY
-- Feeds bundle.refund_history.
-- DETAILS.md §9 reads: prior_refunds (count + total over these records).
-- G-03 escalates when a refund is sought and prior_refunds > 0, citing both.
-- Count and total are derived by the engine from this list, not precomputed
-- here — one source of truth for the arithmetic.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE PROCEDURE GET_REFUND_HISTORY(ORDER_ID VARCHAR)
RETURNS VARIANT
LANGUAGE SQL
COMMENT = 'Prior refunds already issued against one order. Call this before recommending any refund: a previous refund means duplicate-refund risk. Input: order_id. Returns refund_history, one entry per refund (amount, processed_at) oldest first. An order with no prior refund returns found = false and an empty refund_history list, never null.'
EXECUTE AS OWNER
AS
$$
DECLARE
    res VARIANT;
BEGIN
    WITH agg AS (
        SELECT ARRAY_AGG(OBJECT_CONSTRUCT_KEEP_NULL(
                   'amount',       r.amount,
                   'processed_at', ISO_UTC(r.processed_at)))
                 WITHIN GROUP (ORDER BY r.processed_at, r.refund_id) AS refunds
        FROM TIDE.RETAIL.REFUNDS r
        WHERE r.order_id = :ORDER_ID
    )
    SELECT OBJECT_CONSTRUCT_KEEP_NULL(
        'order_id',       :ORDER_ID,
        -- ARRAY_AGG over an empty group yields [], not NULL, so test the size
        'found',          COALESCE(ARRAY_SIZE(agg.refunds), 0) > 0,
        'refund_history', COALESCE(agg.refunds, ARRAY_CONSTRUCT())
    )
    INTO :res
    FROM agg;

    RETURN :res;
END;
$$;

-- ---------------------------------------------------------------------------
-- CHECK_INVENTORY
-- Feeds bundle.inventory.
-- DETAILS.md §9 reads: inventory_feasible(items) — false if the list is empty,
-- any item has unknown availability, or available < ordered.
--
-- quantity_available is summed across warehouses. quantity_ordered is NOT
-- returned: this tool receives SKUs only and has no order context, so the
-- assembler fills it from the order items. `stock_record_found = false` with a
-- null quantity is the "unknown availability" signal the rule tests for — it is
-- deliberately not collapsed to zero, because unknown and out-of-stock lead to
-- different outcomes.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE PROCEDURE CHECK_INVENTORY(SKUS ARRAY)
RETURNS VARIANT
LANGUAGE SQL
COMMENT = 'Current stock for a list of SKUs. Call this when the resolution under consideration is a replacement, to check it can actually be fulfilled. Input: sku_list, an array of SKU strings. Returns inventory, one entry per requested SKU with quantity_available summed across warehouses. A SKU with no stock record returns quantity_available null and stock_record_found false: that is unknown stock, which is not the same as zero in stock.'
EXECUTE AS OWNER
AS
$$
DECLARE
    res VARIANT;
BEGIN
    WITH req AS (
        SELECT DISTINCT f.value::VARCHAR AS sku
        FROM TABLE(FLATTEN(INPUT => COALESCE(:SKUS, ARRAY_CONSTRUCT()))) f
    ),
    agg AS (
        SELECT r.sku,
               SUM(st.quantity_available) AS qty_available,
               COUNT(st.sku)              AS stock_rows
        FROM req r
        LEFT JOIN TIDE.RETAIL.STOCK st ON st.sku = r.sku
        GROUP BY r.sku
    )
    SELECT OBJECT_CONSTRUCT_KEEP_NULL(
        'inventory', COALESCE(ARRAY_AGG(OBJECT_CONSTRUCT_KEEP_NULL(
            'sku',                agg.sku,
            'quantity_available', IFF(agg.stock_rows = 0, NULL, agg.qty_available),
            'stock_record_found', agg.stock_rows > 0))
              WITHIN GROUP (ORDER BY agg.sku), ARRAY_CONSTRUCT())
    )
    INTO :res
    FROM agg;

    RETURN :res;
END;
$$;

-- ---------------------------------------------------------------------------
-- Grants
-- These are agent tools, invoked inside EXECUTE AS OWNER procedures on the
-- assembly path. Persona roles never call them directly, so they get no
-- USAGE — see AGENTS.md §10.1.
-- ---------------------------------------------------------------------------
GRANT USAGE ON FUNCTION ISO_UTC(TIMESTAMP_TZ)              TO ROLE TIDE_ADMIN;
GRANT USAGE ON PROCEDURE GET_SHIPMENT_TIMELINE(VARCHAR)    TO ROLE TIDE_ADMIN;
GRANT USAGE ON PROCEDURE GET_PAYMENT_STATUS(VARCHAR)       TO ROLE TIDE_ADMIN;
GRANT USAGE ON PROCEDURE GET_REFUND_HISTORY(VARCHAR)       TO ROLE TIDE_ADMIN;
GRANT USAGE ON PROCEDURE CHECK_INVENTORY(ARRAY)            TO ROLE TIDE_ADMIN;
