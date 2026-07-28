# TIDE · Environment & capability checklist

Live working document. Update the status columns as you verify things — this is how the three
of us stay on the same picture of what works, what doesn't, and what nobody has tried yet.

Legend: **OK** verified working · **BLOCKED** verified failing · **?** untested

---

## A. Where each thing gets built

The most common confusion. Nothing is built in two places.

| Artifact | Authored in | Lives in | Deployed by | Verified by |
|---|---|---|---|---|
| Tables, views, stages, tasks | Claude Code (or CoCo Snowsight) | `sql/*.sql` | `deploy.py` or `snow sql -f` | `SELECT` in a worksheet |
| Seed data | Claude Code | `sql/seed/*.sql` | same | row counts |
| Decision engine | Claude Code | `tide_decision/` | nothing — pure Python | `pytest tests/ -q`, no account needed |
| Snowpark procedures | Claude Code | `procedures/*.py` | `deploy.py` | `CALL` in a worksheet |
| Cortex Agent | Claude Code | `agents/investigator.yaml` | `deploy.py` | `DATA_AGENT_RUN` |
| Streamlit pages | Claude Code | `streamlit/` | `deploy.py` | open the app URL |
| Docs | Claude Code / here | `docs/` | n/a | review |
| Throwaway probes | worksheet | nowhere — do not keep | n/a | n/a |

**Rule: if it matters, it is a file in the repo.** Worksheets are scratch. Anything created
directly in Snowsight that we intend to keep must be written back into `sql/` and redeployed,
or it will not exist on the canonical account.

---

## B. Per-person setup

Each of us ticks our own row. All three need every item.

| Item | Check | Keith | Nico | Gabe |
|---|---|---|---|---|
| Python 3.11+ | `python --version` | OK | ? | ? |
| Snowflake CLI | `snow --version` | OK | ? | ? |
| `connections.toml` pointing at the canonical account | `snow connection test -c tide` | ? | ? | ? |
| Repo cloned | — | OK | OK | ? |
| GitHub write access (can push a branch) | `git push -u origin <name>` | **BLOCKED** | OK | ? |
| Own branch created | `git branch` | OK | ? | ? |
| Claude Code in VS Code | opens, reads `CLAUDE.md` | OK | ? | ? |
| CoCo in Snowsight opens | click the sparkle icon | ? | ? | ? |

---

## C. Account capability matrix

Tested on Keith's account unless noted. **Everything here must be re-verified on the
canonical account once we switch**, because entitlements are per-account.

### Verified working

| Capability | Test | Status |
|---|---|---|
| Warehouses, roles, schemas | `sql/00_account.sql` | OK |
| Table/view DDL | `sql/01`–`05` | OK |
| Seed load | `sql/seed/*` → 23 orders, 14 policies | OK |
| Cross-region inference | `SHOW PARAMETERS LIKE 'CORTEX_ENABLED_CROSS_REGION' IN ACCOUNT` | OK |
| Agent object **creation** | `CREATE AGENT` | OK |

### Verified blocked — from the CLI only

Everything below was tested through `snow sql`, an external client. Hoa in the participant
group reports the issued trial has external AI locked and web access only, which would mean
these are channel restrictions rather than account restrictions. **Re-test each from a
Snowsight worksheet before believing them.**

| Capability | Test | CLI | Worksheet | In a procedure | In Streamlit |
|---|---|---|---|---|---|
| `AI_COMPLETE` | `SELECT AI_COMPLETE('claude-haiku-4-5','Reply with exactly: OK');` | BLOCKED | ? | ? | ? |
| `AI_COMPLETE` structured output | schema in `response_format` | BLOCKED | ? | ? | ? |
| `AI_COMPLETE` vision from stage | `TO_FILE('@PROOF_STAGE','x.jpg')` | ? | ? | ? | ? |
| `DATA_AGENT_RUN` | run `SPIKE_AGENT` | BLOCKED | ? | ? | ? |
| Legacy `COMPLETE` / `SUMMARIZE` | — | BLOCKED | ? | ? | ? |
| `AI_CLASSIFY` | — | ? | ? | ? | ? |

**The four columns are the whole question.** Our architecture only ever calls AI from inside
a procedure or a Streamlit app, so the two right-hand columns decide whether the design
stands. The CLI column is irrelevant to production.

### Untested — nobody has tried these yet

| Capability | Test | Owner |
|---|---|---|
| Cortex Search service creation | `CREATE CORTEX SEARCH SERVICE` over `DECISION.POLICIES` | Keith |
| Semantic view creation | `CREATE SEMANTIC VIEW` + `DESCRIBE` | Keith |
| Streamlit in Snowflake deploy | create app, open URL | Nico |
| Streamlit reads/writes tables | `get_active_session()` + `SELECT` | Nico |
| Stage upload + directory table | `put_stream` → `ALTER STAGE REFRESH` → `DIRECTORY()` | Keith |
| Streams + triggered tasks | create, resume, fire | Keith |
| Cron task | `USING CRON */5 * * * * UTC` | Keith |
| CoCo in Snowsight, real work | ask it to write a procedure | all |
| Extra users on canonical account | `CREATE USER` + role grants | Porter |

---

## D. Access & coordination

| Item | Owner | Status |
|---|---|---|
| GitHub collaborator write access for Keith and Gabe | Porter | **open — blocking pushes** |
| Canonical account confirmed (team said Porter's) | Porter | open |
| Users created for Keith + Gabe on canonical | Porter | open |
| Cross-region inference set on canonical | Porter | open |
| DDL + seed deployed to canonical | one person, once | open |
| Audit fixes from the peer brief (history reset, gitignore, theme, coverage gate) | Porter | open |
| AI-block question escalated to organizers | Keith | posted in group; no official reply |

---

## E. Standing rules that come out of the above

1. **Deploy to the canonical account only, and one person at a time.** Divergent deploys from
   three laptops is the fastest way to lose a day.
2. **Re-verify this whole matrix on the canonical account** after the switch. Entitlements do
   not transfer.
3. **Never work around a platform block** — no external AI APIs, no containers, no adding a
   payment card. Report it and stop; those are team decisions, not build decisions.
4. Anything created in a worksheet that we want to keep gets written into `sql/` and
   redeployed. Otherwise it is not real.
