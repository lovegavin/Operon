# Library 7.0.4

7.0.4 targets Studio 3.1.6 and continues the operator conformance audit. The
catalog is unchanged in size: **1063 operators / 108 Readers / 1171
descriptors / 7 packages / 78 routes**.

## Fixes

Six robustness defects found by the L1 contract pass are fixed:

- `sc_leiden_cluster`: require a square cell-by-cell adjacency matrix; a
  rectangular matrix previously let igraph grow the vertex set and produced an
  output whose cluster vector and degree vector had different lengths.
- `tree_consensus`: return a valid empty table instead of a one-dimensional
  array when no shared split is observed.
- `motif_scan_pwm`: keep row labels unique when two sequences share a name, so
  the output Form validates.
- `sc_spatial_variable_genes`: reject count matrices whose column count does not
  match the spatial cell count before the Moran calculation.
- `structure_md_interface_occupancy`: require a non-empty `trajectory_path`
  instead of treating the empty string as the working directory.
- `structure_pocket_detect`: require the structural columns (`resname`, `chain`,
  `residue_number`, `atom_name`, `element`) and report the missing names.

The audit harness now also classifies operators that import torch,
transformers, ESM or OpenMM inside their implementation as `SKIP_EXTERNAL`,
instead of letting an avoidable fixture error look like a failure.

## Audit scope

`docs/verification/operator-audit-7.0.4.md` records the measured layers:

- L0 static consistency: 1171/1171 PASS, 0 failures.
- L1 contract behaviour: 286 PASS, 34 FAIL, 577 SKIP_DOMAIN, 53 SKIP_FILE,
  42 SKIP_EXTERNAL, 70 SKIP_HARNESS, 1 SKIP_TIMEOUT. Negative info-predicate
  checks: 97 pass, 30 fail, 736 not applicable. The 34 failures are listed with
  their exceptions; most are raw `ValueError`/`KeyError` domain preconditions
  that should be converted to `StepError`, and are not counted as verified.
- L3 route replay: 78/78 bundles import on Studio 3.1.6; 13 routes replay,
  65 SKIP_DATA (the templates do not ship their input data); generated coverage
  routes execute for 244 operators; union 490/1063.
- L2: five deterministic operators checked against independent oracles; 5/5
  pass (`l2_oracle.json`). L2, L4 and L5 remain partial and are explicitly
  marked as such in the report.

## Compatibility

- `minimum_application` and `build_application`: **3.1.6**
- Protocol: declaration `protocol_version` 3, `protocol_revision` "3.7"
- Bundle: `operon.library` v7.0.4, 1063 operators, 108 Readers
- Verified in a clean Python 3.11 environment with Studio 3.1.6:
  `passed: true`, 95 passed / 2 skipped.
- Full library test suite on the release tree: **3708 passed, 221 skipped,
  0 failed** in 39:45 (bp-numpy21, NumPy 2.1.3).

## Assets

The release publishes the Linux and Windows library bundles, the route
collection, the quickstart, the wheel, the operator-audit archive
(`Operon-Operator-Audit-v7.0.4.zip`) and `SHA256SUMS.txt`. The audit archive
contains the report, the audit scripts and the raw L0/L1/L2/L3 evidence.
