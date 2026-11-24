# Operon library 1.2.0

Released 2026-11-24. Built for Operon Studio 5.8.0.

## Added

- `ValuesReader` (`values`, `vals`): a one-dimensional reader for numeric
  vectors, which is what `diversity_simpson` and `numeric_gini_coefficient`
  consume.
- A per-unit `files` declaration and per-unit `path` for resources whose
  provider publishes a directory tree (the nine AlphaFold-2 units).
- `colabfold_msa` resource (`uniref30_2302`, `colabfold_envdb_202108`) and the
  local MSA path in `boltz_predict` (`msa_mode=local`) and `colabfold_predict`,
  built with `mmseqs createdb/search/result2msa` so no network access is needed
  at run time.

## Changed

- `device` defaults to `auto` in 47 operator schemas, resolved at run time
  against the interpreter that executes the step.
- `environments.json` pins `jaxlib 0.4.23+cuda12.cudnn89` (JAX CUDA-12 index),
  `cuda-cudart=12.2`, `cuda-cupti=12.2` for `alphafold2` and `colabfold`;
  `vina310` (Python 3.10) carries the Vina bindings.
- `alphafold2` drives the stock `run_alphafold.py` with the flag set the 2.3.1
  release actually accepts (`--db_preset`, `--run_relax`, `--use_gpu_relax`, the
  eight `*_database_path` values, `--template_mmcif_dir`,
  `--obsolete_pdbs_path`).

## Fixed

- Resource unit file lookup, label decoding through the reader encoder that ships
  with the package, isolated step workers reading the reader table, external
  tool resolution, DSSP wiring and ligand handling, and the Hi-C TSV import.
