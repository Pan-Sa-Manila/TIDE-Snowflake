# AGENTS.md — TIDE: Snowflake CoCo Edition

> **Read this file in full before touching ANY code in this repository.**
> This document is the single source of truth for all architectural decisions, coding guardrails, and operational boundaries.

---

## 0. Project Identity

**TIDE** (Triage, Intelligence, and Dispute Engine) is a supervised agentic dispute-resolution platform for online retail support. This is a fresh project, purpose-built for the **Snowflake CoCo CLI Hackathon 2026**.

The system is a deeply integrated, AI-native data application built exclusively on the **Snowflake AI Data Cloud**, orchestrated via the **Snowflake CoCo CLI**, and powered by **Snowflake Cortex AI**. Everything — UI, logic, data, and AI — runs inside a single Snowflake account.

---

## 1. Where Truth Lives

| Question | Answer lives in |
|---|---|
| What are the business rules? | `docs/DETAILS.md` — **the law** |
| What tables/views exist? | `docs/SCHEMA.md` — updated on every migration |
| How is the system built? | `docs/ARCHITECTURE.md` — end-to-end design |
| What is the build schedule? | `docs/BUILD_PLAN.md` — workstreams, gates, cut lines |
| What do we do next? | `docs/TASKS.md` — canonical task tracker/stories |
| What are the coding rules? | `AGENTS.md` — ← you are here |

**Change protocol for business logic:** DETAILS.md first, tests second, code third. A code change that disagrees with DETAILS.md is a bug even if it "works". If two documents conflict, stop and flag it — do not pick silently.

---

## 2. Teardown Protocol — STRICT "DO NOT" LIST

> [!CAUTION]
> **Violating any rule below will break the architectural contract of this project.**

| #  | Rule |
|----|------|
| 1  | **DO NOT** use any ORM or query builder (Drizzle, Prisma, SQLAlchemy ORM mode, etc.). Raw parameterized SQL only. |
| 2  | **DO NOT** use PostgreSQL, SQLite, MySQL, or any database other than **Snowflake**. |
| 3  | **DO NOT** use external LLM endpoints (OpenAI, Anthropic, etc.). All AI is via **Snowflake Cortex AI** (`AI_COMPLETE`, Cortex Agent objects) executed natively in SQL. |
| 4  | **DO NOT** use Next.js, React, Express, FastAPI, Flask, or any external web framework. The UI is **Streamlit in Snowflake** (warehouse runtime). |
| 5  | **DO NOT** make external HTTP calls from the application. No `requests`, no webhooks, no external APIs. Everything stays inside Snowflake. |
| 6  | **DO NOT** call the Cortex Agents REST API from Streamlit. Agents are invoked via `SNOWFLAKE.CORTEX.DATA_AGENT_RUN(...)` in SQL. |
| 7  | **DO NOT** use `pip install` or packages outside the **Anaconda channel**. Streamlit warehouse runtime only supports `environment.yml` packages. |
| 8  | **DO NOT** concatenate variables directly into SQL strings. Use **parameterized queries** with bind variables. |
| 9  | **DO NOT** use the `ACCOUNTADMIN` role in any application-level query. All queries must use persona-specific roles. |
| 10 | **DO NOT** hardcode business constants in UI or procedures. They live in `DECISION.RULE_CONSTANTS` and are read, not repeated. |
| 11 | **DO NOT** UPDATE or DELETE rows in `TRIAGE.CHAT` or `TRIAGE.CASE_EVENTS`. These tables are **append-only**. |
| 12 | **DO NOT** let an LLM decide refund amounts. Money decisions are **deterministic** — the decision engine is pure Python with zero LLM calls. |

---

## 3. Enforced Technology Stack

| Layer | Technology |
|---|---|
| **UI** | Streamlit in Snowflake (warehouse runtime), three personas |
| **Orchestration** | Stored procedures (sync path) + streams & triggered tasks (async path) |
| **Decision Engine** | Pure Python module (`tide_decision/`) — deterministic, zero Snowflake imports |
| **AI / ML** | Cortex Agent object (investigation), `AI_COMPLETE` structured output (intake, vision, planning, summarization, reporting) |
| **Models** | Via Cortex: text model for structured output, vision model for proof analysis, `auto` for agent orchestration. Temperature 0, structured output everywhere |
| **Database** | Snowflake AI Data Cloud — 5 schemas (TRIAGE, INVESTIGATION, DECISION, EXECUTION, RETAIL) |
| **Data Pattern** | Event-sourced, append-only tables; current state derived via views |
| **Validation** | Pydantic for structured data validation in procedures |
| **Build Tool** | Snowflake CoCo CLI (AGENTS.md, skills, hooks, transcripts as evidence) |
| **Deploy** | `python scripts/deploy.py` → ordered, idempotent SQL via Snowflake CLI |
| **Testing** | `pytest` — one test per BRL terminal path, runnable locally with no account |

---

## 4. Naming Conventions

### 4.1 File & Directory Naming
| Scope | Convention | Examples |
|---|---|---|
| SQL scripts | Numbered prefix | `00_account.sql`, `01_triage_ddl.sql`, `02_seed.sql` |
| Python modules | snake_case | `tide_decision/`, `adjudicate.py`, `fact_derivation.py` |
| Streamlit pages | Numbered prefix | `1_Customer.py`, `2_Approver.py`, `3_Escalation.py` |
| Docs | UPPER_SNAKE or descriptive | `ARCHITECTURE.md`, `SCHEMA.md`, `DETAILS.md` |

### 4.2 Code Naming
| Scope | Convention | Examples |
|---|---|---|
| Python functions/vars | snake_case | `adjudicate()`, `assemble_evidence()`, `case_id` |
| Python classes | PascalCase | `EvidenceBundle`, `Decision`, `CaseStatus` |
| SQL objects | UPPER_SNAKE | `TIDE.TRIAGE.CASES`, `TIDE.DECISION.ADJUDICATE` |
| Snowflake roles | UPPER_SNAKE with `TIDE_` prefix | `TIDE_ADMIN`, `TIDE_CUSTOMER`, `TIDE_APPROVER` |
| Constants | UPPER_SNAKE | `AUTONOMOUS_LIMIT_USD`, `RETURN_WINDOW_DAYS` |
| Streamlit session keys | snake_case | `current_case_id`, `selected_order` |

### 4.3 SQL Naming Rules
- Prefix `TIDE_` **only** at account-level shared namespaces: warehouses (`TIDE_WH_APP`, `TIDE_WH_TASKS`), roles, integrations.
- Never prefix inside the `TIDE` database — `TIDE.DECISION.TIDE_CASES` says TIDE twice.
- Name for the domain, not the pattern: `ADJUDICATE`, `ASSEMBLE_EVIDENCE`, `ANALYZE_PROOF` — not `PROCESS_CASE`, `GET_DATA`, `HANDLE_IMAGE`.

---

## 5. Project Structure

```text
TIDE-Snowflake/
├── sql/
│   ├── 00_account.sql           # Warehouses, roles, grants
│   ├── 01_triage_ddl.sql        # TRIAGE schema: cases, events, chat, views
│   ├── 02_investigation_ddl.sql # INVESTIGATION schema: bundles, proofs, stage
│   ├── 03_decision_ddl.sql      # DECISION schema: constants, policies, decisions
│   ├── 04_execution_ddl.sql     # EXECUTION schema: requests, reports, pipeline log
│   ├── 05_retail_ddl.sql        # RETAIL schema: simulated enterprise data
│   └── seed/                    # Deterministic demo data (per test matrix)
├── tide_decision/               # Pure Python decision engine (no Snowflake imports)
│   ├── __init__.py
│   ├── adjudicate.py            # Main entry: guardrails → routing → Decision
│   ├── fact_derivation.py       # Bundle → derived facts
│   ├── guardrails.py            # G-01 through G-09
│   ├── routing.py               # R-01 through R-53
│   └── types.py                 # Decision, EvidenceBundle, CaseStatus enums
├── procedures/                  # Snowpark procedure wrappers (thin)
│   ├── intake_turn.py
│   ├── assemble_evidence.py
│   ├── analyze_proof.py
│   ├── execute_resolution.py
│   └── timeout_sweep.py
├── agents/
│   └── investigator.yaml        # CREATE AGENT spec source
├── streamlit/
│   ├── Home.py                  # Landing / login routing
│   ├── pages/
│   │   ├── 1_Customer.py        # Customer chat + intake
│   │   ├── 2_Approver.py        # Approval queue + review
│   │   └── 3_Escalation.py      # Escalation console
│   ├── ui/
│   │   └── theme.py             # inject_css(), palette, status colors
│   └── .streamlit/
│       └── config.toml          # Streamlit theme config
├── tests/
│   └── decision/                # pytest — one test per BRL path id
│       ├── test_guardrails.py
│       ├── test_routing.py
│       ├── test_coverage.py     # Fails if any BRL path lacks a test
│       └── bundles/             # Plain-dict test fixtures
├── scripts/
│   ├── deploy.py                # Master deploy: SQL → procedures → agent → app
│   ├── guard_sql.py             # Pre-commit hook for destructive SQL
│   └── demo_reset.sql           # Reset to pristine seed state
├── evidence/
│   └── coco-transcripts/        # Committed CoCo CLI build session logs
├── docs/
│   ├── ARCHITECTURE.md          # System design (§5 of this file points here)
│   ├── BUILD_PLAN.md            # Workstreams, schedule, gates, cut lines
│   ├── DETAILS.md               # Business requirements & rules (the law)
│   ├── SCHEMA.md                # Living schema reference (updated every migration)
│   └── TASKS.md                 # Canonical task tracker and user stories
├── .cortex/                     # CoCo CLI skills & hooks
│   └── skills/
├── AGENTS.md                    # ← You are here
├── README.md
├── PROVENANCE.md                # Dataset & licence declarations
├── SECURITY.md
├── CONTRIBUTING.md
└── LICENSE
```

---

## 6. Architecture — Two Speeds, One Rule

> [!IMPORTANT]
> Anything a person is actively waiting on is a **synchronous procedure call**. Anything nobody watches in real time is a **triggered or scheduled task**.

### 6.1 Synchronous Chat Path (person is waiting)
```
Customer message → INTAKE_TURN() → ASSEMBLE_EVIDENCE() → ADJUDICATE() → EXECUTE_RESOLUTION()
```
Each step is a stored procedure. The UI shows stage-by-stage progress via `PIPELINE_LOG`, not a spinner.

### 6.2 Asynchronous Path (nobody is watching)
```
Stream on CASE_EVENTS → T_SUMMARIZE (on escalation)
Stream on CASE_EVENTS → T_REPORT (on close)
T_TIMEOUT_SWEEP (cron */5 * * * *) → close idle intake cases
```
Triggered tasks have ~30s minimum latency — that constraint drew this line.

### 6.3 Component Inventory

| Component | Kind | Why |
|---|---|---|
| `INVESTIGATION.INVESTIGATOR` | **Cortex Agent object** | Tool *selection* is real: which sources to query depends on dispute type |
| `TRIAGE.INTAKE_TURN` | Procedure + `AI_COMPLETE` | Single transformation per turn; chat latency budget |
| `INVESTIGATION.ANALYZE_PROOF` | Procedure + `AI_COMPLETE` vision | Fixed task: image → signals |
| `DECISION.ADJUDICATE` | Procedure wrapping **pure Python** | Money decisions are deterministic — no LLM |
| `EXECUTION.PLAN_RESOLUTION` | `AI_COMPLETE` structured | Fixed task: decision → customer-facing plan |
| `EXECUTION.SUMMARIZE` | Task + `AI_COMPLETE` | Escalation summary generation |
| `EXECUTION.REPORT` | Task + `AI_COMPLETE` | Final case report generation |
| `TRIAGE.TIMEOUT_SWEEP` | Task (cron) | Plain SQL, no AI needed |

For full architecture details, see [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

---

## 7. Streamlit UI Rules

### 7.1 Three Personas, One App
| Persona | Page | Layout |
|---|---|---|
| **Customer** | `1_Customer.py` | Single centered column (~760px). Chat + composer + status tracker |
| **Approver** | `2_Approver.py` | Full width. Queue columns (refund/return/replacement) + case review panel |
| **Escalation** | `3_Escalation.py` | Full width. Chat left 3/5, work panel right 2/5 (Actions · Summary · Details tabs) |

### 7.2 Streamlit Constraints (warehouse runtime)
- Streamlit ≤1.52.2, Anaconda-channel packages only via `environment.yml`
- Per-viewer app instance, per-session cache, 32 MB message cap
- No `st.file_uploader` files persisted implicitly — always `session.file.put_stream(...)` then `ALTER STAGE ... REFRESH`
- Custom CSS lives in exactly one place: `ui/theme.py::inject_css()`

### 7.3 Design Identity
- Theme: **calm water over process anxiety** — deep teal, generous whitespace
- Voice: plain, direct, specific. The assistant explains *why*, never vague reassurance
- Light theme only for v1
- Every status conveyed by pill **text**, never color alone

---

## 8. Snowflake & Cortex AI Integration

### 8.1 Database Object Naming
```
TIDE (database)
├── TRIAGE       — cases, chat, events, intake procedure, sweeper
├── INVESTIGATION — evidence bundles, proof files + stage, investigator agent, vision
├── DECISION     — adjudicator, rule constants, policies, reason copy, decision log
├── EXECUTION    — resolution requests/records, case reports, pipeline log
└── RETAIL       — simulated enterprise: orders, items, payments, refunds, shipments, stock
```

### 8.2 Cortex AI Rules
- Every LLM call uses `response_format` with a JSON schema + `additionalProperties: false` + exhaustive `required` at every level + `temperature: 0`
- **Banned schema keywords** (they ERROR in Cortex): `format`, `minLength`, `maxLength`, `minimum`, `maximum`, `multipleOf`, `minItems`, `maxItems`, `uniqueItems`, `patternProperties`. Express constraints in `description` prose instead
- Every call wrapped in `TRY_PARSE_JSON`; NULL → one retry → escalate branch
- Model names are config values in `RULE_CONSTANTS`, not literals

### 8.3 SQL Safety Rules
- **Always** use parameterized queries with bind variables
- **Never** string-interpolate user input into SQL
- All input must be validated with Pydantic before reaching the procedure layer
- CHECK constraints and FKs are **not enforced** by Snowflake — every rule is validated in code and covered by a test

For the complete schema reference, see [`docs/SCHEMA.md`](docs/SCHEMA.md).

---

## 9. Business Rules & System Constants

These are the canonical threshold values. They must match exactly in code and are seeded from `DECISION.RULE_CONSTANTS`.

| Constant | Value | Context |
|---|---|---|
| `AUTONOMOUS_LIMIT_USD` | **$50.00** | Max amount TIDE may refund or replace without approval |
| `RETURN_WINDOW_DAYS` | 7 days | From window-basis date |
| `DELIVERY_SLA_BREACH_DAYS` | 3 days | Past estimated delivery |
| `STALE_TRANSIT_DAYS` | 7 days | Without tracking movement |
| `INACTIVITY_TIMEOUT_MIN` | 15 minutes | Idle in `pending_triage` before auto-close |
| `MIN_REJECTION_CHARS` | 50 | Minimum human rejection-reason length |
| `MIN_REJECTION_CITATIONS` | 1 | Minimum policy citations on a human rejection |
| `MAX_PROOF_UPLOADS` | 2 | Max proof images per case |
| `MAX_FOLLOWUP_QUESTIONS` | 3 | Intake may ask at most this many follow-ups |
| `CURRENCY` | USD | All amounts |

### 9.1 Case Status Lifecycle (9 states)

```
(new) → pending_triage / awaiting_customer_proof (if proof required)
pending_triage → awaiting_customer_proof | awaiting_customer_decision | awaiting_approval | approved_executing | escalated_human_required | closed
awaiting_customer_proof → pending_triage (≥1 upload) | closed
awaiting_customer_decision → escalated_human_required (appeal) | closed
awaiting_approval → approved_executing (approve) | rejected_human_required (reject) | closed
approved_executing → resolved | closed
rejected_human_required → resolved | closed
escalated_human_required → resolved | closed
resolved → closed
closed → (terminal)
```

- Self-transition is always legal (idempotent retries)
- Transitions are events in `TRIAGE.CASE_EVENTS`; legality validated before insert
- `closed` is terminal — no further updates permitted

For the complete business rules and 62 terminal paths, see [`docs/DETAILS.md`](docs/DETAILS.md).

---

## 10. Security Posture

### 10.1 Role-Based Access Control (RBAC)
| Role | Access |
|---|---|
| `TIDE_ADMIN` | Owns objects, deploys |
| `TIDE_CUSTOMER` | Execute intake/upload/close/appeal procedures + select on own-case views (`WHERE customer_id = CURRENT_USER()`) |
| `TIDE_APPROVER` | Queue views + approve/reject procedures |
| `TIDE_ESCALATION` | Escalated-case views + action procedures (assignment checked inside each procedure) |

- Procedures are `EXECUTE AS OWNER` — persona roles can act only through them
- Direct DML on core tables is not granted to any persona role
- State legality (case transitions) is enforced inside procedures

### 10.2 Secrets & Environment
- No secrets in the repo; `connections.toml` is local-only
- Nothing to leak: there are no external API keys because there are no external APIs
- Connection configured via `~/.snowflake/connections.toml` with a connection named `tide`

### 10.3 Chat Append-Only Rule
- Chat messages and case events are **append-only** — no UPDATE, no DELETE
- Current case state is derived through views (`V_CASE_CURRENT`)
- This ensures a complete, tamper-proof audit trail for every case

---

## 11. CoCo CLI & Build Evidence

### 11.1 Build-time vs Runtime AI (state this in the README)
- **Build-time: CoCo CLI.** AGENTS.md + `.cortex/skills/` + hooks steer it; sessions run with `--output-format stream-json` and transcripts are committed to `evidence/coco-transcripts/`
- **Runtime: Cortex.** One agent object where tool *selection* is real (investigation); `AI_COMPLETE` structured calls where the task is fixed; a pure function where money is decided. The deliberate absence of an LLM in adjudication is an architecture feature

### 11.2 Deploy Script
`python scripts/deploy.py --connection tide` → runs `sql/` in order via Snowflake CLI, uploads procedures, creates the agent from `agents/investigator.yaml`, deploys the Streamlit app. Re-runnable from zero.

---

## 12. Git Branching Strategy

| Branch | Purpose |
|---|---|
| `main` | Protected submission branch |
| `dev` | Primary integration branch |
| `feature/*` | Granular feature branches |

---

## 13. Code Quality Checklist

Before committing any code, verify:

- [ ] No hardcoded business constants — they come from `RULE_CONSTANTS`
- [ ] No external HTTP calls or pip packages outside Anaconda channel
- [ ] All SQL uses parameterized queries (bind variables)
- [ ] All Cortex calls use structured output with `temperature: 0`
- [ ] Decision engine has zero Snowflake imports
- [ ] Every BRL path has a pytest test
- [ ] Chat and event tables are append-only (no UPDATE/DELETE)
- [ ] Procedures validate state transitions before writing events
- [ ] Model names are read from `RULE_CONSTANTS`, not hardcoded
- [ ] `evidence/coco-transcripts/` contains build session logs

---

*This document governs all development on TIDE: Snowflake CoCo Edition. When in doubt, refer here first.*
