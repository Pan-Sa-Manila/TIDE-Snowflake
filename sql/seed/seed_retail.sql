-- ============================================================================
-- TIDE · seed_retail.sql
-- Deterministic demo data. Every order is engineered to trip one specific
-- decision path (scenario ids reference the E2E test matrix).
-- All data synthetic: invented names/SKUs/carriers, example.com emails,
-- relative timestamps (never goes stale). Idempotent: scoped deletes first.
-- ============================================================================

USE DATABASE TIDE;
USE SCHEMA RETAIL;

-- ---------------------------------------------------------------------------
-- Reset seeded rows (scoped to seed id patterns; safe to re-run)
-- ---------------------------------------------------------------------------
DELETE FROM TRACKING_EVENTS WHERE shipment_id LIKE 'SHP-1%';
DELETE FROM SHIPMENTS       WHERE shipment_id LIKE 'SHP-1%';
DELETE FROM REFUNDS         WHERE order_id    LIKE 'ORD-1%';
DELETE FROM PAYMENTS        WHERE payment_id  LIKE 'PAY-1%';
DELETE FROM ORDER_ITEMS     WHERE item_id     LIKE 'IT-1%';
DELETE FROM ORDERS          WHERE order_id    LIKE 'ORD-1%';
DELETE FROM STOCK           WHERE sku         LIKE 'SKU-%';

-- ---------------------------------------------------------------------------
-- STOCK — 10 SKUs. SKU-CHRN-LE is the deliberate zero-stock probe (E-07).
-- ---------------------------------------------------------------------------
INSERT INTO STOCK (sku, warehouse, quantity_available, quantity_reserved) VALUES
  ('SKU-HDPH-01', 'DC-01', 14, 2),
  ('SKU-MUGS-01', 'DC-01', 30, 4),
  ('SKU-BLNK-01', 'DC-01',  8, 1),
  ('SKU-LAMP-01', 'DC-01', 12, 0),
  ('SKU-BAGP-01', 'DC-02',  9, 1),
  ('SKU-WTCH-01', 'DC-01',  6, 0),
  ('SKU-SPKR-01', 'DC-02', 11, 2),
  ('SKU-CHRG-01', 'DC-01', 22, 3),
  ('SKU-CHRN-LE', 'DC-01',  0, 0),
  ('SKU-TOWL-01', 'DC-03', 40, 5);

-- ---------------------------------------------------------------------------
-- ORDERS — customers rotate across: sofia.reyes, daniel.cho, amara.osei,
-- lena.novak, rafael.ortiz (@example.com)
-- Scenario map in each comment. Amounts straddle the $50 autonomous limit.
-- ---------------------------------------------------------------------------
INSERT INTO ORDERS (order_id, customer_id, status, total_amount, shipping_fee, placed_at, fulfilled_at, delivered_at, estimated_delivery)
SELECT * FROM VALUES
  -- E-01 damaged_goods refund ≤$50 → autonomous (R-08)
  ('ORD-1001','sofia.reyes@example.com','delivered', 47.49, 4.99, DATEADD('day',-6,CURRENT_TIMESTAMP()), DATEADD('day',-5,CURRENT_TIMESTAMP()), DATEADD('day',-3,CURRENT_TIMESTAMP()), DATEADD('day',-3,CURRENT_TIMESTAMP())),
  -- E-02 damaged_goods refund >$50 → awaiting_approval (R-09)
  ('ORD-1002','daniel.cho@example.com','delivered', 95.98, 5.99, DATEADD('day',-5,CURRENT_TIMESTAMP()), DATEADD('day',-4,CURRENT_TIMESTAMP()), DATEADD('day',-2,CURRENT_TIMESTAMP()), DATEADD('day',-2,CURRENT_TIMESTAMP())),
  -- E-04/E-05 damaged_goods, proof will contradict → ACD + appeal (G-08)
  ('ORD-1003','amara.osei@example.com','delivered', 28.99, 4.99, DATEADD('day',-7,CURRENT_TIMESTAMP()), DATEADD('day',-6,CURRENT_TIMESTAMP()), DATEADD('day',-4,CURRENT_TIMESTAMP()), DATEADD('day',-4,CURRENT_TIMESTAMP())),
  -- E-03 damaged_goods proof gate (no upload yet) → awaiting_customer_proof
  ('ORD-1004','lena.novak@example.com','delivered', 41.74, 4.99, DATEADD('day',-3,CURRENT_TIMESTAMP()), DATEADD('day',-2,CURRENT_TIMESTAMP()), DATEADD('day',-1,CURRENT_TIMESTAMP()), DATEADD('day',-1,CURRENT_TIMESTAMP())),
  -- E-06 wrong_item replacement ≤$50, stock OK → autonomous (R-13)
  ('ORD-1005','rafael.ortiz@example.com','delivered', 28.99, 4.99, DATEADD('day',-5,CURRENT_TIMESTAMP()), DATEADD('day',-4,CURRENT_TIMESTAMP()), DATEADD('day',-2,CURRENT_TIMESTAMP()), DATEADD('day',-2,CURRENT_TIMESTAMP())),
  -- E-07 replacement on zero-stock SKU → ACD insufficient_inventory (R-12)
  ('ORD-1006','sofia.reyes@example.com','delivered', 154.99, 5.99, DATEADD('day',-6,CURRENT_TIMESTAMP()), DATEADD('day',-5,CURRENT_TIMESTAMP()), DATEADD('day',-3,CURRENT_TIMESTAMP()), DATEADD('day',-3,CURRENT_TIMESTAMP())),
  -- E-08 duplicate_charge ≤$50 → autonomous (R-01). Two confirmed payments below.
  ('ORD-1007','daniel.cho@example.com','fulfilled', 41.74, 4.99, DATEADD('day',-4,CURRENT_TIMESTAMP()), DATEADD('day',-3,CURRENT_TIMESTAMP()), NULL, DATEADD('day',1,CURRENT_TIMESTAMP())),
  -- E-09 refund with prior refund on record → escalate duplicate-refund (G-03)
  ('ORD-1008','amara.osei@example.com','delivered', 53.89, 4.99, DATEADD('day',-9,CURRENT_TIMESTAMP()), DATEADD('day',-8,CURRENT_TIMESTAMP()), DATEADD('day',-6,CURRENT_TIMESTAMP()), DATEADD('day',-6,CURRENT_TIMESTAMP())),
  -- E-10 payment status pending → escalate (G-04)
  ('ORD-1009','lena.novak@example.com','fulfilled', 34.94, 4.99, DATEADD('day',-2,CURRENT_TIMESTAMP()), DATEADD('day',-1,CURRENT_TIMESTAMP()), NULL, DATEADD('day',2,CURRENT_TIMESTAMP())),
  -- E-11 non_receipt but tracking shows delivered → escalate + evidence (G-05)
  ('ORD-1010','rafael.ortiz@example.com','delivered', 69.99, 5.99, DATEADD('day',-5,CURRENT_TIMESTAMP()), DATEADD('day',-4,CURRENT_TIMESTAMP()), DATEADD('day',-2,CURRENT_TIMESTAMP()), DATEADD('day',-2,CURRENT_TIMESTAMP())),
  -- E-12 non_receipt, no delivery/lost events, ≤$50 → autonomous (R-31)
  ('ORD-1011','sofia.reyes@example.com','fulfilled', 34.94, 4.99, DATEADD('day',-4,CURRENT_TIMESTAMP()), DATEADD('day',-3,CURRENT_TIMESTAMP()), NULL, DATEADD('day',-1,CURRENT_TIMESTAMP())),
  -- E-13 non_receipt, stale in_transit 9d, >$50 → awaiting_approval + evidence (R-36)
  ('ORD-1012','daniel.cho@example.com','fulfilled', 154.99, 5.99, DATEADD('day',-12,CURRENT_TIMESTAMP()), DATEADD('day',-11,CURRENT_TIMESTAMP()), NULL, DATEADD('day',-6,CURRENT_TIMESTAMP())),
  -- E-14 delayed, delivered 5d past estimate → shipping-fee-only refund, autonomous (R-38)
  ('ORD-1013','amara.osei@example.com','delivered', 28.99, 4.99, DATEADD('day',-11,CURRENT_TIMESTAMP()), DATEADD('day',-10,CURRENT_TIMESTAMP()), DATEADD('day',-3,CURRENT_TIMESTAMP()), DATEADD('day',-8,CURRENT_TIMESTAMP())),
  -- E-15 exception event, undelivered, >$50 → awaiting_approval + evidence (R-46)
  ('ORD-1014','lena.novak@example.com','fulfilled', 61.24, 5.99, DATEADD('day',-4,CURRENT_TIMESTAMP()), DATEADD('day',-3,CURRENT_TIMESTAMP()), NULL, DATEADD('day',-1,CURRENT_TIMESTAMP())),
  -- E-16 lost event, refund ≤$50 → autonomous + evidence (R-50)
  ('ORD-1015','rafael.ortiz@example.com','fulfilled', 24.49, 4.99, DATEADD('day',-6,CURRENT_TIMESTAMP()), DATEADD('day',-5,CURRENT_TIMESTAMP()), NULL, DATEADD('day',-2,CURRENT_TIMESTAMP())),
  -- E-17 return_request within 7d window → awaiting_approval (R-24)
  ('ORD-1016','sofia.reyes@example.com','fulfilled', 47.49, 4.99, DATEADD('day',-6,CURRENT_TIMESTAMP()), DATEADD('day',-5,CURRENT_TIMESTAMP()), DATEADD('day',-3,CURRENT_TIMESTAMP()), DATEADD('day',-3,CURRENT_TIMESTAMP())),
  -- E-18 return_request delivered 10d ago → ACD outside_return_window (R-23)
  ('ORD-1017','daniel.cho@example.com','fulfilled', 53.89, 4.99, DATEADD('day',-14,CURRENT_TIMESTAMP()), DATEADD('day',-13,CURRENT_TIMESTAMP()), DATEADD('day',-10,CURRENT_TIMESTAMP()), DATEADD('day',-10,CURRENT_TIMESTAMP())),
  -- E-19 changed_mind on order still 'placed' → ACD non_returnable_item (R-25)
  ('ORD-1018','amara.osei@example.com','placed', 61.24, 5.99, DATEADD('day',-1,CURRENT_TIMESTAMP()), NULL, NULL, DATEADD('day',3,CURRENT_TIMESTAMP())),
  -- E-20 partial_fulfillment multi-item → escalate (R-21)
  ('ORD-1019','lena.novak@example.com','delivered', 96.94, 4.99, DATEADD('day',-5,CURRENT_TIMESTAMP()), DATEADD('day',-4,CURRENT_TIMESTAMP()), DATEADD('day',-2,CURRENT_TIMESTAMP()), DATEADD('day',-2,CURRENT_TIMESTAMP())),
  -- E-21 subtype 'other' → escalate (R-28)
  ('ORD-1020','rafael.ortiz@example.com','delivered', 69.99, 5.99, DATEADD('day',-4,CURRENT_TIMESTAMP()), DATEADD('day',-3,CURRENT_TIMESTAMP()), DATEADD('day',-1,CURRENT_TIMESTAMP()), DATEADD('day',-1,CURRENT_TIMESTAMP())),
  -- E-25 duplicate-open-case probe (case opened twice on this order via UI)
  ('ORD-1021','sofia.reyes@example.com','delivered', 41.74, 4.99, DATEADD('day',-3,CURRENT_TIMESTAMP()), DATEADD('day',-2,CURRENT_TIMESTAMP()), DATEADD('day',-1,CURRENT_TIMESTAMP()), DATEADD('day',-1,CURRENT_TIMESTAMP())),
  -- E-24 timeout probe (case created then abandoned in UI)
  ('ORD-1022','daniel.cho@example.com','delivered', 28.99, 4.99, DATEADD('day',-2,CURRENT_TIMESTAMP()), DATEADD('day',-1,CURRENT_TIMESTAMP()), DATEADD('hour',-20,CURRENT_TIMESTAMP()), DATEADD('day',-1,CURRENT_TIMESTAMP())),
  -- Intake block: cancelled order (not disputable)
  ('ORD-1023','amara.osei@example.com','cancelled', 95.98, 5.99, DATEADD('day',-8,CURRENT_TIMESTAMP()), NULL, NULL, NULL);

-- ---------------------------------------------------------------------------
-- ORDER_ITEMS
-- ---------------------------------------------------------------------------
INSERT INTO ORDER_ITEMS (item_id, order_id, sku, product_name, quantity, unit_price) VALUES
  ('IT-1001-1','ORD-1001','SKU-HDPH-01','Wireless headphones',1,42.50),
  ('IT-1002-1','ORD-1002','SKU-WTCH-01','Fitness watch',1,89.99),
  ('IT-1003-1','ORD-1003','SKU-MUGS-01','Ceramic mug set (4)',1,24.00),
  ('IT-1004-1','ORD-1004','SKU-BLNK-01','Knit throw blanket',1,36.75),
  ('IT-1005-1','ORD-1005','SKU-MUGS-01','Ceramic mug set (4)',1,24.00),
  ('IT-1006-1','ORD-1006','SKU-CHRN-LE','Limited chronograph',1,149.00),
  ('IT-1007-1','ORD-1007','SKU-BLNK-01','Knit throw blanket',1,36.75),
  ('IT-1008-1','ORD-1008','SKU-LAMP-01','Desk lamp',1,48.90),
  ('IT-1009-1','ORD-1009','SKU-CHRG-01','Charging station',1,29.95),
  ('IT-1010-1','ORD-1010','SKU-BAGP-01','Laptop backpack',1,64.00),
  ('IT-1011-1','ORD-1011','SKU-CHRG-01','Charging station',1,29.95),
  ('IT-1012-1','ORD-1012','SKU-CHRN-LE','Limited chronograph',1,149.00),
  ('IT-1013-1','ORD-1013','SKU-MUGS-01','Ceramic mug set (4)',1,24.00),
  ('IT-1014-1','ORD-1014','SKU-SPKR-01','Portable speaker',1,55.25),
  ('IT-1015-1','ORD-1015','SKU-TOWL-01','Towel set',1,19.50),
  ('IT-1016-1','ORD-1016','SKU-HDPH-01','Wireless headphones',1,42.50),
  ('IT-1017-1','ORD-1017','SKU-LAMP-01','Desk lamp',1,48.90),
  ('IT-1018-1','ORD-1018','SKU-SPKR-01','Portable speaker',1,55.25),
  -- E-20 partial fulfillment: three items, customer will select the missing ones
  ('IT-1019-1','ORD-1019','SKU-HDPH-01','Wireless headphones',1,42.50),
  ('IT-1019-2','ORD-1019','SKU-TOWL-01','Towel set',1,19.50),
  ('IT-1019-3','ORD-1019','SKU-CHRG-01','Charging station',1,29.95),
  ('IT-1020-1','ORD-1020','SKU-BAGP-01','Laptop backpack',1,64.00),
  ('IT-1021-1','ORD-1021','SKU-BLNK-01','Knit throw blanket',1,36.75),
  ('IT-1022-1','ORD-1022','SKU-MUGS-01','Ceramic mug set (4)',1,24.00),
  ('IT-1023-1','ORD-1023','SKU-WTCH-01','Fitness watch',1,89.99);

-- ---------------------------------------------------------------------------
-- PAYMENTS — all confirmed except ORD-1009 (G-04 probe).
-- ORD-1007 has TWO confirmed payments: the duplicate-charge evidence (E-08).
-- ---------------------------------------------------------------------------
INSERT INTO PAYMENTS (payment_id, order_id, status, amount, method, paid_at) VALUES
  ('PAY-1001','ORD-1001','confirmed', 47.49,'card',            DATEADD('day',-6,CURRENT_TIMESTAMP())),
  ('PAY-1002','ORD-1002','confirmed', 95.98,'digital_wallet',  DATEADD('day',-5,CURRENT_TIMESTAMP())),
  ('PAY-1003','ORD-1003','confirmed', 28.99,'card',            DATEADD('day',-7,CURRENT_TIMESTAMP())),
  ('PAY-1004','ORD-1004','confirmed', 41.74,'bank_transfer',   DATEADD('day',-3,CURRENT_TIMESTAMP())),
  ('PAY-1005','ORD-1005','confirmed', 28.99,'card',            DATEADD('day',-5,CURRENT_TIMESTAMP())),
  ('PAY-1006','ORD-1006','confirmed',154.99,'card',            DATEADD('day',-6,CURRENT_TIMESTAMP())),
  ('PAY-1007','ORD-1007','confirmed', 41.74,'card',            DATEADD('day',-4,CURRENT_TIMESTAMP())),
  ('PAY-1008','ORD-1007','confirmed', 41.74,'card',            DATEADD('day',-4,CURRENT_TIMESTAMP())),
  ('PAY-1009','ORD-1008','confirmed', 53.89,'digital_wallet',  DATEADD('day',-9,CURRENT_TIMESTAMP())),
  ('PAY-1010','ORD-1009','pending',   34.94,'bank_transfer',   NULL),
  ('PAY-1011','ORD-1010','confirmed', 69.99,'card',            DATEADD('day',-5,CURRENT_TIMESTAMP())),
  ('PAY-1012','ORD-1011','confirmed', 34.94,'cash_on_delivery',DATEADD('day',-4,CURRENT_TIMESTAMP())),
  ('PAY-1013','ORD-1012','confirmed',154.99,'card',            DATEADD('day',-12,CURRENT_TIMESTAMP())),
  ('PAY-1014','ORD-1013','confirmed', 28.99,'digital_wallet',  DATEADD('day',-11,CURRENT_TIMESTAMP())),
  ('PAY-1015','ORD-1014','confirmed', 61.24,'card',            DATEADD('day',-4,CURRENT_TIMESTAMP())),
  ('PAY-1016','ORD-1015','confirmed', 24.49,'card',            DATEADD('day',-6,CURRENT_TIMESTAMP())),
  ('PAY-1017','ORD-1016','confirmed', 47.49,'digital_wallet',  DATEADD('day',-6,CURRENT_TIMESTAMP())),
  ('PAY-1018','ORD-1017','confirmed', 53.89,'card',            DATEADD('day',-14,CURRENT_TIMESTAMP())),
  ('PAY-1019','ORD-1018','confirmed', 61.24,'card',            DATEADD('day',-1,CURRENT_TIMESTAMP())),
  ('PAY-1020','ORD-1019','confirmed', 96.94,'card',            DATEADD('day',-5,CURRENT_TIMESTAMP())),
  ('PAY-1021','ORD-1020','confirmed', 69.99,'bank_transfer',   DATEADD('day',-4,CURRENT_TIMESTAMP())),
  ('PAY-1022','ORD-1021','confirmed', 41.74,'card',            DATEADD('day',-3,CURRENT_TIMESTAMP())),
  ('PAY-1023','ORD-1022','confirmed', 28.99,'card',            DATEADD('day',-2,CURRENT_TIMESTAMP())),
  ('PAY-1024','ORD-1023','confirmed', 95.98,'card',            DATEADD('day',-8,CURRENT_TIMESTAMP()));

-- ---------------------------------------------------------------------------
-- REFUNDS — one prior refund on ORD-1008: the G-03 duplicate-refund probe.
-- ---------------------------------------------------------------------------
INSERT INTO REFUNDS (refund_id, order_id, amount, reason, processed_at) VALUES
  ('REF-1001','ORD-1008', 53.89, 'Courtesy refund after prior complaint', DATEADD('day',-4,CURRENT_TIMESTAMP()));

-- ---------------------------------------------------------------------------
-- SHIPMENTS — carriers: Arrowline Logistics / BluePost Express (invented)
-- ---------------------------------------------------------------------------
INSERT INTO SHIPMENTS (shipment_id, order_id, carrier, tracking_number, status, estimated_delivery, delivered_at) VALUES
  ('SHP-1001','ORD-1001','Arrowline Logistics','AL-778001','delivered', DATEADD('day',-3,CURRENT_TIMESTAMP()), DATEADD('day',-3,CURRENT_TIMESTAMP())),
  ('SHP-1002','ORD-1002','BluePost Express','BP-556002','delivered',   DATEADD('day',-2,CURRENT_TIMESTAMP()), DATEADD('day',-2,CURRENT_TIMESTAMP())),
  ('SHP-1003','ORD-1003','Arrowline Logistics','AL-778003','delivered', DATEADD('day',-4,CURRENT_TIMESTAMP()), DATEADD('day',-4,CURRENT_TIMESTAMP())),
  ('SHP-1004','ORD-1004','BluePost Express','BP-556004','delivered',   DATEADD('day',-1,CURRENT_TIMESTAMP()), DATEADD('day',-1,CURRENT_TIMESTAMP())),
  ('SHP-1005','ORD-1005','Arrowline Logistics','AL-778005','delivered', DATEADD('day',-2,CURRENT_TIMESTAMP()), DATEADD('day',-2,CURRENT_TIMESTAMP())),
  ('SHP-1006','ORD-1006','BluePost Express','BP-556006','delivered',   DATEADD('day',-3,CURRENT_TIMESTAMP()), DATEADD('day',-3,CURRENT_TIMESTAMP())),
  ('SHP-1008','ORD-1008','Arrowline Logistics','AL-778008','delivered', DATEADD('day',-6,CURRENT_TIMESTAMP()), DATEADD('day',-6,CURRENT_TIMESTAMP())),
  ('SHP-1010','ORD-1010','BluePost Express','BP-556010','delivered',   DATEADD('day',-2,CURRENT_TIMESTAMP()), DATEADD('day',-2,CURRENT_TIMESTAMP())),
  ('SHP-1011','ORD-1011','Arrowline Logistics','AL-778011','in_transit',DATEADD('day',-1,CURRENT_TIMESTAMP()), NULL),
  ('SHP-1012','ORD-1012','BluePost Express','BP-556012','in_transit',  DATEADD('day',-6,CURRENT_TIMESTAMP()), NULL),
  ('SHP-1013','ORD-1013','Arrowline Logistics','AL-778013','delivered', DATEADD('day',-8,CURRENT_TIMESTAMP()), DATEADD('day',-3,CURRENT_TIMESTAMP())),
  ('SHP-1014','ORD-1014','BluePost Express','BP-556014','exception',   DATEADD('day',-1,CURRENT_TIMESTAMP()), NULL),
  ('SHP-1015','ORD-1015','Arrowline Logistics','AL-778015','lost',     DATEADD('day',-2,CURRENT_TIMESTAMP()), NULL),
  ('SHP-1016','ORD-1016','BluePost Express','BP-556016','delivered',   DATEADD('day',-3,CURRENT_TIMESTAMP()), DATEADD('day',-3,CURRENT_TIMESTAMP())),
  ('SHP-1017','ORD-1017','Arrowline Logistics','AL-778017','delivered', DATEADD('day',-10,CURRENT_TIMESTAMP()), DATEADD('day',-10,CURRENT_TIMESTAMP())),
  ('SHP-1019','ORD-1019','BluePost Express','BP-556019','delivered',   DATEADD('day',-2,CURRENT_TIMESTAMP()), DATEADD('day',-2,CURRENT_TIMESTAMP())),
  ('SHP-1020','ORD-1020','Arrowline Logistics','AL-778020','delivered', DATEADD('day',-1,CURRENT_TIMESTAMP()), DATEADD('day',-1,CURRENT_TIMESTAMP())),
  ('SHP-1021','ORD-1021','BluePost Express','BP-556021','delivered',   DATEADD('day',-1,CURRENT_TIMESTAMP()), DATEADD('day',-1,CURRENT_TIMESTAMP())),
  ('SHP-1022','ORD-1022','Arrowline Logistics','AL-778022','delivered', DATEADD('day',-1,CURRENT_TIMESTAMP()), DATEADD('hour',-20,CURRENT_TIMESTAMP()));

-- ---------------------------------------------------------------------------
-- TRACKING_EVENTS — the evidence the delivery guardrails and routes read.
-- ---------------------------------------------------------------------------
INSERT INTO TRACKING_EVENTS (event_id, shipment_id, event_type, location, occurred_at) VALUES
  -- Normal delivered chains (abbreviated: pickup → delivered)
  ('TE-1001a','SHP-1001','picked_up','Riverside sort facility', DATEADD('day',-5,CURRENT_TIMESTAMP())),
  ('TE-1001b','SHP-1001','delivered','Front door',              DATEADD('day',-3,CURRENT_TIMESTAMP())),
  ('TE-1002a','SHP-1002','picked_up','Harbor sort facility',    DATEADD('day',-4,CURRENT_TIMESTAMP())),
  ('TE-1002b','SHP-1002','delivered','Reception desk',          DATEADD('day',-2,CURRENT_TIMESTAMP())),
  ('TE-1003a','SHP-1003','delivered','Front door',              DATEADD('day',-4,CURRENT_TIMESTAMP())),
  ('TE-1004a','SHP-1004','delivered','Mailroom',                DATEADD('day',-1,CURRENT_TIMESTAMP())),
  ('TE-1005a','SHP-1005','delivered','Front door',              DATEADD('day',-2,CURRENT_TIMESTAMP())),
  ('TE-1006a','SHP-1006','delivered','Locker 14',               DATEADD('day',-3,CURRENT_TIMESTAMP())),
  ('TE-1008a','SHP-1008','delivered','Front door',              DATEADD('day',-6,CURRENT_TIMESTAMP())),
  -- E-11 / G-05: delivered WITH proof-of-delivery scan, customer claims non-receipt
  ('TE-1010a','SHP-1010','picked_up','Harbor sort facility',    DATEADD('day',-4,CURRENT_TIMESTAMP())),
  ('TE-1010b','SHP-1010','out_for_delivery','Local depot 7',    DATEADD('day',-2,CURRENT_TIMESTAMP())),
  ('TE-1010c','SHP-1010','delivered','Signed: resident',        DATEADD('day',-2,CURRENT_TIMESTAMP())),
  -- E-12 / R-31: picked up only — no delivered, no lost
  ('TE-1011a','SHP-1011','picked_up','Riverside sort facility', DATEADD('day',-2,CURRENT_TIMESTAMP())),
  -- E-13 / R-36: in_transit 9 days ago, silence since
  ('TE-1012a','SHP-1012','picked_up','Harbor sort facility',    DATEADD('day',-11,CURRENT_TIMESTAMP())),
  ('TE-1012b','SHP-1012','in_transit','Interstate hub',         DATEADD('day',-9,CURRENT_TIMESTAMP())),
  -- E-14 / R-38: delivered 5 days past estimate (SLA breach)
  ('TE-1013a','SHP-1013','picked_up','Riverside sort facility', DATEADD('day',-10,CURRENT_TIMESTAMP())),
  ('TE-1013b','SHP-1013','delayed','Weather hold, interstate hub', DATEADD('day',-7,CURRENT_TIMESTAMP())),
  ('TE-1013c','SHP-1013','delivered','Front door',              DATEADD('day',-3,CURRENT_TIMESTAMP())),
  -- E-15 / R-46: exception, never delivered
  ('TE-1014a','SHP-1014','picked_up','Harbor sort facility',    DATEADD('day',-3,CURRENT_TIMESTAMP())),
  ('TE-1014b','SHP-1014','exception','Address not accessible, depot 7', DATEADD('day',-1,CURRENT_TIMESTAMP())),
  -- E-16 / R-50: declared lost
  ('TE-1015a','SHP-1015','picked_up','Riverside sort facility', DATEADD('day',-5,CURRENT_TIMESTAMP())),
  ('TE-1015b','SHP-1015','in_transit','Interstate hub',         DATEADD('day',-4,CURRENT_TIMESTAMP())),
  ('TE-1015c','SHP-1015','lost','Last scan: interstate hub',    DATEADD('day',-2,CURRENT_TIMESTAMP())),
  -- Return-window probes
  ('TE-1016a','SHP-1016','delivered','Front door',              DATEADD('day',-3,CURRENT_TIMESTAMP())),
  ('TE-1017a','SHP-1017','delivered','Front door',              DATEADD('day',-10,CURRENT_TIMESTAMP())),
  ('TE-1019a','SHP-1019','delivered','Reception desk',          DATEADD('day',-2,CURRENT_TIMESTAMP())),
  ('TE-1020a','SHP-1020','delivered','Front door',              DATEADD('day',-1,CURRENT_TIMESTAMP())),
  ('TE-1021a','SHP-1021','delivered','Mailroom',                DATEADD('day',-1,CURRENT_TIMESTAMP())),
  ('TE-1022a','SHP-1022','delivered','Front door',              DATEADD('hour',-20,CURRENT_TIMESTAMP()));
