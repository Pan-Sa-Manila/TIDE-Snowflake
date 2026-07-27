-- ============================================================================
-- TIDE · 05_retail_ddl.sql
-- RETAIL schema: simulated enterprise data (OMS, payments, logistics, inventory)
-- Idempotent: safe to re-run
-- ============================================================================

USE DATABASE TIDE;

CREATE SCHEMA IF NOT EXISTS RETAIL
    COMMENT = 'Simulated enterprise: orders, items, payments, refunds, shipments, stock';

USE SCHEMA RETAIL;

-- ---------------------------------------------------------------------------
-- ORDERS
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ORDERS (
    order_id           VARCHAR(36)   DEFAULT UUID_STRING() NOT NULL,
    customer_id        VARCHAR(100)  NOT NULL,
    status             VARCHAR(20)   NOT NULL,           -- placed | fulfilled | delivered | returned | cancelled
    total_amount       NUMBER(10,2)  NOT NULL,
    shipping_fee       NUMBER(10,2)  DEFAULT 0,
    placed_at          TIMESTAMP_TZ  NOT NULL,
    fulfilled_at       TIMESTAMP_TZ,
    delivered_at       TIMESTAMP_TZ,
    estimated_delivery TIMESTAMP_TZ,

    CONSTRAINT pk_orders PRIMARY KEY (order_id)
);

-- ---------------------------------------------------------------------------
-- ORDER_ITEMS
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ORDER_ITEMS (
    item_id      VARCHAR(36)   DEFAULT UUID_STRING() NOT NULL,
    order_id     VARCHAR(36)   NOT NULL,
    sku          VARCHAR(30)   NOT NULL,
    product_name VARCHAR       NOT NULL,
    quantity     NUMBER        NOT NULL,
    unit_price   NUMBER(10,2)  NOT NULL,

    CONSTRAINT pk_order_items PRIMARY KEY (item_id)
);

-- ---------------------------------------------------------------------------
-- PAYMENTS
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS PAYMENTS (
    payment_id  VARCHAR(36)   DEFAULT UUID_STRING() NOT NULL,
    order_id    VARCHAR(36)   NOT NULL,
    status      VARCHAR(20)   NOT NULL,                -- pending | confirmed | failed
    amount      NUMBER(10,2)  NOT NULL,
    method      VARCHAR(30)   NOT NULL,                -- card | digital_wallet | bank_transfer | cash_on_delivery
    paid_at     TIMESTAMP_TZ,

    CONSTRAINT pk_payments PRIMARY KEY (payment_id)
);

-- ---------------------------------------------------------------------------
-- REFUNDS
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS REFUNDS (
    refund_id    VARCHAR(36)   DEFAULT UUID_STRING() NOT NULL,
    order_id     VARCHAR(36)   NOT NULL,
    amount       NUMBER(10,2)  NOT NULL,
    reason       VARCHAR,
    processed_at TIMESTAMP_TZ  DEFAULT CURRENT_TIMESTAMP(),

    CONSTRAINT pk_refunds PRIMARY KEY (refund_id)
);

-- ---------------------------------------------------------------------------
-- SHIPMENTS
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS SHIPMENTS (
    shipment_id        VARCHAR(36)   DEFAULT UUID_STRING() NOT NULL,
    order_id           VARCHAR(36)   NOT NULL,
    carrier            VARCHAR(50)   NOT NULL,
    tracking_number    VARCHAR(50),
    status             VARCHAR(20),
    estimated_delivery TIMESTAMP_TZ,
    delivered_at       TIMESTAMP_TZ,

    CONSTRAINT pk_shipments PRIMARY KEY (shipment_id)
);

-- ---------------------------------------------------------------------------
-- TRACKING_EVENTS
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS TRACKING_EVENTS (
    event_id    VARCHAR(36)   DEFAULT UUID_STRING() NOT NULL,
    shipment_id VARCHAR(36)   NOT NULL,
    event_type  VARCHAR(30)   NOT NULL,                -- picked_up | in_transit | out_for_delivery | delivered | delayed | exception | lost
    location    VARCHAR,
    occurred_at TIMESTAMP_TZ  NOT NULL,

    CONSTRAINT pk_tracking_events PRIMARY KEY (event_id)
);

-- ---------------------------------------------------------------------------
-- STOCK
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS STOCK (
    sku                VARCHAR(30)  NOT NULL,
    warehouse          VARCHAR(10)  NOT NULL,           -- DC-01 | DC-02 | DC-03
    quantity_available NUMBER       NOT NULL DEFAULT 0,
    quantity_reserved  NUMBER       NOT NULL DEFAULT 0,

    CONSTRAINT pk_stock PRIMARY KEY (sku, warehouse)
);

-- ---------------------------------------------------------------------------
-- Grants — all persona roles can read retail data (through procedures)
-- ---------------------------------------------------------------------------
GRANT USAGE ON SCHEMA RETAIL TO ROLE TIDE_CUSTOMER;
GRANT USAGE ON SCHEMA RETAIL TO ROLE TIDE_APPROVER;
GRANT USAGE ON SCHEMA RETAIL TO ROLE TIDE_ESCALATION;

GRANT SELECT ON ALL TABLES IN SCHEMA RETAIL TO ROLE TIDE_CUSTOMER;
GRANT SELECT ON ALL TABLES IN SCHEMA RETAIL TO ROLE TIDE_APPROVER;
GRANT SELECT ON ALL TABLES IN SCHEMA RETAIL TO ROLE TIDE_ESCALATION;
