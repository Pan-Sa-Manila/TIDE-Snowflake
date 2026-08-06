"""TIDE UI — Database helpers.

Shared utilities for all Streamlit persona pages:
  - get_session()       returns the active Snowpark session
  - run_sql()           parameterized SELECT with error logging
  - call_proc()         stored procedure call via session.call()
  - fetch_constants()   reads DECISION.RULE_CONSTANTS into a plain dict

Rules:
  - NEVER string-interpolate user data into SQL (use params / bind variables)
  - ALL errors are caught, logged to EXECUTION.PIPELINE_LOG, and surfaced
    via st.error() — never crash the page
  - All queries target TIDE.* fully-qualified objects
"""

from __future__ import annotations

import json

import streamlit as st


# ---------------------------------------------------------------------------
# VARIANT decoding
# ---------------------------------------------------------------------------

def as_json(value, default=None):
    """Decode a VARIANT / ARRAY / OBJECT column into a Python value.

    Snowpark hands these back as a JSON **string**, not a dict or list. A caller
    that assumes otherwise fails in two different ways, both of which shipped
    here: `.get()` on it raises `AttributeError: 'str' object has no attribute
    'get'`, and `", ".join()` on it iterates the raw JSON one character at a
    time. Neither is caught by a SQL check, because the query itself is fine.

    Anything unparseable returns `default` rather than raising — a malformed
    payload should degrade the panel, not take the page down.
    """
    if value is None:
        return default
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value)
        except (ValueError, TypeError):
            return default
    return default

# ---------------------------------------------------------------------------
# Session
# ---------------------------------------------------------------------------

def get_session():
    """Return the active Snowpark session (warehouse runtime provides it)."""
    from snowflake.snowpark.context import get_active_session  # type: ignore
    return get_active_session()


# ---------------------------------------------------------------------------
# Core SQL helper
# ---------------------------------------------------------------------------

def run_sql(
    query: str,
    params: list | None = None,
    session=None,
    log_component: str = "UI",
    case_id: str | None = None,
) -> list[dict]:
    """Execute a parameterized SELECT and return rows as list-of-dicts.

    Parameters
    ----------
    query:         SQL string using ? placeholders for bind variables.
    params:        Ordered list of values for each ? placeholder.
    session:       Snowpark session (fetched automatically if omitted).
    log_component: Component label for PIPELINE_LOG on failure.
    case_id:       Optional case_id for scoped error logging.

    Returns
    -------
    List of row dicts.  Empty list on error (error rendered by this function).
    """
    if session is None:
        session = get_session()
    try:
        df = session.sql(query, params or [])
        return [row.as_dict() for row in df.collect()]
    except Exception as exc:
        _log_error(session, log_component, case_id, str(exc), query)
        st.error(f"⚠️ Query failed: {exc}")
        return []


def run_sql_first(
    query: str,
    params: list | None = None,
    session=None,
    log_component: str = "UI",
    case_id: str | None = None,
) -> dict | None:
    """Like run_sql() but returns only the first row dict, or None."""
    rows = run_sql(query, params, session, log_component, case_id)
    return rows[0] if rows else None


# ---------------------------------------------------------------------------
# Stored procedure helper
# ---------------------------------------------------------------------------

def call_proc(
    proc_name: str,
    args: list,
    session=None,
    log_component: str | None = None,
    case_id: str | None = None,
) -> dict | None:
    """Call a Snowpark stored procedure and return its VARIANT result as dict.

    Parameters
    ----------
    proc_name:  Fully-qualified procedure name, e.g. 'TIDE.TRIAGE.INTAKE_TURN'.
    args:       Positional arguments (Python values; Snowpark handles binding).
    session:    Snowpark session (fetched automatically if omitted).

    Returns
    -------
    The procedure's return value as a Python dict, or None on error.
    """
    if session is None:
        session = get_session()
    component = log_component or proc_name.split(".")[-1]
    try:
        result = session.call(proc_name, *args)
        # session.call returns Python-native types from VARIANT
        if isinstance(result, dict):
            return result
        if result is None:
            return None
        # Snowpark may return a string for VARIANT; parse it
        import json
        return json.loads(str(result))
    except Exception as exc:
        _log_error(session, component, case_id, str(exc), proc_name)
        st.error(f"⚠️ Procedure {proc_name} failed: {exc}")
        return None


# ---------------------------------------------------------------------------
# Constants cache
# ---------------------------------------------------------------------------

@st.cache_data(ttl=300, show_spinner=False)
def fetch_constants() -> dict:
    """Read DECISION.RULE_CONSTANTS and return as a plain dict {key: value}.

    Cached for 5 minutes (constants rarely change during a session).
    Falls back to DEFAULT_CONSTANTS if the table is unreachable.
    """
    try:
        session = get_session()
        rows = session.sql(
            "SELECT key, value::VARIANT FROM TIDE.DECISION.RULE_CONSTANTS"
        ).collect()
        return {row["KEY"]: row["VALUE"] for row in rows}
    except Exception:
        # Fallback to defaults from DETAILS.md §6 — engine defaults
        return {
            "AUTONOMOUS_LIMIT_USD": 50.00,
            "RETURN_WINDOW_DAYS": 7,
            "DELIVERY_SLA_BREACH_DAYS": 3,
            "STALE_TRANSIT_DAYS": 7,
            "INACTIVITY_TIMEOUT_MIN": 15,
            "MIN_REJECTION_CHARS": 50,
            "MIN_REJECTION_CITATIONS": 1,
            "MAX_PROOF_UPLOADS": 2,
            "MAX_FOLLOWUP_QUESTIONS": 3,
        }


def constant(key: str, default=None):
    """Convenience: fetch one constant value by key."""
    return fetch_constants().get(key, default)


# ---------------------------------------------------------------------------
# Current user
# ---------------------------------------------------------------------------

def get_current_user() -> str:
    """Return the Snowflake CURRENT_USER() for this session."""
    # First, try st.experimental_user (available in SiS with Streamlit 1.30+)
    try:
        import streamlit as st
        if hasattr(st, "experimental_user") and getattr(st.experimental_user, "user_name", None):
            return st.experimental_user.user_name
    except Exception:
        pass

    # Fallback to CURRENT_USER() SQL
    try:
        session = get_session()
        row = session.sql("SELECT CURRENT_USER() AS u").collect()
        val = row[0]["U"] if row else None
        return str(val) if val is not None else "unknown"
    except Exception:
        return "unknown"


# ---------------------------------------------------------------------------
# Internal error logger
# ---------------------------------------------------------------------------

def _log_error(
    session,
    component: str,
    case_id: str | None,
    error_msg: str,
    detail: str = "",
) -> None:
    """Best-effort write to EXECUTION.PIPELINE_LOG on error.

    Never raises — if the log write itself fails, we silently ignore it
    to avoid masking the original error.
    """
    try:
        import json
        payload = json.dumps({"error": error_msg, "detail": detail[:500]})
        session.sql(
            """
            INSERT INTO TIDE.EXECUTION.PIPELINE_LOG
                (case_id, component, status, detail)
            SELECT ?, ?, 'failed', PARSE_JSON(?)
            """,
            [case_id, component, payload],
        ).collect()
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Persona resolution
# ---------------------------------------------------------------------------

@st.cache_data(ttl=300, show_spinner=False)
def get_user_personas(username: str) -> list:
    """Personas this user may act as: customer | approver | escalation.

    Streamlit in Snowflake runs with **owner's rights** — every query and
    procedure call executes as the app owner (TIDE_ADMIN) no matter who is
    signed in. CURRENT_USER() is the viewer, but privileges are not. So the page
    cannot ask "what can this role do?"; it has to look the caller up. This
    mirrors TIDE.TRIAGE.HAS_PERSONA, which the procedures use for the same
    reason.

    A user absent from USER_PERSONA gets all three, matching the UDF: admins and
    whoever deployed must not be locked out of their own app.
    """
    rows = run_sql(
        """
        SELECT persona
        FROM TIDE.TRIAGE.USER_PERSONA
        WHERE username = ?
        """,
        [username],
        log_component="db.get_user_personas",
    )
    personas = [r["PERSONA"] for r in rows] if rows else []
    return personas or ["customer", "approver", "escalation"]


def require_persona(persona: str, label: str):
    """Stop the page unless the signed-in user may act as `persona`.

    Presentation only — the enforcement that matters is in the procedures, since
    a page guard cannot stop a direct call.
    """
    if persona not in get_user_personas(get_current_user()):
        st.warning(
            f"This page is for the {label} role. "
            f"You are signed in as **{get_current_user()}**."
        )
        st.stop()
