# Operon Studio 5.7.9 test report

## Scope

- Six-state environment readiness derived from interpreter, error, dependency and
  resource state.
- Durable per-environment logs and their three readers (REST, CLI, MCP).
- Remote retry parity for desktop, remote agent, HTTP, MCP and CLI.
- Per-root installation slots.

## Artifacts

| Artifact | Size (bytes) | SHA256 |
| --- | --- | --- |
| Operon-Studio-v5.7.9-Windows-x64.zip | 357,639,710 | aebf119e5b26114f1325f28acd0de7e18d85aac068a6f933425d17e89ff5610c |
| Operon_Setup-5.7.9.exe | 429,417,069 | 1e045ea19e146ae26477deed561158d3716ff087e7841df177fe7b61222ad472 |
| Operon-5.7.9-Server.zip | 9,856,653 | afa4cff03ff91361fd3647512ca0e82bb874222b2812c79d5f7645e581413990 |
| operon_studio-5.7.9-py3-none-any.whl | 1,004,657 | 97db3599a0a5de9c31b1fb20d1bc2cbb31ecf7e3e1f9b4ee0d9e38088b177795 |
| operon_builtin_library-1.1.5-py3-none-any.whl | 5,774,903 | ee7fe0ebb6d59f3c6fbc09da9778e58a026c0cd9a6832b8dc57f954dae7593ee |
| operon-library-main-v1.1.5.operon-library.zip | 6,998,290 | 6576ea7a4195b2c88f3e948297c809d23e2b6a87118402c2ade1dcb2406ba409 |
| operon-routes-main-v1.1.5.zip | 201,414 | a68df8f08e82eca1e6c8940d4fd65267cfd17d0abd0596eb9bccd0c61a8b62a3 |

Authoritative hashes live in `SHA256SUMS-5.7.9.txt` next to the artifacts.

## Clean install

- Installer: clean install into a fresh root, version directory `5.7.9-d90c97bb0d7c`,
  server ready 38 s after the installer returned, bundle `index-CHP-NLek.js`.
- `/api/version`: `5.7.9 (d90c97bb)`.
- `/api/environments`: 18 entries, each with `interpreter`, `status`, `error`,
  `dependency_total` and `dependency_installed`; `alphafold2` is `missing` with
  dependencies `0/1`, `core` is `missing` on a fresh root.
- `/api/resources`: 16 entries with `present`, `state` and component details.
- Retry: `POST /api/environments/alphafold2/retry` returned 200 in 0.70 s and the
  operation moved to `installing`; `core` retry returned 200 in 0.62 s.
- MCP: 79 tools, including `operon_environment_retry` and `operon_environment_log`;
  the MCP log call returned the same three lines as the HTTP endpoint.
- Durable logs: `core.log` 330 B and `alphafold2.log` 354 B under
  `library/environments/.operon-environment-logs/`.

## Readiness rules

| State | Condition |
| --- | --- |
| 未创建 | status is `missing` and no interpreter exists |
| 未就绪 | interpreter exists but dependencies or resources are incomplete |
| 安装失败 | a stored error is present |
| 准备安装 | the operation is queued |
| 正在安装 | the operation is creating or installing |
| 已就绪 | interpreter exists, dependencies complete and resources present |

## Logging

- `.operon-environment-logs/<name>.log` receives one timestamped line per command
  or output line; the file survives restarts.
- `GET /api/v1/environments/<name>/log?limit=` returns the tail of that file.
- `operon environment log <name> --limit N` and MCP `operon_environment_log`
  return the same content.

## Interface parity

| Action | Desktop | HTTP | MCP | CLI |
| --- | --- | --- | --- | --- |
| prepare | yes | POST /api/v1/environments/prepare | operon_environments_prepare | environment prepare |
| cancel | yes | POST /api/v1/environments/{name}/cancel | operon_environments_cancel | environment cancel |
| retry | yes (local and remote) | POST /api/v1/environments/{name}/retry, POST /api/remote/{key}/environments/{name}/retry | operon_environment_retry | environment retry |
| log | yes | GET /api/v1/environments/{name}/log | operon_environment_log | environment log |
| dependency install | yes | POST /api/v1/environments/{name}/dependencies/download | operon_environment_dependency_install | environment dependency |

## Automated checks

- Backend: `tests/test_environment_install.py`, `tests/test_environment_install_lock.py`,
  `tests/test_environment_api_runtime.py` and `tests/test_resource_fetch.py` pass locally;
  the lock suite covers per-root slots and the stall reader covers carriage-return progress.
- Frontend: 42 files, 265 tests.

## Known limitations

- Resource readiness only covers resources declared for the environment; operators
  that read files from arbitrary paths are not tracked.
- The log file grows without rotation.
- The remote agent must run 5.7.9 for the retry route to exist.

## Not tested

- A remote server older than 5.7.9 (retry returns 404 there by design).
