"""TIDE — Home Page

Landing page with role routing. Sets up the global theme
and navigates users to their persona-specific page.
"""

import streamlit as st
from ui.theme import inject_css, sidebar_branding, PALETTE

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
    sidebar_branding("Dispute Resolution Platform")

    st.markdown(
        f'<p style="color:{PALETTE["sidebar_text"]};font-size:0.85rem;'
        f'line-height:1.6;opacity:0.9;">'
        f'Supervised agentic dispute resolution for online retail, '
        f'powered by Snowflake Cortex AI.'
        f'</p>',
        unsafe_allow_html=True,
    )

    st.markdown(
        f'<div style="height:1px;background:{PALETTE["sidebar_divider"]};'
        f'margin:1rem 0;"></div>',
        unsafe_allow_html=True,
    )

    st.markdown(
        f'<p style="color:{PALETTE["sidebar_muted"]};font-size:0.72rem;'
        f'text-align:center;letter-spacing:0.03em;">'
        f'Snowflake CoCo CLI Hackathon 2026</p>',
        unsafe_allow_html=True,
    )

# ---------------------------------------------------------------------------
# Main content — hero + role selection
# ---------------------------------------------------------------------------

# Hero section
st.markdown(
    f'<div style="text-align:center;padding:2rem 0 1rem 0;">'
    f'<img src="app/static/logo.png" style="width:80px;height:80px;'
    f'object-fit:contain;margin-bottom:0.75rem;" />'
    f'<h1 style="margin:0;font-size:2rem;font-weight:800;'
    f'color:{PALETTE["text_primary"]};letter-spacing:-0.03em;">'
    f'Welcome to TIDE</h1>'
    f'<p style="color:{PALETTE["text_secondary"]};font-size:1rem;'
    f'margin-top:0.5rem;max-width:540px;margin-left:auto;margin-right:auto;'
    f'line-height:1.6;">'
    f'Triage · Investigation · Decision · Execution<br/>'
    f'Select your role to get started.</p>'
    f'</div>',
    unsafe_allow_html=True,
)

st.markdown("")  # spacing

# ---------------------------------------------------------------------------
# Role cards
# ---------------------------------------------------------------------------
col1, col2, col3 = st.columns(3, gap="medium")

ROLE_CARDS = [
    {
        "icon": "🛍️",
        "title": "Customer",
        "desc": "Report a dispute, upload proof, chat with the intake assistant, and track your case in real time.",
        "btn": "Open Customer Portal",
        "key": "btn_customer",
        "page": "pages/1_Customer.py",
    },
    {
        "icon": "✅",
        "title": "Approver",
        "desc": "Review the approval queue, examine evidence bundles, and approve or reject resolution requests.",
        "btn": "Open Approver Dashboard",
        "key": "btn_approver",
        "page": "pages/2_Approver.py",
    },
    {
        "icon": "🛡️",
        "title": "Escalation Agent",
        "desc": "Claim escalated cases, review AI-generated summaries, chat with customers, and resolve manually.",
        "btn": "Open Escalation Console",
        "key": "btn_escalation",
        "page": "pages/3_Escalation.py",
    },
]

for col, card in zip([col1, col2, col3], ROLE_CARDS):
    with col:
        st.markdown(
            f'<div class="tide-card" style="text-align:center;min-height:220px;'
            f'display:flex;flex-direction:column;justify-content:space-between;">'
            f'<div>'
            f'<div style="font-size:2.5rem;margin-bottom:0.75rem;">{card["icon"]}</div>'
            f'<h3 style="margin:0 0 0.5rem 0;">{card["title"]}</h3>'
            f'<p>{card["desc"]}</p>'
            f'</div>'
            f'</div>',
            unsafe_allow_html=True,
        )
        if st.button(card["btn"], key=card["key"], use_container_width=True, type="primary"):
            st.switch_page(card["page"])

# Bottom spacer
st.markdown("")
st.markdown("")
