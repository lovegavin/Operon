# Library 8.0.4

8.0.4 is a contract-correctness release over 8.0.3. It keeps the application,
protocol fields, and the `export_results` public contract unchanged. The
release closes the class of defect that produced the BE-06 failure: a producer
could declare a 2-D output, pass a one-case contract test, and still be
unusable by `join` or `aggregate`.

## Lessons from the online test

- `unknown` is not `compatible`. A test that accepts "not incompatible" can
  pass while the schema has not proved anything.
- A single positive case and one deliberate violation are not a composition
  matrix. Every declared dimension is a `join` edge and every declared label on
  the second dimension is an `aggregate` edge.
- The static schema must carry the labels. Building labels only at runtime is
  not enough: the interface layer cannot resolve `aggregate(group_col=...)`.
- `dependency_imports` is a probe, not a declaration. Every probe needs a
  non-empty `dependencies` list or a named `resources.environment`.
- Dynamic exceptions must be explicit, reviewed, and tested for staleness. They
  must not be silent skips.
- The test document and the executable test must describe the same audit. An
  alias table claimed by the document but absent from the test is a defect in
  the standard.

## Changes

- Added static `statistic`/`score` labels to `cell_communication`,
  `sc_cluster_profile`, `sc_marker_specificity`, `sc_rank_genes`, and
  `ml_partial_dependence`.
- Declared runtime dependencies for the three MD analysis operators
  (`numpy>=1.24`, `scipy>=1.10`) and `structure_openmm_energy`
  (`openmm>=8.0`, `pdbfixer>=1.9`).
- Added a catalog-wide composition test
  (`tests/test_contract_compositions.py`) covering:
  - every declared dimension through `join`'s contract and a real `JoinStep.run`;
  - every second-dimension label through `aggregate`'s contract and a real
    `AggregateStep.run`;
  - static labels on every `statistic`/`score` axis;
  - dependency ownership for every import probe;
  - staleness checks for the three PRS dynamic-label allowlist entries.
- Strengthened `tests/test_interface_contracts.py` to bind the real first
  dimension and require exact `compatible` instead of accepting `unknown`.
- Extended `docs/verification/five-layer-test-standard.md` with sections 4.1
  (composition matrix) and 4.2 (dependency audit), a ninth L1 check, and a
  stricter release gate.

## Compatibility

- Operon Studio: **4.0.7 or newer**. 3.x is no longer supported.
- 1063 operators, 108 Readers, 7 packages, 79 routes.
- Protocol v3 and SDK 3.7 are unchanged.

## Testing

- Focused composition, interface, release, and route-parameter tests:
  **37 passed**.
- `operon registry check --json`: 1063 operators, 108 Readers, 7 packages,
  79 routes, 0 errors.
- Bundle verification on Studio 4.0.7 (`99a677b2…`) is recorded in
  `verification/operator-audit-8.0.4/application-4.0.7.json`: 95 passed,
  2 skipped, 7 deselected.
- The full 8.0.3 suite remains the last full-suite run
  (3722 passed, 209 skipped, 0 failed, 2435.17 s); this metadata-and-test patch
  was verified with the focused set, per the release request.

## Known limits

- `prs_af_filter`, `prs_harmonize`, and `prs_ld_clump` name their statistic
  column through the runtime `weight_label` parameter. They remain explicit,
  validated allowlist entries because the static schema cannot name that column.
- `paga_connectivity`, `pseudotime_dpt`, and `trajectory_gene_trends` are
  data-defined matrices; they are outside the fixed `statistic`/`score` rule.
- The interface energy values remain model estimates, not experimental values.
