---
name: decision-engine
description: How to read, modify, and test TIDE's deterministic adjudication engine. Use whenever touching tide_decision/, guardrails, routing, thresholds, or anything in docs/DETAILS.md.
---

# Decision engine

## Architecture rule

The engine is a **pure Python module** (`tide_decision/`) with zero Snowflake imports:

```
tide_decision/
  fact_derivation.py  # derive_facts(bundle: dict) -> DerivedFacts
  guardrails.py       # check_guardrails(facts) -> Decision | None
  routing.py          # route(facts) -> Decision
  adjudicate.py       # adjudicate(bundle) -> Decision (facts → guardrails → routing)
  types.py            # CaseStatus, Decision, etc.
```

The stored procedure `TIDE.DECISION.ADJUDICATE` is a **thin wrapper**: fetch the evidence
bundle, call `adjudicate()`, insert the decision event, chain to execution. No business
logic in the wrapper. This is what makes the engine testable without an account.

## Non-negotiables

1. **Guardrails run in order and return on first match.** The order is load-bearing. Never reorder, never fall through.
2. **Every branch returns a `Decision` with a human-readable `reason` and, where applicable,
   an `invalid_reason_code`.** No decision without a citable why.
3. **Constants come from docs/DETAILS.md** and are mirrored in `DECISION.RULE_CONSTANTS`. Changing one
   means: BRL edit → constant row update → test update → code. In that order.
4. `adjudicate()` is deterministic and side-effect-free: same bundle in, same decision out.

## Change workflow

1. Edit `docs/DETAILS.md` (get sign-off if the change alters money behaviour).
2. Update/add tests in `tests/decision/` — one test function per terminal path id.
3. Implement. `pytest tests/decision -q` must be 100% green.
4. Redeploy the wrapper procedure only if its signature changed.

## Testing

- Fixtures are plain dict bundles in `tests/decision/bundles/` — hand-editable, no DB.
- Path coverage assertion: `tests/decision/test_coverage.py` fails if any path id
  lacks a test.
- Never test through the stored procedure for logic; wrapper gets one smoke test.
