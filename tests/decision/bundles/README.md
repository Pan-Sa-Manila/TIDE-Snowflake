# Evidence Bundles (Test Fixtures)

The decision engine's entire input is a plain dict (`docs/SCHEMA.md` §5), so the
whole test matrix runs with no Snowflake account.

`__init__.py` exposes the builders:

| Helper | Purpose |
|---|---|
| `make_bundle(subtype, preference, **kw)` | A **clean** case: payment confirmed, delivered inside the return window, no prior refunds, stock on hand, supporting proof where the subtype requires it. No guardrail fires unless a test makes one fire. |
| `tracking_event(type, days_ago, location)` | One `RETAIL.TRACKING_EVENTS` row |
| `days_before(n)` / `days_after(n)` | Timestamps relative to `AS_OF` |
| `default_proof(subtype)` | Proof carrying the subtype-relevant signal |

Every timestamp is relative to `AS_OF` because the engine has no clock — it
reads `bundle["as_of"]` (`docs/DETAILS.md` §9). Tests that need a different
evaluation time pass `as_of=` rather than touching the system clock.

## Writing a new path test

```python
from .bundles import make_bundle

def test_r07_not_as_described_refund_under_limit():
    bundle = make_bundle("not_as_described", "refund", amount=40.00, total_amount=500.00)
    decision = adjudicate(bundle)

    assert decision.path_id == "R-07"
```

Two conventions the coverage gate depends on:

1. Assert the path with `decision.path_id == "R-07"` — `test_coverage.py` scans
   for that exact form, so a path id in a comment cannot fake coverage.
2. Where an eligible amount could come from more than one field, make the fields
   differ (above, affected 40 vs order total 500) so the assertion pins which
   one the BRL actually specifies.
