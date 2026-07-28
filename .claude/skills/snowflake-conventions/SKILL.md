---
name: snowflake-conventions
description: TIDE's Snowflake DDL, DML, and orchestration patterns. Use when writing any SQL, tables, views, tasks, streams, stages, or stored procedures.
---

# Snowflake conventions

## DDL

- IDs: `VARCHAR(36) DEFAULT UUID_STRING()`.
- Money: `NUMBER(10,2)`. Timestamps: `TIMESTAMP_TZ`, stored UTC.
- Semi-structured payloads: `VARIANT`.
- **CHECK constraints and FKs are not enforced.** Declare FKs for lineage/documentation, but
  every enum lives in a lookup table or code-level validation with a test.
- Reference numbers: `CASE_SEQ.NEXTVAL` formatted `TIDE-%05d`.

## Append-only + derived state

- `TRIAGE.CHAT` and `TRIAGE.CASE_EVENTS` are INSERT-only. State transitions are events.
- Current state = `TRIAGE.V_CASE_CURRENT`.
- Transition legality is validated in the procedure layer before the event is
  inserted; illegal transition → raise, nothing written.

## Stages & files

- `INVESTIGATION.PROOF_STAGE`: `DIRECTORY = (ENABLE = TRUE)`, `ENCRYPTION = (TYPE =
  'SNOWFLAKE_SSE')` — SSE is mandatory for AI reads and presigned URLs.
- Store `relative_path` + sha256 + dims in `INVESTIGATION.PROOF_FILES`; never store bytes in a
  table.

## Tasks / streams / orchestration

- Triggered tasks: `WHEN SYSTEM$STREAM_HAS_DATA('<stream>')`.
- Chat-path work is **never** a task (30 s trigger floor) — synchronous procedure calls only.
- Timeout sweeper: cron task, closes idle `pending_triage` cases.
- Every task writes an outcome row to `EXECUTION.PIPELINE_LOG`.

## AI calls

- `AI_COMPLETE` functions only.
- Always `response_format` JSON schema + `temperature: 0` + "Respond in JSON." in the prompt.
- Wrap every call site in `TRY_PARSE_JSON` + explicit failure branch.
