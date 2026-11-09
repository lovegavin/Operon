# Operon Library 7.0.7

7.0.7 is an audit-evidence release on top of 7.0.6. It does not change
operator behavior, route templates or the execution protocol.

## Audit coverage update

The generated coverage routes were rebuilt from the expanded L1 fixtures
(24-row inputs, short column names, group/label parameters). This raised the
number of generated templates that both validate and execute:

| metric | 7.0.6 | 7.0.7 |
| --- | ---: | ---: |
| generated templates | 293 | 348 |
| static validation OK | 259 | 314 |
| execution OK | 250 | 305 |
| built-in route coverage | 245 | 245 |
| overlap | 36 | 41 |
| union coverage | 459 / 1063 | 509 / 1063 |
| operators without a passing route | 604 | 554 |

The L2 sample now contains eleven independent numeric oracles (adds Cohen's
kappa, Sobel gradient, genotype call rate, z-score standardisation, min-max
scaling and a one-sample t-test), all passing. The per-operator
table `verification/operator-audit-7.0.7/operator_table.csv` has one row per
catalog entry (1063 operators plus 108 Readers) and splits route replay by
kind. L5 records a four-way entry-point parity sample (direct runner, CLI,
HTTP and MCP) with identical export hashes; Studio and describe consistency
remain unmeasured. L4 keeps the deterministic replay sample and records the
source-mutation finding: the engine does not pin source-file bytes, so a
changed input is re-read instead of rejected. This is documented as a known
limitation, not hidden as a pass.

## Unchanged

- Library 7.0.6 content: 1063 operators, 108 Readers, 1171 descriptors,
  78 route templates.
- L0 1171/1171 PASS; L1 358 PASS / 0 FAIL / 587 SKIP_DOMAIN /
  53 SKIP_FILE / 42 SKIP_EXTERNAL / 22 SKIP_HARNESS / 1 SKIP_TIMEOUT.
- Studio 3.1.6 compatibility and the published library bundles.

## Verification

- `python scripts/build_operator_docs.py --check` and registry checks pass.
- Full pytest: 3708 passed, 221 skipped, 0 failed.
- `Operon-Operator-Audit-v7.0.7.zip` contains the updated report, the
  per-operator table and the raw JSON/JSONL evidence.
