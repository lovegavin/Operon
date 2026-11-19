# Operon Studio 5.7.13

Patch release focused on report-mode operators in the environment bridge and on
actionable column errors for operators that read labelled fields.

## Fixed

- **F-96** Report-mode operators (for example `barplot`) crashed with
  `'Context' object has no attribute 'out_dir'` when executed inside an
  isolated environment. The bridge context now exposes `out_dir` and a
  `memory` view with `run_dir`, `data_dir` and `cache_dir`.
- **F-97** Operators that declare no `output_parameter` (report-only steps)
  failed in the bridge with `KeyError: 'output'`. The bridge now treats a
  missing output as a report value and returns it to the caller.
- Operators that read labelled fields (`circrna_detect`, `rna_editing_detect`)
  and the shared control-column helper (`_b94_common.controls`) raised a bare
  `KeyError` naming only the column. They now raise a message that names the
  dimension and lists the columns that are available.

## Changed

- `go_ic_profile` and `go_gene_similarity` no longer default `obo_path` and
  `gaf_path` to a path inside an example route. The parameters start empty and
  must point at the local Gene Ontology files for the run.

## Verification

- The five operators behind F-96/F-97 and the column-error fixes complete on a
  clean 5.7.12 installation after hot-patching the two bridge modules
  (`barplot` 7.5 s, `describe` 5.8 s, `circrna_detect` 5.3 s,
  `rna_editing_detect` 5.3 s, `propensity_score_matching` 6.3 s,
  `go_ic_profile` 5.2 s, `go_gene_similarity` 5.1 s).
- `tests/test_env_worker_context.py`, `tests/test_environments.py` and
  `tests/test_environment_install.py` pass (27 tests).
