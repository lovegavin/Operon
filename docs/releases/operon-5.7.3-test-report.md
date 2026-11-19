# Operon Studio 5.7.3 test report

Date: 2026-11-19. Scope: every bundled resource declares a download source,
unit-level coverage is reported to the interface, and preparation progress no
longer stops at 99%.

## Builds

| Artifact | Bytes | SHA-256 |
| --- | --- | --- |
| Operon-Studio-v5.7.3-Windows-x64.zip | 357,477,895 | `06f5d919b9824c5538e0b7dda96d37a32fabf3c56f322fe3fcb799d4d7e273bd` |
| Operon_Setup-5.7.3.exe | 429,255,253 | `71bfc9cdce64c3ded9612d68c5f2ecb9c3afc334a998252b44738687133c19a3` |
| Operon-5.7.3-Server.zip | 9,820,844 | `adb91af66cfc0a6f3f45deee8427f20a954edeb1f1bf4dc02734dd6cdb40aad6` |
| operon_studio-5.7.3-py3-none-any.whl | 997,048 | `8950d42d6c0fc265ac4e20fd062b5041c514170fb95a8bbbf4467e33f31185cb` |
| operon-library-main-v1.1.3.operon-library.zip | 6,993,483 | `f1337340d8a909c8fb5e199cf91c1e24919b9128f6dd64636a486b7a8f9a9fb0` |
| operon-routes-main-v1.1.3.zip | 201,389 | `9a5cb56b405cd0cb657c546d7eba90ff8a78c86901c8c6bd6c32dbe90e61dda9` |

## Clean installation

- Installer exit code 0, 21.37 s, version directory `5.7.3-8e85d54cedfb`,
  headless server ready after 28 s on port 5801.
- `/api/version` reports `5.7.3 (8e85d54c)`.
- `/api/libraries` reports `main-v1.1.3` with 1,181 descriptors.

## Behaviour checks

- `/api/resources` returns 16 resources and none is missing a `downloads`
  entry.
- `alphafold2` exposes eight downloadable files and one link-only file
  (`pdb_mmcif/mmcif_files`), with `download_supported: true`.
- The `afdb` unit reports eight downloadable and one undownloadable file.
- `POST /api/environments/prepare` with `{"names": ["openmm81"]}` prepares
  exactly one environment; an unknown field returns 422 and enqueues nothing.
- Progress cards label the phase with a running elapsed time and switch to an
  indeterminate sheen once the download part is complete.

## MCP surface

77 tools. The 5.7.3 additions are `operon_browse` and
`operon_environment_dependency_install`; 5.7.2 added `unit` and `profile_id`
to `operon_resource_download` and three remote library tools.

## Automated suites

- `tests/test_resource_download_units.py tests/test_resource_api.py
  tests/test_environment_api_runtime.py`: 28 passed.
- `tests/test_remote_library.py tests/test_alphafold2_operators.py`:
  24 passed.
- `pytest tests -k mcp`: 17 passed, 1 skipped, 1 pre-existing
  environment-dependent failure in `test_headless_application.py`.
- Frontend: 43 files / 265 tests passed; production build succeeds.

## Known limitations

- `pdb_mmcif/mmcif_files` has no HTTP mirror; the interface reports it as
  link-only and users must link an existing directory.
- The AlphaFold-2 environment is a shell environment: set `runner` and
  `python_executable`, or export `OPERON_ALPHAFOLD2_HOME`.
- `operon environment status <name>` still resolves against a workflow
  directory.

## Not tested

- Long-running downloads of the multi-gigabyte mirrors were not executed in
  this cycle; only URL reachability and the small-file path were verified.
