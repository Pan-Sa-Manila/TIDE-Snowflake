-- ============================================================================
-- TIDE · 07_semantic_view.sql
-- RETAIL.DISPUTES_SV — the Cortex Analyst semantic view the Investigator agent
-- queries for quantitative order facts (docs/SCHEMA.md §7).
--
-- Scope note: creating and querying this view is plain DDL/SQL and works on
-- this account. Reaching it through Cortex Analyst needs AI functions that are
-- blocked here (docs/CAPABILITIES.md §C), so verification stops at
-- DESCRIBE SEMANTIC VIEW plus direct SEMANTIC_VIEW() queries.
--
-- Naming: measures are named for the question they answer, because the agent
-- picks tools and measures by name. Prefer adding a synonym over adding a
-- second near-identical measure.
--
-- Idempotent: safe to re-run
-- ============================================================================

USE DATABASE TIDE;
USE SCHEMA RETAIL;

-- Depends on RETAIL.V_STOCK_BY_SKU, defined in sql/05_retail_ddl.sql. STOCK is
-- keyed (sku, warehouse), so `sku` is not unique and cannot be a relationship
-- target; that view supplies the unique per-SKU grain items_to_stock needs.

-- ---------------------------------------------------------------------------
-- DISPUTES_SV
-- ---------------------------------------------------------------------------
CREATE OR REPLACE SEMANTIC VIEW DISPUTES_SV

    TABLES (
        orders AS TIDE.RETAIL.ORDERS
            PRIMARY KEY (order_id)
            WITH SYNONYMS = ('order','purchase','sale')
            COMMENT = 'One row per customer order. The grain most dispute questions are asked at.',

        order_items AS TIDE.RETAIL.ORDER_ITEMS
            PRIMARY KEY (item_id)
            WITH SYNONYMS = ('line item','products ordered','basket')
            COMMENT = 'Individual products on an order, with quantity and unit price.',

        payments AS TIDE.RETAIL.PAYMENTS
            PRIMARY KEY (payment_id)
            WITH SYNONYMS = ('charge','card charge','payment record')
            COMMENT = 'Payment attempts against an order. More than one confirmed row means the customer was charged twice.',

        refunds AS TIDE.RETAIL.REFUNDS
            PRIMARY KEY (refund_id)
            WITH SYNONYMS = ('money back','reimbursement','refund record')
            COMMENT = 'Refunds already issued against an order.',

        shipments AS TIDE.RETAIL.SHIPMENTS
            PRIMARY KEY (shipment_id)
            WITH SYNONYMS = ('package','parcel','delivery','shipment record')
            COMMENT = 'The physical shipment for an order, with carrier and delivery dates.',

        tracking AS TIDE.RETAIL.TRACKING_EVENTS
            PRIMARY KEY (event_id)
            WITH SYNONYMS = ('tracking','tracking history','carrier scan','parcel movement')
            COMMENT = 'Carrier scan events for a shipment, oldest to newest.',

        stock AS TIDE.RETAIL.V_STOCK_BY_SKU
            PRIMARY KEY (sku)
            WITH SYNONYMS = ('inventory','availability','warehouse stock')
            COMMENT = 'Current stock per SKU, summed across warehouses.',

        cases AS TIDE.TRIAGE.V_CASE_CURRENT
            PRIMARY KEY (case_id)
            WITH SYNONYMS = ('dispute','claim','ticket')
            COMMENT = 'Current state of each dispute case, one row per case.'
    )

    RELATIONSHIPS (
        items_to_orders       AS order_items(order_id)  REFERENCES orders(order_id),
        payments_to_orders    AS payments(order_id)     REFERENCES orders(order_id),
        refunds_to_orders     AS refunds(order_id)      REFERENCES orders(order_id),
        shipments_to_orders   AS shipments(order_id)    REFERENCES orders(order_id),
        tracking_to_shipments AS tracking(shipment_id)  REFERENCES shipments(shipment_id),
        items_to_stock        AS order_items(sku)       REFERENCES stock(sku),
        cases_to_orders       AS cases(order_id)        REFERENCES orders(order_id)
    )

    FACTS (
        orders.order_total   AS orders.total_amount
            WITH SYNONYMS = ('order amount','order value','amount charged'),
        orders.shipping_fee  AS orders.shipping_fee
            WITH SYNONYMS = ('delivery fee','postage'),
        -- Row-level day counts. Selectable and filterable per order; the
        -- decision engine applies the thresholds, this view only measures.
        orders.days_since_delivery AS
            DATEDIFF('day', orders.delivered_at, CURRENT_TIMESTAMP())
            WITH SYNONYMS = ('days since it arrived','age since delivery')
            COMMENT = 'Whole days between delivery and now. Null when the order has not been delivered.',
        orders.days_past_estimated_delivery AS
            DATEDIFF('day', orders.estimated_delivery, COALESCE(orders.delivered_at, CURRENT_TIMESTAMP()))
            WITH SYNONYMS = ('days late','lateness','days past promised date')
            COMMENT = 'Whole days the order ran past its estimated delivery date; uses today when still undelivered. Negative means early.',

        order_items.quantity_ordered AS order_items.quantity
            WITH SYNONYMS = ('units ordered','how many'),
        order_items.line_amount      AS order_items.quantity * order_items.unit_price
            WITH SYNONYMS = ('line total','item total'),
        order_items.unit_price       AS order_items.unit_price
            WITH SYNONYMS = ('price each'),

        payments.payment_amount AS payments.amount
            WITH SYNONYMS = ('amount paid','charge amount'),

        refunds.refund_amount   AS refunds.amount
            WITH SYNONYMS = ('amount refunded','money returned'),

        stock.quantity_available AS stock.quantity_available
            WITH SYNONYMS = ('in stock','on hand','available units'),

        cases.eligible_amount AS cases.eligible_amount
            WITH SYNONYMS = ('decided amount','amount granted')
    )

    DIMENSIONS (
        orders.order_id           AS orders.order_id
            WITH SYNONYMS = ('order number','order reference'),
        orders.customer_id        AS orders.customer_id
            WITH SYNONYMS = ('customer','buyer','shopper'),
        orders.order_status       AS orders.status
            WITH SYNONYMS = ('order state','fulfilment status')
            COMMENT = 'placed | fulfilled | delivered | returned | cancelled',
        orders.placed_at          AS orders.placed_at
            WITH SYNONYMS = ('order date','when ordered'),
        orders.fulfilled_at       AS orders.fulfilled_at
            WITH SYNONYMS = ('dispatch date','when shipped'),
        orders.delivered_at       AS orders.delivered_at
            WITH SYNONYMS = ('delivery date','when it arrived'),
        orders.estimated_delivery AS orders.estimated_delivery
            WITH SYNONYMS = ('promised date','expected delivery','eta'),

        order_items.sku          AS order_items.sku
            WITH SYNONYMS = ('product code','item code'),
        order_items.product_name AS order_items.product_name
            WITH SYNONYMS = ('product','item name','what was ordered'),

        payments.payment_status AS payments.status
            WITH SYNONYMS = ('payment state')
            COMMENT = 'pending | confirmed | failed',
        payments.payment_method AS payments.method
            WITH SYNONYMS = ('how they paid','tender')
            COMMENT = 'card | digital_wallet | bank_transfer | cash_on_delivery',
        payments.paid_at        AS payments.paid_at
            WITH SYNONYMS = ('payment date','when charged'),

        refunds.refund_reason AS refunds.reason
            WITH SYNONYMS = ('why refunded'),
        refunds.processed_at  AS refunds.processed_at
            WITH SYNONYMS = ('refund date','when refunded'),

        shipments.carrier         AS shipments.carrier
            WITH SYNONYMS = ('courier','shipping company'),
        shipments.tracking_number AS shipments.tracking_number
            WITH SYNONYMS = ('tracking id','consignment number'),
        shipments.shipment_status AS shipments.status
            WITH SYNONYMS = ('parcel status','delivery status'),

        tracking.event_type     AS tracking.event_type
            WITH SYNONYMS = ('scan type','movement type')
            COMMENT = 'picked_up | in_transit | out_for_delivery | delivered | delayed | exception | lost',
        tracking.event_location AS tracking.location
            WITH SYNONYMS = ('where','scan location'),
        tracking.occurred_at    AS tracking.occurred_at
            WITH SYNONYMS = ('scan time','event time'),

        stock.sku AS stock.sku
            WITH SYNONYMS = ('product code','item code'),

        cases.case_id          AS cases.case_id,
        cases.reference_number AS cases.reference_number
            WITH SYNONYMS = ('case number','ticket number'),
        cases.dispute_type     AS cases.dispute_type
            WITH SYNONYMS = ('claim type')
            COMMENT = 'refund | delivery',
        cases.dispute_subtype  AS cases.dispute_subtype
            WITH SYNONYMS = ('reason for dispute','complaint type'),
        cases.current_status   AS cases.current_status
            WITH SYNONYMS = ('case state','where the case is')
    )

    METRICS (
        orders.total_order_value AS SUM(orders.order_total)
            WITH SYNONYMS = ('total ordered','order revenue')
            COMMENT = 'Sum of order totals. For a single order this is that order amount.',
        orders.order_count       AS COUNT(orders.order_id)
            WITH SYNONYMS = ('number of orders','how many orders'),

        order_items.total_item_value AS SUM(order_items.line_amount)
            WITH SYNONYMS = ('basket value','sum of line totals')
            COMMENT = 'Sum of quantity times unit price across the items in scope.',

        payments.total_paid    AS SUM(payments.payment_amount)
            WITH SYNONYMS = ('total charged','amount taken'),
        payments.payment_count AS COUNT(payments.payment_id)
            WITH SYNONYMS = ('number of charges','how many times charged')
            COMMENT = 'Count of payment rows. More than one on an order is the duplicate-charge signal.',

        refunds.total_refunded AS SUM(refunds.refund_amount)
            WITH SYNONYMS = ('money back total','total reimbursed')
            COMMENT = 'Sum of refunds already issued. Zero rows means never refunded.',
        refunds.refund_count   AS COUNT(refunds.refund_id)
            WITH SYNONYMS = ('number of refunds','how many refunds'),

        stock.total_available AS SUM(stock.quantity_available)
            WITH SYNONYMS = ('in stock','units available','how many left'),

        -- "Most recent tracking event" as one row. The ordering key is
        -- occurred_at then event_id, matching INVESTIGATION.GET_SHIPMENT_TIMELINE,
        -- so the two never disagree. The event_id tiebreak is load bearing:
        -- out_for_delivery and delivered can share a timestamp, and plain
        -- MAX_BY(occurred_at) then reports the parcel as undelivered.
        tracking.latest_event_at AS MAX(tracking.occurred_at)
            WITH SYNONYMS = ('last scan time','last movement','last update'),
        tracking.latest_event_type AS MAX_BY(tracking.event_type,
                TO_CHAR(CONVERT_TIMEZONE('UTC', tracking.occurred_at), 'YYYYMMDDHH24MISS') || tracking.event_id)
            WITH SYNONYMS = ('last scan','latest status','where the parcel got to'),
        tracking.latest_event_location AS MAX_BY(tracking.location,
                TO_CHAR(CONVERT_TIMEZONE('UTC', tracking.occurred_at), 'YYYYMMDDHH24MISS') || tracking.event_id)
            WITH SYNONYMS = ('last known location','last seen'),

        cases.case_count AS COUNT(cases.case_id)
            WITH SYNONYMS = ('number of cases','how many disputes')
    )

    COMMENT = 'Quantitative order, payment, refund, shipment, inventory and case facts for dispute investigation. Ask here for amounts, counts, dates and lateness. Tracking event sequencing and evidence-bundle shaped lookups belong to the INVESTIGATION tool procedures.';

-- ---------------------------------------------------------------------------
-- Grants
-- The semantic view is reached by the Investigator agent inside EXECUTE AS
-- OWNER procedures, so persona roles get no direct SELECT (AGENTS.md §10.1).
-- ---------------------------------------------------------------------------
GRANT SELECT ON SEMANTIC VIEW DISPUTES_SV TO ROLE TIDE_ADMIN;

-- ============================================================================
-- Verified queries
--
-- These use the SEMANTIC_VIEW() table function, which is plain SQL. Reaching
-- the same measures through Cortex Analyst natural language needs AI functions
-- that are blocked on this account, so that path is deliberately unverified.
--
-- Two usage constraints, both found by testing rather than by reading:
--
-- 1. A child-table metric inner joins to its parent. An order with no refunds
--    returns NO ROW from refunds.total_refunded, not zero. Callers must read
--    "no row" as zero. Order-side metrics (orders.total_order_value) do return
--    the order.
-- 2. A metric cannot be grouped by a dimension of finer grain than the metric's
--    own table. stock.total_available must be grouped by stock.sku, never by
--    order_items.sku, because order_items is the child of stock in
--    items_to_stock.
-- ============================================================================

/*  Total refunded for a given order.
    ORD-1008 -> 53.89 / 1 refund.  ORD-1001 -> no row (no refunds ever issued).

SELECT * FROM SEMANTIC_VIEW(
    DISPUTES_SV
    DIMENSIONS orders.order_id
    METRICS    refunds.total_refunded, refunds.refund_count
) WHERE order_id = 'ORD-1008';

    Most recent tracking event for a given order.
    ORD-1010 -> delivered / Signed: resident.  ORD-1012 -> in_transit /
    Interstate hub.  ORD-1015 -> lost / Last scan: interstate hub.

SELECT * FROM SEMANTIC_VIEW(
    DISPUTES_SV
    DIMENSIONS orders.order_id
    METRICS    tracking.latest_event_at, tracking.latest_event_type,
               tracking.latest_event_location
) WHERE order_id = 'ORD-1012';

    Duplicate-charge signal. ORD-1007 -> 2 charges, 83.48 taken against a
    41.74 order.

SELECT * FROM SEMANTIC_VIEW(
    DISPUTES_SV
    DIMENSIONS orders.order_id
    METRICS    payments.payment_count, payments.total_paid,
               orders.total_order_value
) WHERE order_id = 'ORD-1007';

    Lateness. ORD-1013 -> 5 days past estimate, delivered 3 days ago.
    ORD-1012 -> 6 days past estimate, days_since_delivery null (undelivered).

SELECT * FROM SEMANTIC_VIEW(
    DISPUTES_SV
    DIMENSIONS orders.order_id, orders.order_status
    FACTS      orders.days_past_estimated_delivery, orders.days_since_delivery
) WHERE order_id = 'ORD-1013';

    Inventory, at the stock grain. SKU-CHRN-LE -> 0, SKU-HDPH-01 -> 14.

SELECT * FROM SEMANTIC_VIEW(
    DISPUTES_SV
    DIMENSIONS stock.sku
    METRICS    stock.total_available
) WHERE sku = 'SKU-CHRN-LE';
*/
