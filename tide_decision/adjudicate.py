"""Main entry point for the TIDE decision engine.

adjudicate(bundle) → Decision

Wires: normalise subtype → derive facts → guardrails → routing.
See DETAILS.md §10–§11 for the complete specification.

No Snowflake imports. No clock — uses bundle['as_of'].
"""

from __future__ import annotations

from typing import Optional

from tide_decision.fact_derivation import derive_facts
from tide_decision.guardrails import check_guardrails
from tide_decision.routing import route
from tide_decision.types import Decision, INTAKE_ALIASES, constant


def _normalise_subtype(raw: str) -> str:
    """Apply intake aliases and lowercase normalisation — DETAILS.md §7.2."""
    normalised = str(raw or "").strip().lower()
    return INTAKE_ALIASES.get(normalised, normalised)


def adjudicate(bundle: dict, constants: Optional[dict] = None) -> Decision:
    """Deterministic adjudication of a dispute case.

    Args:
        bundle: Plain-dict evidence bundle (see SCHEMA.md §5).
            Must include at minimum:
            - dispute_subtype: str
            - resolution_preference: str
            Plus evidence sections (order, payment, shipment, etc.)
        constants: Business constants, normally read from
            DECISION.RULE_CONSTANTS by the calling procedure. Falls back to the
            DETAILS.md §6 defaults.

    Returns:
        A frozen Decision with path_id, target_status, resolution_type,
        eligible_amount, and reason.

    The customer's `resolution_preference` is deliberately **not** normalised
    to the subtype default before guardrails run: G-02 exists to catch an
    unsupported preference, and defaulting it early would make that guardrail
    unreachable. Routing applies §7.3 itself, after G-02 has had its say.
    """
    autonomous_limit = constant("AUTONOMOUS_LIMIT_USD", constants)

    # Step 1: normalise subtype aliases
    subtype = _normalise_subtype(bundle.get("dispute_subtype", ""))
    bundle = {**bundle, "dispute_subtype": subtype}

    # Step 2: derive facts from evidence
    facts = derive_facts(bundle, constants)

    # Step 3: guardrails (ordered, first match returns)
    guardrail_decision = check_guardrails(bundle, facts)
    if guardrail_decision is not None:
        return guardrail_decision

    # Step 4: route by subtype
    return route(bundle, facts, autonomous_limit)
