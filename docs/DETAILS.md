# TIDE · Business Requirements & Rules

**This document is law.** Code implements it; tests assert it; no rule exists only in code.
Change protocol: edit here → update tests → change code.

---

## 1. Problem

Post-purchase disputes are the most expensive routine interaction in online retail. Industry benchmarks put a human-handled support contact at **$5–12**; a dispute contact runs higher (investigation across order, payment, and logistics systems; multi-touch resolution; write-offs when agents give up and refund). Three structural failures:

1. **Investigation is swivel-chair work.** Agents pivot across OMS, payment gateway, carrier portal, and inventory before making any judgment. Most handling time is evidence assembly, not decision-making.
2. **Consistency is aspirational.** Two agents, same facts, different outcomes. Policy exists as PDFs, not as enforcement. Auditors reconstruct decisions from chat logs.
3. **Automation attempts are all-or-nothing.** Rules-only bots can't understand a free-text complaint; LLM-only bots make up refund amounts. Both erode trust in opposite directions.

---

## 2. Solution Economics

TIDE's wager: **most disputes are cheap to decide once the evidence is assembled — and evidence assembly is exactly what an agentic system automates safely.**

| Lever | Mechanism | Metric |
|---|---|---|
| Deflection | Low-value disputes (≤ $50) resolved end-to-end with zero human touch | % cases fully autonomous |
| Faster human decisions | Approvers receive assembled evidence + a recommended decision with cited rules | Median time-in-queue |
| Cheaper escalations | Escalation agents start from an AI summary + one-click actions, not a raw transcript | Handling time per escalated case |
| Loss prevention | Guardrails catch duplicate refunds, unconfirmed payments, delivered-but-disputed claims **before** money moves | Blocked-payout count with evidence |
| Auditability | Every decision traces to a rule id, an input snapshot, and an event trail | % decisions replayable |

---

## 3. Objectives & Target Metrics (demo-scale)

| # | Objective | Target |
|---|---|---|
| O1 | Autonomous resolution of in-policy low-value disputes | 100% of seeded ≤$50 clean paths, zero human touch |
| O2 | Time-to-resolution, autonomous path | < 2 minutes intake-to-resolved |
| O3 | Human decision quality | Every approval/rejection carries evidence + policy citation; rejection rigor enforced (≥50 chars + citation) |
| O4 | Anomaly interception | 4 guardrail classes demonstrably fire (duplicate refund, payment unconfirmed, delivered-but-disputed, proof contradiction) |
| O5 | Audit completeness | Every closed case has a report; every decision replayable from its event snapshot |

---

## 4. Personas

| Persona | Goal | Surface |
|---|---|---|
| **Customer** | Report a problem, get a fast fair outcome, see status honestly | Chat page: guided intake, structured replies, proof upload, status tracker, final report |
| **Approver** | Clear the approval queue confidently and fast | Queues by request type, evidence review, approve / reject-with-citation |
| **Escalation Agent** | Own hard cases end-to-end | Claim-on-open console: chat takeover + summary + actions |

---

## 5. The Pipeline (product view)

1. **Triage** — chat intake. Classify the dispute into a canonical subtype (§7), collect only missing facts (≤3 follow-ups), gate proof-required subtypes on photo upload.
2. **Investigation** — an agent assembles the evidence bundle from enterprise systems (orders, payment, refund history, shipment tracking, inventory) choosing sources per dispute type, plus AI vision analysis of proof photos. Output: one structured bundle with citations.
3. **Decision** — the deterministic adjudicator (§10–§11) returns path + amount + reason. Anomaly guardrails run first: duplicate refund, unconfirmed payment, delivered-but-disputed, proof contradiction.
4. **Execution** — autonomous path executes and resolves; approval path creates a pending request for the approver; customer-decision path explains why and offers appeal; escalation path generates a human-ready summary. Close produces a case report.

---

## 6. Constants (single source; mirrored in `DECISION.RULE_CONSTANTS`)

| Constant | Value | Meaning |
|---|---|---|
| `AUTONOMOUS_LIMIT_USD` | **50.00** | Max amount TIDE may refund or replace without approval |
| `RETURN_WINDOW_DAYS` | 7 | Days from window-basis date a return/refund-for-condition is in policy |
| `DELIVERY_SLA_BREACH_DAYS` | 3 | Days past estimated delivery that constitute an SLA breach |
| `STALE_TRANSIT_DAYS` | 7 | Days without tracking movement that make a shipment presumptively stalled |
| `INACTIVITY_TIMEOUT_MIN` | 15 | Idle minutes in `pending_triage` before auto-close as unresponsive |
| `MIN_REJECTION_CHARS` | 50 | Minimum human rejection-reason length |
| `MIN_REJECTION_CITATIONS` | 1 | Minimum policy citations on a human rejection |
| `MAX_PROOF_UPLOADS` | 2 | Max proof images per case |
| `MAX_PROOF_BYTES` | 5 MB | Per image (jpeg/png/webp only) |
| `MAX_FOLLOWUP_QUESTIONS` | 3 | Intake may ask at most this many follow-ups before routing |
| `CURRENCY` | USD | All amounts |

---

## 7. Dispute Taxonomy

### 7.1 Canonical Subtypes (12)

| Subtype | Type | Proof required | Allowed resolutions | Default |
|---|---|---|---|---|
| `duplicate_charge` | refund | no | refund | refund |
| `not_as_described` | refund | **yes** | refund, replacement | refund |
| `damaged_goods` | refund | **yes** | refund, replacement | refund |
| `wrong_item` | refund | **yes** | refund, replacement | refund |
| `partial_fulfillment` | refund | **yes** | refund | refund |
| `return_request` | refund | no | return | return |
| `changed_mind` | refund | no | return | return |
| `other` | refund | no | refund | refund |
| `non_receipt` | delivery | no | refund, replacement | refund |
| `delayed` | delivery | no | refund | refund |
| `exception` | delivery | no | refund | refund |
| `lost` | delivery | no | refund, replacement | refund |

### 7.2 Intake Aliases (normalised before anything else)

`package_never_arrived → non_receipt` · `delivery_late → delayed` · `wrong_delivery_address → exception` · `quality_issue → not_as_described` · `return_for_refund → return_request`. Unknown subtype after normalisation → G-01.

### 7.3 Resolution-type Resolution

`resolve_type(preference, subtype)`: customer preference if allowed for the subtype; else the subtype default. A preference outside the allowed set does **not** silently downgrade — it triggers G-02 (customer decides).

---

## 8. Case State Machine (9 states)

`pending_triage` · `awaiting_customer_proof` · `awaiting_customer_decision` · `awaiting_approval` · `approved_executing` · `rejected_human_required` · `escalated_human_required` · `resolved` · `closed`

| From | Allowed to |
|---|---|
| *(new)* | `pending_triage`, or `awaiting_customer_proof` if subtype requires proof |
| `pending_triage` | `awaiting_customer_proof`, `awaiting_customer_decision`, `awaiting_approval`, `approved_executing`, `escalated_human_required`, `closed` |
| `awaiting_customer_proof` | `pending_triage` (≥1 upload), `closed` |
| `awaiting_customer_decision` | `escalated_human_required` (appeal), `closed` |
| `awaiting_approval` | `approved_executing` (approve), `rejected_human_required` (reject), `closed` |
| `approved_executing` | `resolved`, `closed` |
| `rejected_human_required` | `resolved`, `closed` |
| `escalated_human_required` | `resolved`, `closed` |
| `resolved` | `closed` |
| `closed` | *(terminal)* |

Rules: self-transition is always legal (idempotent retries). Transitions are events in `TRIAGE.CASE_EVENTS`; legality validated before insert; illegal transition raises and writes nothing. Actors: customer may close; approver may approve/reject; escalation agent may act only on cases assigned to them; the system may do the rest.

---

## 9. Fact Derivation (input to guardrails and routing)

| Fact | Derivation |
|---|---|
| `payment_confirmed` | payment status ∈ {confirmed, completed, paid, success, succeeded} |
| `order_returnable` | order status ∈ {fulfilled, returned} |
| `total_order_amount` | refund-transaction amount ?? order total ?? payment amount ?? 0 |
| `affected_amount` | Σ(qty × unit price) over customer-selected affected items; fallback all items; fallback `total_order_amount` |
| `replacement_amount` | `affected_amount` if > 0 else `total_order_amount` |
| `shipping_fee` | order shipping fee ?? 0 |
| `window_basis_date` | first non-null of: shipment delivered_at, order delivered_at, order fulfilled_at, order placed_at, delivered tracking event time |
| `within_return_window` | 0 ≤ days(`as_of` − `window_basis_date`) ≤ `RETURN_WINDOW_DAYS` |
| `delivered_event` / `lost_event` / `exception_event` / `in_transit_event` | latest tracking event of that type (exception falls back to `delayed` event) |
| `stale_in_transit` | `in_transit_event` exists ∧ days since it > `STALE_TRANSIT_DAYS` ∧ no `delivered_event` |
| `sla_breached` | delivered ∧ days(delivered_at − estimated_delivery) > `DELIVERY_SLA_BREACH_DAYS` |
| `inventory_feasible(items)` | false if item list empty, or any item has unknown availability, or available < ordered (reason names the blocked products) |
| `prior_refunds` | count + total of any prior refund records for the order |
| `confirmed_payment_count` | number of payment records for the order whose status satisfies `payment_confirmed`. Read by G-10; a duplicate-charge claim needs at least 2 |
| `proof_present` / `proof_supports` / `proof_contradicts` | from proof analysis: subtype-relevant signal. `proof_contradicts` = signal explicitly false while proof exists |

The bundle carries `as_of` (evaluation timestamp). The engine contains no clock.

---

## 10. Guardrails — ordered, first match returns (G-01…G-10)

| # | Condition | Decision | Code |
|---|---|---|---|
| G-01 | subtype missing/unknown after normalisation | `escalated_human_required`, type null — "manual review required" | — |
| G-02 | resolved type ∉ allowed set for subtype | `awaiting_customer_decision` | `unsupported_resolution_type` |
| G-03 | type = refund ∧ `prior_refunds` > 0 | `escalated_human_required`, eligible 0 — duplicate-refund risk, reason cites count + total | — |
| G-04 | ¬`payment_confirmed` | `escalated_human_required` — reason cites actual payment status | — |
| G-05 | subtype ∈ {non_receipt, lost} ∧ `delivered_event` exists | `escalated_human_required` + tracking evidence "Delivered at \<loc\> on \<time\>" | — |
| G-06 | proof required ∧ ¬`proof_present` | `awaiting_customer_decision` | `insufficient_proof` |
| G-07 | proof required ∧ analysis failed | `escalated_human_required` | — |
| G-08 | proof required ∧ present ∧ `proof_contradicts` | `awaiting_customer_decision` | `proof_contradicts_claim` |
| G-09 | proof required ∧ present ∧ `proof_supports` = false | `awaiting_customer_decision` | `insufficient_proof` |
| G-10 | subtype = `duplicate_charge` ∧ `confirmed_payment_count` < 2 | `awaiting_customer_decision` — reason cites the number of confirmed charges found | `insufficient_evidence` |

**On G-10.** `duplicate_charge` is the only subtype that makes a direct financial claim with no
evidence requirement, and the evidence for it already exists in the payment record. Without this
guardrail a claim on a single-charge order refunds autonomously on the customer's assertion
alone. It is subtype-conditioned rather than global, following the precedent of G-05, and sits
after G-03 and G-04 so a duplicate-refund risk or an unconfirmed payment still escalates first.
`confirmed_payment_count` is defined in §9.

---

## 11. Routing (after guardrails; ≤ / > refer to `AUTONOMOUS_LIMIT_USD`)

**Notation:** AUTO = `approved_executing` · APPR = `awaiting_approval` · ESC = `escalated_human_required` · ACD = `awaiting_customer_decision`.

### duplicate_charge (refund of `total_order_amount`)
≤ limit → AUTO · > limit → APPR

### not_as_described · damaged_goods · wrong_item
*replacement:* ¬`inventory_feasible(affected)` → ACD `insufficient_inventory` · feasible ∧ `replacement_amount` ≤ limit → AUTO (carries replacement items + affected ids) · feasible ∧ > limit → APPR
*refund:* ¬`within_return_window` → ACD `outside_return_window` (reason cites days vs window) · within ∧ `affected_amount` ≤ limit → AUTO · within ∧ > limit → APPR

### partial_fulfillment
Always ESC — multi-item shortfalls require human review. Eligible = `affected_amount`.

### return_request · changed_mind
¬`order_returnable` → ACD `non_returnable_item` · ¬`within_return_window` → ACD `outside_return_window` · else APPR (eligible = `total_order_amount`). **Returns are never autonomous.**

### non_receipt
*replacement:* ¬feasible → ACD `insufficient_inventory` · feasible → APPR (never autonomous).
*refund:* no delivered ∧ no lost event → ≤ limit AUTO / > APPR · `exception_event` ∧ no delivered → ≤ AUTO / > APPR (+ tracking evidence) · `stale_in_transit` → ≤ AUTO / > APPR (+ tracking evidence) · else ESC

### delayed
`sla_breached` → **shipping-fee-only refund** (`shipping_fee_refund_only = true`, eligible = `shipping_fee`): ≤ AUTO / > APPR · else `exception_event` ∧ no delivered → full `affected_amount`: ≤ AUTO / > APPR · else `stale_in_transit` → ≤ AUTO / > APPR · else ESC

### exception
`exception_event` ∧ no delivered → ≤ AUTO / > APPR (+ tracking evidence) · else ESC

### lost
*replacement:* ¬feasible → ACD `insufficient_inventory` · feasible → APPR.
*refund:* `lost_event` ∧ no delivered → ≤ AUTO / > APPR (+ "Lost at \<loc\> on \<time\>") · else ESC

### other
Always ESC.

---

## 12. Invalid-Reason Codes (closed set) and Appeal Priority

`insufficient_proof` · `proof_contradicts_claim` · `insufficient_evidence` · `outside_return_window` · `non_returnable_item` · `insufficient_inventory` · `unsupported_resolution_type` · `duplicate_case` · `order_not_found` · `ineligible_order_state` · `policy_exclusion`

Every ACD decision carries exactly one code + customer-facing copy (in `DECISION.REASON_COPY`). Customer may **appeal** any ACD → `escalated_human_required`. Appeal priority: **high** for {`proof_contradicts_claim`, `insufficient_evidence`, `duplicate_case`, `policy_exclusion`}, else **normal**.

`insufficient_proof` and `insufficient_evidence` are distinct: the first means the customer's
uploaded images do not establish the claim, the second means the system's own records do not.

---

## 13. Terminal Path Enumeration

Complete branch inventory — test ids map 1:1 to these.

- **G-01…G-10** — 10 guardrail terminals.
- **R-01/02** duplicate_charge ≤ / >.
- **R-03…R-20** not_as_described, damaged_goods, wrong_item — per subtype: replacement {infeasible, ≤, >} and refund {outside-window, ≤, >} = 6 × 3 subtypes.
- **R-21** partial_fulfillment ESC.
- **R-22…R-27** return_request, changed_mind — per subtype {non-returnable, outside-window, APPR}.
- **R-28** other ESC.
- **R-29…R-37** non_receipt — replacement {infeasible, APPR}; refund {no-event ≤, no-event >, exception ≤, exception >, stale ≤, stale >, fallthrough ESC}.
- **R-38…R-44** delayed — {sla ≤, sla >, exception ≤, exception >, stale ≤, stale >, ESC}.
- **R-45…R-47** exception — {event ≤, event >, ESC}.
- **R-48…R-52** lost — replacement {infeasible, APPR}; refund {lost ≤, lost >, ESC}.
- **R-53** unknown-subtype default ESC (defence in depth behind G-01).

**Total: 63 terminal paths (10 guardrail + 53 routing).** Every one has a pytest test; the coverage test fails if any id here lacks one.

---

## 14. Conversation & Operational Rules

- Intake asks at most `MAX_FOLLOWUP_QUESTIONS` follow-ups, one at a time, only for facts it lacks (never re-ask what the order record already answers). Question order: scope (which items) → detail (what happened) → confirmation.
- Chat is append-only; messages are never edited or deleted. Sender types: customer, assistant, agent, system.
- Proof: required subtypes per §7.1; case starts in `awaiting_customer_proof`; composer locked until ≥1 upload; max 2 images; duplicate image (same sha256) rejected; customer may remove proofs only while in `awaiting_customer_proof`.
- Approval: approving a refund/return/replacement request executes it and resolves the case. Rejecting requires ≥`MIN_REJECTION_CHARS` chars + ≥`MIN_REJECTION_CITATIONS` policy citation → `rejected_human_required` for human follow-through.
- Autonomous execution (F4.1) is taken by the pipeline in the same turn as the decision, with no human in the loop and no queue to wait in — that is what makes the path autonomous. `approved_executing` is a moment, not a resting state: a case still sitting there once the turn has ended is a failed execution, not a pending one. Execution is idempotent and adds no judgement — it refuses any case not already routed to AUTO by §11, so it cannot move money the guardrails did not authorise.
- Escalation: opening an unassigned escalated case claims it (assignment recorded as an event); a case assigned to another agent is read-only to everyone else.
- Timeout: cases idle in `pending_triage` > `INACTIVITY_TIMEOUT_MIN` are closed (`closed_by = timeout`, `close_reason = unresponsive`) by the sweeper.
- Close reasons: resolved · unresponsive · duplicate. Closed by: customer · agent · timeout.
- Every resolution execution writes a structured record (refund / return / replacement) and a case report on close — the audit trail is the product.

---

## 15. Functional Requirements

### F1 Intake (customer)
- F1.1 Three-step guided start: pick order → pick issue (12 subtypes) → pick preferred resolution (constrained by subtype per §7.1).
- F1.2 One open case per order; duplicate attempt is blocked with reference to the open case.
- F1.3 Follow-ups per §14; structured quick-replies where the question has a closed answer set.
- F1.4 Proof-required subtypes start in `awaiting_customer_proof`: composer locked, uploader active (≤2 images, jpeg/png/webp, ≤5 MB); analysis runs on upload.
- F1.5 Status tracker on every case; sequence shown adapts to path.
- F1.6 Customer may close their own case anytime; may appeal an `awaiting_customer_decision` outcome.

### F2 Investigation (system)
- F2.1 Evidence bundle assembled per case with per-source status; partial assembly is marked, not hidden.
- F2.2 The investigator selects tools by dispute type — selection is logged and visible.
- F2.3 Proof photos analysed for subtype-relevant signals with a structured verdict.
- F2.4 Bundle failures route to escalation, never to silent defaults.

### F3 Decision (system)
- F3.1 Adjudication is deterministic, ordered, and complete per §10–§11; every decision emits a reason string and, for customer-decision outcomes, an invalid-reason code with customer-facing copy.
- F3.2 Decisions persist as immutable events with the full input snapshot (auditable replay).

### F4 Execution & Human Surfaces
- F4.1 Autonomous: execute refund/replacement ≤ $50, notify in chat, resolve.
- F4.2 Approver: queues for refund / return / replacement requests; approve executes and resolves; reject enforces ≥50-char reason + ≥1 policy citation.
- F4.3 Escalation: FIFO queue; opening claims; console = live chat + AI summary + actions.
- F4.4 Timeout sweeper closes unresponsive `pending_triage` cases.
- F4.5 Case report generated on close: outcome, path, rules applied, sources queried, proof summary, timeline.

### F5 Platform
- F5.1 All state in Snowflake; chat and case events append-only; current state via views.
- F5.2 Roles enforce access — customer sees own cases only; approver sees queues; escalation acts only on claimed cases.
- F5.3 Every AI call uses structured output; AI failure is a routed branch (retry once → escalate), never a crash.
- F5.4 Demo seed: deterministic dataset exercising every terminal path.

---

## 16. Non-goals (v1)

No settings screen · no analytics dashboard · no multi-tenant / org management · no real payment-gateway or carrier integration (simulated enterprise schema stands in) · no email/SMS notifications · no mobile-specific layout · no customer self-registration (demo users are provisioned) · no localisation (English, USD).

---

## 17. Success Narrative (demo)

One sitting, three stories: (1) a $12 damaged-goods case with photo proof resolves autonomously in under two minutes; (2) a $180 case assembles the same evidence and lands in the approval queue where an approver approves in seconds; (3) a duplicate-refund attempt is caught by G-03, escalated with the prior payout cited, and an agent resolves it manually. Same pipeline, three outcomes, every decision explained.