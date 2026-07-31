# TIDE · Decision log

Decisions that are settled and should not be relitigated, with the reason they were made.

This exists because rationale was living in untracked files — a point-in-time briefing and a
scratch folder that `.gitignore` excludes by rule — so none of it survived a clone or reached
anyone outside one laptop. Rules themselves live in `DETAILS.md`, contracts in `SCHEMA.md`,
design in `ARCHITECTURE.md`; this file records **why**, and points at those rather than
restating them.

Add an entry when a choice closes off an alternative someone could reasonably reopen. If a
decision is later reversed, keep the entry and add the reversal underneath — the record of what
we tried is worth more than a tidy list.

---

## Architecture

**No LLM decides money.** Adjudication is a deterministic pure function (`tide_decision/`,
zero Snowflake imports, 63 paths each with a test). Every alternative we considered put a model
somewhere in the money path, and none of them could be tested exhaustively or explained to an
approver after the fact. The deliberate absence of an LLM here is the architecture's central
claim, not an interim measure. → `ARCHITECTURE.md` §7.4

**Two speeds, one rule.** Anything a person is actively waiting on is a synchronous procedure
call; only genuinely detached work — escalation summaries, case reports, the timeout sweep — is
a triggered task. Triggered tasks have a ~30s floor, which is unusable inside a chat turn. That
latency constraint drew the line, not preference. → `ARCHITECTURE.md` §1

**Tools report facts, never judgements.** Thresholds live in the engine; constants live in
`DECISION.RULE_CONSTANTS`. This binds procedures, views and the semantic view alike: a tool that
classifies or thresholds moves a business rule outside `DETAILS.md` and outside the test matrix,
where it stops being reviewable. → `SCHEMA.md` §2

**Append-only.** `TRIAGE.CHAT` and `TRIAGE.CASE_EVENTS` are never updated or deleted; current
state is derived through `V_CASE_CURRENT`. The audit trail is the product — a mutable one proves
nothing. → `AGENTS.md` §11

**CoCo is the build tool, Cortex Agents are the runtime.** Organizer-confirmed. Stated plainly
in the README because conflating the two is the likeliest way to lose Technical Execution
points.

---

## Business rules

**G-10 exists, and it is subtype-conditioned rather than global.** `duplicate_charge` was the
only subtype making a direct financial claim with no evidence requirement, so a claim on a
single-charge order refunded autonomously on the customer's assertion alone. It follows the
precedent of G-05 and sits after G-03 and G-04 so a duplicate-refund risk or an unconfirmed
payment still escalates first. Path count 62 → 63. → `DETAILS.md` §10, the **On G-10.**
paragraph · commit `a6a21e4`

**`insufficient_evidence` is distinct from `insufficient_proof`.** The first means our own
records do not establish the claim; the second means the customer's uploaded images do not.
Collapsing them would have produced customer copy that blames the customer for a gap in our
data. → `DETAILS.md` §12

---

## Contracts

**The evidence bundle carries `payments[]`, and the engine derives the count.** `DETAILS.md` §9
defines `confirmed_payment_count`, but the bundle carried only a singular `payment` object,
which has no field that varies with the number of charges — one confirmed charge and two produce
an identical object, so G-10 was not computable from the documented contract. The alternative
was putting a precomputed `confirmed_payment_count` scalar in the bundle, rejected because
deciding which statuses count as confirmed is the engine's judgement and would have leaked it
into the assembler. Fixed before `ASSEMBLE_EVIDENCE` was written, because that procedure is
built from the contract and would otherwise have dropped the field at assembly, failing G-10
silently and far from the cause. → `SCHEMA.md` §5 · commit `e34b5c7`

**Lifecycle procedure names follow the UI, not the C-5 spec.** `OPEN_CASE` not `CREATE_CASE`,
`AGENT_MESSAGE` not `POST_MESSAGE`, `EXECUTE_RESOLUTION` / `REJECT_RESOLUTION` not
`APPROVE_REQUEST` / `REJECT_REQUEST`. WS-D was built against a master without the backend and
its call sites are already written and committed; renaming SQL objects we control is cheaper and
lower-risk than editing three files owned by someone else mid-flight. `TRANSITION_STATE`,
`POST_MESSAGE` and `REGISTER_PROOF` keep their spec names as internal helpers, since no UI code
calls them. → `TASKS.md` C-5

**Read-only tool procedures do not write `PIPELINE_LOG`.** The agent's four evidence tools are
called repeatedly within a single assembly step; logging each would flood the ops feed and the
demo-day progress view. The calling pipeline step logs once for the whole assembly. The
definition of done was amended to distinguish the two kinds of procedure. → `CLAUDE.md`

**The engine reaches Snowflake as an imported module, not as copied code.** `tide_decision/`
is zipped by `deploy.py` and imported by `DECISION.ADJUDICATE` from `DECISION.CODE_STAGE`. The
alternative was inlining the engine in the procedure body, rejected because the same rules would
then exist in two places and drift — and the 63-path test suite only covers one of them. The
cost is an ordering constraint: `IMPORTS` resolves at CREATE time, so `sql/procedures/*.sql` sits
outside the `sql/*.sql` glob and runs after the upload. → `SCHEMA.md` §1 · commit `c188da2`

**`ASSEMBLE_EVIDENCE` is deterministic, and calls the tools the agent would.** The Investigator
agent is the intended assembler, but `CLAUDE.md` requires every AI call to have a fallback that
keeps the pipeline demonstrable without AI, and the agent object does not exist yet. Rather than
write a stub, the fallback is the real implementation and calls the same four tools; the bundle
records which path produced it in `assembly.assembler`. When the agent lands it becomes the
other branch, not a rewrite. → `SCHEMA.md` §1

**Decision, resolution request and transition are one transaction.** They are a single fact
about the case. Written without one, a failure between them left a case carrying an R-01
decision while still sitting in `pending_triage` — observed, not theorised.

**`V_STOCK_BY_SKU` exists only to give `DISPUTES_SV` a legal grain.** `RETAIL.STOCK` is keyed
`(sku, warehouse)`, so `sku` is not unique and cannot be the target of a semantic-view
relationship. The tool procedures read `STOCK` directly and do not use the view. → `SCHEMA.md`
§6, §7

---

## Platform and operations

**Cortex-blocked files are attempted on every deploy, never skipped.** `deploy.py` tolerates a
failure in any file carrying a `BLOCKED: cortex-trial` marker, collects the names, still runs
the seed step, and exits 3 with a named report. Skipping them instead would mean nobody notices
the day entitlements change; failing hard would leave the database unseeded and unusable. Marked
files self-heal. → `scripts/deploy.py` · commit `ba196ee`

**Never work around a platform block.** No external AI APIs, no containers, no adding a payment
card, no substituting a different model to dodge an entitlement error. Report it and stop —
those are team or organizer decisions, not build decisions. → `CAPABILITIES.md` §E

**Tracking event ids must sort chronologically within a shipment.** Both
`GET_SHIPMENT_TIMELINE` and `DISPUTES_SV` break an `occurred_at` tie on `event_id` to decide the
latest event. On `ORD-1010` the `out_for_delivery` and `delivered` events share a timestamp, and
without the tiebreak the parcel reports as undelivered — silently, with no error — and guardrail
G-05 stops firing on the order engineered to probe it. Enforced by convention in the seed rather
than by a schema column, because `TRACKING_EVENTS` is simulated data with no runtime writer. →
`sql/seed/README.md`

**Customer secure views are built; the RETAIL revoke is deferred.**
`TRIAGE.V_MY_ORDERS` / `V_MY_ORDER_ITEMS` exist so `TIDE_CUSTOMER` never needs a base-table
grant, per `ARCHITECTURE.md` §4. The existing `GRANT SELECT ON ALL TABLES IN SCHEMA RETAIL` is
deliberately still in place: revoking it before WS-D reads the new views would break the customer
page. Additive first, revoke second. → `sql/01_triage_ddl.sql` · commit `23d4b7b`

---

## Open, not yet decided

Tracked in `_handoff/OPEN_QUESTIONS.md` (untracked scratch) and `TASKS.md`. The ones with a hard
deadline: git history reset before the repo link is public, judge access tested rather than
attempted on the day, and demo customer users whose usernames match the seeded `customer_id`
values — without those the customer page renders empty rather than broken.
