"""TIDE UI Theme — inject_css(), palette, status colors.

This is the SINGLE source of custom CSS for the entire Streamlit app.
No page-local CSS. All design tokens defined here.

Design identity: warm energy and action — brand orange accent on clean
neutral chrome with generous whitespace. See AGENTS.md §7.3.

UI Overhaul (Aug 5): Dark sidebar, shadow-based cards, proper typography
hierarchy, orange reserved for accent/CTA only.
"""

# ---------------------------------------------------------------------------
# Palette
# ---------------------------------------------------------------------------
PALETTE = {
    # Brand
    "primary": "#E05D26",           # Warm orange — accent only
    "primary_light": "#F0845A",     # Orange 400 — hover states
    "primary_dark": "#C04A1A",      # Orange 800 — active states
    "primary_bg": "#FFF5F0",        # Warm tint — customer chat bubbles
    "primary_gradient": "linear-gradient(135deg, #E05D26 0%, #F0845A 100%)",

    # Surfaces
    "surface": "#FFFFFF",
    "surface_alt": "#F8FAFC",       # Alternating rows, secondary panels
    "surface_raised": "#FFFFFF",    # Cards — shadow provides depth

    # Sidebar
    "sidebar_bg": "#0F172A",        # Slate 900 — dark sidebar
    "sidebar_text": "#E2E8F0",      # Slate 200 — sidebar body text
    "sidebar_muted": "#64748B",     # Slate 500 — sidebar captions
    "sidebar_divider": "#1E293B",   # Slate 800 — sidebar separators
    "sidebar_hover": "#1E293B",     # Slate 800 — sidebar hover

    # Borders
    "border": "#E2E8F0",            # Slate 200 — subtle borders
    "border_focus": "#E05D26",      # Orange — focus rings

    # Text
    "text_primary": "#0F172A",      # Slate 900 — headings
    "text_body": "#334155",         # Slate 700 — body text
    "text_secondary": "#64748B",    # Slate 500 — secondary info
    "text_muted": "#94A3B8",        # Slate 400 — captions, timestamps

    # Semantic
    "success": "#16A34A",           # Green 600
    "success_bg": "#F0FDF4",
    "warning": "#CA8A04",           # Yellow 600
    "warning_bg": "#FEFCE8",
    "error": "#DC2626",             # Red 600
    "error_bg": "#FEF2F2",
    "info": "#2563EB",              # Blue 600
    "info_bg": "#EFF6FF",
}

# ---------------------------------------------------------------------------
# Status pill colors — text conveyed by pill text, never color alone (§7.3)
# ---------------------------------------------------------------------------
STATUS_COLORS = {
    "pending_triage":              {"bg": "#DBEAFE", "text": "#1E40AF", "label": "Intake"},
    "awaiting_customer_proof":     {"bg": "#FEF3C7", "text": "#92400E", "label": "Proof Needed"},
    "awaiting_customer_decision":  {"bg": "#FEF3C7", "text": "#92400E", "label": "Your Decision"},
    "awaiting_approval":           {"bg": "#E0E7FF", "text": "#3730A3", "label": "Pending Approval"},
    "approved_executing":          {"bg": "#D1FAE5", "text": "#065F46", "label": "Executing"},
    "rejected_human_required":     {"bg": "#FEE2E2", "text": "#991B1B", "label": "Review Required"},
    "escalated_human_required":    {"bg": "#FEE2E2", "text": "#991B1B", "label": "Escalated"},
    "resolved":                    {"bg": "#D1FAE5", "text": "#065F46", "label": "Resolved"},
    "closed":                      {"bg": "#F1F5F9", "text": "#475569", "label": "Closed"},
}


def status_pill_html(status: str) -> str:
    """Return HTML for a status pill badge."""
    colors = STATUS_COLORS.get(status, {"bg": "#F1F5F9", "text": "#475569", "label": status})
    return (
        f'<span style="'
        f"background-color: {colors['bg']}; "
        f"color: {colors['text']}; "
        f"padding: 4px 14px; "
        f"border-radius: 9999px; "
        f"font-size: 0.78rem; "
        f"font-weight: 600; "
        f"letter-spacing: 0.01em; "
        f"white-space: nowrap; "
        f"display: inline-block; "
        f'">{colors["label"]}</span>'
    )


# ---------------------------------------------------------------------------
# Format helpers
# ---------------------------------------------------------------------------

def format_currency(amount) -> str:
    """Format a numeric amount as USD currency string."""
    try:
        return f"${float(amount):,.2f}"
    except (TypeError, ValueError):
        return "\u2014"


def format_age(minutes) -> str:
    """Return a human-readable age string from minutes."""
    try:
        m = int(minutes)
    except (TypeError, ValueError):
        return "\u2014"
    if m < 60:
        return f"{m}m"
    h = m // 60
    rem = m % 60
    if rem:
        return f"{h}h {rem}m"
    return f"{h}h"


def age_bucket_pill(age_minutes) -> str:
    """Return a colored age pill HTML for queue tables."""
    try:
        m = int(age_minutes)
    except (TypeError, ValueError):
        return ""
    label = format_age(m)
    if m < 60:
        bg, fg = "#D1FAE5", "#065F46"  # green
    elif m < 240:
        bg, fg = "#FEF3C7", "#92400E"  # amber
    else:
        bg, fg = "#FEE2E2", "#991B1B"  # red
    return (
        f'<span style="background:{bg};color:{fg};'
        f'padding:3px 10px;border-radius:9999px;'
        f'font-size:0.73rem;font-weight:600;white-space:nowrap;'
        f'display:inline-block;letter-spacing:0.01em;'
        f'">\u23f1 {label}</span>'
    )


def format_datetime(ts) -> str:
    """Format a Snowflake TIMESTAMP_TZ value as a readable string."""
    if ts is None:
        return "\u2014"
    try:
        import datetime
        if isinstance(ts, str):
            dt = datetime.datetime.fromisoformat(ts.replace("Z", "+00:00"))
        elif hasattr(ts, "isoformat"):
            dt = ts
        else:
            return str(ts)
        return dt.strftime("%b %d, %Y %H:%M UTC")
    except Exception:
        return str(ts)


# ---------------------------------------------------------------------------
# Pipeline step tracker
# ---------------------------------------------------------------------------

# Maps each status to a pipeline stage index (0-indexed)
_STATUS_STAGE = {
    "pending_triage":             0,
    "awaiting_customer_proof":    0,
    "awaiting_customer_decision": 1,
    "awaiting_approval":          2,
    "approved_executing":         3,
    "rejected_human_required":    2,
    "escalated_human_required":   2,
    "resolved":                   4,
    "closed":                     4,
}

_PIPELINE_STEPS = ["Intake", "Review", "Decision", "Executing", "Resolved"]


def pipeline_steps_html(current_status: str) -> str:
    """Return HTML for a horizontal pipeline progress tracker.

    Each step is a numbered circle + label. Completed steps show a checkmark
    in brand orange; the current step pulses with a shadow ring; future steps
    are muted. Colour never carries the only meaning -- the label always says
    which stage it is (DETAILS.md §7.3 pill rule).
    """
    active = _STATUS_STAGE.get(current_status, 0)
    parts = []
    for i, label in enumerate(_PIPELINE_STEPS):
        if i < active:
            # Completed step
            circle = (
                f'<div style="width:34px;height:34px;border-radius:50%;'
                f'background:{PALETTE["primary"]};display:flex;align-items:center;'
                f'justify-content:center;color:#fff;font-size:0.85rem;'
                f'box-shadow:0 2px 6px rgba(224,93,38,0.25);">\u2713</div>'
            )
            text_color = PALETTE["primary"]
        elif i == active:
            # Current step — pulsing ring
            circle = (
                f'<div style="width:34px;height:34px;border-radius:50%;'
                f'background:{PALETTE["primary"]};display:flex;align-items:center;'
                f'justify-content:center;color:#fff;font-size:0.8rem;font-weight:700;'
                f'box-shadow:0 0 0 4px {PALETTE["primary_bg"]}, 0 0 0 6px {PALETTE["primary"]};'
                f'">{i + 1}</div>'
            )
            text_color = PALETTE["primary"]
        else:
            # Future step
            circle = (
                f'<div style="width:34px;height:34px;border-radius:50%;'
                f'border:2px solid {PALETTE["border"]};display:flex;align-items:center;'
                f'justify-content:center;color:{PALETTE["text_muted"]};'
                f'font-size:0.8rem;background:{PALETTE["surface_alt"]};">{i + 1}</div>'
            )
            text_color = PALETTE["text_muted"]

        step_html = (
            f'<div style="display:flex;flex-direction:column;align-items:center;gap:8px;">'
            f"{circle}"
            f'<span style="font-size:0.72rem;font-weight:600;color:{text_color};'
            f'white-space:nowrap;letter-spacing:0.02em;text-transform:uppercase;">{label}</span>'
            f"</div>"
        )
        parts.append(step_html)

        if i < len(_PIPELINE_STEPS) - 1:
            line_color = PALETTE["primary"] if i < active else PALETTE["border"]
            line_opacity = "1" if i < active else "0.5"
            parts.append(
                f'<div style="flex:1;height:2px;background:{line_color};'
                f'margin-top:17px;min-width:32px;opacity:{line_opacity};'
                f'border-radius:1px;"></div>'
            )

    return (
        '<div style="display:flex;align-items:flex-start;gap:0;'
        'padding:1.25rem 0.5rem;overflow-x:auto;">'
        + "".join(parts)
        + "</div>"
    )


# ---------------------------------------------------------------------------
# Sidebar logo + branding helper
# ---------------------------------------------------------------------------

def sidebar_branding(subtitle: str = ""):
    """Render the sidebar branding block — logo + title + subtitle.

    Call from every page's sidebar, passing the persona name as subtitle.
    """
    import streamlit as st

    st.markdown(
        '<div style="text-align:center;padding:0.5rem 0 0.25rem 0;">'
        '<img src="app/static/logo.png" style="width:64px;height:64px;'
        'object-fit:contain;margin-bottom:0.25rem;" />'
        '</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<h1 style="text-align:center;margin:0;padding:0;'
        f'color:{PALETTE["surface"]};font-size:1.5rem;font-weight:800;'
        'letter-spacing:0.04em;">TIDE</h1>',
        unsafe_allow_html=True,
    )
    if subtitle:
        st.markdown(
            f'<p style="text-align:center;margin:0;padding:2px 0 0 0;'
            f'color:{PALETTE["sidebar_muted"]};font-size:0.78rem;'
            f'font-weight:500;letter-spacing:0.03em;">{subtitle}</p>',
            unsafe_allow_html=True,
        )
    st.markdown(
        f'<div style="height:1px;background:{PALETTE["sidebar_divider"]};'
        f'margin:1rem 0;"></div>',
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# inject_css — THE SINGLE SOURCE OF CUSTOM CSS
# ---------------------------------------------------------------------------

def inject_css():
    """Inject global custom CSS into the Streamlit app.

    Call this once from Home.py. This is the ONLY place custom CSS lives.
    """
    import streamlit as st

    st.markdown(
        f"""
        <style>
        /* ── Typography — Inter via Google Fonts ───────────────────── */
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

        /* ── Global ─────────────────────────────────────────────── */
        .stApp {{
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
        }}

        /* ── Sidebar — dark slate ──────────────────────────────── */
        [data-testid="stSidebar"] {{
            background-color: {PALETTE["sidebar_bg"]} !important;
            border-right: 1px solid {PALETTE["sidebar_divider"]};
        }}

        [data-testid="stSidebar"] * {{
            color: {PALETTE["sidebar_text"]} !important;
        }}

        [data-testid="stSidebar"] .stMarkdown p {{
            color: {PALETTE["sidebar_text"]} !important;
            font-size: 0.88rem;
        }}

        [data-testid="stSidebar"] .stCaption,
        [data-testid="stSidebar"] .stCaption p {{
            color: {PALETTE["sidebar_muted"]} !important;
        }}

        [data-testid="stSidebar"] hr {{
            border-color: {PALETTE["sidebar_divider"]} !important;
        }}

        [data-testid="stSidebar"] [data-testid="stMetricValue"] {{
            color: {PALETTE["surface"]} !important;
            font-size: 1.5rem !important;
            font-weight: 700 !important;
        }}

        [data-testid="stSidebar"] [data-testid="stMetricLabel"] {{
            color: {PALETTE["sidebar_muted"]} !important;
        }}

        [data-testid="stSidebar"] .stButton > button {{
            background: {PALETTE["sidebar_hover"]} !important;
            color: {PALETTE["sidebar_text"]} !important;
            border: 1px solid {PALETTE["sidebar_divider"]} !important;
            border-radius: 10px !important;
            font-weight: 500 !important;
            font-size: 0.85rem !important;
            padding: 0.5rem 1rem !important;
            transition: all 0.2s ease !important;
        }}

        [data-testid="stSidebar"] .stButton > button:hover {{
            background: {PALETTE["sidebar_bg"]} !important;
            border-color: {PALETTE["primary"]} !important;
            color: {PALETTE["primary_light"]} !important;
        }}

        /* ── Cards ──────────────────────────────────────────────── */
        .tide-card {{
            background: {PALETTE["surface"]};
            border: 1px solid {PALETTE["border"]};
            border-radius: 16px;
            padding: 1.5rem;
            margin-bottom: 1rem;
            box-shadow: 0 1px 3px rgba(0, 0, 0, 0.06), 0 1px 2px rgba(0, 0, 0, 0.04);
            transition: all 0.25s ease;
        }}

        .tide-card:hover {{
            box-shadow: 0 10px 30px rgba(0, 0, 0, 0.08), 0 4px 10px rgba(0, 0, 0, 0.04);
            transform: translateY(-2px);
            border-color: {PALETTE["primary"]};
        }}

        .tide-card h3 {{
            margin-top: 0 !important;
            font-size: 1.1rem !important;
            font-weight: 700 !important;
            color: {PALETTE["text_primary"]} !important;
        }}

        .tide-card p {{
            color: {PALETTE["text_secondary"]} !important;
            font-size: 0.88rem !important;
            line-height: 1.5 !important;
            margin-bottom: 0 !important;
        }}

        /* ── Chat bubbles ───────────────────────────────────────── */
        .chat-customer {{
            background: {PALETTE["primary_bg"]};
            border: 1px solid #FDDCC8;
            border-radius: 18px 18px 4px 18px;
            padding: 0.85rem 1.15rem;
            margin: 0.5rem 0;
            max-width: 80%;
            margin-left: auto;
        }}

        .chat-assistant {{
            background: {PALETTE["surface_alt"]};
            border: 1px solid {PALETTE["border"]};
            border-radius: 18px 18px 18px 4px;
            padding: 0.85rem 1.15rem;
            margin: 0.5rem 0;
            max-width: 80%;
        }}

        /* ── Status pills ───────────────────────────────────────── */
        .status-pill {{
            display: inline-block;
            padding: 4px 14px;
            border-radius: 9999px;
            font-size: 0.78rem;
            font-weight: 600;
            white-space: nowrap;
            letter-spacing: 0.01em;
        }}

        /* ── Buttons — primary gets brand gradient ──────────────── */
        .stButton > button {{
            border-radius: 10px !important;
            font-weight: 600 !important;
            font-size: 0.88rem !important;
            transition: all 0.2s ease !important;
            letter-spacing: 0.01em !important;
        }}

        .stButton > button:hover {{
            transform: translateY(-1px) !important;
            box-shadow: 0 4px 12px rgba(224, 93, 38, 0.2) !important;
        }}

        .stButton > button[kind="primary"] {{
            background: {PALETTE["primary_gradient"]} !important;
            color: #FFFFFF !important;
            border: none !important;
            box-shadow: 0 2px 6px rgba(224, 93, 38, 0.25) !important;
        }}

        .stButton > button[kind="primary"]:hover {{
            box-shadow: 0 6px 20px rgba(224, 93, 38, 0.35) !important;
        }}

        /* ── Typography ─────────────────────────────────────────── */
        h1 {{
            color: {PALETTE["text_primary"]} !important;
            font-weight: 800 !important;
            font-size: 1.75rem !important;
            letter-spacing: -0.02em !important;
        }}

        h2 {{
            color: {PALETTE["text_primary"]} !important;
            font-weight: 700 !important;
            font-size: 1.35rem !important;
            letter-spacing: -0.01em !important;
        }}

        h3 {{
            color: {PALETTE["text_primary"]} !important;
            font-weight: 600 !important;
            font-size: 1.1rem !important;
        }}

        h4 {{
            color: {PALETTE["text_body"]} !important;
            font-weight: 600 !important;
            font-size: 1rem !important;
        }}

        p, li, .stMarkdown {{
            color: {PALETTE["text_body"]};
        }}

        .text-muted {{
            color: {PALETTE["text_muted"]} !important;
            font-size: 0.85rem;
        }}

        /* ── Tabs ───────────────────────────────────────────────── */
        .stTabs [data-baseweb="tab-list"] {{
            gap: 0;
            border-bottom: 2px solid {PALETTE["border"]};
        }}

        .stTabs [data-baseweb="tab"] {{
            padding: 0.75rem 1.25rem;
            font-weight: 600;
            font-size: 0.88rem;
            color: {PALETTE["text_secondary"]};
            border-bottom: 2px solid transparent;
            margin-bottom: -2px;
        }}

        .stTabs [aria-selected="true"] {{
            color: {PALETTE["primary"]} !important;
            border-bottom-color: {PALETTE["primary"]} !important;
        }}

        /* ── Expander ───────────────────────────────────────────── */
        .streamlit-expanderHeader {{
            font-weight: 600 !important;
            font-size: 0.92rem !important;
            color: {PALETTE["text_primary"]} !important;
        }}

        /* ── Metrics ────────────────────────────────────────────── */
        [data-testid="stMetricValue"] {{
            font-size: 1.6rem !important;
            font-weight: 700 !important;
            color: {PALETTE["text_primary"]} !important;
        }}

        [data-testid="stMetricLabel"] {{
            font-size: 0.82rem !important;
            color: {PALETTE["text_secondary"]} !important;
            font-weight: 500 !important;
            text-transform: uppercase !important;
            letter-spacing: 0.04em !important;
        }}

        /* ── Selectbox / inputs ─────────────────────────────────── */
        [data-baseweb="select"] {{
            border-radius: 10px !important;
        }}

        .stTextInput > div > div > input,
        .stTextArea > div > div > textarea {{
            border-radius: 10px !important;
            border-color: {PALETTE["border"]} !important;
            font-size: 0.9rem !important;
        }}

        .stTextInput > div > div > input:focus,
        .stTextArea > div > div > textarea:focus {{
            border-color: {PALETTE["primary"]} !important;
            box-shadow: 0 0 0 3px rgba(224, 93, 38, 0.1) !important;
        }}

        /* ── Divider ────────────────────────────────────────────── */
        hr {{
            border-color: {PALETTE["border"]} !important;
            opacity: 0.6;
        }}

        /* ── Chat input ─────────────────────────────────────────── */
        [data-testid="stChatInput"] > div {{
            border-radius: 12px !important;
            border-color: {PALETTE["border"]} !important;
        }}

        [data-testid="stChatInput"] > div:focus-within {{
            border-color: {PALETTE["primary"]} !important;
            box-shadow: 0 0 0 3px rgba(224, 93, 38, 0.1) !important;
        }}

        /* ── Hide Streamlit default chrome ───────────────────────── */
        #MainMenu {{visibility: hidden;}}
        footer {{visibility: hidden;}}

        /* ── Queue item cards ───────────────────────────────────── */
        .queue-card {{
            background: {PALETTE["surface"]};
            border: 1px solid {PALETTE["border"]};
            border-radius: 12px;
            padding: 0.85rem 1.1rem;
            margin-bottom: 0.5rem;
            box-shadow: 0 1px 2px rgba(0, 0, 0, 0.04);
            transition: all 0.2s ease;
        }}

        .queue-card:hover {{
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.06);
            border-color: {PALETTE["primary"]};
        }}

        .queue-card.selected {{
            border-color: {PALETTE["primary"]};
            background: {PALETTE["primary_bg"]};
            box-shadow: 0 0 0 3px rgba(224, 93, 38, 0.08);
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )
