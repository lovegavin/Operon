# Operator audit 8.0.3

8.0.3 is a targeted patch over 8.0.2. The five-layer evidence from 8.0.2 is
retained unchanged in `verification/operator-audit-8.0.3/`; rerunning the full
audit was outside the requested scope (only the modified areas were tested).

## Patch scope

| item | change | verification |
| --- | --- | --- |
| BE-01 | three interface operators declare `openmm>=8.0`, `pdbfixer>=1.9` | `tests/test_interface_contracts.py` |
| BE-02 | `export_results` no longer requires `hictkpy`; Hi-C import is lazy | `tests/test_interface_contracts.py`, export tests |
| BE-06 | five interface outputs declare `statistic` labels, including `cdr_index` | `tests/test_extension257.py`, `tests/test_interface_contracts.py` |

## Targeted result

- Ten test files: **88 passed** in 148.62 s.
- Registry: 1063 operators, 108 Readers, 7 packages, 79 routes, 0 errors.
- Full pytest was intentionally not rerun for this patch.

The 8.0.2 five-layer counts still apply to the unchanged 1058 operators and are
recorded in `docs/verification/operator-audit-8.0.2.md`.
