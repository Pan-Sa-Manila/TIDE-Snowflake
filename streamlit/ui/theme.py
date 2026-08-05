"""TIDE UI Theme — inject_css(), palette, status colors.

This is the SINGLE source of custom CSS for the entire Streamlit app.
No page-local CSS. All design tokens defined here.

Design identity: warm energy and action — brand orange accent on clean
white chrome with generous whitespace. See AGENTS.md §7.3.

Inspired by modern SaaS dashboards (Cloudflare, Linear):
  - White sidebar with orange accent branding
  - Clean white cards with subtle shadows on light gray canvas
  - Orange for CTAs, active states, brand identity
  - Strong typography hierarchy (Inter font)
"""

# ---------------------------------------------------------------------------
# Palette
# ---------------------------------------------------------------------------
PALETTE = {
    # ── Brand ────────────────────────────────────────────────
    "primary":           "#F6821F",   # Warm orange — core brand
    "primary_hover":     "#E5760D",   # Darker orange — hover/active
    "primary_light":     "#FBAD41",   # Lighter orange — gradient end
    "primary_bg":        "#FFF7F0",   # Warm tint — selected states
    "primary_gradient":  "linear-gradient(135deg, #F6821F 0%, #FBAD41 100%)",

    # ── Surfaces ─────────────────────────────────────────────
    "surface":           "#FFFFFF",   # Cards, sidebar, inputs
    "surface_alt":       "#FDF6F0",   # Page background (warm cream)

    # ── Sidebar (white with orange accents) ──────────────────
    "sidebar_bg":        "#FFFFFF",
    "sidebar_text":      "#1A1A2E",   # Dark text on white
    "sidebar_muted":     "#9CA3AF",   # Gray-400 captions
    "sidebar_divider":   "#E5E7EB",   # Gray-200 separators
    "sidebar_hover":     "#FFF7F0",   # Warm tint on button hover

    # ── Borders ──────────────────────────────────────────────
    "border":            "#E5E7EB",   # Gray-200
    "border_focus":      "#F6821F",   # Orange focus ring

    # ── Text ─────────────────────────────────────────────────
    "text_primary":      "#1A1A2E",   # Near-black headings (for cards)
    "text_body":         "#4B5563",   # Gray-600 body (for cards)
    "text_secondary":    "#6B7280",   # Gray-500 secondary (for cards)
    "text_muted":        "#9CA3AF",   # Gray-400 captions (for cards)
    "text_light":        "#FFFFFF",   # White for dark background
    "text_light_body":   "#E2E8F0",   # Slate-200 body for dark background
    "text_light_muted":  "#94A3B8",   # Slate-400 muted for dark background

    # ── Semantic ─────────────────────────────────────────────
    "success":           "#10B981",   # Emerald-500
    "success_bg":        "#ECFDF5",
    "warning":           "#F59E0B",   # Amber-500
    "warning_bg":        "#FFFBEB",
    "error":             "#EF4444",   # Red-500
    "error_bg":          "#FEF2F2",
    "info":              "#3B82F6",   # Blue-500
    "info_bg":           "#EFF6FF",
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
        f"font-size: 0.76rem; "
        f"font-weight: 600; "
        f"letter-spacing: 0.02em; "
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
        bg, fg = "#ECFDF5", "#065F46"  # green
    elif m < 240:
        bg, fg = "#FFFBEB", "#92400E"  # amber
    else:
        bg, fg = "#FEF2F2", "#991B1B"  # red
    return (
        f'<span style="background:{bg};color:{fg};'
        f'padding:3px 10px;border-radius:9999px;'
        f'font-size:0.72rem;font-weight:600;white-space:nowrap;'
        f'display:inline-block;letter-spacing:0.02em;'
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
    """Return HTML for a horizontal pipeline progress tracker."""
    active = _STATUS_STAGE.get(current_status, 0)
    parts = []
    for i, label in enumerate(_PIPELINE_STEPS):
        if i < active:
            # Completed — orange circle with white checkmark
            circle = (
                f'<div style="width:36px;height:36px;border-radius:50%;'
                f'background:{PALETTE["primary"]};display:flex;align-items:center;'
                f'justify-content:center;color:#fff;font-size:0.85rem;font-weight:700;'
                f'box-shadow:0 2px 8px rgba(246,130,31,0.3);">\u2713</div>'
            )
            text_color = PALETTE["primary"]
            text_weight = "700"
        elif i == active:
            # Current — pulsing double ring
            circle = (
                f'<div style="width:36px;height:36px;border-radius:50%;'
                f'background:{PALETTE["primary"]};display:flex;align-items:center;'
                f'justify-content:center;color:#fff;font-size:0.8rem;font-weight:700;'
                f'box-shadow:0 0 0 4px {PALETTE["primary_bg"]}, 0 0 0 6px {PALETTE["primary"]};'
                f'">{i + 1}</div>'
            )
            text_color = PALETTE["primary"]
            text_weight = "700"
        else:
            # Future — gray outlined
            circle = (
                f'<div style="width:36px;height:36px;border-radius:50%;'
                f'border:2px solid {PALETTE["border"]};display:flex;align-items:center;'
                f'justify-content:center;color:{PALETTE["text_muted"]};'
                f'font-size:0.8rem;background:{PALETTE["surface"]};">{i + 1}</div>'
            )
            text_color = PALETTE["text_light_muted"]
            text_weight = "500"

        step_html = (
            f'<div style="display:flex;flex-direction:column;align-items:center;gap:8px;">'
            f"{circle}"
            f'<span style="font-size:0.7rem;font-weight:{text_weight};color:{text_color};'
            f'white-space:nowrap;letter-spacing:0.03em;text-transform:uppercase;">{label}</span>'
            f"</div>"
        )
        parts.append(step_html)

        if i < len(_PIPELINE_STEPS) - 1:
            line_color = PALETTE["primary"] if i < active else PALETTE["border"]
            parts.append(
                f'<div style="flex:1;height:2px;background:{line_color};'
                f'margin-top:18px;min-width:32px;border-radius:1px;"></div>'
            )

    return (
        '<div style="display:flex;align-items:flex-start;gap:0;'
        'padding:1.25rem 0.5rem;overflow-x:auto;">'
        + "".join(parts)
        + "</div>"
    )


# ---------------------------------------------------------------------------
# Sidebar branding (white sidebar, orange accent)
# ---------------------------------------------------------------------------

def sidebar_branding(subtitle: str = ""):
    """Render the sidebar branding block — logo + title + subtitle.

    Call from every page's sidebar, passing the persona name as subtitle.
    Uses a white sidebar with orange brand accent.
    """
    import streamlit as st
    from ui.logo import LOGO_BASE64

    st.markdown(
        '<div style="text-align:center;padding:0.5rem 0 0.25rem 0;">'
        f'<img src="data:image/png;base64,{LOGO_BASE64}" style="width:56px;height:56px;'
        'object-fit:contain;" />'
        '</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        f'<p style="text-align:center;margin:0;padding:0;'
        f'color:{PALETTE["primary"]} !important;font-size:1.5rem;font-weight:800;'
        f'letter-spacing:0.02em;">TIDE</p>',
        unsafe_allow_html=True,
    )
    if subtitle:
        st.markdown(
            f'<p style="text-align:center;margin:2px 0 0 0;'
            f'color:{PALETTE["text_secondary"]} !important;font-size:0.78rem;'
            f'font-weight:500;letter-spacing:0.02em;">{subtitle}</p>',
            unsafe_allow_html=True,
        )
    # Branded gradient divider
    st.markdown(
        f'<div style="height:2px;margin:0.75rem 0;border-radius:1px;'
        f'background:linear-gradient(90deg, transparent, {PALETTE["primary"]}, transparent);'
        f'opacity:0.3;"></div>',
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# inject_css — THE SINGLE SOURCE OF CUSTOM CSS
# ---------------------------------------------------------------------------

def inject_css():
    """Inject global custom CSS into the Streamlit app.

    Call this once at the top of every page. This is the ONLY place custom CSS
    lives — see AGENTS.md §7.2.
    """
    import streamlit as st

    st.markdown(
        f"""
        <style>
        /* ── Font ──────────────────────────────────────────────── */
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

        .stApp {{
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
        }}

        /* ── Sidebar — white with orange accents ───────────────── */
        [data-testid="stSidebar"] {{
            background-color: {PALETTE["sidebar_bg"]} !important;
            border-right: 1px solid {PALETTE["sidebar_divider"]};
        }}

        /* Force sidebar nav links visible (SiS dark theme sets white text) */
        [data-testid="stSidebarNav"] * {{
            color: {PALETTE["text_body"]} !important;
        }}

        [data-testid="stSidebarNav"] [aria-selected="true"],
        [data-testid="stSidebarNav"] [aria-current="page"] {{
            color: {PALETTE["primary"]} !important;
            font-weight: 600 !important;
        }}

        [data-testid="stSidebar"] .stMarkdown p {{
            color: {PALETTE["text_body"]} !important;
            font-size: 0.88rem;
        }}

        [data-testid="stSidebar"] .stCaption,
        [data-testid="stSidebar"] .stCaption p {{
            color: {PALETTE["sidebar_muted"]} !important;
        }}

        [data-testid="stSidebar"] hr {{
            border-color: {PALETTE["sidebar_divider"]} !important;
        }}

        [data-testid="stSidebar"] [data-testid="stMetricValue"],
        [data-testid="stSidebar"] [data-testid="stMetricValue"] * {{
            color: {PALETTE["text_primary"]} !important;
            font-size: 1.5rem !important;
            font-weight: 700 !important;
        }}

        [data-testid="stSidebar"] [data-testid="stMetricLabel"],
        [data-testid="stSidebar"] [data-testid="stMetricLabel"] * {{
            color: {PALETTE["sidebar_muted"]} !important;
            font-size: 0.75rem !important;
            text-transform: uppercase !important;
            letter-spacing: 0.04em !important;
        }}

        [data-testid="stSidebar"] .stButton > button {{
            background: {PALETTE["surface"]} !important;
            color: {PALETTE["primary"]} !important;
            border: 1px solid {PALETTE["sidebar_divider"]} !important;
            border-radius: 10px !important;
            font-weight: 600 !important;
            font-size: 0.85rem !important;
            padding: 0.5rem 1rem !important;
            transition: all 0.2s ease !important;
        }}

        [data-testid="stSidebar"] .stButton > button *,
        [data-testid="stSidebar"] .stButton > button p,
        [data-testid="stSidebar"] .stButton > button span {{
            color: {PALETTE["primary"]} !important;
        }}

        [data-testid="stSidebar"] .stButton > button:hover {{
            background: {PALETTE["primary_bg"]} !important;
            border-color: {PALETTE["primary"]} !important;
        }}

        /* ── Typography (Global Dark Mode Text) ─────────────────── */
        h1 {{
            color: {PALETTE["text_light"]} !important;
            font-weight: 800 !important;
            font-size: 1.75rem !important;
            letter-spacing: -0.025em !important;
        }}

        h2 {{
            color: {PALETTE["text_light"]} !important;
            font-weight: 700 !important;
            font-size: 1.35rem !important;
            letter-spacing: -0.015em !important;
        }}

        h3 {{
            color: {PALETTE["text_light"]} !important;
            font-weight: 600 !important;
            font-size: 1.1rem !important;
        }}

        h4 {{
            color: {PALETTE["text_light_body"]} !important;
            font-weight: 600 !important;
            font-size: 0.95rem !important;
        }}

        p, li {{
            color: {PALETTE["text_light_body"]};
        }}

        /* ── Cards (main content) ───────────────────────────────── */
        .tide-card {{
            background: {PALETTE["surface"]};
            border: 1px solid {PALETTE["border"]};
            border-radius: 14px;
            padding: 1.5rem;
            margin-bottom: 1rem;
            box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04), 0 1px 2px rgba(0, 0, 0, 0.02);
            transition: all 0.25s ease;
        }}

        .tide-card:hover {{
            box-shadow: 0 10px 30px rgba(0, 0, 0, 0.07), 0 4px 10px rgba(0, 0, 0, 0.03);
            transform: translateY(-2px);
            border-color: {PALETTE["primary"]};
        }}

        .tide-card h3 {{
            margin-top: 0 !important;
            font-size: 1.05rem !important;
            font-weight: 700 !important;
            color: {PALETTE["text_primary"]} !important;
        }}

        .tide-card p {{
            color: {PALETTE["text_secondary"]} !important;
            font-size: 0.85rem !important;
            line-height: 1.55 !important;
            margin-bottom: 0 !important;
        }}

        /* ── Queue item cards ───────────────────────────────────── */
        .queue-card {{
            background: {PALETTE["surface"]};
            border: 1px solid {PALETTE["border"]};
            border-left: 3px solid transparent;
            border-radius: 12px;
            padding: 0.85rem 1.1rem;
            margin-bottom: 0.5rem;
            box-shadow: 0 1px 2px rgba(0, 0, 0, 0.03);
            transition: all 0.2s ease;
        }}

        .queue-card p, .queue-card span, .queue-card div {{
            color: {PALETTE["text_primary"]};
        }}

        .queue-card:hover {{
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.06);
            border-color: {PALETTE["border"]};
            border-left-color: {PALETTE["primary"]};
        }}

        .queue-card.selected {{
            border-left-color: {PALETTE["primary"]};
            background: {PALETTE["primary_bg"]};
            box-shadow: 0 2px 8px rgba(246, 130, 31, 0.1);
        }}

        /* ── Buttons ────────────────────────────────────────────── */
        .stButton > button {{
            border-radius: 10px !important;
            font-weight: 600 !important;
            font-size: 0.88rem !important;
            transition: all 0.2s ease !important;
            letter-spacing: 0.01em !important;
        }}

        .stButton > button:hover {{
            transform: translateY(-1px) !important;
        }}

        /* Primary buttons — gradient bg + forced white text */
        .stButton > button[kind="primary"],
        .stButton > button[data-testid="baseButton-primary"],
        .stApp [data-testid="stButton"] > button[kind="primary"] {{
            background: {PALETTE["primary_gradient"]} !important;
            color: #FFFFFF !important;
            border: none !important;
            box-shadow: 0 2px 8px rgba(246, 130, 31, 0.3) !important;
        }}

        /* Catch inner spans/text inside primary buttons */
        .stButton > button[kind="primary"] *,
        .stButton > button[kind="primary"] p,
        .stButton > button[kind="primary"] span,
        .stButton > button[data-testid="baseButton-primary"] * {{
            color: #FFFFFF !important;
        }}

        .stButton > button[kind="primary"]:hover,
        .stButton > button[data-testid="baseButton-primary"]:hover {{
            box-shadow: 0 6px 20px rgba(246, 130, 31, 0.4) !important;
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
            color: {PALETTE["text_light_muted"]};
            border-bottom: 2px solid transparent;
            margin-bottom: -2px;
        }}

        .stTabs [aria-selected="true"] {{
            color: {PALETTE["primary"]} !important;
            border-bottom-color: {PALETTE["primary"]} !important;
        }}

        /* ── Metrics ────────────────────────────────────────────── */
        [data-testid="stMetricValue"] {{
            font-size: 1.6rem !important;
            font-weight: 700 !important;
            color: {PALETTE["text_light"]} !important;
        }}

        [data-testid="stMetricLabel"] {{
            font-size: 0.78rem !important;
            color: {PALETTE["text_light_muted"]} !important;
            font-weight: 500 !important;
            text-transform: uppercase !important;
            letter-spacing: 0.04em !important;
        }}

        /* ── Expander ───────────────────────────────────────────── */
        .streamlit-expanderHeader {{
            font-weight: 600 !important;
            font-size: 0.92rem !important;
            color: {PALETTE["text_light"]} !important;
        }}

        /* ── Inputs ─────────────────────────────────────────────── */
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
            box-shadow: 0 0 0 3px rgba(246, 130, 31, 0.1) !important;
        }}

        /* ── Chat input ─────────────────────────────────────────── */
        [data-testid="stChatInput"] > div {{
            border-radius: 12px !important;
            border-color: {PALETTE["border"]} !important;
        }}

        [data-testid="stChatInput"] > div:focus-within {{
            border-color: {PALETTE["primary"]} !important;
            box-shadow: 0 0 0 3px rgba(246, 130, 31, 0.1) !important;
        }}

        /* ── Dividers ───────────────────────────────────────────── */
        hr {{
            border-color: {PALETTE["border"]} !important;
            opacity: 0.6;
        }}

        /* ── Hide Streamlit chrome ──────────────────────────────── */
        #MainMenu {{visibility: hidden;}}
        footer {{visibility: hidden;}}
        </style>
        """,
        unsafe_allow_html=True,
    )
