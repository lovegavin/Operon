# Library 7.0.10

Audit-evidence release for Studio 3.1.6. No operator, protocol or route contract
changed in this version; the library code is identical to 7.0.9.

## Coverage

- L0 static conformance: 1171/1171 (1063 operators + 108 Readers).
- L1 contract audit: 358 PASS, 0 FAIL, 587 SKIP_DOMAIN, 53 SKIP_FILE,
  42 SKIP_EXTERNAL, 22 SKIP_HARNESS, 1 SKIP_TIMEOUT.
- L2 independent oracles: 13/13.
- L3 route coverage: 620/1063, 443 uncovered. New in 7.0.10: 25 group-comparison
  routes, 25 machine-learning routes and 8 PDB geometry routes.
- L4: spill/recompute determinism, budget and wire round-trip evidence unchanged
  from 7.0.9; source mutation is still not rejected by `workflow prepare`.
- L5: CLI/HTTP/MCP describe parity and four-way run parity unchanged from 7.0.9.

The per-operator table is `verification/operator-audit-7.0.10/operator_table.csv`
(1177 rows including the header). Full method and limitations are in
`docs/verification/operator-audit-7.0.10.md`.

## Compatibility

- Application: 3.1.6 (minimum and build).
- SDK range unchanged.
- Full suite: 3722 passed, 209 skipped, 0 failed (41:24, bp-numpy21/NumPy 2.1.3).

## Assets

Linux and Windows library bundles, routes, quickstart, audit archive, wheel,
verification JSON for both platforms, and `SHA256SUMS.txt`.
