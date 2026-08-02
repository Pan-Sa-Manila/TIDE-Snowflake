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

**Status:** 114 tests green (`pytest tests/ -q`), all 63 BRL paths asserted. Day-4 gate met. G-10 was added to the engine by Keith after Gabe's branch closed (B-2 below).

- [x] **B-1: Fact Derivation** — 🔵 Gabe
  - [x] Implement robust bundle parsing logic in `fact_derivation.py`
  - [x] Calculate derived facts (e.g., return window eligibility, stock levels, delivery SLA breach)
  - [x] Latest-wins tracking-event selection; `exception` falls back to `delayed` (§9)
  - [x] Subtype-relevant proof signals resolved as real facts (§9)
- [x] **B-2: Guardrail Tests (G-01 to G-10)** — 🔵 Gabe · G-10 🔴 Keith
  - [x] Write pytest bundles and assertions for all 10 guardrails in `test_guardrails.py`
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

~~**Open item for WS-C:** the `DECISION.ADJUDICATE` wrapper must read `DECISION.RULE_CONSTANTS` and pass it as `adjudicate(bundle, constants)`.~~ **Closed** by C-6 — the wrapper reads the table and passes it in; the engine's `DEFAULT_CONSTANTS` remain a fallback so the module stays runnable without a database.

---

## Workstream C: Agents & Orchestration — 🔴 Keith

**Goal:** Wire up Cortex Agents, structured `AI_COMPLETE` calls, and Snowflake background tasks.

**Status:** the synchronous chain is closed and running on canonical — a customer message drives `INTAKE_TURN` → `ASSEMBLE_EVIDENCE` → `ADJUDICATE`, producing a decision and a resolution request. Async tasks are resumed. **One item open: `ANALYZE_PROOF` (vision), plus `PLAN_RESOLUTION`.** Tasks are listed in numeric order below; they were built out of order (C-5 and C-6 first, because everything else depended on them).

- [x] **C-0: Seed Data** — 🔴 Keith · deployed and verified on canonical
  - [x] Write `sql/seed/seed_retail.sql` per test-matrix spec (5 customers, 10 SKUs, 23 orders + payments/shipments/tracking/stock engineered per scenario)
  - [x] Write `sql/seed/seed_decision.sql` (14 rule constants, 10 reason-copy rows, 14 policies)
  - [x] Load on the canonical account; verify with a scenario spot-check
- [x] **C-1: Investigation Agent (`TIDE.INVESTIGATION.INVESTIGATOR`)** — 🔴 Keith
  - [x] Create semantic view `RETAIL.DISPUTES_SV` (Cortex Analyst surface) — 8 tables, 7 relationships, 12 metrics
  - [x] Create Cortex Search service `DECISION.POLICY_SEARCH` over policies — ACTIVE, 14 rows indexed
  - [x] Finalize YAML spec with clear tool selection policy, then `CREATE AGENT` — `sql/13_investigator_agent.sql`. Verified with `DATA_AGENT_RUN` on ORD-1007: selected `GetPaymentStatus`, then reached for `GetRefundHistory` unprompted, reported both confirmed charges and declined to recommend an outcome
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
- [/] **C-2: AI Complete Procedures** — 🔴 Keith · `sql/11_ai_procedures.sql`
  - Every AI call goes through one wrapper, `DECISION.AI_JSON`, which reads the model from `RULE_CONSTANTS`. No procedure names a model. Every call site has a deterministic fallback and takes it when the model is unavailable, malformed, or answers outside the closed set.
  - [x] `INTAKE_TURN` — records the turn, may ask one bounded follow-up, otherwise runs `ASSEMBLE_EVIDENCE` → `ADJUDICATE`. **This is the orchestrator**; the whole chat path runs through it
  - [x] `SUMMARIZE_ESCALATION` — writes to `PIPELINE_LOG` as `T_SUMMARIZE` with the text under `detail.summary`, which is what `3_Escalation.py` already reads
  - [x] `GENERATE_REPORT` — one `CASE_REPORTS` row on close, assembled from recorded facts with the model writing only the prose on top
  - [ ] `ANALYZE_PROOF` (vision) — **not started.** Cut line 3 covers stubbing it; `AI_COMPLETE` + `TO_FILE` on a staged image is still unverified
  - [ ] `PLAN_RESOLUTION` — **not started.** Named in `AGENTS.md` §6.3: decision → customer-facing plan. Not blocking, because `INTAKE_TURN` already returns the decision and the UI renders status from `V_CASE_CURRENT`; it upgrades the copy the customer reads from templated to written. Templated fallback required either way
- [x] **C-3: Event Streams & Triggered Tasks** — 🔴 Keith · `sql/12_streams_tasks.sql`
  - [x] `T_SUMMARIZE` on `S_ESCALATIONS`, `T_REPORT` on `S_CLOSURES` — both serverless triggered, both resumed and `started`
  - [x] `T_TIMEOUT_SWEEP` cron `*/5 * * * *` → `TRIAGE.TIMEOUT_SWEEP`, closing idle `pending_triage` cases through `CLOSE_CASE` so the state machine stays enforced in one place
  - [x] Each consumer drains its stream into a temp table first — reading the stream in DML is what advances the offset, without which a task re-fires forever
- [x] **C-4: Pipeline Logging** — 🔴 Keith
  - [x] Every pipeline-step procedure and task writes one `EXECUTION.PIPELINE_LOG` row. Read-only tool procedures deliberately do not — the calling step logs once for the whole assembly

---

## Workstream D: Interface — 🟢 Nico (pages complete, not yet wired)

**Goal:** Build the Streamlit in Snowflake (warehouse runtime) UI for all three personas.

**Status:** All four tasks shipped. `ui/db.py` + extended `ui/theme.py` form the shared layer; all three persona pages are fully implemented and syntax-verified. Pushed in 5 atomic commits on `master`.

**Not yet true end to end:** the pages were built before the backend existed, and the procedures they call only landed on 1 Aug. Names and arities now match on both sides, but the two halves have never been exercised together, and the app itself is not deployed (`deploy.py` step 4 is still a stub). Budget real time for integration.

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

- [x] **E-1: Documentation** — 🟢 Nico
  - [x] Finalize `README.md` — including the build-time (CoCo) versus runtime (Cortex) split, which `SUBMISSION.md` flags as organizer-endorsed framing
  - [x] Update `SCHEMA.md` with final data model
  - [x] Finalize `PROVENANCE.md`
- [ ] **E-2: Demo Readiness** — 🔴 Keith
  - [x] Generate deterministic seed data matching the BRL matrix
  - [ ] Run `demo_reset.sql` and rehearse cold-start demo
  - [ ] Build submission deck **on the organizers' provided template** (link in `docs/SUBMISSION.md`)
  - [ ] **Record the public demo video** (Tue 4, off a clean matrix pass — new mandatory requirement)
  - [ ] Write the Prototype/MVP brief
- [ ] **E-4: Judge Access (mandatory, test before the deadline)** — 🟢 Nico → taken over by Keith
  - [x] Create judge users on the canonical account with a read-scoped role and `ALLOWED_INTERFACES = (STREAMLIT)`
        — `TIDE_JUDGE` role + four users live; `sql/14_demo_access.sql`. The role is the union of
        the three personas by role inheritance, so it cannot drift from them. Grants verified by
        role-switching: all twelve persona surfaces resolve.
  - [x] Create demo customer users whose usernames match the seeded `customer_id` values, or the customer page renders empty
        — `sql/seed/seed_demo_customer.sql` now seeds one set of five orders per owner
        (deployer, `TIDE_DEMO_CUSTOMER`, `TIDE_JUDGE`), 15 rows verified.
  - [ ] **BLOCKER: password login is refused — MFA enrolment is mandatory on this account.**
        Verified for all four accounts: the password is accepted, then
        `250001 (08001): Multi-factor authentication is required for this account. Log in to
        Snowsight to enroll.` A judge handed these credentials hits an enrolment wall, not the app.
        A user-scoped authentication policy is the intended fix, but `MFA_ENROLLMENT = OPTIONAL`
        was silently stored as `REQUIRED_SNOWFLAKE_UI_PASSWORD_ONLY` — the judge's exact path — so
        it is **not** yet a fix. See the note in `sql/14_demo_access.sql`. Fallbacks if the policy
        cannot be made to hold: enrol MFA on the judge account once and publish that it is
        enrolled, or move canonical to an account without the MFA mandate.
  - [ ] Confirm `ALLOWED_INTERFACES = ('STREAMLIT')` still admits the Snowsight page that hosts a
        Streamlit app — untestable until the app is deployed, and a lockout if it does not
  - [ ] Have someone outside the team open the deployed link cold and confirm they can use it
- [ ] **E-5: CoCo Evidence** — 🔵 Gabe
  - [ ] Screen-record CoCo sessions as they happen (organizers explicitly encourage this as supplementary evidence)
  - [ ] Keep `evidence/` current
- [ ] **E-3: Hackathon Specifics** — 🔵 Gabe
  - [ ] Ensure all CoCo CLI build session logs are committed to `evidence/coco-transcripts/`
  - [ ] Dry-run the submission form
