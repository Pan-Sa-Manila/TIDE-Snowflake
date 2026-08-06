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
        /* ── Chat surface ──────────────────────────────────────────
           The conversation is the page, not a section of it. A single quiet
           surface behind the bubbles does more to say "this is a chat" than a
           heading does, and it costs no vertical space. */
        .tide-chat {{
            background: {PALETTE["surface_alt"]};
            border: 1px solid {PALETTE["border"]};
            border-radius: 16px;
            padding: 0.85rem 1rem 0.35rem 1rem;
            margin-bottom: 0.5rem;
        }}

        /* The composer should read as one control with the surface above it,
           not as a form that happens to sit nearby. */
        [data-testid="stForm"] {{
            border: 1px solid {PALETTE["border"]} !important;
            border-radius: 14px !important;
            padding: 0.6rem 0.75rem 0.4rem 0.75rem !important;
            background: {PALETTE["surface"]} !important;
        }}

        [data-testid="stForm"] textarea {{
            border: none !important;
            box-shadow: none !important;
            background: transparent !important;
            resize: none !important;
            font-size: 0.92rem !important;
        }}

        [data-testid="stForm"] textarea:focus {{
            outline: none !important;
            box-shadow: none !important;
        }}

        /* ── Action Required panel ─────────────────────────────────
           Streamlit 1.13 has no st.dialog, and widgets cannot live inside
           injected HTML — so a real centred modal with working buttons is not
           available. This is the honest alternative: a full-width card with an
           accent edge, directly above the composer, impossible to scroll past.

           It animates once on appearance because it is genuinely new and rare
           (a decision landing), which is exactly the frequency where motion
           earns its place. */
        @keyframes tide-action-in {{
            from {{ opacity: 0; transform: translateY(6px); }}
            to   {{ opacity: 1; transform: none; }}
        }}

        .tide-action {{
            border: 1px solid {PALETTE["warning"]};
            border-left: 4px solid {PALETTE["warning"]};
            background: {PALETTE["warning_bg"]};
            border-radius: 12px;
            padding: 1.1rem 1.25rem;
            margin: 0.75rem 0 0.25rem 0;
            animation: tide-action-in 240ms var(--tide-ease-out) both;
        }}

        .tide-action__title {{
            font-weight: 700;
            font-size: 0.95rem;
            color: {PALETTE["text_primary"]};
            margin: 0 0 0.4rem 0;
            letter-spacing: -0.01em;
        }}

        .tide-action__body {{
            color: {PALETTE["text_body"]};
            font-size: 0.9rem;
            line-height: 1.6;
            margin: 0;
        }}

        /* ── Chat bubbles ──────────────────────────────────────────
           Only the newest message animates. The history re-renders on every
           rerun, so animating all of it would replay the whole transcript
           several times a minute — motion the user would see hundreds of times
           and quickly resent. The newest bubble is the only one that is
           genuinely new information.

           Entry is scale(0.98) + a few pixels of travel, never scale(0):
           nothing in the real world appears out of nothing, and starting from
           zero reads as a pop rather than an arrival. */
        @keyframes tide-bubble-in {{
            from {{ opacity: 0; transform: translateY(4px) scale(0.98); }}
            to   {{ opacity: 1; transform: none; }}
        }}

        .tide-bubble {{
            padding: 10px 14px;
            margin: 6px 0;
            line-height: 1.5;
            max-width: 80%;
            word-wrap: break-word;
        }}

        .tide-bubble--new {{
            animation: tide-bubble-in 200ms var(--tide-ease-out) both;
        }}

        .tide-bubble--customer {{
            background: {PALETTE["primary"]};
            color: #fff;
            border-radius: 14px 14px 3px 14px;
            margin-left: auto;
            text-align: right;
        }}

        .tide-bubble--assistant {{
            background: {PALETTE["surface"]};
            color: {PALETTE["text_primary"]};
            border: 1px solid {PALETTE["border"]};
            border-radius: 14px 14px 14px 3px;
            margin-right: auto;
        }}

        /* An escalation agent is a person, not the assistant. Different accent
           so the customer can tell at a glance who is talking. */
        .tide-bubble--agent {{
            background: {PALETTE["info_bg"]};
            color: {PALETTE["text_primary"]};
            border: 1px solid {PALETTE["info"]};
            border-radius: 14px 14px 14px 3px;
            margin-right: auto;
        }}

        .tide-bubble__meta {{
            display: block;
            margin-top: 4px;
            font-size: 0.7rem;
            opacity: 0.65;
        }}

        /* ── Motion tokens ─────────────────────────────────────────
           The built-in CSS easings are too weak to read as intentional.
           These are stronger variants: ease-out for anything entering or
           responding to a press (starts fast, feels immediate), ease-in-out
           for movement across the screen. `ease-in` is deliberately absent —
           it delays the first frame, which is exactly when the user is
           looking, and makes the whole interface feel sluggish.

           Durations stay under 300ms. Only transform and opacity are animated
           where possible; both skip layout and paint and run on the GPU. */
        :root {{
            --tide-ease-out: cubic-bezier(0.23, 1, 0.32, 1);
            --tide-ease-in-out: cubic-bezier(0.77, 0, 0.175, 1);
        }}

        /* Press feedback. A button that does not move on press reads as
           unresponsive even when it is doing the work. Subtle on purpose —
           scale() also scales the label, so anything lower starts to look
           like a glitch rather than a press. */
        .stButton > button:active {{
            transform: scale(0.97) !important;
            transition-duration: 100ms !important;
        }}

        [data-testid="stSidebar"] button:active {{
            transform: scale(0.97) !important;
            transition-duration: 100ms !important;
        }}

        /* Hover effects only where a real pointer exists. On touch, :hover
           latches after a tap and leaves the element stuck in its hover state. */
        @media (hover: none) {{
            .tide-card:hover, .queue-card:hover {{
                transform: none;
            }}
        }}

        /* Reduced motion means less movement, not none: opacity and colour
           still carry meaning, so they stay. */
        @media (prefers-reduced-motion: reduce) {{
            *, *::before, *::after {{
                animation-duration: 0.01ms !important;
                animation-iteration-count: 1 !important;
                transition-duration: 0.01ms !important;
                scroll-behavior: auto !important;
            }}
        }}

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

        [data-testid="stSidebar"] button,
        [data-testid="stSidebar"] [data-testid="stButton"] > button,
        [data-testid="stSidebar"] .stButton > button {{
            background: {PALETTE["surface"]} !important;
            color: {PALETTE["primary"]} !important;
            border: 1px solid {PALETTE["sidebar_divider"]} !important;
            border-radius: 10px !important;
            font-weight: 600 !important;
            font-size: 0.85rem !important;
            padding: 0.5rem 1rem !important;
            transition: background-color 160ms var(--tide-ease-out),
                        color 160ms var(--tide-ease-out),
                        transform 160ms var(--tide-ease-out) !important;
        }}

        [data-testid="stSidebar"] button *,
        [data-testid="stSidebar"] button p,
        [data-testid="stSidebar"] button span {{
            color: {PALETTE["primary"]} !important;
        }}

        [data-testid="stSidebar"] button:hover {{
            background: {PALETTE["primary_bg"]} !important;
            border-color: {PALETTE["primary"]} !important;
        }}

        /* Force alert texts (like st.info) in the sidebar to be dark */
        [data-testid="stSidebar"] [data-testid="stAlert"] * {{
            color: {PALETTE["sidebar_text"]} !important;
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
            transition: box-shadow 220ms var(--tide-ease-out),
                        transform 220ms var(--tide-ease-out),
                        border-color 220ms var(--tide-ease-out);
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
            transition: box-shadow 180ms var(--tide-ease-out),
                        transform 180ms var(--tide-ease-out),
                        border-color 180ms var(--tide-ease-out);
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
            transition: background-color 160ms var(--tide-ease-out),
                        box-shadow 160ms var(--tide-ease-out),
                        transform 160ms var(--tide-ease-out) !important;
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


# ---------------------------------------------------------------------------
# Flash messages
#
# Every action in this app calls st.experimental_rerun() straight after doing
# its work, which throws away anything written by st.success() a line earlier.
# That is why approving a $180 refund appeared to do nothing at all: the money
# moved, the queue emptied, and the approver was told none of it.
#
# flash() queues the message; render_flash() drains it on the next run. Call
# render_flash() once per page, right after inject_css().
# ---------------------------------------------------------------------------

def flash(message: str, kind: str = "success"):
    """Queue a message to show after the next rerun. kind: success|info|warning|error."""
    import streamlit as st  # imported per-function, matching this module

    st.session_state.setdefault("_flash", []).append((kind, message))


def render_flash():
    """Draw and clear any queued messages. Safe to call when none are pending."""
    import streamlit as st

    for kind, message in st.session_state.pop("_flash", []):
        {
            "success": st.success,
            "info": st.info,
            "warning": st.warning,
            "error": st.error,
        }.get(kind, st.info)(message)


# ---------------------------------------------------------------------------
# Chat bubbles
# ---------------------------------------------------------------------------

_BUBBLE_ICON = {"assistant": "🤖", "agent": "🛡️", "system": "ℹ️"}


def chat_bubble_html(sender: str, content: str, ts: str, is_latest: bool = False) -> str:
    """One chat bubble.

    `is_latest` animates the entry. Pass it only for the most recent message:
    the transcript re-renders on every rerun, so animating the whole history
    replays it constantly. See the frequency note in the CSS.

    Shared by the customer portal and the escalation console so the two cannot
    drift apart — they previously carried separate copies of this markup with
    hardcoded colours.
    """
    kind = "customer" if sender == "customer" else ("agent" if sender == "agent" else "assistant")
    new = " tide-bubble--new" if is_latest else ""
    prefix = "" if kind == "customer" else f'{_BUBBLE_ICON.get(sender, "🤖")} '
    safe = (content or "").replace("<", "&lt;").replace(">", "&gt;")
    return (
        f'<div class="tide-bubble tide-bubble--{kind}{new}">'
        f'{prefix}{safe}'
        f'<span class="tide-bubble__meta">{ts}</span>'
        f'</div>'
    )


def action_panel_html(title: str, body: str) -> str:
    """The Action Required card.

    Streamlit 1.13 has no st.dialog and widgets cannot be placed inside
    injected HTML, so this renders the *card* and the caller places real
    Streamlit buttons immediately beneath it. Less pretty than a true modal,
    and it cannot be dismissed by clicking away — but it always works, and it
    survives a Streamlit upgrade.
    """
    safe = (body or "").replace("<", "&lt;").replace(">", "&gt;")
    return (
        f'<div class="tide-action">'
        f'<p class="tide-action__title">{title}</p>'
        f'<p class="tide-action__body">{safe}</p>'
        f'</div>'
    )
