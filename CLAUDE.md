# CLAUDE.md — Claude Code working rules for TIDE

## Read before doing anything

`AGENTS.md` is the primary rulebook and it applies to you in full: naming, stack
constraints, prohibitions, the BRL-first change protocol. **Do not duplicate or restate its
rules here or anywhere else** — read it, follow it. This file only adds what is specific to
working through Claude Code on this machine.

Then read whichever of these your task touches:

| Task area | Read |
|---|---|
| Business logic, guardrails, routing | `docs/DETAILS.md` (the law) |
| Tables, views, bundle shape | `docs/SCHEMA.md` |
| System design, sync/async split | `docs/ARCHITECTURE.md` |
| What's assigned and in flight | `docs/TASKS.md` |
| Why a choice was made | `docs/DECISIONS.md` (settled — don't relitigate) |
| Schedule, gates, cut lines | `docs/BUILD_PLAN.md` |

Never infer a business rule from existing code. Code can be wrong; `DETAILS.md` cannot.
If they disagree, stop and say so.

## Environment

Windows. Repo at `D:\Projects\TIDE-Snowflake`. Snowflake connection is named `tide`
(`~/.snowflake/connections.toml`). Python 3.12, Snowflake CLI 3.23.

```powershell
snow sql -c tide -f path\to\file.sql     # preferred: always use a file
snow sql -c tide -q "SELECT 1"           # only for trivial, brace-free SQL
python scripts/deploy.py --connection tide
pytest tests/ -q
```

## Platform reality — read this before writing any AI call

**Cortex AI is currently blocked on the issued trial account.** Verified failing:
`AI_COMPLETE` (every model and call form), legacy `COMPLETE`, `SUMMARIZE`, and
`DATA_AGENT_RUN` — all return "not available for trial accounts". Agent *objects* can be
created; they just cannot be run. DDL, seed, warehouses, stages, tasks, and Streamlit all
work normally. This is under escalation with the organizers.

What this means for you:

- **Write AI call sites anyway**, exactly as specified in the agent spec. They are correct
  code that currently cannot execute. Mark them with a `# BLOCKED: cortex-trial` comment so
  they are greppable when access lands.
- **Route every AI call through one wrapper** that reads model names from
  `DECISION.RULE_CONSTANTS`. When the block lifts it must be a config change, not a rewrite.
- **Give every AI call a deterministic fallback path** so the pipeline is demonstrable
  without AI: intake falls back to the structured selector, proof analysis falls back to
  "unverified", summaries fall back to a templated digest. These are required behaviour
  under `DETAILS.md` failure handling, not scaffolding.
- **Do not attempt workarounds.** No external AI APIs, no `requests`, no External Access
  Integration, no Snowpark Container Services, no Docker, no suggesting a credit card be
  added. All are either blocked on this account, out of scope, or a team decision that is
  not yours. If you think you have found a way around the block, say so and stop.

## Git discipline

Work on your own branch (`keith`, `gabe`, `nico`). Never commit to `master` directly.

**Never run `git add .` or `git add -A`.** The `_handoff/` folder is untracked scratch and
must not be committed. Stage explicit paths only:

```powershell
git add sql/ procedures/ docs/TASKS.md
```

Commit messages: conventional prefix, imperative, and reference the doc section that drove
the change where one exists — `feat(decision): implement DETAILS.md §10 guardrail G-04`.
Small commits. No AI attribution in commit messages or code.

Before any commit touching `tide_decision/`: `pytest tests/ -q` must be green.

## Ask before

- Deploying to any account other than the one in the `tide` connection
- Any change to a table's columns or a procedure's signature (other people build against both)
- Adding a dependency (requires a line in `docs/ARCHITECTURE.md`)
- Changing anything in `docs/DETAILS.md` — business rules need Keith's sign-off
- Deleting or rewriting files you did not create in this session

## Definition of done

- **SQL object**: file in `sql/`, idempotent (`CREATE OR REPLACE` / `IF NOT EXISTS`, scoped
  deletes before seed inserts), runs clean via `snow sql -f`, verified with a `SELECT`.
- **Pipeline-step procedure** (intake turn, assemble evidence, adjudicate, execute, tasks):
  deploys, callable, writes a row to `EXECUTION.PIPELINE_LOG`, handles its failure branch,
  no business constants hardcoded.
- **Read-only tool procedure** (the agent's evidence tools): deploys, callable, returns a
  well formed object when data is absent, **does not** log — the calling pipeline step logs
  once for the whole assembly. Tools report facts and never classify or threshold.
- **Engine change**: `DETAILS.md` updated first if the rule changed, test per affected path
  id, full suite green.
- **UI page**: renders against seeded data, recovers state from SQL on rerun, all SQL through
  the shared `run_sql()` helper, no raw tracebacks shown.

## Known gotchas, learned the hard way

- `snow sql -f` **aborts the whole file on the first error** — put risky statements in their
  own file when probing.
- cmd mangles `{`/`}` in `-q` strings. Use `-f` with a file for anything with a JSON schema.
- Non-ASCII characters in Python `print()` crash on this machine's cp1252 console. Plain
  ASCII in scripts.
- A `UserWarning: Encoding mismatch` line prefixes most `snow` output. It is noise, not an
  error.
- Stage paths are case-sensitive; stage names are not. Always `ALTER STAGE ... REFRESH`
  after an upload.
- `PUT` does not work from a Snowsight worksheet. Use `session.file.put_stream` or the CLI.
- In `CREATE PROCEDURE`, **`COMMENT =` must come before `EXECUTE AS`** — the wrong order
  fails with a bare `unexpected 'COMMENT'`.
- **`ARRAY_AGG` over an empty group returns `[]`, not NULL.** `IS NOT NULL` is never a valid
  emptiness test on an aggregated array; use `ARRAY_SIZE(...) > 0`.
- Test a `found` flag against a primary key, never against a nullable-looking column.
- `snow`'s stderr can appear **ahead of** Python's stdout when piped, so one failing SQL file
  can look like two, blamed on the wrong file. Redirect a full run to a file before diagnosing.

## Clean-room rule

This is a greenfield project. Do not reference, compare against, or import from any other
project or repository, in code, comments, docs, or commit messages. Everything originates
here.
