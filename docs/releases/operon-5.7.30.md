# Operon Studio 5.7.30

5.7.30 ships library 1.1.18, which removes the last network dependency from the
structure operators: an MSA can now be built locally from a downloaded database.

## Library

- **Local MSAs from a downloaded database.** The new `colabfold_msa` resource
  declares the two ColabFold sequence databases (UniRef30 2302, 95.8 GiB, and
  the ColabFold environmental database 2021-08, 109.9 GiB) as downloadable
  units, so the resource panel can fetch them once and link or move them later.
  `_msa_common.build_msa()` runs MMseqs2 against the installed database and
  returns an `.a3m` alignment; `boltz_predict` gained `msa_mode: local`, which
  writes `msa: <alignment>` into the Boltz YAML and stops passing
  `--use_msa_server`, so the run never talks to the ColabFold API.
- **MMseqs2 in the colabfold environment.** The `colabfold` environment now
  declares `mmseqs2`, which provides the `mmseqs` binary the local search needs.
- **Boltz cache defaults to the installed weights** (`boltz_predict`,
  `boltz_complex_confidence`): when `cache_dir` is empty the operators point
  `--cache` at the `boltz` resource root instead of letting Boltz download the
  checkpoints on every run.

## Verification

- `mmseqs createdb` + `mmseqs search` + `mmseqs result2msa --msa-format-mode 6`
  produced a 20-sequence A3M for crambin (1CRN) from a Swiss-Prot database.
- `python -m py_compile` passes for the new helper and the patched operator.
- `python -m operon registry build --scope routes` keeps 1074 operators,
  108 readers and 79 routes with 0 errors.

## Known limits

- The two databases are 205 GiB compressed in total; the panel shows the
  planned bytes before starting a download.
- `boltz_predict` still needs a GPU for practical runtimes; the CPU reference
  path is supported but slow.
- `vina` remains an optional binding (`best_effort`) because no cp311 wheel
  exists, and `prodigal` is built from source.
