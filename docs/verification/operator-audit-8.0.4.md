# Operator audit 8.0.4

8.0.4 is a contract-correctness patch over 8.0.3. The five-layer evidence from
8.0.3 is retained in `verification/operator-audit-8.0.4/`; the patch was
verified with the focused composition, interface, release, and route-parameter
tests rather than a full audit rerun.

## Patch scope

| item | change | verification |
| --- | --- | --- |
| composition labels | five 2-D outputs now declare their `statistic`/`score` labels | `tests/test_contract_compositions.py`, `tests/test_interface_contracts.py` |
| dependency ownership | three MD operators declare `numpy>=1.24`, `scipy>=1.10`; `structure_openmm_energy` declares `openmm>=8.0`, `pdbfixer>=1.9` | `tests/test_contract_compositions.py` |
| real composition | every declared dimension runs `JoinStep`; every second-dimension label runs `AggregateStep` | `tests/test_contract_compositions.py` |
| dynamic exceptions | three PRS operators are allowlisted with a reason and a staleness test | `tests/test_contract_compositions.py` |
| standard | L1 ninth check, sections 4.1/4.2, stricter release gate | `docs/verification/five-layer-test-standard.md` |

## Targeted result

- Composition + interface + release + route-parameter tests: **37 passed**.
- Registry: 1063 operators, 108 Readers, 7 packages, 79 routes, 0 errors.
- `git diff --check`: clean.
- Full pytest was not rerun for this metadata-and-test patch; the last full run
  is the 8.0.3 record (3722 passed, 209 skipped, 0 failed).

## Bundle verification

- Studio 4.0.7: `passed: true`, bundle `99a677b2…`, 95 passed,
  2 skipped, 7 deselected, 1063 operators, 108 Readers.
- Bundle SHA-256 and the application record are in
  `verification/operator-audit-8.0.4/application-4.0.7.json`.
