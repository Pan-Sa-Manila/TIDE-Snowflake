"""Main entry point for the TIDE decision engine.

adjudicate(bundle) → Decision

Wires: normalise subtype → derive facts → guardrails → routing.
See DETAILS.md §10–§11 for the complete specification.

No Snowflake imports. No clock — uses bundle['as_of'].
"""

from __future__ import annotations

from tide_decision.fact_derivation import derive_facts
from tide_decision.guardrails import check_guardrails
from tide_decision.routing import route
from tide_decision.types import Decision, INTAKE_ALIASES, SUBTYPE_META


def _normalise_subtype(raw: str) -> str:
    """Apply intake aliases and lowercase normalisation.

    See DETAILS.md §7.2.
    """
    normalised = raw.strip().lower()
    return INTAKE_ALIASES.get(normalised, normalised)


def _resolve_type(preference: str, subtype: str) -> str:
    """Resolve the effective resolution type.

    See DETAILS.md §7.3: customer preference if allowed for the subtype;
    else the subtype default.
    """
    meta = SUBTYPE_META.get(subtype)
    if not meta:
        return preference or "refund"
    allowed = meta["allowed"]
    if preference in allowed:
        return preference
    return meta["default"]


def adjudicate(
    bundle: dict,
    constants: dict | None = None,
) -> Decision:
    """Deterministic adjudication of a dispute case.

    Args:
        bundle: Plain-dict evidence bundle (see SCHEMA.md §5).
            Must include at minimum:
            - dispute_subtype: str
            - resolution_preference: str
            Plus evidence sections (order, payment, shipment, etc.)
        constants: Override thresholds for testing. Defaults to BRL values.

    Returns:
        A frozen Decision dataclass with path_id, target_status,
        resolution_type, eligible_amount, and reason.
    """
    c = constants or {}
    autonomous_limit = c.get("AUTONOMOUS_LIMIT_USD", 50.0)

    # Step 1: Normalise subtype aliases
    raw_subtype = bundle.get("dispute_subtype", "")
    subtype = _normalise_subtype(raw_subtype)
    bundle = {**bundle, "dispute_subtype": subtype}

    # Step 2: Resolve effective resolution type
    preference = bundle.get("resolution_preference", "")
    resolved = _resolve_type(preference, subtype)
    bundle = {**bundle, "resolution_preference": resolved}

    # Step 3: Derive facts from evidence
    facts = derive_facts(bundle, constants)

    # Step 4: Run guardrails (ordered, first match returns)
    guardrail_decision = check_guardrails(bundle, facts, autonomous_limit)
    if guardrail_decision is not None:
        return guardrail_decision

    # Step 5: Route by subtype
    return route(bundle, facts, autonomous_limit)
