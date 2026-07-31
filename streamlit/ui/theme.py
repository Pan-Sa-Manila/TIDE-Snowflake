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
        bg, fg = "#d1fae5", "#065f46"  # green
    elif m < 240:
        bg, fg = "#fef3c7", "#92400e"  # amber
    else:
        bg, fg = "#fee2e2", "#991b1b"  # red
    return (
        f'<span style="background:{bg};color:{fg};'
        f'padding:3px 10px;border-radius:9999px;'
        f'font-size:0.75rem;font-weight:600;white-space:nowrap;'
        f'display:inline-block;">\u23f1 {label}</span>'
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
                f'<div style="width:32px;height:32px;border-radius:50%;'
                f'background:{PALETTE["primary"]};display:flex;align-items:center;'
                f'justify-content:center;color:#fff;font-size:0.9rem;">\u2713</div>'
            )
            text_color = PALETTE["primary"]
        elif i == active:
            # Current step
            circle = (
                f'<div style="width:32px;height:32px;border-radius:50%;'
                f'background:{PALETTE["primary"]};display:flex;align-items:center;'
                f'justify-content:center;color:#fff;font-size:0.8rem;font-weight:700;'
                f'box-shadow:0 0 0 4px {PALETTE["primary_bg"]};">{i + 1}</div>'
            )
            text_color = PALETTE["primary"]
        else:
            # Future step
            circle = (
                f'<div style="width:32px;height:32px;border-radius:50%;'
                f'border:2px solid {PALETTE["border"]};display:flex;align-items:center;'
                f'justify-content:center;color:{PALETTE["text_muted"]};'
                f'font-size:0.8rem;">{i + 1}</div>'
            )
            text_color = PALETTE["text_muted"]

        step_html = (
            f'<div style="display:flex;flex-direction:column;align-items:center;gap:6px;">'
            f"{circle}"
            f'<span style="font-size:0.72rem;font-weight:600;color:{text_color};'
            f'white-space:nowrap;">{label}</span>'
            f"</div>"
        )
        parts.append(step_html)

        if i < len(_PIPELINE_STEPS) - 1:
            line_color = PALETTE["primary"] if i < active else PALETTE["border"]
            parts.append(
                f'<div style="flex:1;height:2px;background:{line_color};'
                f'margin-top:16px;min-width:24px;"></div>'
            )

    return (
        '<div style="display:flex;align-items:flex-start;gap:0;'
        'padding:1rem 0.5rem;overflow-x:auto;">'
        + "".join(parts)
        + "</div>"
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
