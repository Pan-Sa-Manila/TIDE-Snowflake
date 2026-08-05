"""TIDE — Escalation Console (3_Escalation.py)

Escalation agent persona: claim-on-open console for hard cases.
Live chat, AI-generated summaries, and manual resolution actions.

Layout: Full width. Chat left 3/5, work panel right 2/5
(Actions · Summary · Details tabs).
See AGENTS.md §7.1, DETAILS.md §4, §14 F4.3.
"""

from __future__ import annotations

import streamlit as st
from ui.theme import (
    inject_css,
    sidebar_branding,
    status_pill_html,
    age_bucket_pill,
    format_currency,
    format_datetime,
    pipeline_steps_html,
    PALETTE,
)
from ui.db import (
    run_sql,
    run_sql_first,
    call_proc,
    get_current_user,
    get_session,
)

st.set_page_config(
    page_title="TIDE — Escalation",
    page_icon="🛡️",
    layout="wide",
)

inject_css()

# ---------------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------------
if "esc_case_id" not in st.session_state:
    st.session_state.esc_case_id = None

username = get_current_user()

# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------

def load_queue() -> list[dict]:
    """Load the full escalation queue."""
    return run_sql(
        """
        SELECT case_id, reference_number, dispute_subtype, current_status,
               eligible_amount, resolution_type, age_minutes, age_bucket,
               status_changed_at, customer_id, order_id,
               assigned_to, assigned_at
        FROM TIDE.TRIAGE.V_QUEUE_ESCALATION
        ORDER BY
            CASE WHEN assigned_to IS NULL THEN 0 ELSE 1 END,
            status_changed_at ASC
        """,
        log_component="3_Escalation.load_queue",
    )


def load_case(case_id: str) -> dict | None:
    return run_sql_first(
        """
        -- age_minutes / age_bucket are derived by V_QUEUE_ESCALATION, not by
        -- V_CASE_CURRENT, and a case opened from the queue may since have left
        -- it. Computed inline with the same expressions the queue view uses so
        -- the two never disagree — see sql/01_triage_ddl.sql.
        SELECT case_id, reference_number, order_id, customer_id,
               dispute_type, dispute_subtype, resolution_preference,
               intake_summary, proof_required, current_status,
               eligible_amount, resolution_type, path_id,
               DATEDIFF('minute', status_changed_at, CURRENT_TIMESTAMP())
                   AS age_minutes,
               CASE
                   WHEN DATEDIFF('minute', status_changed_at, CURRENT_TIMESTAMP()) < 15 THEN 'fresh'
                   WHEN DATEDIFF('minute', status_changed_at, CURRENT_TIMESTAMP()) < 60 THEN 'aging'
                   ELSE 'urgent'
               END AS age_bucket,
               status_changed_at, created_at,
               assigned_to, assigned_at, closed_by, close_reason
        FROM TIDE.TRIAGE.V_CASE_CURRENT
        WHERE case_id = ?
        """,
        [case_id],
        log_component="3_Escalation.load_case",
        case_id=case_id,
    )


def load_messages(case_id: str) -> list[dict]:
    return run_sql(
        """
        SELECT sender_type, sender_id, content, metadata, created_at
        FROM TIDE.TRIAGE.CHAT
        WHERE case_id = ?
        ORDER BY created_at ASC
        """,
        [case_id],
        log_component="3_Escalation.load_messages",
        case_id=case_id,
    )


def load_evidence_bundle(case_id: str) -> dict | None:
    return run_sql_first(
        """
        SELECT bundle_id, assembly_status, bundle,
               sources_queried, assembled_at
        FROM TIDE.INVESTIGATION.EVIDENCE_BUNDLES
        WHERE case_id = ?
        ORDER BY assembled_at DESC
        LIMIT 1
        """,
        [case_id],
        log_component="3_Escalation.load_bundle",
        case_id=case_id,
    )


def load_decision(case_id: str) -> dict | None:
    return run_sql_first(
        """
        SELECT path_id, target_status, resolution_type,
               eligible_amount, shipping_fee_only,
               invalid_reason_code, reason, decided_at
        FROM TIDE.DECISION.DECISIONS
        WHERE case_id = ?
        ORDER BY decided_at DESC
        LIMIT 1
        """,
        [case_id],
        log_component="3_Escalation.load_decision",
        case_id=case_id,
    )


def load_escalation_summary(case_id: str) -> str | None:
    row = run_sql_first(
        """
        SELECT outcome_summary
        FROM TIDE.EXECUTION.CASE_REPORTS
        WHERE case_id = ?
        """,
        [case_id],
        log_component="3_Escalation.load_summary",
        case_id=case_id,
    )
    if row:
        return row.get("OUTCOME_SUMMARY")
    # Fallback: look for a summarized event in PIPELINE_LOG
    log_row = run_sql_first(
        """
        SELECT detail:summary::VARCHAR AS summary
        FROM TIDE.EXECUTION.PIPELINE_LOG
        WHERE case_id = ?
          AND component = 'T_SUMMARIZE'
          AND status = 'completed'
        ORDER BY logged_at DESC
        LIMIT 1
        """,
        [case_id],
        log_component="3_Escalation.load_summary_log",
        case_id=case_id,
    )
    return (log_row or {}).get("SUMMARY")


def load_case_events(case_id: str) -> list[dict]:
    return run_sql(
        """
        SELECT event_type, actor_type, actor_id, payload, occurred_at
        FROM TIDE.TRIAGE.CASE_EVENTS
        WHERE case_id = ?
        ORDER BY occurred_at ASC
        """,
        [case_id],
        log_component="3_Escalation.load_events",
        case_id=case_id,
    )


def claim_case(case_id: str):
    """Claim an unassigned escalated case — records a 'claimed' event."""
    return call_proc(
        "TIDE.TRIAGE.CLAIM_CASE",
        [case_id],
        log_component="CLAIM_CASE",
        case_id=case_id,
    )


def queue_counts_for_user() -> tuple[int, int]:
    rows = run_sql(
        """
        SELECT
            COUNT(CASE WHEN assigned_to IS NULL THEN 1 END) AS unassigned,
            COUNT(CASE WHEN assigned_to = ? THEN 1 END) AS mine
        FROM TIDE.TRIAGE.V_QUEUE_ESCALATION
        """,
        [username],
        log_component="3_Escalation.queue_counts",
    )
    r = rows[0] if rows else {}
    return int(r.get("UNASSIGNED", 0)), int(r.get("MINE", 0))


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
with st.sidebar:
    sidebar_branding("Escalation Console")

    st.markdown(
        f'<p style="color:{PALETTE["sidebar_muted"]} !important;font-size:0.82rem;">'
        f'Signed in as</p>'
        f'<p style="color:{PALETTE["sidebar_text"]} !important;font-weight:600;'
        f'font-size:0.92rem;margin-top:-0.5rem;">{username}</p>',
        unsafe_allow_html=True,
    )

    st.markdown(
        f'<div style="height:1px;background:{PALETTE["sidebar_divider"]};'
        f'margin:1rem 0;"></div>',
        unsafe_allow_html=True,
    )

    st.markdown(
        f'<p style="color:{PALETTE["primary"]} !important;font-size:0.88rem;'
        f'font-weight:600;margin-bottom:0.75rem;">Escalation Queue</p>',
        unsafe_allow_html=True,
    )
    unassigned, my_cases = queue_counts_for_user()
    st.metric("Unassigned", unassigned)
    st.metric("My Cases", my_cases)

    st.markdown(
        f'<div style="height:1px;background:{PALETTE["sidebar_divider"]};'
        f'margin:1rem 0;"></div>',
        unsafe_allow_html=True,
    )

    if st.session_state.esc_case_id:
        if st.button("← Clear Selection", use_container_width=True):
            st.session_state.esc_case_id = None
            st.experimental_rerun()

    if st.button("← Back to Home", use_container_width=True):
        try:
            st.switch_page("Home.py")
        except AttributeError:
            st.info("👉 Click **Home** in the sidebar to navigate.")


# ---------------------------------------------------------------------------
# Page header
# ---------------------------------------------------------------------------
st.markdown("## 🛡️ Escalation Console")
st.markdown("Claim and resolve escalated dispute cases.")
st.divider()

# ---------------------------------------------------------------------------
# Queue list (top)
# ---------------------------------------------------------------------------
queue = load_queue()

if not queue:
    st.success("🎉 No cases in the escalation queue.")
    st.stop()

# Compact queue selector
with st.expander(f"📋 Queue — {len(queue)} case(s)", expanded=st.session_state.esc_case_id is None):
    for row in queue:
        assigned_to = row.get("ASSIGNED_TO")
        is_mine = assigned_to == username
        is_unassigned = assigned_to is None
        is_selected = st.session_state.esc_case_id == row["CASE_ID"]
        sel_class = " selected" if is_selected else ""

        st.markdown(
            f'<div class="queue-card{sel_class}">'
            f'<div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:6px;">'
            f'<span style="font-weight:700;color:{PALETTE["text_primary"]};">{row.get("REFERENCE_NUMBER", "—")}</span>'
            + status_pill_html(row.get("CURRENT_STATUS", ""))
            + age_bucket_pill(row.get("AGE_MINUTES", 0))
            + f'</div>'
            f'<div style="font-size:0.8rem;color:{PALETTE["text_secondary"]};margin-top:6px;">'
            f'{row.get("DISPUTE_SUBTYPE", "").replace("_", " ").title()}'
            f'{" — " + format_currency(row.get("ELIGIBLE_AMOUNT")) if row.get("ELIGIBLE_AMOUNT") else ""}'
            f'{" — 🔒 Claimed by you" if is_mine else ""}'
            f'{" — 👤 " + str(assigned_to) if (assigned_to and not is_mine) else ""}'
            f'{" — Unassigned" if is_unassigned else ""}'
            f'</div></div>',
            unsafe_allow_html=True,
        )
        btn_label = (
            "✓ Open" if is_selected
            else ("Open My Case →" if is_mine else ("Claim & Open →" if is_unassigned else "View (read-only) →"))
        )
        if st.button(btn_label, key=f"esc_sel_{row['CASE_ID']}", use_container_width=True):
            if is_unassigned:
                with st.spinner("Claiming case…"):
                    claim_case(row["CASE_ID"])
            st.session_state.esc_case_id = row["CASE_ID"]
            st.experimental_rerun()

# ---------------------------------------------------------------------------
# Case workspace
# ---------------------------------------------------------------------------
case_id = st.session_state.esc_case_id
if not case_id:
    st.stop()

case = load_case(case_id)
if not case:
    st.warning("Case data unavailable.")
    st.stop()

current_status = case.get("CURRENT_STATUS", "")
assigned_to = case.get("ASSIGNED_TO")
is_mine = assigned_to == username
is_readonly = (not is_mine) and (assigned_to is not None)

# Case header bar
hcol1, hcol2, hcol3 = st.columns([2, 1, 1])
with hcol1:
    st.markdown(f"### {case.get('REFERENCE_NUMBER', '—')}")
    st.caption(
        f"Order: `{case.get('ORDER_ID', '—')[:12]}…`  |  "
        f"Customer: `{case.get('CUSTOMER_ID', '—')}`  |  "
        f"Opened: {format_datetime(case.get('CREATED_AT'))}"
    )
with hcol2:
    st.markdown(status_pill_html(current_status), unsafe_allow_html=True)
with hcol3:
    if is_readonly:
        st.warning(f"🔒 Assigned to {assigned_to}")
    elif is_mine:
        st.success("✅ Claimed by you")
    else:
        st.info("🔓 Unassigned")

st.divider()

# 3/5 + 2/5 layout
col_chat, col_panel = st.columns([3, 2], gap="large")

# ============================================================
# LEFT 3/5: Chat panel
# ============================================================
with col_chat:
    st.markdown("#### 💬 Case Chat")

    if is_readonly:
        st.warning("Read-only view — this case is claimed by another agent.")

    def _escalation_chat(case_id: str):
        messages = load_messages(case_id)
        if not messages:
            st.info("No messages yet.")
            return
        for msg in messages:
            sender = msg.get("SENDER_TYPE", "assistant")
            content = msg.get("CONTENT", "")
            ts = format_datetime(msg.get("CREATED_AT"))
            sid = msg.get("SENDER_ID", "")
            if sender == "customer":
                st.markdown(
                    f'<div style="background:#E87722;color:#fff;border-radius:12px 12px 2px 12px;'
                    f'padding:10px 14px;margin:6px 0 6px 20%;text-align:right;">'
                    f'{content}<br><span style="font-size:0.72em;opacity:0.8;">Customer · {ts}</span></div>',
                    unsafe_allow_html=True,
                )
            elif sender == "agent":
                st.markdown(
                    f'<div style="background:#1e3a5f;color:#eee;border-radius:12px 12px 12px 2px;'
                    f'padding:10px 14px;margin:6px 20% 6px 0;">'
                    f'🛡️ {content}<br><span style="font-size:0.72em;opacity:0.6;">Agent {sid} · {ts}</span></div>',
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    f'<div style="background:#2a2a2a;color:#eee;border-radius:12px 12px 12px 2px;'
                    f'padding:10px 14px;margin:6px 20% 6px 0;">'
                    f'🤖 {content}<br><span style="font-size:0.72em;opacity:0.6;">TIDE · {ts}</span></div>',
                    unsafe_allow_html=True,
                )
        st.button("🔄 Refresh Chat", key="refresh_chat_escalation")

    _escalation_chat(case_id)

    if not is_readonly and current_status not in ("resolved", "closed"):
        with st.form(key="esc_chat_form", clear_on_submit=True):
            agent_msg = st.text_area(
                "Message the customer",
                placeholder="Message the customer…",
                height=80,
                label_visibility="collapsed",
            )
            esc_submitted = st.form_submit_button("Send ➤")
        if esc_submitted and agent_msg and agent_msg.strip():
            with st.spinner("Sending…"):
                result = call_proc(
                    "TIDE.TRIAGE.AGENT_MESSAGE",
                    [case_id, agent_msg.strip()],
                    log_component="AGENT_MESSAGE",
                    case_id=case_id,
                )
            if result is None:
                st.error("⚠️ Failed to send message.")
            st.experimental_rerun()

# ============================================================
# RIGHT 2/5: Work panel
# ============================================================
with col_panel:
    tab_actions, tab_summary, tab_details = st.tabs(["⚡ Actions", "📝 Summary", "🔎 Details"])

    # ── Actions ──────────────────────────────────────────────
    with tab_actions:
        st.markdown("#### Resolution Actions")

        if is_readonly:
            st.warning("Actions disabled — case claimed by another agent.")
        elif current_status in ("resolved", "closed"):
            st.success("This case is already resolved/closed.")
        else:
            # Resolve
            with st.expander("✅ Resolve Case", expanded=True):
                resolve_type = st.selectbox(
                    "Resolution type",
                    ["refund", "replacement"],
                    key="resolve_type_sel",
                )
                resolve_amount = st.number_input(
                    "Amount (USD)",
                    min_value=0.01,
                    value=float(case.get("ELIGIBLE_AMOUNT") or 0.01),
                    step=0.01,
                    key="resolve_amount_input",
                    format="%.2f",
                )
                resolve_note = st.text_area(
                    "Resolution note (visible to customer)",
                    placeholder="Explain the resolution outcome…",
                    key="resolve_note_input",
                    height=80,
                )
                if st.button("✅ Confirm Resolution", key="btn_resolve", use_container_width=True, type="primary"):
                    with st.spinner("Resolving…"):
                        result = call_proc(
                            "TIDE.TRIAGE.ESCALATION_RESOLVE",
                            [case_id, resolve_type, resolve_amount, resolve_note],
                            log_component="ESCALATION_RESOLVE",
                            case_id=case_id,
                        )
                    if result and result.get("success"):
                        st.success("Case resolved.")
                        st.session_state.esc_case_id = None
                        st.experimental_rerun()
                    else:
                        err = (result or {}).get("error", "Unknown error.")
                        st.error(f"⚠️ {err}")

            st.divider()

            # Close
            with st.expander("✖ Close Without Resolution"):
                close_reason_input = st.text_area(
                    "Close reason",
                    placeholder="Why is this case being closed without resolution?",
                    key="close_reason_esc",
                    height=80,
                )
                if st.button("✖ Close Case", key="btn_close_esc", use_container_width=True):
                    if not close_reason_input.strip():
                        st.error("Please provide a close reason.")
                    else:
                        with st.spinner("Closing…"):
                            result = call_proc(
                                "TIDE.TRIAGE.CLOSE_CASE",
                                [case_id, "agent", close_reason_input.strip()],
                                log_component="CLOSE_CASE",
                                case_id=case_id,
                            )
                        if result and result.get("success"):
                            st.success("Case closed.")
                            st.session_state.esc_case_id = None
                            st.experimental_rerun()
                        else:
                            err = (result or {}).get("error", "Unknown error.")
                            st.error(f"⚠️ {err}")

    # ── Summary ───────────────────────────────────────────────
    with tab_summary:
        st.markdown("#### AI-Generated Escalation Summary")
        summary = load_escalation_summary(case_id)
        if summary:
            st.markdown(summary)
        else:
            st.info(
                "No escalation summary available yet. "
                "The T_SUMMARIZE task generates one automatically when a case is escalated "
                "(may take ~30 seconds after escalation)."
            )
            if st.button("🔄 Refresh Summary", key="btn_refresh_summary"):
                st.experimental_rerun()

        st.divider()
        if case.get("INTAKE_SUMMARY"):
            st.markdown("**Intake Summary (AI)**")
            st.markdown(case["INTAKE_SUMMARY"])

    # ── Details ───────────────────────────────────────────────
    with tab_details:
        st.markdown("#### Case Details")

        # Key facts
        dcols = st.columns(2)
        dcols[0].markdown(f"**Subtype:** {case.get('DISPUTE_SUBTYPE', '—').replace('_', ' ').title()}")
        dcols[0].markdown(f"**Type:** {case.get('DISPUTE_TYPE', '—')}")
        dcols[0].markdown(f"**Preference:** {case.get('RESOLUTION_PREFERENCE', '—')}")
        dcols[1].markdown(f"**Path:** `{case.get('PATH_ID', '—')}`")
        dcols[1].markdown(f"**Eligible:** {format_currency(case.get('ELIGIBLE_AMOUNT'))}")
        dcols[1].markdown(f"**Resolution:** {(case.get('RESOLUTION_TYPE') or '—').title()}")

        # Decision
        decision = load_decision(case_id)
        if decision:
            st.divider()
            st.markdown("**Decision**")
            st.info(
                f"**Path:** `{decision.get('PATH_ID', '—')}` · "
                f"**Status target:** {decision.get('TARGET_STATUS', '—')} · "
                f"{format_datetime(decision.get('DECIDED_AT'))}\n\n"
                f"{decision.get('REASON', '')}"
            )

        # Evidence bundle (collapsed)
        bundle_row = load_evidence_bundle(case_id)
        if bundle_row:
            with st.expander("📋 Evidence Bundle"):
                bundle = bundle_row.get("BUNDLE") or {}
                st.json(bundle)
                sources = bundle_row.get("SOURCES_QUERIED")
                if sources:
                    st.caption(f"Sources: {', '.join(sources)}")

        # Event timeline
        events = load_case_events(case_id)
        if events:
            with st.expander(f"🕒 Timeline ({len(events)} events)"):
                for ev in events:
                    ev_type = ev.get("EVENT_TYPE", "")
                    actor = ev.get("ACTOR_ID") or ev.get("ACTOR_TYPE", "")
                    ts = format_datetime(ev.get("OCCURRED_AT"))
                    st.markdown(
                        f"- `{ts}` — **{ev_type.replace('_', ' ').title()}** by *{actor}*"
                    )
