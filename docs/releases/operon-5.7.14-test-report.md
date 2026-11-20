# Operon Studio 5.7.14 test report

## Defects

| ID | Operator | Before | After |
| --- | --- | --- | --- |
| F-100 | `gwas_top_hits` | `not enough values to unpack` | `ValueError` naming the row and the required columns |
| F-101 | `structure_hbonds` | `KeyError: 'z'` | message naming the missing element column |
| F-102 | `structure_contacts`, `structure_ligand_geometry_qc`, `structure_ligand_pose_qc` | `TypeError` on `None` | message naming the missing structure field |
| F-103 | eight tree operators | `parent 'n1' of '0' is not a node` | labels and indices are both accepted |
| F-104 | `phylogenetics_jc69_likelihood`, `tree_outgroup_root`, `tree_robinson_foulds` | `trailing newick text ')'` | redundant parenthesis accepted, otherwise positioned error |
| F-105 | two nucleotide-transformer operators | weights message printed a structure path | message reports the weights setting and searched directory |
| F-106 | three GO operators | example path defaults | parameter name and absolute-path request |

## Operator evidence

Each guard was exercised through `tests/test_operator_input_validation.py`
(15 passed) with the same malformed inputs that the coverage sweep produced.
Valid inputs are unchanged: the guards only run when the required field is
absent.

## Coverage

The coverage follow-up recorded in the 5.7.13 report stands: 515 of 1,074
operators have produced a real result (48.0%). This release removes nine
bare-exception paths from that set, so the remaining failures now carry
actionable messages instead of tracebacks.

## Automated checks

- `tests/test_operator_input_validation.py` — 15 passed.
- `tests/test_env_worker_context.py`, `tests/test_environments.py`,
  `tests/test_environment_install.py` — 27 passed.

## Known limitations

- The five environments that have no win-64 builds (hmmer, antismash,
  genomics, hic, rna) remain unavailable on Windows; their 83 blocked
  operators are recorded with the submission error.
- Operators that need a non-core environment cannot run on a machine where
  that environment is not installed, by design.

## Not tested

- Full end-to-end reruns of every remaining failing operator; the next
  coverage pass covers them.
