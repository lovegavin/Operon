# Operon Studio 5.7.15

Released 2026-11-20. Library: `main-v1.1.9`.

## Added

- Nothing new in this release; it is a defect-only patch.

## Changed

- The `core` environment now declares the scientific stack its operators import
  (`pandas`, `scipy`, `scikit-learn`, `statsmodels`, `matplotlib`, `seaborn`,
  `h5py`, `openpyxl`) instead of only the application runtime packages. 987 of
  the 1,074 operators are assigned to `core`, so a fresh installation previously
  failed most of them with `No module named 'pandas'`.
- A step that declares an environment now runs with that environment's `bin`
  directory first on `PATH`, so packaged tools such as `quast`, `antismash` and
  `amrfinder` are found instead of reporting `not on PATH`.

## Fixed

- **F-107** Validation errors rendered as a bare tuple (`('Form', 'orphan encoder
  column.chain')`) are now readable and name the offending column and dimension.
- **F-108** The `core` environment requirements no longer omit the packages the
  assigned operators import.
- **F-109** Environment `bin` directories were missing from `PATH`, which made
  every external-tool step fail even when the tool was installed.
- **F-110** The bridged `Context` lacked `artifact_path`, `out_dir` and a
  populated `memory`, so operators writing files failed with
  `'Context' object has no attribute 'artifact_path'`.

- **F-111** Remote environment snapshots now carry dependency counts: the agent's
  `environment_snapshot` merges `dependency_total`, `dependency_installed` and the
  per-row `installed` flags, so the desktop no longer shows `0/x` for environments
  that are already ready on the server. Binary requirements are also matched with
  the Windows launcher suffixes (`.exe`, `.cmd`, `.bat`).

## Verification

- Clean installation: 5.7.15 installs, reports library `main-v1.1.9`, 18
  environments, 16 resources and 141 MCP tools.
- Unit tests: `tests/test_env_worker_context.py`, `tests/test_environments.py`,
  `tests/test_form_validation_errors.py` and
  `tests/test_operator_input_validation.py` pass.
- Operator coverage is measured on Linux (18/18 environments ready); the Windows
  host cannot install the five bioconda environments, so it is not the reference
  platform for coverage.
