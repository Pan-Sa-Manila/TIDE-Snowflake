# TIDE · Schema Reference

> **Living document.** Update this file on every migration or DDL change.
> This is the single source of truth for what exists in the `TIDE` database.

**Conventions:** IDs `VARCHAR(36) DEFAULT UUID_STRING()` · money `NUMBER(10,2)` USD · times `TIMESTAMP_TZ` UTC · payloads `VARIANT` · FKs declared for lineage, enforced in procedures (not by Snowflake).

---

## 1. TRIAGE — cases, chat, events

### CASES (immutable core; mutable state lives in events)

| Column | Type | Notes |
|---|---|---|
| `case_id` | `VARCHAR(36)` PK | `DEFAULT UUID_STRING()` |
| `reference_number` | `VARCHAR(20)` | `TIDE-%05d` from `CASE_SEQ` |
| `order_id` | `VARCHAR(36)` | → RETAIL.ORDERS |
| `customer_id` | `VARCHAR(100)` | Snowflake user or demo id |
| `dispute_type` | `VARCHAR(20)` | `refund` \| `delivery` |
| `dispute_subtype` | `VARCHAR(30)` | One of 12 canonical subtypes (DETAILS.md §7.1) |
| `resolution_preference` | `VARCHAR(20)` | `refund` \| `replacement` \| `return` |
| `intake_summary` | `VARCHAR` | AI-generated intake summary |
| `proof_required` | `BOOLEAN` | Per subtype definition |
| `created_at` | `TIMESTAMP_TZ` | `DEFAULT CURRENT_TIMESTAMP()` |

### CASE_EVENTS (append-only; the spine of the system)

| Column | Type | Notes |
|---|---|---|
| `event_id` | `VARCHAR(36)` PK | `DEFAULT UUID_STRING()` |
| `case_id` | `VARCHAR(36)` | → TRIAGE.CASES |
| `event_key` | `VARCHAR(100)` UNIQUE | Idempotency key |
| `event_type` | `VARCHAR(30)` | See event types below |
| `actor_type` | `VARCHAR(20)` | `customer` \| `assistant` \| `agent` \| `system` |
| `actor_id` | `VARCHAR(100)` | Who performed the action |
| `payload` | `VARIANT` | Event-specific data |
| `occurred_at` | `TIMESTAMP_TZ` | `DEFAULT CURRENT_TIMESTAMP()` |

**Event types:** `case_created` · `status_changed` (payload: from, to, reason) · `intake_classified` · `followup_asked` / `followup_answered` · `proof_uploaded` / `proof_removed` / `proof_analyzed` · `evidence_assembled` · `decision_made` (payload: full Decision + input-bundle snapshot) · `resolution_requested` / `resolution_executed` · `approved` / `rejected` · `claimed` · `appealed` · `summarized` · `reported` · `closed`

### CHAT (append-only)

| Column | Type | Notes |
|---|---|---|
| `message_id` | `VARCHAR(36)` PK | `DEFAULT UUID_STRING()` |
| `case_id` | `VARCHAR(36)` | → TRIAGE.CASES |
| `sender_type` | `VARCHAR(20)` | `customer` \| `assistant` \| `agent` \| `system` |
| `sender_id` | `VARCHAR(100)` | |
| `content` | `VARCHAR` | Message text |
| `metadata` | `VARIANT` | Structured-reply options, attachments, client echo key |
| `created_at` | `TIMESTAMP_TZ` | `DEFAULT CURRENT_TIMESTAMP()` |

### Views

| View | Purpose |
|---|---|
| `V_CASE_CURRENT` | Case core + latest `status_changed` + latest decision + assignment + closed fields. `QUALIFY ROW_NUMBER()` over status events. **The only way the app reads state.** |
| `V_MY_CASES` (secure) | `V_CASE_CURRENT` filtered `customer_id = CURRENT_USER()` |
| `V_QUEUE_APPROVAL` (secure) | Approval-persona queue with age buckets |
| `V_QUEUE_ESCALATION` (secure) | Escalation-persona queue with age buckets |

---

## 2. INVESTIGATION — evidence & proof

### EVIDENCE_BUNDLES

| Column | Type | Notes |
|---|---|---|
| `bundle_id` | `VARCHAR(36)` PK | |
| `case_id` | `VARCHAR(36)` | → TRIAGE.CASES |
| `assembly_status` | `VARCHAR(20)` | `complete` \| `partial` \| `failed` |
| `bundle` | `VARIANT` | Shape per §5 below |
| `sources_queried` | `ARRAY` | Which tools the agent invoked |
| `agent_citations` | `VARIANT` | Per-section source attribution |
| `assembled_at` | `TIMESTAMP_TZ` | |

New row per assembly; latest wins via view.

### PROOF_FILES

| Column | Type | Notes |
|---|---|---|
| `proof_id` | `VARCHAR(36)` PK | |
| `case_id` | `VARCHAR(36)` | → TRIAGE.CASES |
| `relative_path` | `VARCHAR` | On PROOF_STAGE: `<case_id>/<uuid>.<ext>` |
| `content_type` | `VARCHAR(20)` | `image/jpeg` \| `image/png` \| `image/webp` |
| `byte_size` | `NUMBER` | |
| `sha256` | `VARCHAR(64)` | Unique per case (procedure-enforced) |
| `width` | `NUMBER` | |
| `height` | `NUMBER` | |
| `analysis` | `VARIANT` | Vision model output |
| `analysis_status` | `VARCHAR(20)` | `pending` \| `completed` \| `failed` |
| `uploaded_at` | `TIMESTAMP_TZ` | |

### PROOF_STAGE

Internal stage, `DIRECTORY = (ENABLE = TRUE)`, `ENCRYPTION = (TYPE = 'SNOWFLAKE_SSE')`. Every upload is followed by `ALTER STAGE PROOF_STAGE REFRESH`.

**No image bytes in tables — stage only.**

### Investigator tool procedures

The four custom tools the Investigator agent calls (`agents/investigator.yaml`), plus one formatting helper. All return `VARIANT`, `EXECUTE AS OWNER`, defined in `sql/06_investigation_tools.sql`.

| Object | Signature | Returns |
|---|---|---|
| `GET_SHIPMENT_TIMELINE` | `(order_id VARCHAR)` | `{order_id, found, shipment, tracking_events[]}` → bundle `shipment` + `tracking_events` |
| `GET_PAYMENT_STATUS` | `(order_id VARCHAR)` | `{order_id, found, payment, payments[]}` → bundle `payment`; `payments[]` is the duplicate-charge evidence |
| `GET_REFUND_HISTORY` | `(order_id VARCHAR)` | `{order_id, found, refund_history[]}` → bundle `refund_history` |
| `CHECK_INVENTORY` | `(skus ARRAY)` | `{inventory[]}` → bundle `inventory`, minus `quantity_ordered` (no order context) |
| `ISO_UTC` | `(ts TIMESTAMP_TZ)` UDF | UTC ISO-8601 string; every timestamp in a bundle goes through it |

Contract: `found = false` with a null/empty payload means **no such record**, never a tool failure. Timestamps are ISO-8601 UTC strings, not Snowflake timestamps. These tools report facts only — no thresholds, no status classification; that is the decision engine's job (`DETAILS.md` §9).

Known limitation: an order with more than one shipment collapses to the most recently completed or scheduled one, and only that shipment's tracking events are returned — mixing events across shipments would corrupt the "latest event of type X" derivation. The only scenario that splits shipments is `partial_fulfillment`, which always escalates to a human (`DETAILS.md` §11), so this can never affect an autonomous decision.

---

## 3. DECISION — rules, policies, decisions

### RULE_CONSTANTS

| Column | Type | Notes |
|---|---|---|
| `key` | `VARCHAR(50)` PK | e.g. `AUTONOMOUS_LIMIT_USD` |
| `value` | `VARIANT` | The constant value |
| `description` | `VARCHAR` | Human-readable explanation |
| `brl_ref` | `VARCHAR(20)` | Reference to DETAILS.md section |

Seeded from DETAILS.md §6. Procedures and UI read it; nobody hardcodes it.

### POLICIES

| Column | Type | Notes |
|---|---|---|
| `policy_id` | `VARCHAR(36)` PK | |
| `slug` | `VARCHAR(50)` UNIQUE | e.g. `return-window-policy` |
| `category` | `VARCHAR(20)` | `store` \| `payment` \| `return` \| `delivery` \| `sla` |
| `title` | `VARCHAR` | |
| `body` | `VARCHAR` | Full policy text |
| `active` | `BOOLEAN` | |

Feeds `POLICY_SEARCH` (Cortex Search over `body`, attributes slug/category/title) and the rejection citation picker.

### REASON_COPY

| Column | Type | Notes |
|---|---|---|
| `invalid_reason_code` | `VARCHAR(40)` PK | From DETAILS.md §12 closed set |
| `customer_copy` | `VARCHAR` | Customer-facing explanation text |
| `appeal_priority` | `VARCHAR(10)` | `high` \| `normal` |

### DECISIONS — immutable log of every adjudication

| Column | Type | Notes |
|---|---|---|
| `decision_id` | `VARCHAR(36)` PK | `DEFAULT UUID_STRING()` |
| `case_id` | `VARCHAR(36)` | → TRIAGE.CASES |
| `path_id` | `VARCHAR(10)` | `G-xx` / `R-xx` |
| `target_status` | `VARCHAR(30)` | |
| `resolution_type` | `VARCHAR(20)` | `refund` \| `return` \| `replacement` \| null |
| `eligible_amount` | `NUMBER(10,2)` | |
| `shipping_fee_only` | `BOOLEAN` | |
| `invalid_reason_code` | `VARCHAR(40)` | |
| `reason` | `VARCHAR` | Human-readable decision reason |
| `input_snapshot` | `VARIANT` | Full evidence bundle at decision time (auditable replay) |
| `decided_at` | `TIMESTAMP_TZ` | `DEFAULT CURRENT_TIMESTAMP()` |

`path_id` on every decision makes the matrix demonstrable to a judge in one query.
`input_snapshot` enables deterministic replay: feed it back to `adjudicate()` to reproduce the exact outcome.

---

## 4. EXECUTION — resolutions, reports, ops log

### RESOLUTION_REQUESTS

| Column | Type | Notes |
|---|---|---|
| `request_id` | `VARCHAR(36)` PK | |
| `case_id` | `VARCHAR(36)` | → TRIAGE.CASES |
| `request_type` | `VARCHAR(20)` | `refund` \| `return` \| `replacement` |
| `status` | `VARCHAR(20)` | `pending` \| `approved` \| `rejected` \| `executing` \| `completed` \| `cancelled` \| `failed` |
| `amount` | `NUMBER(10,2)` | |
| `item_ids` | `ARRAY` | Affected item IDs |
| `detail` | `VARIANT` | Replacement items, partial flags, shipping_fee_only |
| `decided_by` | `VARCHAR(100)` | |
| `created_at` | `TIMESTAMP_TZ` | |
| `updated_at` | `TIMESTAMP_TZ` | |

### CASE_REPORTS

| Column | Type | Notes |
|---|---|---|
| `case_id` | `VARCHAR(36)` PK | |
| `outcome_summary` | `VARCHAR` | |
| `resolution_path` | `VARCHAR` | |
| `rules_applied` | `ARRAY` | Path IDs (validated against actual decision events) |
| `policies_cited` | `ARRAY` | |
| `sources_queried` | `ARRAY` | |
| `proof_summary` | `VARIANT` | |
| `timeline` | `VARIANT` | |
| `generated_at` | `TIMESTAMP_TZ` | |

### PIPELINE_LOG

| Column | Type | Notes |
|---|---|---|
| `log_id` | `VARCHAR(36)` PK | |
| `case_id` | `VARCHAR(36)` | |
| `component` | `VARCHAR(50)` | Procedure/task/agent name |
| `status` | `VARCHAR(20)` | `started` \| `completed` \| `failed` |
| `elapsed_ms` | `NUMBER` | |
| `detail` | `VARIANT` | |
| `logged_at` | `TIMESTAMP_TZ` | |

Every procedure/task/agent call writes one row. This is the ops debugging surface **and** demo-day progress feed.

---

## 5. Evidence Bundle Shape (`EVIDENCE_BUNDLES.bundle`)

```json
{
  "as_of": "2026-08-01T09:30:00Z",
  "order":     {"order_id":"...","status":"fulfilled","total_amount":47.50,
                "shipping_fee":4.99,"placed_at":"...","fulfilled_at":"...","delivered_at":null},
  "items":     [{"item_id":"...","sku":"...","name":"...","qty":1,"unit_price":42.51}],
  "affected_items": [{"item_id":"...","qty":1,"unit_price":42.51}],
  "payment":   {"status":"confirmed","amount":47.50,"method":"card"},
  "refund_history": [{"amount":47.50,"processed_at":"..."}],
  "shipment":  {"carrier":"...","estimated_delivery":"...","delivered_at":null},
  "tracking_events": [{"event_type":"in_transit","location":"...","occurred_at":"..."}],
  "inventory": [{"sku":"...","quantity_available":3,"quantity_ordered":1}],
  "proof":     {"present":true,"analysis_status":"completed",
                "signals":{"damage_detected":true,"wrong_item_signals":false,
                            "missing_item_signals":false,"not_as_described_signals":false},
                "notes":"..."},
  "assembly":  {"status":"complete","sources":["orders","payments","shipments"],"failures":[]}
}
```

This dict is the **entire input** to `tide_decision.adjudicate()` — which is why the engine tests need no database.

---

## 6. RETAIL — simulated enterprise schema

Stands in for the retailer's OMS, payment gateway, carrier feed, and inventory system.

| Table | Key Columns |
|---|---|
| **ORDERS** | `order_id` PK · `customer_id` · `status` (placed\|fulfilled\|delivered\|returned\|cancelled) · `total_amount` · `shipping_fee` · `placed_at` · `fulfilled_at` · `delivered_at` · `estimated_delivery` |
| **ORDER_ITEMS** | `item_id` PK · `order_id` · `sku` · `product_name` · `quantity` · `unit_price` |
| **PAYMENTS** | `payment_id` PK · `order_id` · `status` (pending\|confirmed\|failed) · `amount` · `method` (card\|digital_wallet\|bank_transfer\|cash_on_delivery) · `paid_at` |
| **REFUNDS** | `refund_id` PK · `order_id` · `amount` · `reason` · `processed_at` |
| **SHIPMENTS** | `shipment_id` PK · `order_id` · `carrier` · `tracking_number` · `status` · `estimated_delivery` · `delivered_at` |
| **TRACKING_EVENTS** | `event_id` PK · `shipment_id` · `event_type` (picked_up\|in_transit\|out_for_delivery\|delivered\|delayed\|exception\|lost) · `location` · `occurred_at` |
| **STOCK** | `(sku, warehouse)` PK · `warehouse` (DC-01..03) · `quantity_available` · `quantity_reserved` |

| View | Purpose |
|---|---|
| `V_STOCK_BY_SKU` | `STOCK` rolled up to one row per SKU (`quantity_available`, `quantity_reserved`, `warehouse_count`). Exists to give `DISPUTES_SV` a unique `sku` grain — see §7. Tool procedures read `STOCK` directly. |

---

## 7. Semantic View — `RETAIL.DISPUTES_SV`

Cortex Analyst surface for the investigator (and ad-hoc ops questions). Defined in `sql/07_semantic_view.sql`. Built: **8 logical tables · 7 relationships · 26 dimensions · 11 facts · 12 metrics.**

| Logical table | Base object | Key measures |
|---|---|---|
| `orders` | `RETAIL.ORDERS` | `total_order_value`, `order_count`; facts `order_total`, `shipping_fee`, `days_since_delivery`, `days_past_estimated_delivery` |
| `order_items` | `RETAIL.ORDER_ITEMS` | `total_item_value` |
| `payments` | `RETAIL.PAYMENTS` | `total_paid`, `payment_count` (>1 = duplicate-charge signal) |
| `refunds` | `RETAIL.REFUNDS` | `total_refunded`, `refund_count` |
| `shipments` | `RETAIL.SHIPMENTS` | dimensions only (carrier, tracking number, status) |
| `tracking` | `RETAIL.TRACKING_EVENTS` | `latest_event_at`, `latest_event_type`, `latest_event_location` |
| `stock` | `RETAIL.V_STOCK_BY_SKU` | `total_available` |
| `cases` | `TRIAGE.V_CASE_CURRENT` | `case_count`; fact `eligible_amount` |

Relationships fan in to `orders` on `order_id` (items, payments, refunds, shipments, cases), plus `tracking → shipments` on `shipment_id` and `order_items → stock` on `sku`. Synonyms follow the spec: "money back" → refund, "package"/"parcel" → shipment, "in stock" → `quantity_available`.

**`RETAIL.V_STOCK_BY_SKU`** (defined in `sql/05_retail_ddl.sql`, see §6) supplies the unique per-SKU grain the `items_to_stock` relationship needs, because `STOCK` is keyed `(sku, warehouse)`.

Two behaviours that surprised on first use, both verified:

- A child-table metric **inner joins**. An order with no refunds returns *no row* from `refunds.total_refunded`, not zero — callers must read "no row" as zero. Order-side metrics still return the order.
- A metric cannot be grouped by a dimension of finer grain than its own table: `stock.total_available` groups by `stock.sku`, never by `order_items.sku`.

`latest_event_type` / `latest_event_location` order by `occurred_at` then `event_id`, matching `GET_SHIPMENT_TIMELINE` so the two never disagree. The `event_id` tiebreak is load-bearing: `out_for_delivery` and `delivered` share a timestamp on ORD-1010, and a plain `MAX_BY(occurred_at)` reports that parcel as undelivered.

Creating and querying the view via `SEMANTIC_VIEW()` is plain SQL and works. Reaching it through **Cortex Analyst natural language is blocked** on the trial account (`CAPABILITIES.md` §C) and is therefore unverified.

---

## 8. Streams & Tasks (orchestration objects)

| Object | Kind | Trigger | Action |
|---|---|---|---|
| `S_ESCALATIONS` | Stream on CASE_EVENTS | `status_changed → escalated_human_required` | → `T_SUMMARIZE` generates escalation summary |
| `S_CLOSURES` | Stream on CASE_EVENTS | `closed` event | → `T_REPORT` generates case report row |
| `T_TIMEOUT_SWEEP` | Task (cron `*/5 * * * *`) | Schedule | Close idle `pending_triage` cases per DETAILS.md §14 |

All tasks: `TASK_AUTO_RETRY_ATTEMPTS = 2`, write to `PIPELINE_LOG`, serverless.
