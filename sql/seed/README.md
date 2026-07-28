# Seed Data

Deterministic demo data generated per `docs/DETAILS.md` §15.4.

All names, SKUs, carriers, and amounts are **invented**. Emails use the reserved `example.com` domain (RFC 2606). No real customer data.

## Seed files

- `seed_retail.sql` — 23 orders + items, payments, refunds, shipments, tracking events, stock. Every order is engineered to trip one specific decision path; the scenario id is in the comment above each row.
- `seed_decision.sql` — 14 rule constants, 10 reason-copy rows, 14 policies (the Cortex Search corpus).
- `seed_cases.sql` — *(not yet needed)* cases are created through the UI during E2E runs; add pre-seeded cases here only if demo rehearsal shows we need instant queue depth.

Load order: DDL first (`sql/00–05`), then `seed_retail.sql`, then `seed_decision.sql`. Both are idempotent — scoped deletes precede inserts, and all timestamps are relative to `CURRENT_TIMESTAMP()` so the seed never goes stale.

Key probes to know about: `ORD-1008` carries a prior refund (duplicate-refund guardrail), `ORD-1009` has a pending payment, `ORD-1010` has a delivery scan but will be disputed as non-receipt, `SKU-CHRN-LE` has zero stock everywhere (replacement-infeasible probe), `ORD-1013` was delivered 5 days past estimate (SLA breach → shipping-fee-only refund).

## Invariant: tracking event ids must sort chronologically within a shipment

`TRACKING_EVENTS.event_id` values seeded for one `shipment_id` **must sort in the same order as their `occurred_at` values** — hence `TE-1010a`, `TE-1010b`, `TE-1010c`. Keep that scheme when editing or regenerating this file.

Two call sites break `occurred_at` ties on `event_id` to decide which event is the latest:

- `INVESTIGATION.GET_SHIPMENT_TIMELINE` — `ORDER BY occurred_at, event_id`
- `RETAIL.DISPUTES_SV` — `latest_event_type` / `latest_event_location`, via `MAX_BY(..., occurred_at || event_id)`

The tie is not hypothetical. On `ORD-1010` the `out_for_delivery` and `delivered` events share a timestamp, and that order is the delivered-but-disputed probe for guardrail G-05. With ids that do not sort chronologically the tie resolves the wrong way and the parcel is reported as still out for delivery — **silently, with no error**, and the guardrail stops firing.

The DDL declares `event_id VARCHAR(36) DEFAULT UUID_STRING()`, so regenerating this seed with real UUIDs would violate the invariant. `TRACKING_EVENTS` is simulated enterprise data with no runtime writer, so this is enforced by convention here rather than by a schema column. If a runtime writer is ever added, replace the tiebreak with a real ordinal column and delete this note.

See `PROVENANCE.md` for full dataset provenance declarations.
