# Operon Studio 5.6.1 test report

Date: 2026-11-18. Scope: application 5.6.1 with operator library 1.0.1.

## Builds

| Artifact | Bytes | SHA-256 |
| --- | --- | --- |
| `Operon-Studio-v5.6.1-Windows-x64.zip` | 357,328,520 | `7eda013f5fba45f50f08b3cdf5e55790ef597f0def23a78adbfba3b02f5aed06` |
| `Operon_Setup-5.6.1.exe` | 429,105,877 | `4ab934998471c7099846959affed70f67a2bcefe2ebf616f2883cd708c912a9c` |
| `Operon-5.6.1-Server.zip` | 4,744,768 | `316d5413c797c45276ddab207b4e11195e60add384cd8a77bc53a0fb21c16d87` |
| `operon_studio-5.6.1-py3-none-any.whl` | 991,677 | `c6f191c1db90ea9c74b29e028cc8c45ea8ab98e5c1205cafce236c608a22bedb` |
| `operon-library-main-v1.0.1.operon-library.zip` | 6,946,968 | `49edeb3767482706b1e51f7d4027a6efb3043a05dbba3d0ccadfce5b774924f1` |
| `operon-routes-main-v1.0.1.zip` | 201,314 | `3d9d578cb38275e89ab8d1976a5772f82865ca5f23e246a8eaafd39f144f506e` |

## Clean install

- Installer time: 21 s; version directory `5.6.1-461201b9e3d1`; `/api/version`
  reports `5.6.1 (461201b9)`.
- `/api/libraries`: `main-v1.0.1`, 7 packages, 1,177 descriptors, 1,069
  operators, 108 readers, digest `49edeb37...`.
- `/api/environments`: 18 entries; every entry carries `dependencies`,
  `resources`, `operator_count` and a truncated `operators` list; the counts sum
  to 1,177 descriptors.
- `/api/v1/large-resources`: 16 resources, 16 official units, one per resource;
  `alphafold2` reports the `afdb` unit with nine declared files, all missing on
  a fresh profile.

## Interface parity

- HTTP: `POST /api/resources/{name}/download` accepts `unit`;
  `POST /api/environments/{name}/dependencies/download` installs one declared
  requirement.
- CLI: `operon environment list`, `operon environment status <name>`,
  `operon resources list` run against the installed library; list commands
  accept `--profile` for remote execution.
- MCP: the resource and environment tools keep the same behaviour and accept
  `profile_id` for remote execution.

## User interface

The runtime panel was driven through a headless browser against the installed
build:

- 18 environment cards, one "install all" and one "download all" action.
- Opening an environment shows the two card entries (dependencies, resources).
- The dependency view lists the pinned requirements as cards with individual
  download actions.
- The resource view lists the official unit cards (`afdb`, `ProteinMPNN`, ...)
  with per-unit download and link actions and a group-level download action.
- No console errors were reported during the run.

## Automation

- `pytest tests/test_resource_link.py tests/test_environment_install.py tests/test_environment_api.py tests/test_resource_api.py`
  passes (59 passed, 1 skipped), including the unit download and single
  dependency installation paths.
- `pytest tests/test_environment_install.py tests/test_environment_api_runtime.py tests/test_environment_queue.py tests/test_environment_estimates.py`
  passes (27 passed).
- `pytest tests/test_manifest_registry.py tests/test_registry_maintenance.py`
  reports one pre-existing failure (`test_manifest_only_refresh_discovers_added_source_and_publishes_generation`)
  that also fails on the previous release commit.
- Frontend: `npm test -- --run` passes 43 files / 265 tests.

## Known limitations

- `operon environment status <name>` resolves its argument as a workflow
  directory and therefore reports a missing path for an environment name; the
  list commands are unaffected.
- The disk space guard uses the declared estimate; a download whose real size
  exceeds the estimate is still stopped by the second check against the
  response `Content-Length`.
- `alphafold2` declares no bundled operator, so its card shows zero operators
  until a runner operator is added.

## Not tested

- Downloads on the SSH remote host were not exercised in this cycle; only local
  downloads, unit downloads and dependency installation were verified.
- The installer upgrade path over an existing 5.6.0 installation was not run.
