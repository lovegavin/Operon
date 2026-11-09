# Operon Library 7.0.6

7.0.6 is an audit-evidence correction release on top of 7.0.5. It does not
change operator behavior, routes or the execution protocol.

## Correction

The 7.0.5 route-coverage summary counted `export_results` as an operator and
therefore overstated built-in coverage by one. The corrected numbers are:

| metric | 7.0.5 published | 7.0.6 corrected |
| --- | ---: | ---: |
| operators covered by built-in routes | 246 | 245 |
| operators covered by generated routes | 250 | 250 |
| overlap | 36 | 36 |
| union coverage | 460 / 1063 | 459 / 1063 |
| operators without a passing route | 603 | 604 |

The machine-readable coverage files under
`verification/operator-audit-7.0.5/` and the audit report and 7.0.5 release
note carry the corrected values. `scripts/operator_audit/report_table.py` now
emits a per-operator table split by kind (1063 operators, 108 Readers) so
Readers are no longer mixed into contract pass rates.

## Unchanged

- Library 7.0.5 content: 1063 operators, 108 Readers, 1171 descriptors,
  78 route templates.
- L0 1171/1171 PASS; L1 358 PASS / 0 FAIL; L2 5/5 sampled oracles;
  L4 13/14 sampled deterministic routes.
- Studio 3.1.6 compatibility and the published 7.0.5 bundles.

## Verification

- `python scripts/build_operator_docs.py --check` and registry checks pass.
- Full pytest: 3708 passed, 221 skipped, 0 failed (39:36).
  note and in the release evidence.
- The `Operon-Operator-Audit-v7.0.6.zip` asset contains the corrected report,
  the per-operator table and the raw JSON/JSONL evidence.
