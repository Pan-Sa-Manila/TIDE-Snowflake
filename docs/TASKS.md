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

## Workstream B: Decision Engine — 🔵 Gabe

**Goal:** Implement the full test matrix for the 62 terminal paths in the decision engine (`tide_decision/`).

- [ ] **B-1: Fact Derivation** — 🔵 Gabe
  - [ ] Implement robust bundle parsing logic in `fact_derivation.py`
  - [ ] Calculate derived facts (e.g., return window eligibility, stock levels, delivery SLA breach)
- [ ] **B-2: Guardrail Tests (G-01 to G-09)** — 🔵 Gabe
  - [ ] Write pytest bundles and assertions for all 9 guardrails in `test_guardrails.py`
  - [ ] Implement logic in `guardrails.py` to pass the tests
- [ ] **B-3: Routing Tests (R-01 to R-53)** — 🔵 Gabe
  - [ ] Write pytest bundles and assertions for all 53 routing paths in `test_routing.py`
  - [ ] Implement logic in `routing.py` to pass the tests
- [ ] **B-4: Test Coverage & Validation** — 🔵 Gabe
  - [ ] Ensure `test_coverage.py` is 100% green
  - [ ] Validate constants are read from parameters, not hardcoded

---

## Workstream C: Agents & Orchestration — 🔴 Keith

**Goal:** Wire up Cortex Agents, structured `AI_COMPLETE` calls, and Snowflake background tasks.

- [ ] **C-1: Investigation Agent (`TIDE.INVESTIGATION.INVESTIGATOR`)** — 🔴 Keith
  - [ ] Finalize YAML spec with clear tool selection policy
  - [ ] Implement custom tools (`GET_SHIPMENT_TIMELINE`, `GET_PAYMENT_STATUS`, `CHECK_INVENTORY`, `GET_REFUND_HISTORY`)
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

## Workstream D: Interface — 🟢 Nico

**Goal:** Build the Streamlit in Snowflake (warehouse runtime) UI for all three personas.

- [ ] **D-1: Shared UI Components** — 🟢 Nico
  - [ ] Build global `run_sql()` helper with error catching and pipeline logging
  - [ ] Implement real-time polling logic (`st.fragment`) for active pages
- [ ] **D-2: Customer Portal (`1_Customer.py`)** — 🟢 Nico
  - [ ] Build order/dispute selector
  - [ ] Implement chat interface for guided intake
  - [ ] Implement file uploader for proof images (writing to `PROOF_STAGE`)
  - [ ] Build visual status tracker
- [ ] **D-3: Approver Dashboard (`2_Approver.py`)** — 🟢 Nico
  - [ ] Build queue list sorted by age
  - [ ] Create evidence review panel (displaying bundles and proof images)
  - [ ] Implement one-click execution for approvals
  - [ ] Implement rejection rigor form (≥50 chars, policy citation picker via Cortex Search)
- [ ] **D-4: Escalation Console (`3_Escalation.py`)** — 🟢 Nico
  - [ ] Build claim-on-open queue logic
  - [ ] Implement live chat panel (3/5 layout)
  - [ ] Implement AI-summarized work panel and manual resolution actions (2/5 layout)

---

## Workstream E: Evidence & Submission — All Hands

**Goal:** Prepare the project for final hackathon submission.

- [ ] **E-1: Documentation** — 🟢 Nico
  - [ ] Finalize `README.md`
  - [ ] Update `SCHEMA.md` with final data model
  - [ ] Finalize `PROVENANCE.md`
- [ ] **E-2: Demo Readiness** — 🔴 Keith
  - [ ] Generate deterministic seed data matching the BRL matrix
  - [ ] Run `demo_reset.sql` and rehearse cold-start demo
  - [ ] Build submission deck
- [ ] **E-3: Hackathon Specifics** — 🔵 Gabe
  - [ ] Ensure all CoCo CLI build session logs are committed to `evidence/coco-transcripts/`
  - [ ] Dry-run the submission form
