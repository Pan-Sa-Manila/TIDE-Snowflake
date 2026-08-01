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

**Goal:** Implement the full test matrix for the 63 terminal paths in the decision engine (`tide_decision/`).

**Status:** 114 tests green (`pytest tests/ -q`), all 63 BRL paths asserted. Day-4 gate met. G-10 was added to the engine after Gabe's branch closed — see the WS-C note below.

- [x] **B-1: Fact Derivation** — 🔵 Gabe
  - [x] Implement robust bundle parsing logic in `fact_derivation.py`
  - [x] Calculate derived facts (e.g., return window eligibility, stock levels, delivery SLA breach)
  - [x] Latest-wins tracking-event selection; `exception` falls back to `delayed` (§9)
  - [x] Subtype-relevant proof signals resolved as real facts (§9)
- [x] **B-2: Guardrail Tests (G-01 to G-10)** — 🔵 Gabe · G-10 🔴 Keith
  - [x] Write pytest bundles and assertions for all 9 guardrails in `test_guardrails.py`
  - [x] Implement logic in `guardrails.py` to pass the tests
  - [x] Ordering tests: G-01→G-02→G-03→G-04→G-05, G-06→G-07 (order is load-bearing)
  - [x] **G-10** duplicate-charge evidence guardrail + `confirmed_payment_count`, ordering tests G-03→G-10 and G-04→G-10 (commit `e34b5c7`)
- [x] **B-3: Routing Tests (R-01 to R-53)** — 🔵 Gabe
  - [x] Write pytest bundles and assertions for all 53 routing paths in `test_routing.py`
  - [x] Implement logic in `routing.py` to pass the tests
- [x] **B-4: Test Coverage & Validation** — 🔵 Gabe
  - [x] `test_coverage.py` enforces all 63 paths (assertion-based, not substring) and rejects undefined path ids
  - [x] Constants read from `constants` param via `types.constant()`; `DEFAULT_CONSTANTS` mirrors DETAILS.md §6
  - [x] `test_engine_purity.py` asserts zero Snowflake/network imports in `tide_decision/`

**Open item for WS-C:** the `DECISION.ADJUDICATE` wrapper must read `DECISION.RULE_CONSTANTS` and pass it as `adjudicate(bundle, constants)` — the engine defaults are a fallback, not the source of truth.

---

## Workstream C: Agents & Orchestration — 🔴 Keith

**Goal:** Wire up Cortex Agents, structured `AI_COMPLETE` calls, and Snowflake background tasks.

- [x] **C-0: Seed Data** — 🔴 Keith · deployed and verified on canonical
  - [x] Write `sql/seed/seed_retail.sql` per test-matrix spec (5 customers, 10 SKUs, 23 orders + payments/shipments/tracking/stock engineered per scenario)
  - [x] Write `sql/seed/seed_decision.sql` (14 rule constants, 10 reason-copy rows, 14 policies)
  - [x] Load on the canonical account; verify with a scenario spot-check
- [/] **C-1: Investigation Agent (`TIDE.INVESTIGATION.INVESTIGATOR`)** — 🔴 Keith
  - [x] Create semantic view `RETAIL.DISPUTES_SV` (Cortex Analyst surface) — 8 tables, 7 relationships, 12 metrics
  - [x] Create Cortex Search service `DECISION.POLICY_SEARCH` over policies — ACTIVE, 14 rows indexed
  - [ ] Finalize YAML spec with clear tool selection policy, then `CREATE AGENT`
  - [x] Implement custom tools (`GET_SHIPMENT_TIMELINE`, `GET_PAYMENT_STATUS`, `CHECK_INVENTORY`, `GET_REFUND_HISTORY`)
- [x] **C-5: Case Lifecycle Procedures (blocks all of WS-D)** — 🔴 Keith · `sql/09_lifecycle_procedures.sql`, commit `c188da2`
  - Names follow the UI's existing call sites, not the original spec names — see `docs/DECISIONS.md`. `session.call()` passes args positionally and callers read **lowercase** keys off the returned object.
  - [x] `TRIAGE.OPEN_CASE(order_id, subtype, resolution)` → `{case_id}` / `{error}` — one open case per order, reference number from `CASE_SEQ`, proof gate sets initial status
  - [x] `TRIAGE.CLOSE_CASE` — **two arities**: `(case_id, closed_by)` from the customer page and `(case_id, closed_by, close_reason)` from escalation, per DETAILS.md §14
  - [x] `TRIAGE.CLAIM_CASE(case_id)` — assignment event; actor from `CURRENT_USER()`; a case assigned to someone else is read-only
  - [x] `TRIAGE.APPEAL_CASE(case_id)` — ACD to escalation, priority from `REASON_COPY`
  - [x] `TRIAGE.RESUME_INTAKE(case_id)` — `awaiting_customer_proof` → `pending_triage` once a proof exists
  - [x] `TRIAGE.AGENT_MESSAGE(case_id, content)` — escalation agent chat turn
  - [x] `TRIAGE.ESCALATION_RESOLVE(case_id, resolve_type, amount, note)` — manual resolution
  - [x] `EXECUTION.EXECUTE_RESOLUTION(case_id, request_id)` / `REJECT_RESOLUTION(case_id, request_id, reason, citations ARRAY)` — rejection enforces the reason length and citation minimums from `RULE_CONSTANTS`
  - [x] Internal helpers, no UI caller: `TRIAGE.TRANSITION_STATE` (validates legality against DETAILS.md §8; illegal transition raises and writes nothing), `TRIAGE.POST_MESSAGE` (append-only `CHAT` insert), `INVESTIGATION.REGISTER_PROOF` (staged file, reject duplicate sha256, enforce upload cap)
  - [x] All of the above are pure SQL over existing tables: unaffected by any AI entitlement block
  - [x] Smoke-tested on canonical: both open paths, duplicate/unknown/not-yours refused, claim idempotent, close terminal, illegal transition raises, rejection minimums enforced
- [x] **C-6: Engine bridge — the linchpin** — 🔴 Keith
  - [x] `DECISION.ADJUDICATE` — Python procedure importing `tide_decision` from `DECISION.CODE_STAGE`. Reads `DECISION.RULE_CONSTANTS` and passes it as `adjudicate(bundle, constants)`
  - [x] `INVESTIGATION.ASSEMBLE_EVIDENCE` — builds the bundle per SCHEMA.md §5 from the four tools, carrying `payments[]` so G-10 can fire
  - [x] Writes the decision to `DECISION.DECISIONS` and a `decision_made` event; creates the `EXECUTION.RESOLUTION_REQUESTS` row the approver queue reads. All three in one transaction
  - [x] `deploy.py` step 3 packages `tide_decision/` and uploads it before creating the procedure
  - [x] Verified end to end on canonical: two confirmed charges → R-01, refund 41.74, `approved_executing`, pending request row; one confirmed charge → G-10, `insufficient_evidence`, `awaiting_customer_decision`, no request row
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

**Open handoff to WS-D (🟢 Nico):** two items, neither blocking WS-C.
- [ ] `1_Customer.py::load_orders()` reads `TIDE.RETAIL.ORDERS` directly. Repoint it at `TRIAGE.V_MY_ORDERS` (same columns, already secure and filtered on `CURRENT_USER()`), and the affected-items picker at `V_MY_ORDER_ITEMS`. Once done, the `GRANT SELECT ON ALL TABLES IN SCHEMA RETAIL TO ROLE TIDE_CUSTOMER` in `05_retail_ddl.sql` can be revoked — it currently contradicts `ARCHITECTURE.md` §4, which says the customer role gets no base-table grants.
- [ ] Approver evidence panel: `refunds.total_refunded` returns **no row** for an order with no refunds, not `0.00`. Child-table metrics inner join. Reads as a bug on screen if unhandled — see `SCHEMA.md` §7.

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
  - [x] Generate deterministic seed data matching the BRL matrix
  - [ ] Run `demo_reset.sql` and rehearse cold-start demo
  - [ ] Build submission deck **on the organizers' provided template** (link in `docs/SUBMISSION.md`)
  - [ ] **Record the public demo video** (Tue 4, off a clean matrix pass — new mandatory requirement)
  - [ ] Write the Prototype/MVP brief
- [ ] **E-4: Judge Access (mandatory, test before the deadline)** — 🟢 Nico
  - [ ] Create judge users on the canonical account with a read-scoped role and `ALLOWED_INTERFACES = (STREAMLIT)`
  - [ ] Create demo customer users whose usernames match the seeded `customer_id` values, or the customer page renders empty
  - [ ] Have someone outside the team open the deployed link cold and confirm they can use it
- [ ] **E-5: CoCo Evidence** — 🔵 Gabe
  - [ ] Screen-record CoCo sessions as they happen (organizers explicitly encourage this as supplementary evidence)
  - [ ] Keep `evidence/` current
- [ ] **E-3: Hackathon Specifics** — 🔵 Gabe
  - [ ] Ensure all CoCo CLI build session logs are committed to `evidence/coco-transcripts/`
  - [ ] Dry-run the submission form
