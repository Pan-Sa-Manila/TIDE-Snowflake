# Evidence Bundles (Test Fixtures)

This directory contains plain-JSON representations of evidence bundles
for use in tests.

To keep the decision engine pure and testable without a database, we snapshot
the state of a case (including orders, shipments, and proof signals) into a
bundle.

These fixtures will be populated during WS-B.
