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

**Cortex AI is UNBLOCKED as of 4 August 2026.** The trial-account restriction that shaped
much of this codebase has lifted. Verified working on canonical:

- `AI_COMPLETE` with `openai-gpt-5-mini` (the `MODEL_TEXT` constant) — returns normally
- `AI_COMPLETE` with `gemini-2.5-flash` (`MODEL_VISION`), **multimodal**: `PROMPT(... {0},
  TO_FILE('@stage','path'))` combined with `response_format` constrained decoding, both at
  once. This is what `INVESTIGATION.ANALYZE_PROOF` runs on.
- `DATA_AGENT_RUN` against the `INVESTIGATOR` agent, and Cortex Search.

A model that is not entitled in this region now fails with `"Model X is unavailable"` rather
than `"not available for trial accounts"`. If you see the latter, the block is back — say so
and stop. Do not assume a model exists because another one does: `claude-3-5-sonnet` is
unavailable here while the two above work.

The rules that outlived the block, and still apply:

- **Route every AI call through a wrapper that reads its model from
  `DECISION.RULE_CONSTANTS`.** `DECISION.AI_JSON` is that wrapper for text. Multimodal calls
  cannot use it — its prompt parameter is `VARCHAR` and `PROMPT(...)` is not — so
  `ANALYZE_PROOF` calls `AI_COMPLETE` directly but still reads `MODEL_VISION` from the table.
  **Never hardcode a model name.**
- **Give every AI call a deterministic fallback**, still required under `DETAILS.md` failure
  handling. Note the distinction that matters: proof analysis that *fails* must record
  `analysis_status = 'failed'`, because §10 G-07 routes that to a human. Recording it as
  merely unanalysed reaches G-09 and tells the customer their proof is insufficient when in
  truth nobody looked at it.
- `# BLOCKED: cortex-trial` markers are now historical. `scripts/deploy.py` still tolerates
  files carrying them; leave that in place, but no new file should need one.
- **Do not attempt workarounds** if something is genuinely unavailable. No external AI APIs,
  no `requests`, no External Access Integration, no Snowpark Container Services, no Docker,
  no suggesting a credit card be added. If you think you have found a way around a
  restriction, say so and stop.

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
- **`GRANT ALL PRIVILEGES ON SCHEMA` does not cascade to the objects in it.** Tables, views,
  stages and sequences each need their own `ON ALL` *and* `ON FUTURE` grant. `ON FUTURE` alone
  misses what already exists; `ON ALL` alone misses a fresh deploy.
- A **missing grant reads as "invalid identifier" or "object does not exist"**, not as a
  permission error. `invalid identifier 'TIDE.TRIAGE.CASE_SEQ.NEXTVAL'` inside a procedure meant
  the owner role lacked `USAGE` on the sequence — it looked like a syntax problem for three
  rewrites. Suspect grants before syntax when an object you can see from a worksheet is
  invisible inside `EXECUTE AS OWNER`.
- In a procedure body, **alias every table and qualify every column**. A parameter named
  `ORDER_ID` shadows the column `order_id`, so `SELECT case_id ... WHERE order_id = :ORDER_ID`
  silently reads the parameter instead of the column.
- **Use bracket notation for VARIANT paths in SQL that the CLI will echo.** `analysis:notes`
  produces the token `:notes:`, which the CLI's renderer turns into an emoji and then dies
  encoding to cp1252 — killing the whole deploy with a `UnicodeEncodeError` and no SQL error.
  `analysis['notes']` is immune. Any common English key can trigger it.
- Snowflake Scripting rejects **`SELECT ... INTO` when the select list contains a scalar
  subquery** — "INTO clause is not allowed in this context". Build each piece into its own
  variable, then assemble.
- In a Python procedure, **a Python list cannot be bound to a placeholder**. Binding one for an
  `ARRAY` column fails with `list index out of range`, which reads like a bug in your own code.
  Pass `json.dumps(...)` and use `PARSE_JSON(?)::ARRAY`.
- A procedure that writes several related rows should wrap them in `BEGIN` / `COMMIT` with
  `ROLLBACK` in the handler. Without it a mid-way failure leaves a half-written case — a
  decision row recorded against a status the case never moved to.

## Clean-room rule

This is a greenfield project. Do not reference, compare against, or import from any other
project or repository, in code, comments, docs, or commit messages. Everything originates
here.
