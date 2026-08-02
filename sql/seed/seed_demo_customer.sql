-- ============================================================================
-- TIDE · seed/seed_demo_customer.sql
-- Demo orders owned by whoever deploys, so the customer persona is usable.
--
-- Why this exists, separately from seed_retail.sql:
--
-- The customer views filter on `customer_id = CURRENT_USER()`. Every order in
-- seed_retail.sql belongs to an example.com address, so unless a Snowflake user
-- exists with that exact username the customer page renders EMPTY rather than
-- broken — no error, no traceback, nothing to debug. These rows are owned by
-- CURRENT_USER(), so the page works for whoever ran the deploy.
--
-- It is a separate file on purpose. Each of the 23 orders in seed_retail.sql is
-- engineered to trip one specific decision path and the whole test matrix maps
-- to them; reassigning any of those would break the mapping. These are additive
-- and disposable.
--
-- The five orders below cover the three demo stories in DETAILS.md §17 plus
-- two more guardrails. **The subtype you open each case with is part of the
-- setup** — the same order reaches a different path under a different subtype,
-- so open them exactly as listed:
--
--   Order       Open as             Expect                                    Story
--   ---------------------------------------------------------------------------------
--   ORD-DEMO-1  duplicate_charge    R-01  autonomous refund $41.74            autonomous
--   ORD-DEMO-2  duplicate_charge    R-02  approval queue, $180.00             approval
--   ORD-DEMO-3  duplicate_charge    G-10  ACD, insufficient_evidence          guardrail
--   ORD-DEMO-4  duplicate_charge    G-03  escalated, prior refund cited       guardrail
--   ORD-DEMO-5  non_receipt         G-05  escalated, delivery scan quoted     guardrail
--
-- ORD-DEMO-4 must be opened as duplicate_charge, not changed_mind: G-03 only
-- fires when the resolved type is `refund`, and changed_mind resolves to
-- `return`, which reaches routing and lands on R-25 non_returnable_item
-- instead. Verified the hard way.
--
-- Deliberately no proof-required subtype here: ANALYZE_PROOF does not exist
-- yet, so damaged_goods would stop at G-06/G-09 and make a confusing demo.
-- Add one when vision lands.
--
-- Idempotent: scoped deletes precede inserts. Timestamps are relative to
-- CURRENT_TIMESTAMP() so the seed never goes stale.
-- ============================================================================

USE DATABASE TIDE;
USE SCHEMA RETAIL;

-- ---------------------------------------------------------------------------
-- Scoped teardown. Cases first, because they reference the orders.
-- ---------------------------------------------------------------------------
DELETE FROM TIDE.EXECUTION.CASE_REPORTS        WHERE case_id IN (SELECT case_id FROM TIDE.TRIAGE.CASES WHERE order_id LIKE 'ORD-DEMO-%');
DELETE FROM TIDE.EXECUTION.PIPELINE_LOG        WHERE case_id IN (SELECT case_id FROM TIDE.TRIAGE.CASES WHERE order_id LIKE 'ORD-DEMO-%');
DELETE FROM TIDE.EXECUTION.RESOLUTION_REQUESTS WHERE case_id IN (SELECT case_id FROM TIDE.TRIAGE.CASES WHERE order_id LIKE 'ORD-DEMO-%');
DELETE FROM TIDE.DECISION.DECISIONS            WHERE case_id IN (SELECT case_id FROM TIDE.TRIAGE.CASES WHERE order_id LIKE 'ORD-DEMO-%');
DELETE FROM TIDE.INVESTIGATION.EVIDENCE_BUNDLES WHERE case_id IN (SELECT case_id FROM TIDE.TRIAGE.CASES WHERE order_id LIKE 'ORD-DEMO-%');
DELETE FROM TIDE.TRIAGE.CASE_EVENTS            WHERE case_id IN (SELECT case_id FROM TIDE.TRIAGE.CASES WHERE order_id LIKE 'ORD-DEMO-%');
DELETE FROM TIDE.TRIAGE.CHAT                   WHERE case_id IN (SELECT case_id FROM TIDE.TRIAGE.CASES WHERE order_id LIKE 'ORD-DEMO-%');
DELETE FROM TIDE.TRIAGE.CASES                  WHERE order_id LIKE 'ORD-DEMO-%';

DELETE FROM TRACKING_EVENTS WHERE shipment_id LIKE 'SHP-DEMO-%';
DELETE FROM SHIPMENTS       WHERE shipment_id LIKE 'SHP-DEMO-%';
DELETE FROM REFUNDS         WHERE refund_id   LIKE 'REF-DEMO-%';
DELETE FROM PAYMENTS        WHERE payment_id  LIKE 'PAY-DEMO-%';
DELETE FROM ORDER_ITEMS     WHERE item_id     LIKE 'IT-DEMO-%';
DELETE FROM ORDERS          WHERE order_id    LIKE 'ORD-DEMO-%';

-- ---------------------------------------------------------------------------
-- ORDERS — customer_id is CURRENT_USER(), which is the whole point
-- ---------------------------------------------------------------------------
INSERT INTO ORDERS (order_id, customer_id, status, total_amount, shipping_fee, placed_at, fulfilled_at, delivered_at, estimated_delivery)
SELECT 'ORD-DEMO-1', CURRENT_USER(), 'fulfilled',  41.74, 4.99, DATEADD('day',-4,CURRENT_TIMESTAMP()), DATEADD('day',-3,CURRENT_TIMESTAMP()), NULL, DATEADD('day',1,CURRENT_TIMESTAMP())
UNION ALL SELECT 'ORD-DEMO-2', CURRENT_USER(), 'fulfilled', 180.00, 5.99, DATEADD('day',-5,CURRENT_TIMESTAMP()), DATEADD('day',-4,CURRENT_TIMESTAMP()), NULL, DATEADD('day',1,CURRENT_TIMESTAMP())
UNION ALL SELECT 'ORD-DEMO-3', CURRENT_USER(), 'fulfilled',  29.95, 4.99, DATEADD('day',-3,CURRENT_TIMESTAMP()), DATEADD('day',-2,CURRENT_TIMESTAMP()), NULL, DATEADD('day',2,CURRENT_TIMESTAMP())
UNION ALL SELECT 'ORD-DEMO-4', CURRENT_USER(), 'delivered',  53.89, 4.99, DATEADD('day',-9,CURRENT_TIMESTAMP()), DATEADD('day',-8,CURRENT_TIMESTAMP()), DATEADD('day',-6,CURRENT_TIMESTAMP()), DATEADD('day',-6,CURRENT_TIMESTAMP())
UNION ALL SELECT 'ORD-DEMO-5', CURRENT_USER(), 'delivered',  69.99, 5.99, DATEADD('day',-5,CURRENT_TIMESTAMP()), DATEADD('day',-4,CURRENT_TIMESTAMP()), DATEADD('day',-2,CURRENT_TIMESTAMP()), DATEADD('day',-2,CURRENT_TIMESTAMP());

-- ---------------------------------------------------------------------------
-- ORDER_ITEMS — SKUs reused from seed_retail so stock lookups resolve
-- ---------------------------------------------------------------------------
INSERT INTO ORDER_ITEMS (item_id, order_id, sku, product_name, quantity, unit_price)
SELECT 'IT-DEMO-1','ORD-DEMO-1','SKU-BLNK-01','Knit throw blanket',1,36.75
UNION ALL SELECT 'IT-DEMO-2','ORD-DEMO-2','SKU-WTCH-01','Fitness watch',2,87.00
UNION ALL SELECT 'IT-DEMO-3','ORD-DEMO-3','SKU-CHRG-01','Charging station',1,24.96
UNION ALL SELECT 'IT-DEMO-4','ORD-DEMO-4','SKU-LAMP-01','Desk lamp',1,48.90
UNION ALL SELECT 'IT-DEMO-5','ORD-DEMO-5','SKU-BAGP-01','Laptop backpack',1,64.00;

-- ---------------------------------------------------------------------------
-- PAYMENTS
-- DEMO-1 and DEMO-2 carry TWO confirmed charges: the duplicate-charge evidence
-- G-10 requires. DEMO-3 carries one, so the same claim is blocked.
-- ---------------------------------------------------------------------------
INSERT INTO PAYMENTS (payment_id, order_id, status, amount, method, paid_at)
SELECT 'PAY-DEMO-1A','ORD-DEMO-1','confirmed', 41.74,'card',           DATEADD('day',-4,CURRENT_TIMESTAMP())
UNION ALL SELECT 'PAY-DEMO-1B','ORD-DEMO-1','confirmed', 41.74,'card',           DATEADD('day',-4,CURRENT_TIMESTAMP())
UNION ALL SELECT 'PAY-DEMO-2A','ORD-DEMO-2','confirmed',180.00,'card',           DATEADD('day',-5,CURRENT_TIMESTAMP())
UNION ALL SELECT 'PAY-DEMO-2B','ORD-DEMO-2','confirmed',180.00,'card',           DATEADD('day',-5,CURRENT_TIMESTAMP())
UNION ALL SELECT 'PAY-DEMO-3A','ORD-DEMO-3','confirmed', 29.95,'digital_wallet', DATEADD('day',-3,CURRENT_TIMESTAMP())
UNION ALL SELECT 'PAY-DEMO-4A','ORD-DEMO-4','confirmed', 53.89,'card',           DATEADD('day',-9,CURRENT_TIMESTAMP())
UNION ALL SELECT 'PAY-DEMO-5A','ORD-DEMO-5','confirmed', 69.99,'card',           DATEADD('day',-5,CURRENT_TIMESTAMP());

-- ---------------------------------------------------------------------------
-- REFUNDS — the prior payout that makes DEMO-4 trip G-03
-- ---------------------------------------------------------------------------
INSERT INTO REFUNDS (refund_id, order_id, amount, reason, processed_at)
SELECT 'REF-DEMO-4', 'ORD-DEMO-4', 53.89, 'Goodwill refund issued earlier', DATEADD('day',-4,CURRENT_TIMESTAMP());

-- ---------------------------------------------------------------------------
-- SHIPMENTS + TRACKING — DEMO-5 is delivered with a signed scan, so a
-- non_receipt claim against it trips G-05 with the evidence quoted back.
-- Event ids sort chronologically within the shipment; see sql/seed/README.md.
-- ---------------------------------------------------------------------------
INSERT INTO SHIPMENTS (shipment_id, order_id, carrier, tracking_number, status, estimated_delivery, delivered_at)
SELECT 'SHP-DEMO-4','ORD-DEMO-4','Arrowline Logistics','AL-DEMO-004','delivered', DATEADD('day',-6,CURRENT_TIMESTAMP()), DATEADD('day',-6,CURRENT_TIMESTAMP())
UNION ALL SELECT 'SHP-DEMO-5','ORD-DEMO-5','BluePost Express','BP-DEMO-005','delivered', DATEADD('day',-2,CURRENT_TIMESTAMP()), DATEADD('day',-2,CURRENT_TIMESTAMP());

INSERT INTO TRACKING_EVENTS (event_id, shipment_id, event_type, location, occurred_at)
SELECT 'TE-DEMO-4a','SHP-DEMO-4','picked_up','Riverside sort facility', DATEADD('day',-8,CURRENT_TIMESTAMP())
UNION ALL SELECT 'TE-DEMO-4b','SHP-DEMO-4','delivered','Front door',              DATEADD('day',-6,CURRENT_TIMESTAMP())
UNION ALL SELECT 'TE-DEMO-5a','SHP-DEMO-5','picked_up','Harbor sort facility',    DATEADD('day',-4,CURRENT_TIMESTAMP())
UNION ALL SELECT 'TE-DEMO-5b','SHP-DEMO-5','out_for_delivery','Local depot 7',    DATEADD('day',-2,CURRENT_TIMESTAMP())
UNION ALL SELECT 'TE-DEMO-5c','SHP-DEMO-5','delivered','Signed: resident',        DATEADD('day',-2,CURRENT_TIMESTAMP());

-- ---------------------------------------------------------------------------
-- Verify
-- ---------------------------------------------------------------------------
SELECT o.order_id,
       o.customer_id,
       o.total_amount,
       COUNT(DISTINCT p.payment_id) AS confirmed_charges,
       COUNT(DISTINCT r.refund_id)  AS prior_refunds
FROM ORDERS o
LEFT JOIN PAYMENTS p ON p.order_id = o.order_id AND p.status = 'confirmed'
LEFT JOIN REFUNDS  r ON r.order_id = o.order_id
WHERE o.order_id LIKE 'ORD-DEMO-%'
GROUP BY o.order_id, o.customer_id, o.total_amount
ORDER BY o.order_id;
