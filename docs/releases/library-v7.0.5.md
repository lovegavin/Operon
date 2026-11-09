# Library 7.0.5

Library 7.0.5 is an audit release. It does not change operator behaviour; it
publishes the expanded contract audit, its evidence and the audit tooling with
the library, and targets Studio 3.1.6.

## Audit result

- L0 static consistency: 1171 / 1171 PASS (1063 operators, 108 Readers),
  0 failures.
- L1 contract behaviour: 358 PASS, 0 FAIL, 587 SKIP_DOMAIN, 53 SKIP_FILE,
  42 SKIP_EXTERNAL, 22 SKIP_HARNESS, 1 SKIP_TIMEOUT. Negative `info`
  predicates: 102 PASS, 34 FAIL, 787 not applicable.
- L2 independent oracles: 5 / 5 deterministic checks pass (Kalman vs scalar
  recursion, Gaussian blur vs scipy, PCA vs SVD, conformal width vs empirical
  quantile, Bayesian posterior mean vs OLS).
- L3 routes: 78 / 78 route bundles import on Studio 3.1.6; 13 builtin routes
  replay (65 SKIP_DATA because input data is not distributed with the
  template); 250 generated CSV-backed routes execute; union coverage
  459 / 1063 operators. 604 operators still lack a passing route.
- L4: sampled double-run determinism 13 / 14 byte-identical; `pca` route peak
  RSS 141 MiB; a 1 KiB managed budget raises `MemoryBudgetError`.
- L5: bundle import through the Studio HTTP API is verified; cross-entry-point
  byte equality is not yet measured.

The exact scope and the reproducible commands are in
`docs/verification/operator-audit-7.0.5.md`. L2-L5 remain partial and are not
reported as complete.

## Compatibility

- Application: Studio 3.1.6 (minimum and build target).
- Protocol: integer `protocol_version = 3`, `protocol_revision = "3.7"`.
- Catalog: 1063 operators, 108 Readers, 7 packages, 78 route templates.

## Assets

The release workflow publishes Linux and Windows library bundles, the route
collection, the quickstart archives, the wheel, verification JSON files,
`SHA256SUMS.txt`, and `Operon-Operator-Audit-v7.0.5.zip` with the audit
report, scripts and raw evidence.

## Tests

Full pytest under NumPy 2.1.3: 3708 passed, 221 skipped, 0 failed (39:27).
7.0.5 changes audit scripts, evidence and release metadata only.
