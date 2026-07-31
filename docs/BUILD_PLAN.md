# TIDE — Build Plan

Snowflake CoCo CLI Hackathon 2026 · Track 1 (Intelligent Workflow Automation Agent)
Submission deadline: **Wed 6 Aug 2026** (submit by noon; the lock is hard)

---

## 1. Locked Decisions

| Area | Decision |
|---|---|
| Product | **TIDE** — Triage · Investigation · Decision · Execution. Supervised agentic dispute resolution for online retail |
| Runtime | Streamlit in Snowflake, **warehouse runtime**, three personas (customer / approver / escalation) |
| Orchestration | No external workflow engine. 3 synchronous stored procedures + 3 triggered tasks + 1 Cortex Agent object |
| Decision engine | **Deterministic** pure Python module (`tide_decision/`) — no LLM in the money path, by design |
| Agents | Cortex Agent object for investigation (genuine tool selection); `AI_COMPLETE` structured calls for intake, planning, summarisation, reporting, vision |
| Models | Via Cortex: text model for structured output, vision model for proof analysis, `auto` for agent orchestration. Temperature 0, structured output everywhere |
| Data | Event-sourced append-only tables; current state derived via views. Proof photos on internal stage (`SNOWFLAKE_SSE`) |
| Scope | Full decision matrix — 12 canonical subtypes, all four resolution types, every terminal path (63 paths per `docs/DETAILS.md` §13) |
| Currency | **USD.** Autonomous limit $50.00 |
| Docs | Written before code. `docs/DETAILS.md` is law: change BRL → change tests → change code, in that order |

---

## 2. Workstreams

**WS-A · Foundation** — Canonical account setup, warehouses, roles, all DDL (5 schemas), seed data, proof stage, semantic view, Cortex Search service over policies.
Blocks everything. ~1.5 days. *Interfaces out: schema DDL frozen by end of Day 2.*

**WS-B · Decision engine** — `tide_decision/` pure Python module (zero Snowflake imports) implementing `docs/DETAILS.md` §10–§13, wrapped by a thin stored procedure. Full pytest suite: one test per terminal path, runnable locally with no account. The crown jewel.
Depends: BRL only (not WS-A). ~2 days incl. tests.

**WS-C · Agents & orchestration** — Investigation agent object + tools, intake/planner/summariser/reporter structured calls, vision procedure, streams + triggered tasks + timeout sweeper, task graph wiring.
Depends: WS-A semantic view + DDL. ~3 days. Highest platform uncertainty — front-load the spikes.

**WS-D · Interface** — Three Streamlit personas, TIDE theme, chat flow with structured response pills, proof upload → stage → refresh, approver queues + rejection rigor (≥50-char reason + policy citation), escalation claim-on-open.
Depends: WS-A DDL; consumes B and C over SQL. Largest surface; most likely to slip. ~4 days.

**WS-E · Evidence & submission** — README, PROVENANCE, CoCo build transcripts (`--output-format stream-json` committed to `evidence/coco-transcripts/`), deck, demo rehearsal, contamination re-scan, dashboard re-verification.
Starts day 6, not day 10.

---

## 3. Day-by-Day Schedule

| Day | Date | Milestone |
|---|---|---|
| **1** | Mon 28 Jul | All spikes run (see §5). Account topology fixed. Repo initialised, docs adopted by team. Workstream owners assigned |
| **2** | Tue 29 Jul | WS-A complete: DDL applied, seed loaded, stage live, semantic view + Search service up. WS-B module skeleton + first 15 path tests green |
| **3** | Wed 30 Jul | WS-B all guardrail paths green. WS-C: Investigation agent created, first `DATA_AGENT_RUN` round-trip from a procedure. WS-D: app shell + theme + login-role routing |
| **4** | Thu 31 Jul | **Gate: WS-B 100% paths green** (else cut line 1 fires). WS-C: intake + vision procedures working. WS-D: customer chat renders live case |
| **5** | Fri 1 Aug | End-to-end happy path: intake → investigation → adjudicate → autonomous execution, visible in UI |
| **6** | Sat 2 Aug | **Gate: vision working** (else cut line 3). WS-C: task graph + summariser + reporter + sweeper. WS-D: approver queue + approve/reject flows |
| **7** | Sun 3 Aug | **Gate: escalation persona started** (else cut line 2). WS-D: escalation console. Integration day — three personas against one seeded account |
| **8** | Mon 4 Aug | Full matrix run: every scenario in `docs/DETAILS.md` §15 executed E2E, results logged. Fix day |
| **9** | Tue 5 Aug | Second full run clean. Deck built from BRD. README + PROVENANCE finalised. Demo rehearsed twice, cold-start included. Dry-run submission form |
| **10** | Wed 6 Aug | **Freeze by noon.** Submit: repo, deck, prototype link, profiles. Verify dashboard confirmation |

---

## 4. Cut Lines (pre-agreed — no debate mid-week)

1. WS-B not 100% green by **end of Day 4 (Thu 31)** → drop `return_request`/`changed_mind` subtypes (three resolution types remain)
2. Escalation persona not started by **Day 7 (Sun 3)** → merge escalation into approver as a single agent console
3. Vision not working by **Day 6 (Sat 2)** → proof upload stores + displays; analysis stubbed deterministically; disclosed in deck

---

## 5. Spike Gate Outcomes (run Day 1, decide Day 1)

| Spike | If green | If red |
|---|---|---|
| `DATA_AGENT_RUN` from warehouse-runtime Streamlit | Agents called via SQL everywhere | Investigation agent becomes `AI_COMPLETE` orchestration inside a procedure; drop agent-object framing from deck |
| CoCo CLI auth on canonical account | Build evidence via `stream-json` transcripts | Escalate to hackathon support same day; meanwhile use CoCo in Snowsight (GA, no CLI dependency) |
| Vision from stage | Proof pipeline as designed | Check network policy first (AI functions incompatible with custom network policies); else cut line 3 |
| Cortex daily credit ceiling | Ignore | Add card to canonical account if possible; else LLM-heavy iteration moves to overflow accounts |

---

## 6. Risks & Mitigations

| Risk | Mitigation |
|---|---|
| Warehouse-runtime Streamlit: separate app instance per viewer, per-session cache, ~15-min socket timeout | Demo-day: pre-warm one viewer per persona, keep sessions alive, XS warehouse with 5-min auto-suspend |
| `AI_COMPLETE` structured-output schema rejections (`format`, `minItems`, `minimum` etc. ERROR) | Schema conventions in `.cortex/skills/`; validate schemas Day 2 before agents are built |
| Model behaviour differs from prior assumptions | All prompts validated against actual Cortex models Day 3; budget half a day |
| Credit burn | XS warehouses, auto-suspend ≤5 min, suspend Search service when idle, watch the Snowsight balance tile daily |
| Submission-form surprises | Dry-run the Hack2skill submission form on Day 9, not Day 10 |

---

## 7. Judging Alignment

| Criterion | Weight | Where we earn it |
|---|---|---|
| **Technical Execution** | 40% | Agent object with real tool selection; deterministic engine + full 63-path test suite; event-sourced audit trail; task-graph orchestration; structured output with constrained decoding; CoCo transcripts as committed evidence |
| **Real-World Relevance** | 30% | Human-in-the-loop approval, escalation queue, auditable refund decisions, anomaly guardrails (duplicate refund, proof contradiction, delivered-but-disputed, payment unconfirmed) |
| **Solution Completeness** | 30% | Three personas, full subtype matrix, proof flow, reports, timeout handling — a complete operations loop, not a chat demo |
| **Special consideration** | bonus | **Snowpark** (procedures + pure-module engine), **Streamlit** (entire UI), **Cortex Search** (policy retrieval), **Cortex Analyst** (semantic view) |

---

## 8. Acceptance

The product is done when: every scenario in `docs/DETAILS.md` §15 passes E2E through the UI; all 63 BRL paths are unit-tested green; the three-persona demo (intake → autonomous resolve, intake → approval → approve, intake → invalid → appeal → escalation → manual resolve) runs cold in under 10 minutes.

---

*This plan governs execution. When in doubt about priority, check the cut lines. When in doubt about scope, check the locked decisions.*
