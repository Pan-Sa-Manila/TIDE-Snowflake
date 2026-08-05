"""TIDE — Customer Portal (1_Customer.py)

Customer persona: chat-based dispute intake, proof upload,
status tracker, and resolution updates.

Layout: Single centered column (~760px). Chat + composer + status tracker.
See AGENTS.md §7.1, DETAILS.md §4, §15 F1.
"""

from __future__ import annotations

import streamlit as st
from ui.theme import (
    inject_css,
    sidebar_branding,
    status_pill_html,
    pipeline_steps_html,
    format_currency,
    format_datetime,
    PALETTE,
)
from ui.db import (
    run_sql,
    run_sql_first,
    call_proc,
    fetch_constants,
    get_current_user,
    get_session,
)

st.set_page_config(
    page_title="TIDE — Customer",
    page_icon="🛍️",
    layout="centered",
)

inject_css()

# ---------------------------------------------------------------------------
# Subtype metadata (DETAILS.md §7.1)
# ---------------------------------------------------------------------------
SUBTYPES = {
    "duplicate_charge":   {"label": "Duplicate Charge",         "type": "refund",    "proof": False, "resolutions": ["refund"]},
    "not_as_described":   {"label": "Not As Described",         "type": "refund",    "proof": True,  "resolutions": ["refund", "replacement"]},
    "damaged_goods":      {"label": "Damaged Goods",            "type": "refund",    "proof": True,  "resolutions": ["refund", "replacement"]},
    "wrong_item":         {"label": "Wrong Item Received",      "type": "refund",    "proof": True,  "resolutions": ["refund", "replacement"]},
    "partial_fulfillment":{"label": "Partial Fulfillment",      "type": "refund",    "proof": True,  "resolutions": ["refund"]},
    "return_request":     {"label": "Return Request",           "type": "refund",    "proof": False, "resolutions": ["return"]},
    "changed_mind":       {"label": "Changed My Mind",          "type": "refund",    "proof": False, "resolutions": ["return"]},
    "other":              {"label": "Other Issue",              "type": "refund",    "proof": False, "resolutions": ["refund"]},
    "non_receipt":        {"label": "Never Received",           "type": "delivery",  "proof": False, "resolutions": ["refund", "replacement"]},
    "delayed":            {"label": "Delivery Delayed",         "type": "delivery",  "proof": False, "resolutions": ["refund"]},
    "exception":          {"label": "Delivery Exception",       "type": "delivery",  "proof": False, "resolutions": ["refund"]},
    "lost":               {"label": "Package Lost",             "type": "delivery",  "proof": False, "resolutions": ["refund", "replacement"]},
}

RESOLUTION_LABELS = {
    "refund": "Refund to original payment method",
    "replacement": "Send a replacement",
    "return": "Return for refund",
}

# ---------------------------------------------------------------------------
# Session state defaults
# ---------------------------------------------------------------------------
if "selected_order_id" not in st.session_state:
    st.session_state.selected_order_id = None
if "selected_case_id" not in st.session_state:
    st.session_state.selected_case_id = None
if "selected_subtype" not in st.session_state:
    st.session_state.selected_subtype = None

# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
with st.sidebar:
    sidebar_branding("Customer Portal")

    username = get_current_user()
    st.markdown(
        f'<p style="color:{PALETTE["sidebar_muted"]} !important;font-size:0.82rem;">'
        f'Signed in as</p>'
        f'<p style="color:{PALETTE["sidebar_text"]} !important;font-weight:600;'
        f'font-size:0.92rem;margin-top:-0.5rem;">{username}</p>',
        unsafe_allow_html=True,
    )

    st.markdown(
        f'<div style="height:1px;background:{PALETTE["sidebar_divider"]};'
        f'margin:1rem 0;"></div>',
        unsafe_allow_html=True,
    )

    if st.button("← Back to Home", use_container_width=True):
        try:
            st.switch_page("Home.py")
        except AttributeError:
            st.info("👉 Click **Home** in the sidebar to navigate.")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_orders() -> list[dict]:
    return run_sql(
        # V_MY_ORDERS, not RETAIL.ORDERS: ARCHITECTURE.md §4 gives the customer
        # role own-case views and no base-table grant. The view is secure and
        # already filters on CURRENT_USER(), so it exposes no customer_id column
        # and needs no predicate — the filter cannot be forgotten at a call site.
        """
        SELECT order_id, status, total_amount, shipping_fee,
               placed_at, fulfilled_at, delivered_at,
               item_count, item_summary
        FROM TIDE.TRIAGE.V_MY_ORDERS
        ORDER BY placed_at DESC
        """,
        [],
        log_component="1_Customer.load_orders",
    )


def load_open_case(order_id: str) -> dict | None:
    return run_sql_first(
        """
        SELECT case_id, reference_number, dispute_subtype,
               current_status, proof_required, eligible_amount, resolution_type,
               created_at, status_changed_at
        FROM TIDE.TRIAGE.V_CASE_CURRENT
        WHERE order_id = ?
          AND customer_id = ?
          AND current_status NOT IN ('closed', 'resolved')
        LIMIT 1
        """,
        [order_id, username],
        log_component="1_Customer.load_open_case",
    )


def load_case_messages(case_id: str) -> list[dict]:
    return run_sql(
        """
        SELECT sender_type, sender_id, content, metadata, created_at
        FROM TIDE.TRIAGE.CHAT
        WHERE case_id = ?
        ORDER BY created_at ASC
        """,
        [case_id],
        log_component="1_Customer.load_messages",
        case_id=case_id,
    )


def load_proof_files(case_id: str) -> list[dict]:
    return run_sql(
        """
        SELECT proof_id, relative_path, content_type, byte_size,
               analysis_status, uploaded_at
        FROM TIDE.INVESTIGATION.PROOF_FILES
        WHERE case_id = ?
        ORDER BY uploaded_at ASC
        """,
        [case_id],
        log_component="1_Customer.load_proofs",
        case_id=case_id,
    )


def load_case_report(case_id: str) -> dict | None:
    return run_sql_first(
        """
        SELECT outcome_summary, resolution_path, rules_applied,
               policies_cited, timeline, generated_at
        FROM TIDE.EXECUTION.CASE_REPORTS
        WHERE case_id = ?
        """,
        [case_id],
        log_component="1_Customer.load_report",
        case_id=case_id,
    )


def send_message(case_id: str, message: str) -> dict | None:
    return call_proc(
        "TIDE.TRIAGE.INTAKE_TURN",
        [case_id, message],
        log_component="INTAKE_TURN",
        case_id=case_id,
    )


def open_case(order_id: str, subtype: str, resolution: str) -> dict | None:
    return call_proc(
        "TIDE.TRIAGE.OPEN_CASE",
        [order_id, subtype, resolution],
        log_component="OPEN_CASE",
    )


def appeal_case(case_id: str) -> dict | None:
    return call_proc(
        "TIDE.TRIAGE.APPEAL_CASE",
        [case_id],
        log_component="APPEAL_CASE",
        case_id=case_id,
    )


def close_case(case_id: str) -> dict | None:
    return call_proc(
        "TIDE.TRIAGE.CLOSE_CASE",
        [case_id, "customer"],
        log_component="CLOSE_CASE",
        case_id=case_id,
    )


# ---------------------------------------------------------------------------
# Page header
# ---------------------------------------------------------------------------
st.markdown("## 🛍️ Customer Portal")
st.markdown("Report an order dispute, upload proof, and track your case.")
st.divider()

# ---------------------------------------------------------------------------
# Step 1: Order Selector
# ---------------------------------------------------------------------------
st.markdown("### 1. Select an Order")
orders = load_orders()

if not orders:
    st.info(
        "📦 No orders found for your account. "
        "If you believe this is an error, please contact support."
    )
    st.stop()

# Build display labels
order_opts = {
    row["ORDER_ID"]: (
        f"Order {row['ORDER_ID'][:8]}… — "
        f"{format_currency(row['TOTAL_AMOUNT'])} — "
        f"Status: {row['STATUS']} — "
        f"Placed {format_datetime(row['PLACED_AT'])}"
    )
    for row in orders
}

selected_label = st.selectbox(
    "Choose an order",
    options=list(order_opts.values()),
    key="order_selector",
)
# Reverse-map to get the order_id
selected_order_id = next(
    oid for oid, lbl in order_opts.items() if lbl == selected_label
)
st.session_state.selected_order_id = selected_order_id

# ---------------------------------------------------------------------------
# Check for existing open case on this order
# ---------------------------------------------------------------------------
open_case_row = load_open_case(selected_order_id)

if open_case_row:
    case_id = open_case_row["CASE_ID"]
    st.session_state.selected_case_id = case_id
else:
    # -----------------------------------------------------------------------
    # Step 2: Open a new dispute
    # -----------------------------------------------------------------------
    st.divider()
    st.markdown("### 2. Open a Dispute")

    subtype_keys = list(SUBTYPES.keys())
    subtype_labels = [SUBTYPES[k]["label"] for k in subtype_keys]

    selected_subtype_label = st.selectbox(
        "What is the issue?",
        options=subtype_labels,
        key="subtype_selector",
    )
    selected_subtype = subtype_keys[subtype_labels.index(selected_subtype_label)]
    st.session_state.selected_subtype = selected_subtype
    meta = SUBTYPES[selected_subtype]

    if meta["proof"]:
        st.info("📷 This dispute type will require a photo as proof. You'll be prompted to upload it.")

    # Resolution preference — constrained per subtype
    resolution_opts = meta["resolutions"]
    resolution_labels = [RESOLUTION_LABELS[r] for r in resolution_opts]
    selected_resolution_label = st.selectbox(
        "Preferred resolution",
        options=resolution_labels,
        key="resolution_selector",
    )
    selected_resolution = resolution_opts[resolution_labels.index(selected_resolution_label)]

    if st.button("🚀 Start Dispute", key="btn_open_case", use_container_width=True, type="primary"):
        with st.spinner("Opening your case…"):
            result = open_case(selected_order_id, selected_subtype, selected_resolution)
        if result and result.get("case_id"):
            st.session_state.selected_case_id = result["case_id"]
            st.success("✅ Case opened. The intake assistant will guide you.")
            st.rerun()
        else:
            msg = (result or {}).get("error", "Unknown error. Please try again.")
            st.error(f"⚠️ Could not open case: {msg}")
    st.stop()

# ---------------------------------------------------------------------------
# Active case view
# ---------------------------------------------------------------------------
case_id = st.session_state.selected_case_id
case = run_sql_first(
    """
    SELECT case_id, reference_number, dispute_subtype, dispute_type,
           resolution_preference, current_status, proof_required,
           eligible_amount, resolution_type, created_at, status_changed_at,
           path_id, assigned_to, closed_by, close_reason, closed_at
    FROM TIDE.TRIAGE.V_CASE_CURRENT
    WHERE case_id = ?
      AND customer_id = ?
    """,
    [case_id, username],
    log_component="1_Customer.load_case",
    case_id=case_id,
)

if not case:
    st.warning("Case not found or access denied.")
    st.stop()

current_status = case.get("CURRENT_STATUS", "pending_triage")
proof_required = case.get("PROOF_REQUIRED", False)
subtype_key = case.get("DISPUTE_SUBTYPE", "")
subtype_meta = SUBTYPES.get(subtype_key, {})

# ---------------------------------------------------------------------------
# Case header
# ---------------------------------------------------------------------------
col_ref, col_status = st.columns([2, 1])
with col_ref:
    st.markdown(f"### Case {case.get('REFERENCE_NUMBER', '—')}")
    st.caption(
        f"**Issue:** {SUBTYPES.get(subtype_key, {}).get('label', subtype_key)}  |  "
        f"**Opened:** {format_datetime(case.get('CREATED_AT'))}"
    )
with col_status:
    st.markdown(
        status_pill_html(current_status),
        unsafe_allow_html=True,
    )

# ---------------------------------------------------------------------------
# Pipeline tracker
# ---------------------------------------------------------------------------
st.markdown(pipeline_steps_html(current_status), unsafe_allow_html=True)

st.divider()

# ---------------------------------------------------------------------------
# Proof uploader (shown when awaiting_customer_proof)
# ---------------------------------------------------------------------------
if current_status == "awaiting_customer_proof":
    proof_files = load_proof_files(case_id)
    max_uploads = int(fetch_constants().get("MAX_PROOF_UPLOADS", 2))

    st.markdown("### 📷 Upload Proof")
    st.markdown(
        f"This dispute requires photo evidence. "
        f"Upload up to **{max_uploads}** images (jpeg, png, webp, ≤5 MB each)."
    )

    if proof_files:
        st.markdown(f"**{len(proof_files)}** file(s) already uploaded:")
        for pf in proof_files:
            col_a, col_b = st.columns([3, 1])
            with col_a:
                st.text(f"📎 {pf.get('RELATIVE_PATH', '').split('/')[-1]} ({pf.get('CONTENT_TYPE', '')})")
            with col_b:
                analysis = pf.get("ANALYSIS_STATUS", "pending")
                if analysis == "completed":
                    st.success("Analyzed ✓")
                elif analysis == "failed":
                    st.error("Analysis failed")
                else:
                    st.info("Analyzing…")

    remaining = max_uploads - len(proof_files)
    if remaining > 0:
        uploaded = st.file_uploader(
            f"Add proof image(s) — {remaining} remaining",
            type=["jpg", "jpeg", "png", "webp"],
            accept_multiple_files=(remaining > 1),
            key="proof_uploader",
        )
        if uploaded:
            files = uploaded if isinstance(uploaded, list) else [uploaded]
            session = get_session()
            any_uploaded = False
            for f in files:
                if f.size > 5 * 1024 * 1024:
                    st.error(f"⚠️ {f.name} exceeds 5 MB. Please upload a smaller image.")
                    continue
                try:
                    with st.spinner(f"Uploading {f.name}…"):
                        # Upload to internal stage via put_stream
                        stage_path = f"@TIDE.INVESTIGATION.PROOF_STAGE/{case_id}/"
                        session.file.put_stream(
                            f,
                            stage_path,
                            auto_compress=False,
                            overwrite=False,
                        )
                        session.sql(
                            "ALTER STAGE TIDE.INVESTIGATION.PROOF_STAGE REFRESH"
                        ).collect()
                    any_uploaded = True
                    st.success(f"✅ {f.name} uploaded.")
                    # Trigger proof analysis
                    call_proc(
                        "TIDE.INVESTIGATION.ANALYZE_PROOF",
                        [case_id, f"{case_id}/{f.name}"],
                        log_component="ANALYZE_PROOF",
                        case_id=case_id,
                    )
                except Exception as exc:
                    st.error(f"⚠️ Upload failed for {f.name}: {exc}")

            if any_uploaded:
                st.rerun()
    else:
        st.success("Maximum proof images uploaded. The system is analyzing them.")
        st.info("Once analysis is complete, press Continue to resume intake.")
        if st.button("🔄 Continue Intake", key="btn_continue_intake", type="primary"):
            result = call_proc(
                "TIDE.TRIAGE.RESUME_INTAKE",
                [case_id],
                log_component="RESUME_INTAKE",
                case_id=case_id,
            )
            st.rerun()

    st.divider()

# ---------------------------------------------------------------------------
# Chat panel (polling fragment)
# ---------------------------------------------------------------------------
st.markdown("### 💬 Intake Chat")

@st.fragment(run_every="4s")
def _chat_panel(case_id: str, current_status: str):
    """Polling fragment — only this section auto-refreshes every 4 s."""
    messages = load_case_messages(case_id)

    if not messages:
        st.info("💡 The intake assistant will guide you through your dispute. Start by describing your issue below.")

    for msg in messages:
        sender = msg.get("SENDER_TYPE", "assistant")
        content = msg.get("CONTENT", "")
        ts = format_datetime(msg.get("CREATED_AT"))

        if sender == "customer":
            with st.chat_message("user"):
                st.markdown(content)
                st.caption(ts)
        else:
            icon = "🤖" if sender == "assistant" else ("🛡️" if sender == "agent" else "ℹ️")
            with st.chat_message("assistant", avatar=icon):
                st.markdown(content)
                st.caption(ts)


_chat_panel(case_id, current_status)

# ---------------------------------------------------------------------------
# Message composer
# ---------------------------------------------------------------------------
# Disable composer while awaiting proof or in terminal states
composer_disabled = current_status in (
    "awaiting_customer_proof",
    "resolved",
    "closed",
)

if not composer_disabled:
    user_input = st.chat_input(
        "Type your message…",
        key="chat_composer",
        disabled=composer_disabled,
    )
    if user_input and user_input.strip():
        with st.spinner("Processing…"):
            result = send_message(case_id, user_input.strip())
        if result is None:
            st.error("⚠️ Failed to send message. Please try again.")
        st.rerun()
elif current_status == "awaiting_customer_proof":
    st.info("📷 Upload your proof above to continue the conversation.")

# ---------------------------------------------------------------------------
# Customer-decision actions (awaiting_customer_decision)
# ---------------------------------------------------------------------------
if current_status == "awaiting_customer_decision":
    st.divider()
    st.markdown("### 🔔 Action Required")
    reason_copy_row = run_sql_first(
        # V_CASE_CURRENT does not carry invalid_reason_code — it lives in the
        # decision_made event payload. Lifted into a CTE rather than selected
        # off the view (which does not compile) or joined via a correlated
        # subquery (which Snowflake will not accept in an ON clause).
        """
        WITH reason AS (
            SELECT payload['invalid_reason_code']::VARCHAR AS invalid_reason_code
            FROM TIDE.TRIAGE.CASE_EVENTS
            WHERE case_id = ?
              AND event_type = 'decision_made'
            ORDER BY occurred_at DESC
            LIMIT 1
        )
        SELECT rc.invalid_reason_code,
               c.path_id,
               r.customer_copy,
               r.appeal_priority
        FROM TIDE.TRIAGE.V_CASE_CURRENT c
        LEFT JOIN reason rc ON TRUE
        LEFT JOIN TIDE.DECISION.REASON_COPY r
               ON r.invalid_reason_code = rc.invalid_reason_code
        WHERE c.case_id = ?
        """,
        [case_id, case_id],
        log_component="1_Customer.reason_copy",
        case_id=case_id,
    )

    if reason_copy_row and reason_copy_row.get("CUSTOMER_COPY"):
        st.warning(reason_copy_row["CUSTOMER_COPY"])

    col_appeal, col_close = st.columns(2)
    with col_appeal:
        if st.button("⚡ Appeal This Decision", key="btn_appeal", use_container_width=True, type="primary"):
            with st.spinner("Submitting appeal…"):
                appeal_case(case_id)
            st.success("Appeal submitted. An escalation agent will review your case.")
            st.rerun()
    with col_close:
        if st.button("✖ Close My Case", key="btn_close_acd", use_container_width=True):
            with st.spinner("Closing case…"):
                close_case(case_id)
            st.success("Your case has been closed.")
            st.rerun()

# ---------------------------------------------------------------------------
# Close action (always available for non-terminal cases)
# ---------------------------------------------------------------------------
if current_status not in ("resolved", "closed", "awaiting_customer_decision"):
    with st.expander("⚙️ Case options"):
        if st.button("✖ Close My Case", key="btn_close_main", use_container_width=True):
            with st.spinner("Closing case…"):
                close_case(case_id)
            st.success("Your case has been closed.")
            st.rerun()

# ---------------------------------------------------------------------------
# Resolution summary (resolved / closed)
# ---------------------------------------------------------------------------
if current_status in ("resolved", "closed"):
    st.divider()
    st.markdown("### 📋 Resolution Summary")

    res_type = case.get("RESOLUTION_TYPE", "")
    elig_amount = case.get("ELIGIBLE_AMOUNT")
    path_id = case.get("PATH_ID", "")

    cols = st.columns(3)
    with cols[0]:
        st.metric("Outcome", current_status.replace("_", " ").title())
    with cols[1]:
        st.metric("Resolution", res_type.replace("_", " ").title() if res_type else "—")
    with cols[2]:
        st.metric("Amount", format_currency(elig_amount) if elig_amount else "—")

    report = load_case_report(case_id)
    if report:
        st.markdown("---")
        st.markdown("**Case Report**")
        if report.get("OUTCOME_SUMMARY"):
            st.markdown(report["OUTCOME_SUMMARY"])
        if report.get("RESOLUTION_PATH"):
            st.caption(f"Decision path: `{report['RESOLUTION_PATH']}`")
        st.caption(f"Generated: {format_datetime(report.get('GENERATED_AT'))}")
    elif path_id:
        st.caption(f"Decision path: `{path_id}`")
