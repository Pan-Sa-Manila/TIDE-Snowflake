-- ============================================================================
-- TIDE · seed/seed_demo_customer.sql
-- Demo orders owned by each account that needs a working customer page.
--
-- Why this exists, separately from seed_retail.sql:
--
-- The customer views filter on `customer_id = CURRENT_USER()`. Every order in
-- seed_retail.sql belongs to an example.com address, so unless a Snowflake user
-- exists with that exact username the customer page renders EMPTY rather than
-- broken — no error, no traceback, nothing to debug.
--
-- It is a separate file on purpose. Each of the 23 orders in seed_retail.sql is
-- engineered to trip one specific decision path and the whole test matrix maps
-- to them; reassigning any of those would break the mapping. These are additive
-- and disposable.
--
-- ONE SET PER OWNER. The same five scenarios are seeded for each account in the
-- `owners` CTE, tagged into the id so the sets never collide:
--
--   Tag  Owner                 Why it needs its own orders
--   ------------------------------------------------------------------------
--   ME   CURRENT_USER()        whoever ran the deploy — the developer loop
--   DC   TIDE_DEMO_CUSTOMER    the customer persona used in the demo video
--   JG   TIDE_JUDGE            the evaluator login (sql/14_demo_access.sql)
--
-- Seeding once for CURRENT_USER() was not enough: the demo and judge accounts
-- authenticate fine and then land on an empty page, which reads as a broken
-- submission. TIDE_DEMO_APPROVER and TIDE_DEMO_ESCALATION are deliberately
-- absent — those personas work a queue of other people's cases and never open
-- the customer page.
--
-- The five scenarios cover the three demo stories in DETAILS.md §17 plus two
-- more guardrails. **The subtype you open each case with is part of the
-- setup** — the same order reaches a different path under a different subtype,
-- so open them exactly as listed (`N` is the per-owner tag):
--
--   Order          Open as             Expect                                 Story
--   ---------------------------------------------------------------------------------
--   ORD-DEMO-N-1   duplicate_charge    R-01  autonomous refund $41.74         autonomous
--   ORD-DEMO-N-2   duplicate_charge    R-02  approval queue, $180.00          approval
--   ORD-DEMO-N-3   duplicate_charge    G-10  ACD, insufficient_evidence       guardrail
--   ORD-DEMO-N-4   duplicate_charge    G-03  escalated, prior refund cited    guardrail
--   ORD-DEMO-N-5   non_receipt         G-05  escalated, delivery scan quoted  guardrail
--
-- ORD-DEMO-N-4 must be opened as duplicate_charge, not changed_mind: G-03 only
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
-- The owner tag sits inside the existing 'ORD-DEMO-%' prefix, so these
-- patterns still match every generated set without change.
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
-- ORDERS — customer_id is the owner's username, which is the whole point.
--
-- Day offsets rather than literal dates so the seed never goes stale.
-- DATEADD propagates NULL, so a NULL offset leaves the column NULL: that is how
-- orders 1-3 stay undelivered without an IFF.
-- ---------------------------------------------------------------------------
INSERT INTO ORDERS (order_id, customer_id, status, total_amount, shipping_fee, placed_at, fulfilled_at, delivered_at, estimated_delivery)
WITH owners AS (
    SELECT 'ME' AS tag, CURRENT_USER() AS username
    UNION ALL SELECT 'DC', 'TIDE_DEMO_CUSTOMER'
    UNION ALL SELECT 'JG', 'TIDE_JUDGE'
),
scenarios AS (
    SELECT 1 AS n, 'fulfilled' AS status,  41.74 AS total_amount, 4.99 AS shipping_fee, -4 AS placed_d, -3 AS fulfilled_d, NULL::NUMBER AS delivered_d,  1 AS est_d
    UNION ALL SELECT 2, 'fulfilled', 180.00, 5.99, -5, -4, NULL,  1
    UNION ALL SELECT 3, 'fulfilled',  29.95, 4.99, -3, -2, NULL,  2
    UNION ALL SELECT 4, 'delivered',  53.89, 4.99, -9, -8,   -6, -6
    UNION ALL SELECT 5, 'delivered',  69.99, 5.99, -5, -4,   -2, -2
)
SELECT 'ORD-DEMO-' || o.tag || '-' || s.n,
       o.username,
       s.status,
       s.total_amount,
       s.shipping_fee,
       DATEADD('day', s.placed_d,    CURRENT_TIMESTAMP()),
       DATEADD('day', s.fulfilled_d, CURRENT_TIMESTAMP()),
       DATEADD('day', s.delivered_d, CURRENT_TIMESTAMP()),
       DATEADD('day', s.est_d,       CURRENT_TIMESTAMP())
FROM owners o CROSS JOIN scenarios s;

-- ---------------------------------------------------------------------------
-- ORDER_ITEMS — SKUs reused from seed_retail so stock lookups resolve
-- ---------------------------------------------------------------------------
INSERT INTO ORDER_ITEMS (item_id, order_id, sku, product_name, quantity, unit_price)
WITH owners AS (
    SELECT 'ME' AS tag, CURRENT_USER() AS username
    UNION ALL SELECT 'DC', 'TIDE_DEMO_CUSTOMER'
    UNION ALL SELECT 'JG', 'TIDE_JUDGE'
),
line_items AS (
    SELECT 1 AS n, 'SKU-BLNK-01' AS sku, 'Knit throw blanket' AS product_name, 1 AS quantity, 36.75 AS unit_price
    UNION ALL SELECT 2, 'SKU-WTCH-01', 'Fitness watch',    2, 87.00
    UNION ALL SELECT 3, 'SKU-CHRG-01', 'Charging station', 1, 24.96
    UNION ALL SELECT 4, 'SKU-LAMP-01', 'Desk lamp',        1, 48.90
    UNION ALL SELECT 5, 'SKU-BAGP-01', 'Laptop backpack',  1, 64.00
)
SELECT 'IT-DEMO-'  || o.tag || '-' || i.n,
       'ORD-DEMO-' || o.tag || '-' || i.n,
       i.sku, i.product_name, i.quantity, i.unit_price
FROM owners o CROSS JOIN line_items i;

-- ---------------------------------------------------------------------------
-- PAYMENTS
-- DEMO-1 and DEMO-2 carry TWO confirmed charges: the duplicate-charge evidence
-- G-10 requires. DEMO-3 carries one, so the same claim is blocked.
-- ---------------------------------------------------------------------------
INSERT INTO PAYMENTS (payment_id, order_id, status, amount, method, paid_at)
WITH owners AS (
    SELECT 'ME' AS tag, CURRENT_USER() AS username
    UNION ALL SELECT 'DC', 'TIDE_DEMO_CUSTOMER'
    UNION ALL SELECT 'JG', 'TIDE_JUDGE'
),
charges AS (
    SELECT 1 AS n, 'A' AS seq, 'confirmed' AS status,  41.74 AS amount, 'card' AS method, -4 AS paid_d
    UNION ALL SELECT 1, 'B', 'confirmed',  41.74, 'card',           -4
    UNION ALL SELECT 2, 'A', 'confirmed', 180.00, 'card',           -5
    UNION ALL SELECT 2, 'B', 'confirmed', 180.00, 'card',           -5
    UNION ALL SELECT 3, 'A', 'confirmed',  29.95, 'digital_wallet', -3
    UNION ALL SELECT 4, 'A', 'confirmed',  53.89, 'card',           -9
    UNION ALL SELECT 5, 'A', 'confirmed',  69.99, 'card',           -5
)
SELECT 'PAY-DEMO-' || o.tag || '-' || c.n || c.seq,
       'ORD-DEMO-' || o.tag || '-' || c.n,
       c.status, c.amount, c.method,
       DATEADD('day', c.paid_d, CURRENT_TIMESTAMP())
FROM owners o CROSS JOIN charges c;

-- ---------------------------------------------------------------------------
-- REFUNDS — the prior payout that makes DEMO-4 trip G-03
-- ---------------------------------------------------------------------------
INSERT INTO REFUNDS (refund_id, order_id, amount, reason, processed_at)
WITH owners AS (
    SELECT 'ME' AS tag, CURRENT_USER() AS username
    UNION ALL SELECT 'DC', 'TIDE_DEMO_CUSTOMER'
    UNION ALL SELECT 'JG', 'TIDE_JUDGE'
)
SELECT 'REF-DEMO-' || o.tag || '-4',
       'ORD-DEMO-' || o.tag || '-4',
       53.89,
       'Goodwill refund issued earlier',
       DATEADD('day', -4, CURRENT_TIMESTAMP())
FROM owners o;

-- ---------------------------------------------------------------------------
-- SHIPMENTS + TRACKING — DEMO-5 is delivered with a signed scan, so a
-- non_receipt claim against it trips G-05 with the evidence quoted back.
-- Event ids sort chronologically within the shipment; see sql/seed/README.md.
-- The owner tag sits before the event ordinal, so 'a' < 'b' < 'c' still holds
-- within any one shipment — which is what that invariant actually requires.
-- ---------------------------------------------------------------------------
INSERT INTO SHIPMENTS (shipment_id, order_id, carrier, tracking_number, status, estimated_delivery, delivered_at)
WITH owners AS (
    SELECT 'ME' AS tag, CURRENT_USER() AS username
    UNION ALL SELECT 'DC', 'TIDE_DEMO_CUSTOMER'
    UNION ALL SELECT 'JG', 'TIDE_JUDGE'
),
parcels AS (
    SELECT 4 AS n, 'Arrowline Logistics' AS carrier, 'AL-DEMO-004' AS tracking_number, 'delivered' AS status, -6 AS est_d, -6 AS delivered_d
    UNION ALL SELECT 5, 'BluePost Express', 'BP-DEMO-005', 'delivered', -2, -2
)
SELECT 'SHP-DEMO-' || o.tag || '-' || p.n,
       'ORD-DEMO-' || o.tag || '-' || p.n,
       p.carrier,
       p.tracking_number || '-' || o.tag,
       p.status,
       DATEADD('day', p.est_d,       CURRENT_TIMESTAMP()),
       DATEADD('day', p.delivered_d, CURRENT_TIMESTAMP())
FROM owners o CROSS JOIN parcels p;

INSERT INTO TRACKING_EVENTS (event_id, shipment_id, event_type, location, occurred_at)
WITH owners AS (
    SELECT 'ME' AS tag, CURRENT_USER() AS username
    UNION ALL SELECT 'DC', 'TIDE_DEMO_CUSTOMER'
    UNION ALL SELECT 'JG', 'TIDE_JUDGE'
),
scans AS (
    SELECT 4 AS n, 'a' AS seq, 'picked_up' AS event_type, 'Riverside sort facility' AS location, -8 AS occurred_d
    UNION ALL SELECT 4, 'b', 'delivered',        'Front door',           -6
    UNION ALL SELECT 5, 'a', 'picked_up',        'Harbor sort facility', -4
    UNION ALL SELECT 5, 'b', 'out_for_delivery', 'Local depot 7',        -2
    UNION ALL SELECT 5, 'c', 'delivered',        'Signed: resident',     -2
)
SELECT 'TE-DEMO-'  || o.tag || '-' || s.n || s.seq,
       'SHP-DEMO-' || o.tag || '-' || s.n,
       s.event_type, s.location,
       DATEADD('day', s.occurred_d, CURRENT_TIMESTAMP())
FROM owners o CROSS JOIN scans s;

-- ---------------------------------------------------------------------------
-- Verify — one row per owner per scenario, with the two counts the guardrails
-- turn on. Expect 15 rows: three owners x five orders.
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
ORDER BY o.customer_id, o.order_id;
