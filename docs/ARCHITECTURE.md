# TIDE · Architecture

## 1. Shape

Everything runs inside one Snowflake account. No external services, no webhooks, no egress.

```
Streamlit in Snowflake (warehouse runtime)
  Home.py → pages/1_Customer · 2_Approver · 3_Escalation
      │  SQL only
      ▼
Synchronous chat path                     Asynchronous path
  TRIAGE.INTAKE_TURN()                      stream on CASE_EVENTS
  INVESTIGATION.ASSEMBLE_EVIDENCE()   ──▶   ├─ EXECUTION.SUMMARIZE task (on escalation)
  INVESTIGATION.ANALYZE_PROOF()             ├─ EXECUTION.REPORT task (on close)
  DECISION.ADJUDICATE()                     └─ TRIAGE.TIMEOUT_SWEEP task (cron 5 min)
  EXECUTION.EXECUTE_RESOLUTION()
      ▼
  Event-sourced tables + derived views (V_CASE_CURRENT)
  PROOF_STAGE (SNOWFLAKE_SSE) + directory table
  RETAIL.* simulated enterprise schema + DISPUTES_SV semantic view
  DECISION.POLICY_SEARCH (Cortex Search)
  INVESTIGATION.INVESTIGATOR (Cortex Agent)
```

**Two speeds, one rule:** anything a person is actively waiting on is a synchronous procedure call (chat turns, adjudication, approval execution). Anything nobody watches in real time is a triggered or scheduled task (summaries, reports, timeout sweep). Triggered tasks have a ~30s minimum latency — that constraint drew this line.

---

## 2. Object Inventory

| Object | Kind | Purpose |
|---|---|---|
| `TIDE` | database | Everything |
| `TIDE.TRIAGE` | schema | Cases, chat, events, intake procedure, sweeper |
| `TIDE.INVESTIGATION` | schema | Evidence bundles, proof files + stage, investigator agent, vision |
| `TIDE.DECISION` | schema | Adjudicator, rule constants, policies, reason copy, decision log |
| `TIDE.EXECUTION` | schema | Resolution requests/records, case reports, pipeline log, summariser/reporter |
| `TIDE.RETAIL` | schema | Simulated enterprise systems: orders, order_items, payments, refunds, shipments, tracking_events, stock |
| `TIDE.RETAIL.DISPUTES_SV` | semantic view | Cortex Analyst surface over RETAIL + case facts |
| `TIDE.DECISION.POLICY_SEARCH` | Cortex Search service | Policy retrieval for the investigator + reject-citation picker |
| `TIDE.INVESTIGATION.INVESTIGATOR` | Cortex Agent | The tool-selecting evidence assembler |
| `TIDE_WH_APP` / `TIDE_WH_TASKS` | warehouses | XS, auto-suspend 300s / 60s |
| `TIDE_ADMIN` / `_CUSTOMER` / `_APPROVER` / `_ESCALATION` | roles | See §4 |
| Streamlit app `TIDE_APP` | app | Three personas, app-viewer URLs |

---

## 3. Sync Path Latency Budget (per chat turn)

| Step | Budget |
|---|---|
| Intake classification (`AI_COMPLETE`, structured) | ≤ 4s |
| Evidence assembly (agent, budget-capped 60s; typical) | ≤ 15s |
| Proof vision (per image) | ≤ 8s |
| Adjudication (pure function) | ≤ 1s |
| Execution + events | ≤ 2s |

The UI shows stage-by-stage progress during investigation (poll `PIPELINE_LOG`), not a spinner.

---

## 4. Security Model

- **Roles:** `TIDE_CUSTOMER` — execute intake/upload/close/appeal procedures + select on own-case views (`WHERE customer_id = CURRENT_USER()` baked into secure views); no base-table grants. `TIDE_APPROVER` — queue views + approve/reject procedures. `TIDE_ESCALATION` — escalated-case views + action procedures (assignment checked inside each procedure). `TIDE_ADMIN` — owns objects, deploys.
- Demo users: one per persona; customer user gets `ALLOWED_INTERFACES = (STREAMLIT)`.
- Procedures are `EXECUTE AS OWNER` — the app's role can act only through them; direct DML on core tables is not granted to any persona role. State legality is enforced inside procedures.
- No secrets in the repo; `connections.toml` is local-only. Nothing to leak: there are no external API keys because there are no external APIs.

---

## 5. Repo Layout

```
TIDE-Snowflake/
  AGENTS.md                    # Agent operating rules (build-time)
  .cortex/                     # Skills + hooks (CoCo)
  docs/                        # ARCHITECTURE, DETAILS, SCHEMA
  sql/
    00_account.sql … NN_*.sql  # Ordered, idempotent DDL
    seed/                      # Deterministic demo data
  tide_decision/               # Pure decision engine (no Snowflake imports)
  procedures/                  # Snowpark procedure wrappers (thin)
  agents/investigator.yaml     # CREATE AGENT spec source
  streamlit/                   # The app
  tests/decision/              # pytest — one test per BRL path id
  scripts/                     # deploy.py, guard_sql.py, demo_reset.sql
  evidence/coco-transcripts/   # Committed stream-json build sessions
```

Deploy = `python scripts/deploy.py` → runs `sql/` in order via Snowflake CLI, uploads procedures, creates the agent from `agents/investigator.yaml`, deploys the Streamlit app. Re-runnable from zero; that script is also the judges' setup instructions.

---

## 6. Build-time vs Runtime AI

- **Build-time: CoCo CLI.** AGENTS.md + `.cortex/skills/` + hooks steer it; sessions run with `--output-format stream-json` and transcripts are committed to `evidence/`.
- **Runtime: Cortex.** One agent object where tool *selection* is real (investigation); `AI_COMPLETE` structured calls where the task is fixed; a pure function where money is decided. The deliberate absence of an LLM in adjudication is an architecture feature.

---

## 7. Component Detail

### 7.1 INVESTIGATOR — the Cortex Agent object

Tool-selecting evidence assembler. Invoked via `DATA_AGENT_RUN` (non-streaming) from `ASSEMBLE_EVIDENCE()`.

**Tools:**
- `Analyst` — Cortex Analyst over `DISPUTES_SV` semantic view (quantitative order facts)
- `PolicySearch` — Cortex Search over `POLICY_SEARCH` (policy passages)
- `GetShipmentTimeline` — Custom procedure (full tracking event sequence)
- `GetPaymentStatus` — Custom procedure (payment confirmation state)
- `GetRefundHistory` — Custom procedure (prior refunds for an order)
- `CheckInventory` — Custom procedure (availability vs ordered quantity)

Orchestration budget: 60 seconds, 24,000 tokens. Failure or invalid shape: one retry, then `assembly_status='failed'` (adjudicator escalates).

### 7.2 INTAKE_TURN — structured chat turns

Runs on each customer message while `pending_triage`. Loads case + chat + order snapshot, calls `AI_COMPLETE` with a structured schema (action, subtype, followup, choices, affected items, confidence, reply). Enforces follow-up limit (≤3), alias normalisation, structured reply pills.

### 7.3 ANALYZE_PROOF — vision

Per image: `AI_COMPLETE` vision model with proof image from `@PROOF_STAGE`. Returns structured signals: damage_detected, wrong_item_signals, missing_item_signals, not_as_described_signals, matches_product, description, confidence.

### 7.4 ADJUDICATE — the deterministic decision engine

Pure Python module (`tide_decision/`) with zero Snowflake imports. Receives a plain-dict evidence bundle, returns a Decision (target_status, resolution_type, eligible_amount, path_id, reason). Guardrails run first (G-01 through G-09, ordered, first match returns), then routing per subtype. **62 terminal paths, each with a pytest test.**

### 7.5 Async Tasks

- **T_SUMMARIZE** — triggered by stream on escalation events → generates human handoff summary
- **T_REPORT** — triggered by stream on close events → generates final case report
- **T_TIMEOUT_SWEEP** — cron `*/5 * * * *` → closes idle `pending_triage` cases per BRL rules

All tasks: `TASK_AUTO_RETRY_ATTEMPTS = 2`, write to `PIPELINE_LOG`, serverless.

---

## 8. Dependencies

Anaconda-channel only (Streamlit warehouse runtime): `streamlit`, `snowflake-snowpark-python`, `pydantic`. Dev-side: `pytest`, `snowflake-cli`. Additions require a row here.

---

## 9. Platform Constraints Accepted

- Warehouse-runtime Streamlit (per-viewer instance, session cache, ≤1.52.2, 32 MB)
- No Agents REST API from the app (SQL `DATA_AGENT_RUN` instead)
- No EAI/external HTTP on this account
- CHECK/FK not enforced (validation in procedures + tests)
- Triggered-task latency floor ~30s (hence the two-speed design)
- Vision requires SSE stage + no custom network policy
