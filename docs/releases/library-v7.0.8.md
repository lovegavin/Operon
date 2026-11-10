# Operon Library 7.0.8

7.0.8 extends the audit evidence on top of 7.0.7. It adds eleven zero-input
execution routes, brings the independent-oracle sample to thirteen, and records
CLI/HTTP/MCP describe-contract parity. Operator and protocol behaviour is
unchanged from 7.0.7.

## Operator and route changes

`aggregate` previously declared a fixed `[group_dim, other_dim]` output. When
both inputs were `[residue, field]` and the grouping column was `cdr_index`,
the result collapsed to duplicate `[field, field]` dimensions and the runner
rejected the dimension order. The operator now promotes the grouping column to
a new axis when `group_dim == other_dim`: the output is `[cdr_index, field]`,
the grouping column is removed from the measurements, and the remaining
labels are preserved. Distinct-dimension inputs keep their previous behaviour.

The new built-in route `vhh_cdr_quantification` reads the public 1MEL nanobody
structure, computes interface and paratope residues, joins them on the residue
axis, and aggregates buried surface area by CDR index. The template is also
the regression route for the fix.

## Audit coverage update

The generated coverage routes were rebuilt from the expanded L1 fixtures
(24-row inputs, short column names, group/label parameters). This raised the
number of generated templates that both validate and execute:

| metric | 7.0.7 | 7.0.8 |
| --- | ---: | ---: |
| generated templates | 348 | 348 + 94 zero-input |
| static validation OK | 314 | 314 + 89 |
| execution OK | 305 | 305 + 11 |
| built-in route coverage | 247 | 247 |
| overlap | 41 | 41 |
| union coverage | 459 / 1063 | 522 / 1063 |
| operators without a passing route | 604 | 541 |

The L2 sample now contains thirteen independent numeric oracles; 7.0.8 adds
chi-square against `scipy.stats.chi2_contingency` and Fisher exact against
`scipy.stats.fisher_exact`. The zero-input probe generated 94 default-parameter
routes: 89 passed static validation and 11 executed successfully; the rest stop
on structure/affinity paths or model weights and are recorded as SKIP_DOMAIN. The per-operator
table `verification/operator-audit-7.0.8/operator_table.csv` has one row per
catalog entry (1063 operators plus 108 Readers) and splits route replay by
kind. L5 records a four-way entry-point parity sample (direct runner, CLI,
HTTP and MCP) with identical export hashes; Studio and describe consistency
remain unmeasured. L4 keeps the deterministic replay sample and records the
source-mutation finding: the engine does not pin source-file bytes, so a
changed input is re-read instead of rejected. This is documented as a known
limitation, not hidden as a pass.

## Unchanged

- Library 7.0.6 content: 1063 operators, 108 Readers, 1171 descriptors,
  79 route templates.
- L0 1171/1171 PASS; L1 358 PASS / 0 FAIL / 587 SKIP_DOMAIN /
  53 SKIP_FILE / 42 SKIP_EXTERNAL / 22 SKIP_HARNESS / 1 SKIP_TIMEOUT.
- Studio 3.1.6 compatibility and the published library bundles.

## Verification

- `python scripts/build_operator_docs.py --check` and registry checks pass.
- Full pytest: 3720 passed, 209 skipped, 2 failed. Both failures were stale
  `builtin_routes.json` counts after adding the VHH template; rebuilding the
  route index fixed them, and the two affected files then passed 9/9.
- `Operon-Operator-Audit-v7.0.8.zip` contains the updated report, the
  per-operator table and the raw JSON/JSONL evidence.
