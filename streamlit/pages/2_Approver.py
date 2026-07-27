"""TIDE — Approver Page

Approver persona: queue-based review of resolution requests.
Examine evidence, recommended decisions, approve or reject with rigor.

Layout: Full width. Queue columns (refund/return/replacement) + case review panel.
See AGENTS.md §7.1.
"""

import streamlit as st
from ui.theme import inject_css, status_pill_html, PALETTE

st.set_page_config(
    page_title="TIDE — Approver",
    page_icon="✅",
    layout="wide",
)

inject_css()

# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown("# 🌊 TIDE")
    st.caption("Approver Dashboard")
    st.divider()

    # TODO: Replace with actual session user
    st.markdown(f"**User:** demo_approver")
    st.markdown("---")

    # Queue summary
    st.markdown("### Queue Summary")
    st.metric("Pending Refunds", "—")
    st.metric("Pending Returns", "—")
    st.metric("Pending Replacements", "—")
    st.markdown("---")

    if st.button("← Back to Home", use_container_width=True):
        st.switch_page("Home.py")

# ---------------------------------------------------------------------------
# Main content
# ---------------------------------------------------------------------------
st.markdown("## ✅ Approver Dashboard")
st.markdown("Review and action pending resolution requests.")

st.divider()

# TODO: Implement when WS-D (Interface) begins
#
# Components to build:
#   1. Queue tabs — Refund | Return | Replacement
#   2. Case list — sorted by age, with age bucket pills
#   3. Case review panel — evidence summary, decision details
#   4. Approve button — one-click execution
#   5. Reject form — ≥50 chars reason + ≥1 policy citation
#   6. Rejection citation picker — from DECISION.POLICIES via Cortex Search

st.info(
    "🚧 **Approver dashboard under construction.**\n\n"
    "This page will include:\n"
    "- Approval queue with age-based priority\n"
    "- Evidence review panel with AI-assembled bundles\n"
    "- One-click approve with automatic execution\n"
    "- Reject with enforced rigor (≥50 chars + policy citation)"
)
