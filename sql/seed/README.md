# Seed Data

Deterministic demo data generated per `docs/DETAILS.md` §15.4.

All names, SKUs, carriers, and amounts are **invented**. Emails use the reserved `example.com` domain (RFC 2606). No real customer data.

## Seed files

- `seed_retail.sql` — 23 orders + items, payments, refunds, shipments, tracking events, stock. Every order is engineered to trip one specific decision path; the scenario id is in the comment above each row.
- `seed_decision.sql` — 14 rule constants, 10 reason-copy rows, 14 policies (the Cortex Search corpus).
- `seed_cases.sql` — *(not yet needed)* cases are created through the UI during E2E runs; add pre-seeded cases here only if demo rehearsal shows we need instant queue depth.

Load order: DDL first (`sql/00–05`), then `seed_retail.sql`, then `seed_decision.sql`. Both are idempotent — scoped deletes precede inserts, and all timestamps are relative to `CURRENT_TIMESTAMP()` so the seed never goes stale.

Key probes to know about: `ORD-1008` carries a prior refund (duplicate-refund guardrail), `ORD-1009` has a pending payment, `ORD-1010` has a delivery scan but will be disputed as non-receipt, `SKU-CHRN-LE` has zero stock everywhere (replacement-infeasible probe), `ORD-1013` was delivered 5 days past estimate (SLA breach → shipping-fee-only refund).

See `PROVENANCE.md` for full dataset provenance declarations.
