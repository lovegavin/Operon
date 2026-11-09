# Library 7.0.3

7.0.3 targets Studio 3.1.6 and adds the first operator-audit toolchain and
evidence set. The operator catalog is unchanged in size: **1063 operators /
108 Readers / 1171 descriptors / 7 packages / 78 routes**.

## Fixes

7.0.2 fixed four defects found by the L1 contract audit, and 7.0.3 adds seven
hardening fixes from the follow-up contract pass:

- `sc_batch_kbet`: require a square graph and matching batch vector before
  indexing.
- `ml_partial_dependence`: validate the feature matrix shape against the
  requested feature index.
- `hic_distance_decay`: reject empty contact sets and guard a zero grand total.
- `isoform_quantification_em`: validate compatibility/count alignment and
  raise `StepError` for inconsistent shapes.
- `fleiss_kappa`: require every subject to contribute the same number of
  ratings.
- `doublet_detect`: require at least 30 cells and two expressed genes before
  invoking scanpy.
- `barplot`: accept a filename without an image suffix by appending `.png`.

The original four fixes are:

- `graph_pseudotime`: clamp `n_neighbors` to `n - 1` so small inputs no longer
  raise `IndexError`.
- `cohens_kappa`: reject non-square count tables with a `StepError` instead of
  letting statsmodels broadcast.
- `fba_flux_balance`: require the bounds row count to equal the reaction count
  before building the LP.
- `pedigree_inbreeding`: detect ancestral cycles and raise `StepError`
  instead of recursing until `RecursionError`.

## Audit scope

`docs/verification/operator-audit-7.0.3.md` records the measured layers:

- L0 static consistency: 1171/1171 PASS.
- L1 contract behaviour: 286 PASS, 41 FAIL, 585 SKIP_DOMAIN, 53 SKIP_FILE,
  26 SKIP_EXTERNAL, 71 SKIP_HARNESS, 1 SKIP_TIMEOUT. Every FAIL records its
  step error; most are unsatisfied domain fixtures, and they are not counted
  as verified.
- L3 route replay: 78/78 bundles import on Studio 3.1.6; 13 routes replay,
  65 SKIP_DATA; generated coverage routes execute for 244 operators; union
  490/1063.
- L2, L4, L5 are partial and explicitly marked as such in the report.

## Compatibility

- `minimum_application` and `build_application`: **3.1.6**
- Protocol: declaration `protocol_version` 3, `protocol_revision` "3.7"
- Bundle: `operon.library` v7.0.3, 1063 operators, 108 Readers
- Verified in a clean Python 3.11 environment with Studio 3.1.6:
  `passed: true`, 95 passed / 2 skipped.
- Full library test suite on the release tree: **3708 passed, 221 skipped, 0 failed** in 39:58 (bp-numpy21, NumPy 2.1.3); skipped cases are
  optional-dependency or platform gates listed by the test runner.

## Assets

The release publishes the Linux and Windows library bundles, the wheel, the
route bundle set, Quickstart, verification JSON, the operator-audit archive
(`Operon-Operator-Audit-v7.0.3.zip`), and `SHA256SUMS.txt`.
