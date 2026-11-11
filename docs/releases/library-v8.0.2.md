# Library 8.0.2

8.0.2 is the coverage and trust-evidence release for the native Operon library.
It keeps the 8.0.1 Studio 4.0.0 registration fixes and adds the missing test and
execution evidence.

## Changes

- Added `tests/test_l2_gap.py` plus two PDB fixtures, closing the last 12 L2
  unit-test gaps (12 passed).
- Measured determinism for 23 more operators; L4 now has 37 measured entries.
- Added per-operator trust sheets for all 1063 operators
  (`docs/operators/<id>.md`, indexed by `docs/operators/README.md`).
- Fixed `ligandmpnn_side_chain_packing` packed-structure discovery; added CSV
  export and result files to both Nucleotide Transformer operators.
- Added per-operator five-layer coverage records
  (`verification/coverage-8.0.1/`), including 223 local executions, 47 server
  executions, and explicit, reproducible SKIPs for four operators.

## Five-layer result

| layer | result |
| --- | --- |
| L1 | 1063 PASS, 0 FAIL, 0 SKIP |
| L2 | 0 SKIP (11 oracle, 8 smoke, 1044 unit) |
| L3 | 270 executed + 789 compiled routes; 4 SKIP with evidence |
| L4 | 37 measured, 1026 estimates; 0 SKIP |
| L5 | 984 installed + 79 route bundles; 0 SKIP |

The four L3 SKIPs are three Boltz operators (no Boltz runtime or weights) and
RFdiffusion (no compatible generic checkpoint; GPU DGL ABI error; CPU timeout
after 1800 s). See `verification/coverage-8.0.1/l3_skips.json`.

## Compatibility

- Operon Studio: **3.1.9 or newer** (native `operon` namespace).
- No `sources/biopipe` entries; seven Operon provider wheels.
- 1063 operators, 108 Readers, 1171 descriptors.

## Testing

- `tests/test_l2_gap.py`: 12 passed.
- `tests/test_library_release.py`: 9 passed.
- Full pytest: **3722 passed, 209 skipped, 0 failed** in 2435.17 s (bp-numpy21, NumPy 2.1.3). The 209 environment-gate skip reasons are listed in `verification/coverage-8.0.1/pytest-8.0.2-skips.txt`.
- Studio UI automation remains an explicit SKIP; bundle install and route
  validation were exercised on Studio 4.0.0.
