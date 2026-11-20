# Operon Studio 5.7.14

## Fixed

- **F-100** `gwas_top_hits` raised an unpacking error instead of reporting the
  malformed effect-size row.
- **F-101** `structure_hbonds` raised a bare `KeyError` when an atom lacked an
  element symbol; it now names the missing element column.
- **F-102** `structure_contacts`, `structure_ligand_geometry_qc` and
  `structure_ligand_pose_qc` raised `TypeError` on inputs without coordinates;
  they now explain which structure field is missing.
- **F-103** the Newick loader used by the eight tree operators rejected trees
  whose inner nodes carry labels while leaves carry indices; both conventions
  are accepted.
- **F-104** `phylogenetics_jc69_likelihood`, `tree_outgroup_root` and
  `tree_robinson_foulds` reported a bare `trailing newick text`; the parser now
  accepts a redundant closing parenthesis and reports the offending position
  otherwise.
- **F-105** `nucleotide_transformer_embedding` and
  `nucleotide_transformer_variant_effect` printed a structure path in the
  missing-weights message; the message now reports the weights setting and the
  directory that was searched.
- **F-106** the GO operators (`go_ic_profile`, `go_gene_similarity`,
  `go_term_similarity`) no longer default to example paths; a missing
  `obo_path` or `gaf_path` fails with the parameter name and asks for an
  absolute path.

Every guard raises `ValueError` with the operator name, the missing field and
what to provide, so the run log and the UI both show an actionable message.

## Verification

- `tests/test_operator_input_validation.py` — 15 passed. It calls each guard
  directly and asserts the message names the operator and the missing key.
- Operator registry rebuilt (1,074 operators, 1,183 descriptors).
- Clean install and interface checks are recorded in the test report.

The library is bumped to 1.1.8 because the operator sources changed.
