"""TIDE — Home Page

Landing page with role routing. Sets up the global theme
and navigates users to their persona-specific page.
"""

import streamlit as st
from ui.theme import inject_css, sidebar_branding, PALETTE
from ui.logo import LOGO_BASE64

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
        f'<p style="color:{PALETTE["text_secondary"]};font-size:0.85rem;'
        f'line-height:1.6;">'
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
        f'<p style="color:{PALETTE["text_muted"]};font-size:0.72rem;'
        f'text-align:center;letter-spacing:0.03em;">'
        f'Snowflake CoCo CLI Hackathon 2026</p>',
        unsafe_allow_html=True,
    )

# ---------------------------------------------------------------------------
# Main content — hero + role selection
# ---------------------------------------------------------------------------

# Hero section
st.markdown(
    f'<div style="text-align:center;padding:2.5rem 0 1.5rem 0;">'
    f'<img src="data:image/png;base64,{LOGO_BASE64}" style="width:72px;height:72px;'
    f'object-fit:contain;margin-bottom:0.5rem;" />'
    f'<h1 style="margin:0;font-size:2.2rem;font-weight:800;'
    f'color:{PALETTE["text_light"]};letter-spacing:-0.03em;">'
    f'Welcome to TIDE</h1>'
    f'<p style="color:{PALETTE["text_light_body"]};font-size:0.95rem;'
    f'margin-top:0.5rem;max-width:480px;margin-left:auto;margin-right:auto;'
    f'line-height:1.6;">'
    f'Triage \u00b7 Investigation \u00b7 Decision \u00b7 Execution<br/>'
    f'<span style="color:{PALETTE["text_light_muted"]};">Select your role in the sidebar to get started.</span></p>'
    f'</div>',
    unsafe_allow_html=True,
)

st.markdown("")

# ---------------------------------------------------------------------------
# Role cards — icon in orange gradient square, title, description
# ---------------------------------------------------------------------------
col1, col2, col3 = st.columns(3, gap="medium")

ROLE_CARDS = [
    {
        "icon": "\U0001f6cd\ufe0f",
        "title": "Customer",
        "desc": "Report a dispute, upload proof, chat with the intake assistant, and track your case in real time.",
        "btn": "Open Customer Portal",
        "key": "btn_customer",
        "page": "pages/1_Customer.py",
    },
    {
        "icon": "\u2705",
        "title": "Approver",
        "desc": "Review the approval queue, examine evidence bundles, and approve or reject resolution requests.",
        "btn": "Open Approver Dashboard",
        "key": "btn_approver",
        "page": "pages/2_Approver.py",
    },
    {
        "icon": "\U0001f6e1\ufe0f",
        "title": "Escalation Agent",
        "desc": "Claim escalated cases, review AI summaries, chat with customers, and resolve manually.",
        "btn": "Open Escalation Console",
        "key": "btn_escalation",
        "page": "pages/3_Escalation.py",
    },
]

for col, card in zip([col1, col2, col3], ROLE_CARDS):
    with col:
        st.markdown(
            f'<div class="tide-card" style="text-align:center;min-height:240px;'
            f'display:flex;flex-direction:column;justify-content:space-between;'
            f'padding:1.75rem 1.25rem;">'
            f'<div>'
            # Icon in rounded orange gradient square
            f'<div style="width:52px;height:52px;border-radius:14px;'
            f'background:{PALETTE["primary_gradient"]};'
            f'display:inline-flex;align-items:center;justify-content:center;'
            f'margin-bottom:1rem;box-shadow:0 4px 12px rgba(246,130,31,0.25);">'
            f'<span style="font-size:1.4rem;line-height:1;">{card["icon"]}</span></div>'
            f'<h3 style="margin:0 0 0.5rem 0;font-size:1.1rem !important;">{card["title"]}</h3>'
            f'<p style="margin:0;">{card["desc"]}</p>'
            f'</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

# Footer spacer
st.markdown("")
st.markdown("")
