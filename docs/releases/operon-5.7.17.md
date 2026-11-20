# Operon Studio 5.7.17

## Added

- `POST /api/environments/{name}/repair` (and `operon environment repair <name>`)
  rewrites entry-point shebangs that still point at a staging tree, so
  environments installed by an earlier release keep working.
- Merge linking: `POST /api/v1/large-resources/{name}/link` with
  `{"source": "...", "unit": "...", "replace": true}` now links only the
  declared files that are missing from an existing resource directory and
  leaves files the user already has untouched (`status: "merged"`).

## Changed

- The default `core` runtime declares the analysis packages that the
  core-scoped operators import (`networkx`, `rdkit`, `lifelines`, `anndata`,
  `arch`, `econml`), so those operators no longer fail with a missing module
  after a clean install.

## Fixed

- F-117: pip progress output used `--progress-bar raw`, which the bootstrapped
  pip rejects (`invalid choice: 'raw'`), making every environment installation
  fail; the installer now asks for `--progress-bar on`.
- F-118: shebang rewriting only walked `bin/` and `Scripts/` one level deep and
  skipped already-installed trees; it now recurses and also repairs existing
  environments.
- F-119: `state()` reports the dependency counts for environments that are not
  created yet, so a fresh install shows the full declared dependency list.

## Verification

Clean installation, API checks and the installer action audit are recorded in
`operon-5.7.17-test-report.md`.
