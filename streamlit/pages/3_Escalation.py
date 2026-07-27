"""TIDE — Escalation Page

Escalation agent persona: claim-on-open console for hard cases.
Live chat, AI-generated summaries, and manual resolution actions.

Layout: Full width. Chat left 3/5, work panel right 2/5
(Actions · Summary · Details tabs).
See AGENTS.md §7.1.
"""

import streamlit as st
from ui.theme import inject_css, status_pill_html, PALETTE

st.set_page_config(
    page_title="TIDE — Escalation",
    page_icon="🛡️",
    layout="wide",
)

inject_css()

# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown("# 🌊 TIDE")
    st.caption("Escalation Console")
    st.divider()

    # TODO: Replace with actual session user
    st.markdown(f"**User:** demo_escalation")
    st.markdown("---")

    # Queue summary
    st.markdown("### Escalation Queue")
    st.metric("Unassigned", "—")
    st.metric("My Cases", "—")
    st.markdown("---")

    if st.button("← Back to Home", use_container_width=True):
        st.switch_page("Home.py")

# ---------------------------------------------------------------------------
# Main content — 3/5 + 2/5 layout
# ---------------------------------------------------------------------------
st.markdown("## 🛡️ Escalation Console")
st.markdown("Claim and resolve escalated dispute cases.")

st.divider()

# TODO: Implement when WS-D (Interface) begins
#
# Components to build:
#   1. Queue list — unassigned + my claimed cases
#   2. Claim button — claim-on-open (records assignment event)
#   3. Chat panel (left 3/5) — live chat with customer
#   4. Work panel (right 2/5) with tabs:
#      a. Actions — resolve, close, transfer
#      b. Summary — AI-generated escalation summary
#      c. Details — evidence bundle, decision history, timeline
#   5. Read-only mode for cases assigned to other agents

col_chat, col_panel = st.columns([3, 2])

with col_chat:
    st.info(
        "🚧 **Chat panel under construction.**\n\n"
        "Live chat with the customer will appear here, "
        "with full conversation history and agent messaging."
    )

with col_panel:
    st.info(
        "🚧 **Work panel under construction.**\n\n"
        "Tabs for Actions · Summary · Details will appear here, "
        "with AI-generated summaries and one-click resolution actions."
    )
