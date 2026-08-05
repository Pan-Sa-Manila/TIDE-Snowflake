"""TIDE — Approver Dashboard (2_Approver.py)

Approver persona: queue-based review of resolution requests.
Examine evidence, recommended decisions, approve or reject with rigor.

Layout: Full width. Queue tabs (Refund / Return / Replacement) + case review panel.
See AGENTS.md §7.1, DETAILS.md §4, §14 F4.2.
"""

from __future__ import annotations

import streamlit as st
from ui.theme import (
    inject_css,
    sidebar_branding,
    status_pill_html,
    age_bucket_pill,
    format_currency,
    format_datetime,
    pipeline_steps_html,
    PALETTE,
)
from ui.db import (
    run_sql,
    run_sql_first,
    call_proc,
    fetch_constants,
    current_user,
)

st.set_page_config(
    page_title="TIDE — Approver",
    page_icon="✅",
    layout="wide",
)

inject_css()

# ---------------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------------
if "selected_case_id" not in st.session_state:
    st.session_state.selected_case_id = None
if "rejection_reason" not in st.session_state:
    st.session_state.rejection_reason = ""
if "rejection_citations" not in st.session_state:
    st.session_state.rejection_citations = []
if "policy_search_query" not in st.session_state:
    st.session_state.policy_search_query = ""

username = current_user()
constants = fetch_constants()
MIN_REJECTION_CHARS = int(constants.get("MIN_REJECTION_CHARS", 50))
MIN_REJECTION_CITATIONS = int(constants.get("MIN_REJECTION_CITATIONS", 1))

# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------

def load_queue(request_type: str) -> list[dict]:
    return run_sql(
        """
        SELECT q.case_id, q.reference_number, q.dispute_subtype,
               q.current_status, q.eligible_amount, q.resolution_type,
               q.age_minutes, q.age_bucket, q.status_changed_at,
               q.customer_id, q.order_id,
               r.request_id, r.request_type, r.amount, r.status AS req_status
        FROM TIDE.TRIAGE.V_QUEUE_APPROVAL q
        JOIN TIDE.EXECUTION.RESOLUTION_REQUESTS r
          ON r.case_id = q.case_id AND r.status = 'pending'
        WHERE r.request_type = ?
        ORDER BY q.status_changed_at ASC
        """,
        [request_type],
        log_component="2_Approver.load_queue",
    )


def load_case_detail(case_id: str) -> dict | None:
    return run_sql_first(
        """
        SELECT c.case_id, c.reference_number, c.order_id, c.customer_id,
               c.dispute_type, c.dispute_subtype, c.resolution_preference,
               c.intake_summary, c.proof_required, c.current_status,
               c.eligible_amount, c.resolution_type, c.path_id,
               c.age_minutes, c.age_bucket, c.status_changed_at, c.created_at
        FROM TIDE.TRIAGE.V_QUEUE_APPROVAL c
        WHERE c.case_id = ?
        """,
        [case_id],
        log_component="2_Approver.case_detail",
        case_id=case_id,
    )


def load_resolution_request(case_id: str) -> dict | None:
    return run_sql_first(
        """
        SELECT request_id, request_type, status, amount,
               item_ids, detail, decided_by, created_at, updated_at
        FROM TIDE.EXECUTION.RESOLUTION_REQUESTS
        WHERE case_id = ? AND status = 'pending'
        ORDER BY created_at DESC
        LIMIT 1
        """,
        [case_id],
        log_component="2_Approver.load_request",
        case_id=case_id,
    )


def load_evidence_bundle(case_id: str) -> dict | None:
    return run_sql_first(
        """
        SELECT bundle_id, assembly_status, bundle,
               sources_queried, agent_citations, assembled_at
        FROM TIDE.INVESTIGATION.EVIDENCE_BUNDLES
        WHERE case_id = ?
        ORDER BY assembled_at DESC
        LIMIT 1
        """,
        [case_id],
        log_component="2_Approver.load_bundle",
        case_id=case_id,
    )


def load_decision(case_id: str) -> dict | None:
    return run_sql_first(
        """
        SELECT path_id, target_status, resolution_type, eligible_amount,
               shipping_fee_only, invalid_reason_code, reason, decided_at
        FROM TIDE.DECISION.DECISIONS
        WHERE case_id = ?
        ORDER BY decided_at DESC
        LIMIT 1
        """,
        [case_id],
        log_component="2_Approver.load_decision",
        case_id=case_id,
    )


def load_proof_files(case_id: str) -> list[dict]:
    return run_sql(
        """
        SELECT proof_id, relative_path, content_type,
               byte_size, analysis, analysis_status, uploaded_at
        FROM TIDE.INVESTIGATION.PROOF_FILES
        WHERE case_id = ?
        ORDER BY uploaded_at ASC
        """,
        [case_id],
        log_component="2_Approver.load_proofs",
        case_id=case_id,
    )


def search_policies(query: str) -> list[dict]:
    """Search policies with ILIKE fallback (Cortex Search optional)."""
    if not query.strip():
        return run_sql(
            """
            SELECT policy_id, slug, category, title, body
            FROM TIDE.DECISION.POLICIES
            WHERE active = TRUE
            ORDER BY category, title
            LIMIT 20
            """,
            log_component="2_Approver.policies",
        )
    return run_sql(
        """
        SELECT policy_id, slug, category, title, body
        FROM TIDE.DECISION.POLICIES
        WHERE active = TRUE
          AND (title ILIKE ? OR body ILIKE ? OR category ILIKE ?)
        ORDER BY category, title
        LIMIT 15
        """,
        [f"%{query}%", f"%{query}%", f"%{query}%"],
        log_component="2_Approver.policy_search",
    )


def count_queue_by_type() -> dict:
    rows = run_sql(
        """
        SELECT r.request_type, COUNT(*) AS cnt
        FROM TIDE.TRIAGE.V_QUEUE_APPROVAL q
        JOIN TIDE.EXECUTION.RESOLUTION_REQUESTS r
          ON r.case_id = q.case_id AND r.status = 'pending'
        GROUP BY r.request_type
        """,
        log_component="2_Approver.queue_counts",
    )
    return {row["REQUEST_TYPE"]: row["CNT"] for row in rows}


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
with st.sidebar:
    sidebar_branding("Approver Dashboard")

    st.markdown(
        f'<p style="color:{PALETTE["sidebar_muted"]};font-size:0.82rem;">'
        f'Signed in as</p>'
        f'<p style="color:{PALETTE["sidebar_text"]};font-weight:600;'
        f'font-size:0.92rem;margin-top:-0.5rem;">{username}</p>',
        unsafe_allow_html=True,
    )

    st.markdown(
        f'<div style="height:1px;background:{PALETTE["sidebar_divider"]};'
        f'margin:1rem 0;"></div>',
        unsafe_allow_html=True,
    )

    st.markdown(
        f'<p style="color:{PALETTE["primary"]};font-size:0.88rem;'
        f'font-weight:600;margin-bottom:0.75rem;">Queue Summary</p>',
        unsafe_allow_html=True,
    )
    counts = count_queue_by_type()
    st.metric("Pending Refunds", counts.get("refund", 0))
    st.metric("Pending Returns", counts.get("return", 0))
    st.metric("Pending Replacements", counts.get("replacement", 0))

    st.markdown(
        f'<div style="height:1px;background:{PALETTE["sidebar_divider"]};'
        f'margin:1rem 0;"></div>',
        unsafe_allow_html=True,
    )

    if st.session_state.selected_case_id:
        if st.button("← Clear Selection", use_container_width=True):
            st.session_state.selected_case_id = None
            st.session_state.rejection_reason = ""
            st.session_state.rejection_citations = []
            st.rerun()

    if st.button("← Back to Home", use_container_width=True):
        st.switch_page("Home.py")


# ---------------------------------------------------------------------------
# Page header
# ---------------------------------------------------------------------------
st.markdown("## ✅ Approver Dashboard")
st.markdown("Review resolution requests and approve or reject with full evidence.")
st.divider()

# ---------------------------------------------------------------------------
# Layout: queue list (left) + case review panel (right)
# ---------------------------------------------------------------------------
col_queue, col_review = st.columns([2, 3], gap="large")

# ============================================================
# LEFT: Queue tabs
# ============================================================
with col_queue:
    tab_refund, tab_return, tab_replacement = st.tabs(
        [
            f"💵 Refund ({counts.get('refund', 0)})",
            f"📦 Return ({counts.get('return', 0)})",
            f"🔄 Replacement ({counts.get('replacement', 0)})",
        ]
    )

    def _render_queue_tab(request_type: str):
        rows = load_queue(request_type)
        if not rows:
            st.info(f"No pending {request_type} requests.")
            return
        for row in rows:
            is_selected = st.session_state.selected_case_id == row["CASE_ID"]
            sel_class = " selected" if is_selected else ""

            with st.container():
                st.markdown(
                    f'<div class="queue-card{sel_class}">'
                    f'<div style="display:flex;justify-content:space-between;align-items:center;">'
                    f'<span style="font-weight:700;font-size:0.95rem;color:{PALETTE["text_primary"]};'
                    f'">'
                    f'{row.get("REFERENCE_NUMBER", "—")}</span>'
                    + age_bucket_pill(row.get("AGE_MINUTES", 0))
                    + f'</div>'
                    f'<div style="font-size:0.82rem;color:{PALETTE["text_secondary"]};margin-top:6px;">'
                    f'{row.get("DISPUTE_SUBTYPE", "").replace("_", " ").title()} — '
                    f'<strong>{format_currency(row.get("AMOUNT") or row.get("ELIGIBLE_AMOUNT"))}</strong>'
                    f'</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
                if st.button(
                    "Select →" if not is_selected else "✓ Selected",
                    key=f"sel_{row['CASE_ID']}",
                    use_container_width=True,
                ):
                    st.session_state.selected_case_id = row["CASE_ID"]
                    st.session_state.rejection_reason = ""
                    st.session_state.rejection_citations = []
                    st.rerun()

    with tab_refund:
        _render_queue_tab("refund")
    with tab_return:
        _render_queue_tab("return")
    with tab_replacement:
        _render_queue_tab("replacement")


# ============================================================
# RIGHT: Case review panel
# ============================================================
with col_review:
    case_id = st.session_state.selected_case_id

    if not case_id:
        st.markdown(
            f'<div style="display:flex;flex-direction:column;align-items:center;'
            f'justify-content:center;height:300px;color:{PALETTE["text_muted"]};">'
            f'<span style="font-size:3rem;">👈</span>'
            f'<p style="margin-top:0.5rem;">Select a case from the queue to review it.</p>'
            f'</div>',
            unsafe_allow_html=True,
        )
    else:
        case = load_case_detail(case_id)
        if not case:
            st.warning("Case data unavailable or no longer in queue.")
        else:
            request = load_resolution_request(case_id)
            decision = load_decision(case_id)
            bundle_row = load_evidence_bundle(case_id)
            proof_files = load_proof_files(case_id)

            # ── Case header ──────────────────────────────────────────
            hdr_col, status_col = st.columns([3, 1])
            with hdr_col:
                st.markdown(f"### {case.get('REFERENCE_NUMBER', '—')}")
                st.caption(
                    f"Order: `{case.get('ORDER_ID', '—')[:12]}…`  |  "
                    f"Customer: `{case.get('CUSTOMER_ID', '—')}`  |  "
                    f"Opened: {format_datetime(case.get('CREATED_AT'))}"
                )
            with status_col:
                st.markdown(
                    status_pill_html(case.get("CURRENT_STATUS", "")),
                    unsafe_allow_html=True,
                )
                st.markdown(
                    age_bucket_pill(case.get("AGE_MINUTES", 0)),
                    unsafe_allow_html=True,
                )

            st.markdown(pipeline_steps_html(case.get("CURRENT_STATUS", "")), unsafe_allow_html=True)

            # ── Decision summary ─────────────────────────────────────
            if decision:
                st.markdown("#### 🤖 System Recommendation")
                dcols = st.columns(4)
                dcols[0].metric("Path", decision.get("PATH_ID", "—"))
                dcols[1].metric(
                    "Resolution",
                    (decision.get("RESOLUTION_TYPE") or "—").replace("_", " ").title()
                )
                dcols[2].metric(
                    "Eligible",
                    format_currency(decision.get("ELIGIBLE_AMOUNT"))
                )
                dcols[3].metric(
                    "Shipping Only",
                    "Yes" if decision.get("SHIPPING_FEE_ONLY") else "No"
                )
                if decision.get("REASON"):
                    st.info(f"**Reason:** {decision['REASON']}")

            # ── Evidence bundle ──────────────────────────────────────
            if bundle_row:
                with st.expander("📋 Evidence Bundle", expanded=True):
                    bundle = bundle_row.get("BUNDLE") or {}
                    asm_status = bundle_row.get("ASSEMBLY_STATUS", "—")
                    st.caption(
                        f"Assembly: **{asm_status}**  |  "
                        f"Assembled: {format_datetime(bundle_row.get('ASSEMBLED_AT'))}"
                    )

                    bcol1, bcol2 = st.columns(2)
                    with bcol1:
                        st.markdown("**Order**")
                        order_b = bundle.get("order", {})
                        st.json({
                            "status": order_b.get("status"),
                            "total": order_b.get("total_amount"),
                            "shipping_fee": order_b.get("shipping_fee"),
                        })

                        st.markdown("**Payment**")
                        pay = bundle.get("payment", {})
                        st.json({
                            "status": pay.get("status"),
                            "amount": pay.get("amount"),
                            "method": pay.get("method"),
                        })

                    with bcol2:
                        st.markdown("**Shipment**")
                        ship = bundle.get("shipment", {})
                        st.json({
                            "carrier": ship.get("carrier"),
                            "est_delivery": ship.get("estimated_delivery"),
                            "delivered_at": ship.get("delivered_at"),
                        })

                        st.markdown("**Proof Signals**")
                        proof_b = bundle.get("proof", {})
                        sigs = proof_b.get("signals", {})
                        if sigs:
                            st.json(sigs)
                        else:
                            st.caption("No proof signals.")

                    if bundle.get("refund_history"):
                        st.markdown("**Prior Refunds ⚠️**")
                        st.json(bundle["refund_history"])

                    sources = bundle_row.get("SOURCES_QUERIED")
                    if sources:
                        st.caption(f"Sources queried: {', '.join(sources)}")

            # ── Proof images ─────────────────────────────────────────
            if proof_files:
                with st.expander(f"🖼 Proof Images ({len(proof_files)})"):
                    for pf in proof_files:
                        path = pf.get("RELATIVE_PATH", "")
                        fname = path.split("/")[-1] if path else "file"
                        st.text(f"📎 {fname} — {pf.get('CONTENT_TYPE', '')} — {pf.get('BYTE_SIZE', 0):,} bytes")
                        analysis = pf.get("ANALYSIS") or {}
                        if analysis:
                            st.json(analysis)
                        st.caption(f"Status: {pf.get('ANALYSIS_STATUS', '—')} | Uploaded: {format_datetime(pf.get('UPLOADED_AT'))}")

            st.divider()

            # ── Action buttons ───────────────────────────────────────
            if case.get("CURRENT_STATUS") == "awaiting_approval" and request:
                request_id = request.get("REQUEST_ID", "")
                req_type = request.get("REQUEST_TYPE", "")
                req_amount = request.get("AMOUNT")

                st.markdown(f"#### Action — {req_type.title()} of {format_currency(req_amount)}")

                act_col1, act_col2 = st.columns(2)

                with act_col1:
                    if st.button(
                        f"✅ Approve {req_type.title()}",
                        key="btn_approve",
                        use_container_width=True,
                        type="primary",
                    ):
                        with st.spinner("Approving and executing…"):
                            result = call_proc(
                                "TIDE.EXECUTION.EXECUTE_RESOLUTION",
                                [case_id, request_id],
                                log_component="EXECUTE_RESOLUTION",
                                case_id=case_id,
                            )
                        if result and result.get("success"):
                            st.success(f"✅ Approved. {req_type.title()} executing.")
                            st.session_state.selected_case_id = None
                            st.rerun()
                        else:
                            err = (result or {}).get("error", "Unknown error.")
                            st.error(f"⚠️ Approval failed: {err}")

                with act_col2:
                    with st.expander("✖ Reject with Reason", expanded=False):
                        # Rejection rigor form (DETAILS.md §14: ≥50 chars + ≥1 citation)
                        st.markdown(
                            f"Rejection requires **≥{MIN_REJECTION_CHARS} characters** "
                            f"and **≥{MIN_REJECTION_CITATIONS} policy citation(s)**."
                        )
                        rejection_reason = st.text_area(
                            "Rejection reason",
                            value=st.session_state.rejection_reason,
                            placeholder="Explain why this request is rejected, citing specific evidence…",
                            height=120,
                            key="rejection_reason_input",
                        )
                        st.session_state.rejection_reason = rejection_reason
                        char_count = len(rejection_reason)
                        char_ok = char_count >= MIN_REJECTION_CHARS
                        st.caption(
                            f"{'✅' if char_ok else '⚠️'} {char_count}/{MIN_REJECTION_CHARS} characters"
                        )

                        # Policy citation picker
                        st.markdown("**Policy Citations**")
                        search_q = st.text_input(
                            "Search policies",
                            key="policy_search_input",
                            placeholder="e.g. return window, refund policy…",
                        )
                        policies = search_policies(search_q)
                        if policies:
                            for pol in policies:
                                pol_id = pol.get("POLICY_ID", "")
                                is_cited = pol_id in st.session_state.rejection_citations
                                label = f"{'✓ ' if is_cited else ''}{pol.get('TITLE', '')} [{pol.get('CATEGORY', '')}]"
                                if st.checkbox(label, value=is_cited, key=f"cite_{pol_id}"):
                                    if pol_id not in st.session_state.rejection_citations:
                                        st.session_state.rejection_citations.append(pol_id)
                                else:
                                    if pol_id in st.session_state.rejection_citations:
                                        st.session_state.rejection_citations.remove(pol_id)
                        else:
                            st.caption("No policies found.")

                        cited_count = len(st.session_state.rejection_citations)
                        citations_ok = cited_count >= MIN_REJECTION_CITATIONS
                        st.caption(
                            f"{'✅' if citations_ok else '⚠️'} {cited_count}/{MIN_REJECTION_CITATIONS} citation(s) selected"
                        )

                        submit_enabled = char_ok and citations_ok
                        if st.button(
                            "Submit Rejection",
                            key="btn_reject",
                            disabled=not submit_enabled,
                            use_container_width=True,
                        ):
                            with st.spinner("Submitting rejection…"):
                                result = call_proc(
                                    "TIDE.EXECUTION.REJECT_RESOLUTION",
                                    [
                                        case_id,
                                        request_id,
                                        rejection_reason,
                                        st.session_state.rejection_citations,
                                    ],
                                    log_component="REJECT_RESOLUTION",
                                    case_id=case_id,
                                )
                            if result and result.get("success"):
                                st.success("✖ Rejection recorded.")
                                st.session_state.selected_case_id = None
                                st.session_state.rejection_reason = ""
                                st.session_state.rejection_citations = []
                                st.rerun()
                            else:
                                err = (result or {}).get("error", "Unknown error.")
                                st.error(f"⚠️ Rejection failed: {err}")

            elif case.get("CURRENT_STATUS") not in ("awaiting_approval",):
                st.info("This case is no longer awaiting approval.")
