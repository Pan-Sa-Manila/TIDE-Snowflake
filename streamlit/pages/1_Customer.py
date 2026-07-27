"""TIDE — Customer Page

Customer persona: chat-based dispute intake, proof upload,
status tracker, and resolution updates.

Layout: Single centered column (~760px). Chat + composer + status tracker.
See AGENTS.md §7.1.
"""

import streamlit as st
from ui.theme import inject_css, status_pill_html, PALETTE

st.set_page_config(
    page_title="TIDE — Customer",
    page_icon="🛍️",
    layout="centered",
)

inject_css()

# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown("# 🌊 TIDE")
    st.caption("Customer Portal")
    st.divider()

    # TODO: Replace with actual session user
    st.markdown(f"**User:** demo_customer")
    st.markdown("---")

    if st.button("← Back to Home", use_container_width=True):
        st.switch_page("Home.py")

# ---------------------------------------------------------------------------
# Main content
# ---------------------------------------------------------------------------
st.markdown("## 🛍️ Customer Portal")
st.markdown("Report a dispute, track your case, and receive updates.")

st.divider()

# TODO: Implement when WS-D (Interface) begins
#
# Components to build:
#   1. Order selector — pick an order to dispute
#   2. Dispute type selector — 12 subtypes with descriptions
#   3. Resolution preference — constrained by subtype (§7.1)
#   4. Chat interface — guided intake with structured replies
#   5. Proof uploader — for proof-required subtypes
#   6. Status tracker — visual pipeline with current stage
#   7. Case history — list of past/active cases

st.info(
    "🚧 **Customer portal under construction.**\n\n"
    "This page will include:\n"
    "- Guided dispute intake with AI-powered follow-ups\n"
    "- Proof image upload and analysis\n"
    "- Real-time case status tracking\n"
    "- Resolution details and case reports"
)
