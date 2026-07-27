---
name: streamlit-sis
description: Streamlit-in-Snowflake warehouse-runtime patterns and limits for TIDE's three personas. Use when writing any UI code in streamlit/.
---

# Streamlit in Snowflake (warehouse runtime)

## Hard limits to design around

- Streamlit ≤1.52.2; Anaconda channel only, declared in `environment.yml`; no pip.
- **One app instance per viewer**, cache is per-session — never assume shared memory.
- No Cortex Agents REST API; no external HTTP.
- WebSocket idles out ~15 min; design pages to recover state from SQL on rerun, always.
- `st.set_page_config` partially ignored.

## App shape

```
streamlit/
  Home.py             # route
  pages/1_Customer.py # chat intake, proof upload, status tracker
  pages/2_Approver.py # queues, evidence review, approve/reject
  pages/3_Escalation.py # claim-on-open console
  ui/                 # theme.py, shared components
```

## Patterns

- **Chat:** `st.chat_message` / `st.chat_input`. On send: INSERT message → call procedure
  synchronously → INSERT reply → `st.rerun()`. State lives in tables.
- **Polling:** `st.fragment(run_every="4s")` on the message pane only — never whole-page
  autorefresh loops.
- **Proof upload:** `st.file_uploader` (jpeg/png/webp, ≤5 MB) → `put_stream` → `ALTER STAGE REFRESH` → call `ANALYZE_PROOF` → rerun.
- **Errors:** catch, log to `EXECUTION.PIPELINE_LOG`, and render `st.error` with a retry button.

## Theme

`streamlit/.streamlit/config.toml` carries the TIDE theme.
Custom CSS only through the one sanctioned `ui/theme.py::inject_css()` block.

## Demo-day

Pre-warm one browser session per persona 30 min before; a `scripts/demo_reset.sql` restores the seeded state between rehearsals.
