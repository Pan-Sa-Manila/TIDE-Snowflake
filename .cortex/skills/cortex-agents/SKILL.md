---
name: cortex-agents
description: Authoring and invoking Cortex Agent objects in TIDE — CREATE AGENT specs, tools, DATA_AGENT_RUN, and when to use plain AI_COMPLETE instead. Use when touching anything in agents/.
---

# Cortex agents

## Agent object vs AI_COMPLETE — the decision rule

Use an **agent object** only where the model must *choose between tools* based on what it
finds (Investigation). Use **`AI_COMPLETE` with a structured schema** where the task is a
single transformation (intake classification, resolution planning, summarisation, report,
vision). An agent object wrapping one hardcoded call is overhead pretending to be
architecture — and judges can read specs.

## CREATE AGENT conventions

- One agent: `TIDE.INVESTIGATION.INVESTIGATOR`. Schema-level object, YAML spec ≤100 KB.
- `models.orchestration: auto`. Budget tight: `{seconds: 60, tokens: 24000}` — investigation
  must finish inside a chat-adjacent wait.
- `instructions.orchestration` states tool selection policy in plain language (which source
  for which dispute type); `instructions.response` demands citations of the records used.
- Tools:
  - `cortex_analyst_text_to_sql` → `tool_resources.semantic_view: TIDE.RETAIL.DISPUTES_SV`
  - `cortex_search` → policy search service `TIDE.DECISION.POLICY_SEARCH`
  - custom tools = stored procedures (`GET_SHIPMENT_TIMELINE`, `GET_PAYMENT_STATUS`,
    `CHECK_INVENTORY`, `GET_REFUND_HISTORY`) — each with a one-sentence description written
    for the model, not for humans.

## Invocation

From SQL / procedures (never the REST API from Streamlit):

```sql
SELECT TRY_PARSE_JSON(SNOWFLAKE.CORTEX.DATA_AGENT_RUN(
  'TIDE.INVESTIGATION.INVESTIGATOR',
  OBJECT_CONSTRUCT('messages', ARRAY_CONSTRUCT(
      OBJECT_CONSTRUCT('role','user','content', ARRAY_CONSTRUCT(
          OBJECT_CONSTRUCT('type','text','text', :question)))))::STRING
));
```

- Non-streaming always; parse `TRY_PARSE_JSON`, treat NULL as failure → escalate branch.
- Log every run: agent name, case_id, elapsed, token usage if surfaced → `EXECUTION.PIPELINE_LOG`.

## Failure discipline

Agent/AI failure is a routed branch, not an exception: investigation failure marks the bundle
`assembly_status = 'failed'` and adjudication's guardrails handle it.
Never retry in a tight loop; one retry, then route.
