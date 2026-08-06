# TIDE — End-to-End Guide

How to deploy TIDE from nothing, verify it automatically, and walk it by hand through the three
demo stories. Written for a teammate, a rehearsal, or an evaluator.

**Status of the claims below.** Everything in *Deploy* and *Automated verification* is verified
on the canonical account as of **4 August 2026**. The *Manual walkthrough* expectations are
derived from the seed's engineered scenarios and from the same procedures the automated matrix
exercises, but the pages themselves have **not yet been clicked through by a person** — that is
the one step no script can do. Treat §4 as "expected", not "confirmed", until someone signs it off.

---

## 1. Prerequisites

| | |
|---|---|
| Snowflake CLI | 3.23+ (`snow --version`) |
| Python | 3.12 with `pytest` |
| Connection | named `tide` in `~/.snowflake/connections.toml`, role `TIDE_ADMIN` |
| Account | canonical, `OXAZYMD-GQ85743` |

The connection authenticates with a **programmatic access token**, not a password. This account
mandates MFA for password logins (a Snowflake platform floor for `TYPE = PERSON` users, not our
configuration), so a PAT is the only workable path for scripted access.

Verify before starting:

```bash
snow sql -c tide -q "SELECT CURRENT_ACCOUNT(), CURRENT_ROLE(), CURRENT_WAREHOUSE()"
```

---

## 2. Deploy

One command builds everything: schemas, tables, views, procedures, the decision engine, the
Cortex agent, the seed, and the Streamlit app.

```bash
python scripts/deploy.py --connection tide
```

**Exit codes.** `0` is clean. `3` means one or more SQL files carrying a `BLOCKED: cortex-trial`
marker failed and were tolerated — the script names them in a block at the end. Anything else is
a real failure.

What the four steps do:

1. **SQL DDL** — every file in `sql/` in numeric order. Files marked `REQUIRES: ACCOUNTADMIN`
   are run with that role automatically.
2. **Seed** — `seed_retail.sql` (23 engineered orders), `seed_decision.sql` (rule constants,
   reason copy, the policy corpus), `seed_demo_customer.sql` (demo orders per persona).
3. **Procedures & agents** — packages `tide_decision/` into a zip, uploads it to
   `DECISION.CODE_STAGE`, then creates the procedures that import it.
4. **Streamlit app** — `snow streamlit deploy` from `streamlit/snowflake.yml`, then re-runs
   `sql/14_demo_access.sql` so the app grants land (they are skipped on the first pass, since
   the app does not exist yet on a cold build).

Everything is idempotent. Re-running is safe and is the normal way to pick up changes.

> **Note.** `deploy.py` has been verified as a **re-deploy** over existing objects. Running it
> against a genuinely empty database has not been tested. That is the harder claim and remains
> an open pre-submission gate.

---

## 3. Automated verification

Run both. Together they take a few minutes and cover far more than a manual pass can.

### 3.1 Unit tests — the decision engine

```bash
pytest tests/ -q
```

**Expect: `114 passed`.** These prove the *engine* against fabricated evidence bundles. Every one
of the 63 terminal paths (10 guardrails, 53 routing) has a test, and `test_engine_purity.py`
asserts `tide_decision/` imports nothing from Snowflake — the engine runs and is testable with no
database at all.

### 3.2 Matrix — the deployed system

```bash
python scripts/run_matrix.py --connection tide
```

**Expect: `14 pass · 7 blocked · 1 observe · 0 fail`, exit 0.**

This is a different claim from the unit tests. It drives each seeded order through the real
chain — `OPEN_CASE → ASSEMBLE_EVIDENCE → ADJUDICATE` on Snowflake — and asserts it lands on the
path its seed comment engineered. It also reads `path_id` back off `V_CASE_CURRENT`, because a
decision *returned* is not a decision *written*, and keeping those in step is exactly what
`ADJUDICATE`'s transaction exists to guarantee.

Reading the outcomes:

| Outcome | Meaning |
|---|---|
| **pass** | Landed on the engineered path, decision persisted. |
| **blocked** | Held correctly at the proof gate. Not a failure — see below. |
| **observe** | Recorded, not asserted. |
| **fail** | A real regression. Investigate before doing anything else. |

The 7 **blocked** scenarios are proof-required subtypes. They open into
`awaiting_customer_proof` and stop, which is correct: `RESUME_INTAKE` refuses while no proof
file exists. They are counted apart from *pass* so the gap stays visible rather than being
absorbed into a green run. To turn them into passes you would need photographs whose contents
actually support each claim; the runner has none, and uploading an arbitrary image would reach
G-08 (*proof contradicts*) and assert nothing useful.

Useful flags:

```bash
python scripts/run_matrix.py --only E-08          # one scenario
python scripts/run_matrix.py --only E-08 --keep   # leave the case in place to inspect
python scripts/run_matrix.py --restore-only       # diagnose order ownership after a crash
```

**Why ownership matters.** `OPEN_CASE` scopes orders to `CURRENT_USER()`, and the 23 seeded
orders belong to `@example.com` addresses that are not Snowflake users. The runner borrows one
order at a time and hands it straight back, restoring everything in a `finally`. It refuses to
start if an order is already misowned — capture-then-restore would otherwise cement a bad owner
left by an interrupted run. If it ever refuses, re-run `sql/seed/seed_retail.sql`.

---

## 4. Manual walkthrough

### 4.1 Open the app

**https://app.snowflake.com/OXAZYMD/GQ85743/#/streamlit-apps/TIDE.TRIAGE.TIDE_APP**

Or sign in at **https://app.snowflake.com/** and go to **Projects → Streamlit →
TIDE - Dispute Resolution**.

> **Do not use the URL `snow streamlit get-url` prints.** It returns the
> `region/account-name` form (`.../ap-southeast-7.aws/gq85743/...`), which Snowsight answers with
> **Page not found**. The browser wants `organisation/account`: `OXAZYMD` / `GQ85743`. The CLI
> output is still useful for confirming the app exists — just not as a link to hand anyone.

### 4.2 Accounts

| Account | Role | Page |
|---|---|---|
| `TIDE_DEMO_CUSTOMER` | `TIDE_CUSTOMER` | Customer Portal |
| `TIDE_DEMO_APPROVER` | `TIDE_APPROVER` | Approver Dashboard |
| `TIDE_DEMO_ESCALATION` | `TIDE_ESCALATION` | Escalation Console |
| `TIDE_JUDGE` | `TIDE_JUDGE` | all three |

**Passwords are not recorded in this repository.** Ask Keith.

`TIDE_JUDGE` is the union of the three persona roles, built by role inheritance so it cannot
drift from them. It also carries `ALLOWED_INTERFACES = ('STREAMLIT')`, which is confirmed *not*
to block Snowsight or MFA enrolment.

> **Do not log in as `TIDE_JUDGE`.** MFA enrolment binds to the enrolling device. An account
> enrolled by a team member demands *that person's phone* at the evaluator's login. It must
> reach them unenrolled. Check with `SHOW USERS LIKE 'TIDE_JUDGE'` → `has_mfa` must be `false`.

### 4.3 Demo data

Each demo account owns its own set of five orders, tagged into the id so the sets never collide:
`ME` for whoever deployed, `DC` for `TIDE_DEMO_CUSTOMER`, `JG` for `TIDE_JUDGE`.

**The subtype you open a case with is part of the setup.** The same order reaches a different
path under a different subtype, so open them exactly as listed.

| Order | Open as | Expected outcome | Story |
|---|---|---|---|
| `ORD-DEMO-N-1` | `duplicate_charge` | **R-01** — autonomous refund, $41.74 | autonomous |
| `ORD-DEMO-N-2` | `duplicate_charge` | **R-02** — approval queue, $180.00 | approval |
| `ORD-DEMO-N-3` | `duplicate_charge` | **G-10** — blocked, cites 1 confirmed charge | guardrail |
| `ORD-DEMO-N-4` | `duplicate_charge` | **G-03** — escalated, prior refund cited | guardrail |
| `ORD-DEMO-N-5` | `non_receipt` | **G-05** — escalated, delivery scan quoted | guardrail |

`ORD-DEMO-N-4` must be opened as `duplicate_charge`, not `changed_mind`: G-03 fires only when
the resolved type is `refund`, and `changed_mind` resolves to `return`, which reaches routing and
lands on R-25 instead.

### 4.4 Story 1 — autonomous resolution

Sign in as **`TIDE_DEMO_CUSTOMER`** → Customer Portal.

1. The order list appears. It reads `TRIAGE.V_MY_ORDERS`, a secure view filtered on
   `CURRENT_USER()` — no base-table access. *An empty list here is the single most important
   thing to report:* it means identity is not resolving as expected.
2. Select `ORD-DEMO-DC-1`, subtype **duplicate_charge**, resolution **refund**.
3. Describe the problem in the chat box.

**Expect:** the case resolves without a human. Path **R-01**, refund **$41.74**, status
`approved_executing`. Two confirmed charges exist on the order and the amount is under the $50
autonomous limit.

**The point:** the amount was not chosen by a language model. It came from the payment record
through a deterministic engine, and it traces to rule R-01.

### 4.5 Story 2 — human approval

Same account, `ORD-DEMO-DC-2`, **duplicate_charge** / **refund**.

**Expect:** path **R-02**, status `awaiting_approval`. $180.00 exceeds the autonomous limit, so
it stops and waits.

Now sign in as **`TIDE_DEMO_APPROVER`** → Approver Dashboard.

1. The case is in the queue, sorted by age.
2. Open it. The evidence bundle, the recommended decision and the cited policies are already
   assembled — the approver reads, they do not investigate.
3. **Approve** it, or **reject** it.

Rejection is deliberately effortful: it requires **≥50 characters** and **≥1 policy citation**,
enforced in the procedure from `RULE_CONSTANTS`, not in the UI. Try a ten-character rejection —
it must be refused.

**The point:** the human decides, with the work already done for them.

### 4.6 Story 3 — a guardrail firing with evidence

Same customer account, `ORD-DEMO-DC-5`, subtype **non_receipt**.

**Expect:** path **G-05**, status `escalated_human_required`, and the reason **quotes the
delivery scan back** — location and timestamp.

**The point:** the claim contradicts the carrier record, so no money moves and a person is
handed the specific evidence. Compare with `ORD-DEMO-DC-3` (**G-10**), where a duplicate-charge
claim is blocked because the payment record shows only one charge, and the reason says so.

### 4.7 Escalation console

Sign in as **`TIDE_DEMO_ESCALATION`**. The cases escalated above are in the queue.

- **Claim** a case — assignment is exclusive; a case held by someone else is read-only.
- The work panel shows an **AI-generated summary** of the bundle and decision.
- **Chat** with the customer, or resolve manually.

### 4.8 Proof and vision

Proof-required subtypes (`damaged_goods`, `wrong_item`, `not_as_described`,
`partial_fulfillment`) hold the case until evidence arrives.

1. Open a case on any order with **damaged_goods**.
2. It stops at `awaiting_customer_proof`. Intake will not proceed.
3. Upload an image. `ANALYZE_PROOF` registers it and analyses it with the vision model, writing
   damage / wrong-item / not-as-described / missing-item signals plus a prose note.
4. Press **Continue Intake**. `RESUME_INTAKE` accepts only once a proof file exists.
5. Adjudication runs with the proof signals in the bundle.

**Expected outcomes:** an image supporting the claim proceeds to routing; an image that does not
show the claimed problem reaches **G-08** (*proof contradicts*) or **G-09** (*insufficient
proof*); an analysis that fails reaches **G-07** and escalates to a person.

Verified trace: a `damaged_goods` case with an image showing no damage produced
`damage_detected: false` → **G-08**, "Uploaded proof contradicts the 'damaged_goods' claim".

Uploads are capped (2 per case by default, from `RULE_CONSTANTS`) and duplicate images are
rejected by SHA-256.

---

## 5. Reset between runs

Cases accumulate. Before a rehearsal or a recording, clear them.

The cleanest reset is to re-run the seed files, which delete their own rows before inserting:

```bash
snow sql -c tide -f sql/seed/seed_retail.sql
snow sql -c tide -f sql/seed/seed_demo_customer.sql
```

`seed_demo_customer.sql` deletes **every case attached to an `ORD-DEMO-%` order** before
reseeding. That is what makes it idempotent, and it also means a `deploy.py` run will silently
wipe demo cases someone was mid-way through. Reset deliberately, not accidentally, the night
before a recording.

> `scripts/demo_reset.sql` exists but has not been touched since 27 July and predates several
> tables added since. **Verify it before relying on it**, or use the seed files above.

---

## 6. Troubleshooting

| Symptom | Cause |
|---|---|
| Customer order list is empty | The customer views filter on `customer_id = CURRENT_USER()`. Either the account owns no seeded orders, or identity is not resolving as expected inside the app. |
| `invalid identifier` inside a procedure | Suspect a **missing grant** before suspecting syntax. A missing privilege surfaces as "invalid identifier" or "object does not exist", not as a permission error. |
| `snow sql -f` fails and takes the whole file down | `-f` aborts on the first error. Isolate the risky statement in its own file when probing. |
| A model call fails with *"Model X is unavailable"* | That model is not entitled in this region. `openai-gpt-5-mini` and `gemini-2.5-flash` work; `claude-3-5-sonnet` does not. Model names come from `DECISION.RULE_CONSTANTS`. |
| A model call fails with *"not available for trial accounts"* | The Cortex entitlement block has returned. Stop and report it — it is not something to work around. |
| Matrix refuses to start, naming misowned orders | A previous run died mid-scenario. Re-run `sql/seed/seed_retail.sql`. |
| Login demands MFA enrolment | Expected. Snowflake mandates it for password logins on `TYPE = PERSON` users. Enrol, or use a PAT for scripted access. |

Useful checks:

```bash
snow sql -c tide -q "SHOW STREAMLITS IN DATABASE TIDE"
snow sql -c tide -q "SHOW PROCEDURES IN DATABASE TIDE"
snow sql -c tide -q "SELECT * FROM TIDE.EXECUTION.PIPELINE_LOG ORDER BY logged_at DESC LIMIT 20"
snow sql -c tide -q "SELECT * FROM TIDE.TRIAGE.V_CASE_CURRENT"
```

`PIPELINE_LOG` is the first place to look when a page misbehaves: every pipeline step and every
UI error writes a row there.

---

## 7. Known limitations

Stated plainly so nothing here is oversold.

- **`PLAN_RESOLUTION` is not built.** The customer receives templated resolution copy assembled
  from the recorded decision rather than model-written prose. No decision or amount is affected.
- **G-06 is unreachable end to end.** It fires on "proof required but not present", but the only
  route to adjudication for such a subtype is `RESUME_INTAKE`, which requires a proof file — so
  proof is always present by then. The guardrail is correct and tested in the engine; the
  deployed system enforces that gate one layer earlier, in the state machine. Claim ten
  guardrails *of the engine*, not of the end-to-end system.
- **`ineligible_order_state` is not enforced at `OPEN_CASE`.** A case opens on a cancelled order
  and adjudicates. `DETAILS.md` §12 defines the reason code; nothing checks order status on the
  way in.
- **`deploy.py` has not been run against an empty database**, only as a re-deploy.
- **Cortex Analyst natural-language querying is unverified.** The semantic view works through
  plain `SEMANTIC_VIEW()` SQL; the NL path has not been re-tested since the entitlement block
  lifted.
- **The pages have not been clicked through by a person.** Every procedure and object the UI
  references is verified to exist, and every SQL literal in `streamlit/` is verified to compile
  against the live schema — but that is not the same as a human using it.

---

## 8. Reference

| | |
|---|---|
| App | `TIDE.TRIAGE.TIDE_APP` |
| Warehouse | `TIDE_WH_APP` |
| Schemas | `TRIAGE`, `INVESTIGATION`, `DECISION`, `EXECUTION`, `RETAIL` |
| Engine | `tide_decision/` — pure Python, no Snowflake imports |
| Business rules | `docs/DETAILS.md` — the law; code is never the authority |
| Data model | `docs/SCHEMA.md` |
| Design | `docs/ARCHITECTURE.md` |
| Settled decisions | `docs/DECISIONS.md` |

**Autonomous limit** $50 · **return window** 7 days · **rejection minimum** 50 characters and 1
citation · **max follow-up questions** 3 · **proof uploads** 2 per case. All read from
`DECISION.RULE_CONSTANTS` at runtime; none are hardcoded.
