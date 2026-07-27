"""TIDE UI Theme — inject_css(), palette, status colors.

This is the SINGLE source of custom CSS for the entire Streamlit app.
No page-local CSS. All design tokens defined here.

Design identity: warm energy and action — brand orange, generous whitespace.
See AGENTS.md §7.3.
"""

# ---------------------------------------------------------------------------
# Palette
# ---------------------------------------------------------------------------
PALETTE = {
    "primary": "#D4581A",          # Orange 600
    "primary_light": "#E8862E",    # Orange 400
    "primary_dark": "#B04614",     # Orange 800
    "primary_bg": "#FAE8DC",       # Orange 100
    "surface": "#FFFFFF",
    "surface_alt": "#F9F9F9",
    "border": "#E0E0E0",
    "border_focus": "#D4581A",
    "text_primary": "#111111",
    "text_secondary": "#444444",
    "text_muted": "#888888",
    "success": "#3B6D11",
    "warning": "#BA7517",
    "error": "#A32D2D",
    "info": "#185FA5",
}

# ---------------------------------------------------------------------------
# Status pill colors — text conveyed by pill text, never color alone (§7.3)
# ---------------------------------------------------------------------------
STATUS_COLORS = {
    "pending_triage":              {"bg": "#dbeafe", "text": "#1e40af", "label": "Intake"},
    "awaiting_customer_proof":     {"bg": "#fef3c7", "text": "#92400e", "label": "Proof Needed"},
    "awaiting_customer_decision":  {"bg": "#fef3c7", "text": "#92400e", "label": "Your Decision"},
    "awaiting_approval":           {"bg": "#e0e7ff", "text": "#3730a3", "label": "Pending Approval"},
    "approved_executing":          {"bg": "#d1fae5", "text": "#065f46", "label": "Executing"},
    "rejected_human_required":     {"bg": "#fee2e2", "text": "#991b1b", "label": "Review Required"},
    "escalated_human_required":    {"bg": "#fee2e2", "text": "#991b1b", "label": "Escalated"},
    "resolved":                    {"bg": "#d1fae5", "text": "#065f46", "label": "Resolved"},
    "closed":                      {"bg": "#f1f5f9", "text": "#475569", "label": "Closed"},
}


def status_pill_html(status: str) -> str:
    """Return HTML for a status pill badge."""
    colors = STATUS_COLORS.get(status, {"bg": "#f1f5f9", "text": "#475569", "label": status})
    return (
        f'<span style="'
        f"background-color: {colors['bg']}; "
        f"color: {colors['text']}; "
        f"padding: 4px 12px; "
        f"border-radius: 9999px; "
        f"font-size: 0.8rem; "
        f"font-weight: 600; "
        f"white-space: nowrap; "
        f"display: inline-block; "
        f'">{colors["label"]}</span>'
    )


def inject_css():
    """Inject global custom CSS into the Streamlit app.

    Call this once from Home.py. This is the ONLY place custom CSS lives.
    """
    import streamlit as st

    st.markdown(
        f"""
        <style>
        /* ── Global ─────────────────────────────────────────────── */
        .stApp {{
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
        }}

        /* ── Sidebar ────────────────────────────────────────────── */
        [data-testid="stSidebar"] {{
            background-color: {PALETTE["primary_bg"]};
            border-right: 1px solid {PALETTE["border"]};
        }}

        [data-testid="stSidebar"] .stMarkdown h1 {{
            color: {PALETTE["primary_dark"]};
            font-size: 1.2rem;
            font-weight: 700;
        }}

        /* ── Cards ──────────────────────────────────────────────── */
        .tide-card {{
            background: {PALETTE["surface"]};
            border: 1px solid {PALETTE["border"]};
            border-radius: 12px;
            padding: 1.25rem;
            margin-bottom: 1rem;
            transition: box-shadow 0.2s ease;
        }}

        .tide-card:hover {{
            box-shadow: 0 4px 12px rgba(212, 88, 26, 0.08);
        }}

        /* ── Chat bubbles ───────────────────────────────────────── */
        .chat-customer {{
            background: {PALETTE["primary_bg"]};
            border: 1px solid {PALETTE["border"]};
            border-radius: 16px 16px 4px 16px;
            padding: 0.75rem 1rem;
            margin: 0.5rem 0;
            max-width: 80%;
            margin-left: auto;
        }}

        .chat-assistant {{
            background: {PALETTE["surface"]};
            border: 1px solid {PALETTE["border"]};
            border-radius: 16px 16px 16px 4px;
            padding: 0.75rem 1rem;
            margin: 0.5rem 0;
            max-width: 80%;
        }}

        /* ── Status pills ───────────────────────────────────────── */
        .status-pill {{
            display: inline-block;
            padding: 4px 12px;
            border-radius: 9999px;
            font-size: 0.8rem;
            font-weight: 600;
            white-space: nowrap;
        }}

        /* ── Buttons ────────────────────────────────────────────── */
        .stButton > button {{
            border-radius: 8px;
            font-weight: 600;
            transition: all 0.2s ease;
        }}

        .stButton > button:hover {{
            transform: translateY(-1px);
            box-shadow: 0 4px 8px rgba(212, 88, 26, 0.15);
        }}

        /* ── Typography ─────────────────────────────────────────── */
        h1 {{
            color: {PALETTE["text_primary"]};
            font-weight: 700;
        }}

        h2, h3 {{
            color: {PALETTE["text_primary"]};
            font-weight: 600;
        }}

        .text-muted {{
            color: {PALETTE["text_muted"]};
            font-size: 0.85rem;
        }}

        /* ── Hide Streamlit default chrome ───────────────────────── */
        #MainMenu {{visibility: hidden;}}
        footer {{visibility: hidden;}}
        </style>
        """,
        unsafe_allow_html=True,
    )
