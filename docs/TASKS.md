# TIDE Master Task Tracker

This document tracks all user stories and tasks for the TIDE project, aligned with `BUILD_PLAN.md`, `DETAILS.md`, and `ARCHITECTURE.md`. 
It serves as the single source of truth for what needs to be implemented.

**Status Legend:**
- `[x]` Completed
- `[/]` In Progress
- `[ ]` Not Started

**Assignees:** 🔵 Gabe · 🟢 Nico · 🔴 Keith

---

## Workstream A: Foundation (COMPLETED)

**Goal:** Canonical account setup, DDL, seed data, and project skeletons.

- [x] **A-1: Database Architecture (DDL)**
  - [x] Create warehouses, roles, and schema definitions (`00_account.sql`)
  - [x] Create event-sourced spine (`CASES`, `CASE_EVENTS`, `CHAT`) and derived current state view (`V_CASE_CURRENT`) (`01_triage_ddl.sql`)
  - [x] Create investigation schema, stage, and bundles (`02_investigation_ddl.sql`)
  - [x] Create decision schema, policies, constants, and logging (`03_decision_ddl.sql`)
  - [x] Create execution schema, reports, streams (`04_execution_ddl.sql`)
  - [x] Create simulated retail data (`05_retail_ddl.sql`)
- [x] **A-2: Decision Engine Skeleton**
  - [x] Implement deterministic pure Python module (`tide_decision/`) with no Snowflake imports
  - [x] Define types, derivation, guardrails, routing, and adjudicate entrypoint
- [x] **A-3: Orchestration Stubs & App Shell**
  - [x] Create Snowpark procedure wrappers (`intake_turn`, `assemble_evidence`, `analyze_proof`, `execute_resolution`, `timeout_sweep`)
  - [x] Define Cortex Agent spec (`agents/investigator.yaml`)
  - [x] Initialize Streamlit app with global theme and persona-based routing (`Home.py`, `1_Customer.py`, `2_Approver.py`, `3_Escalation.py`)
- [x] **A-4: Testing & Tooling Base**
  - [x] Set up `pytest` suite and `test_coverage.py` checker
  - [x] Create deployment scripts (`deploy.py`, `demo_reset.sql`)
  - [x] Implement pre-commit hook for destructive SQL prevention (`guard_sql.py`)

---

## Workstream B: Decision Engine — 🔵 Gabe (COMPLETE)

**Goal:** Implement the full test matrix for the 62 terminal paths in the decision engine (`tide_decision/`).

**Status:** 107 tests green (`pytest tests/decision -q`), all 62 BRL paths asserted. Day-4 gate met.

- [x] **B-1: Fact Derivation** — 🔵 Gabe
  - [x] Implement robust bundle parsing logic in `fact_derivation.py`
  - [x] Calculate derived facts (e.g., return window eligibility, stock levels, delivery SLA breach)
  - [x] Latest-wins tracking-event selection; `exception` falls back to `delayed` (§9)
  - [x] Subtype-relevant proof signals resolved as real facts (§9)
- [x] **B-2: Guardrail Tests (G-01 to G-09)** — 🔵 Gabe
  - [x] Write pytest bundles and assertions for all 9 guardrails in `test_guardrails.py`
  - [x] Implement logic in `guardrails.py` to pass the tests
  - [x] Ordering tests: G-01→G-02→G-03→G-04→G-05, G-06→G-07 (order is load-bearing)
- [x] **B-3: Routing Tests (R-01 to R-53)** — 🔵 Gabe
  - [x] Write pytest bundles and assertions for all 53 routing paths in `test_routing.py`
  - [x] Implement logic in `routing.py` to pass the tests
- [x] **B-4: Test Coverage & Validation** — 🔵 Gabe
  - [x] `test_coverage.py` enforces all 62 paths (assertion-based, not substring) and rejects undefined path ids
  - [x] Constants read from `constants` param via `types.constant()`; `DEFAULT_CONSTANTS` mirrors DETAILS.md §6
  - [x] `test_engine_purity.py` asserts zero Snowflake/network imports in `tide_decision/`

**Open item for WS-C:** the `DECISION.ADJUDICATE` wrapper must read `DECISION.RULE_CONSTANTS` and pass it as `adjudicate(bundle, constants)` — the engine defaults are a fallback, not the source of truth.

---

## Workstream C: Agents & Orchestration — 🔴 Keith

**Goal:** Wire up Cortex Agents, structured `AI_COMPLETE` calls, and Snowflake background tasks.

- [ ] **C-0: Seed Data (TODAY — everyone downstream needs it)** — 🔴 Keith
  - [ ] Write `sql/seed/seed_retail.sql` per test-matrix spec (5 customers, 10 SKUs, ~22 orders + payments/shipments/tracking/stock engineered per scenario)
  - [ ] Write `sql/seed/seed_decision.sql` (rule constants, policies, reason copy)
  - [ ] Load on the canonical account; verify with a scenario spot-check
- [ ] **C-1: Investigation Agent (`TIDE.INVESTIGATION.INVESTIGATOR`)** — 🔴 Keith
  - [ ] Create semantic view `RETAIL.DISPUTES_SV` (Cortex Analyst surface)
  - [ ] Create Cortex Search service `DECISION.POLICY_SEARCH` over policies
  - [ ] Finalize YAML spec with clear tool selection policy
  - [ ] Implement custom tools (`GET_SHIPMENT_TIMELINE`, `GET_PAYMENT_STATUS`, `CHECK_INVENTORY`, `GET_REFUND_HISTORY`)
- [ ] **C-5: Case Lifecycle Procedures (blocks all of WS-D)** — 🔴 Keith
  - [ ] `TRIAGE.CREATE_CASE` — one open case per order, reference number from sequence, proof gate sets initial status
  - [ ] `TRIAGE.POST_MESSAGE` — append-only insert into `CHAT`, idempotent on an event key
  - [ ] `TRIAGE.TRANSITION_STATE` — validates legality against DETAILS.md §8 before writing the `status_changed` event; illegal transition raises and writes nothing
  - [ ] `INVESTIGATION.REGISTER_PROOF` — record a staged file, reject duplicate sha256, enforce the upload cap
  - [ ] `EXECUTION.APPROVE_REQUEST` / `REJECT_REQUEST` — rejection enforces the reason length and citation minimums from `RULE_CONSTANTS`
  - [ ] `TRIAGE.CLAIM_CASE` — assignment event; a case assigned to someone else is read-only
  - [ ] `TRIAGE.APPEAL_CASE` — ACD to escalation, priority from `REASON_COPY`
  - [ ] `TRIAGE.CLOSE_CASE` — close reason and closed-by, per DETAILS.md §14
  - [ ] All of the above are pure SQL over existing tables: unaffected by the AI entitlement block
- [ ] **C-2: AI Complete Procedures** — 🔴 Keith
  - [ ] Implement `INTAKE_TURN` (turn-based classification and follow-ups)
  - [ ] Implement `ANALYZE_PROOF` (vision model analysis of images)
  - [ ] Implement `PLAN_RESOLUTION` and `SUMMARIZE_ESCALATION`
- [ ] **C-3: Event Streams & Triggered Tasks** — 🔴 Keith
  - [ ] Implement tasks triggered by `S_ESCALATIONS` and `S_CLOSURES` streams
  - [ ] Implement `TIMEOUT_SWEEP` cron task for idle cases
- [ ] **C-4: Pipeline Logging** — 🔴 Keith
  - [ ] Ensure all AI and task steps write to `EXECUTION.PIPELINE_LOG`

---

## Workstream D: Interface — 🟢 Nico (COMPLETE)

**Goal:** Build the Streamlit in Snowflake (warehouse runtime) UI for all three personas.

**Status:** All four tasks shipped. `ui/db.py` + extended `ui/theme.py` form the shared layer; all three persona pages are fully implemented and syntax-verified. Pushed in 5 atomic commits on `master`.

- [x] **D-1: Shared UI Components** — 🟢 Nico
  - [x] Build global `run_sql()` helper with error catching and pipeline logging
  - [x] Implement real-time polling logic (`st.fragment`) for active pages
- [x] **D-2: Customer Portal (`1_Customer.py`)** — 🟢 Nico
  - [x] Build order/dispute selector
  - [x] Implement chat interface for guided intake
  - [x] Implement file uploader for proof images (writing to `PROOF_STAGE`)
  - [x] Build visual status tracker
- [x] **D-3: Approver Dashboard (`2_Approver.py`)** — 🟢 Nico
  - [x] Build queue list sorted by age
  - [x] Create evidence review panel (displaying bundles and proof images)
  - [x] Implement one-click execution for approvals
  - [x] Implement rejection rigor form (≥50 chars, policy citation picker via Cortex Search)
- [x] **D-4: Escalation Console (`3_Escalation.py`)** — 🟢 Nico
  - [x] Build claim-on-open queue logic
  - [x] Implement live chat panel (3/5 layout)
  - [x] Implement AI-summarized work panel and manual resolution actions (2/5 layout)

---

## Workstream E: Evidence & Submission — All Hands

**Goal:** Prepare the project for final hackathon submission.

- [/] **E-1: Documentation** — 🟢 Nico
  - [x] Finalize `README.md`
  - [x] Update `SCHEMA.md` with final data model
  - [x] Finalize `PROVENANCE.md`
- [ ] **E-2: Demo Readiness** — 🔴 Keith
  - [ ] Generate deterministic seed data matching the BRL matrix
  - [ ] Run `demo_reset.sql` and rehearse cold-start demo
  - [ ] Build submission deck
- [ ] **E-3: Hackathon Specifics** — 🔵 Gabe
  - [ ] Ensure all CoCo CLI build session logs are committed to `evidence/coco-transcripts/`
  - [ ] Dry-run the submission form
