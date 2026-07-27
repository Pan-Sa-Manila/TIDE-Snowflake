"""TIDE — Home Page

Landing page with role routing. Sets up the global theme
and navigates users to their persona-specific page.
"""

import streamlit as st
from ui.theme import inject_css, PALETTE

# ---------------------------------------------------------------------------
# Page config — must be the first Streamlit command
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="TIDE — Dispute Resolution",
    page_icon="🌊",
    layout="centered",
    initial_sidebar_state="expanded",
)

# Inject global CSS
inject_css()

# ---------------------------------------------------------------------------
# Sidebar — app identity
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown("# 🌊 TIDE")
    st.caption("Triage · Investigation · Decision · Execution")
    st.divider()
    st.markdown("**Supervised agentic dispute resolution** for online retail.")
    st.markdown("---")
    st.markdown(
        f'<p style="color: {PALETTE["text_muted"]}; font-size: 0.75rem;">'
        f"Snowflake CoCo CLI Hackathon 2026</p>",
        unsafe_allow_html=True,
    )

# ---------------------------------------------------------------------------
# Main content — role selection
# ---------------------------------------------------------------------------
st.markdown("## Welcome to TIDE")
st.markdown(
    "Select your role to get started. Each persona has a dedicated "
    "workspace designed for their workflow."
)

st.markdown("---")

col1, col2, col3 = st.columns(3)

with col1:
    st.markdown(
        '<div class="tide-card">'
        "<h3>🛍️ Customer</h3>"
        "<p>Report a dispute, upload proof, track your case, "
        "and receive resolution updates.</p>"
        "</div>",
        unsafe_allow_html=True,
    )
    if st.button("Open Customer Portal", key="btn_customer", use_container_width=True):
        st.switch_page("pages/1_Customer.py")

with col2:
    st.markdown(
        '<div class="tide-card">'
        "<h3>✅ Approver</h3>"
        "<p>Review the approval queue, examine evidence, "
        "and approve or reject resolution requests.</p>"
        "</div>",
        unsafe_allow_html=True,
    )
    if st.button("Open Approver Dashboard", key="btn_approver", use_container_width=True):
        st.switch_page("pages/2_Approver.py")

with col3:
    st.markdown(
        '<div class="tide-card">'
        "<h3>🛡️ Escalation Agent</h3>"
        "<p>Claim escalated cases, review AI summaries, "
        "and take manual resolution actions.</p>"
        "</div>",
        unsafe_allow_html=True,
    )
    if st.button("Open Escalation Console", key="btn_escalation", use_container_width=True):
        st.switch_page("pages/3_Escalation.py")
