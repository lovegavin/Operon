# Operon Studio 5.1.0

## Highlights

- **Multiple operator libraries coexist.** Every import is an equal-status
  branch under the version-scoped library root (`library/libraries/<name>/`),
  with its own `library.json`, `version.json`, `archive.zip` and
  `operators/<id>.json` metadata. The panel lists every branch; there is no
  active-library pointer. Libraries must not overlap: duplicate
  operator/Reader ids, distribution names or top-level modules are rejected
  with a structured `library_conflict` (HTTP 409).
- **A test fork bundle is published separately** as
  `operon-library-fork1-v0.0.0.operon-library.zip` (package `operon-fork1`,
  operator `fork1_numeric_gini`). Import it with the name `fork1-v0.0.0` next
  to the main library to exercise coexistence.
- **Per-run reproduction skeleton.** Each task folder now contains
  `runs/<job-id>/` with `run.json`, `job.json`, `graph.json`,
  `parameters.json`, `plugins.lock.json` and `logs/README.txt`. `run.json`
  records the libraries and only the operators/Readers used by that run,
  including `code_sha`, `declaration_sha`, `execution_sha` and wheel
  `sha256`.
- **Interface:** `GET /api/libraries`, `POST /api/libraries/install`
  (optional `name`), `DELETE /api/libraries/{name}`; CLI
  `operon library install|list|remove`; MCP `operon_library_install`,
  `operon_library_list`, `operon_library_remove`.

## Compatibility

- `minimum_application` stays 5.1.0 for new bundles; the 8.x bundle format is
  still rejected with a migration message.
- Existing single-library installs migrate to a labelled branch without data
  loss. `bundle_format=1`, `operator_protocol=3`.

## Verification

- Backend focused: `tests/test_run_skeleton.py`,
  `tests/test_library_install_500.py`, `tests/test_library_branches.py`,
  `tests/test_application_library_separation.py` - 36 passed.
- Frontend: `tsc -b` clean; 34 files / 215 tests passed.
- Source-tree CLI acceptance: import main 0.1.0 + `fork1-v0.0.0`, list shows
  two branches; VHH route completes 5/5, export
  `bsa_by_cdr.csv` 457 B sha256
  `faa7bd4fb61868a87751b3474b5f899be8e123741142299a432eda0d62ce2c2e`;
  `runs/<job-id>/` skeleton and per-run provenance present.
