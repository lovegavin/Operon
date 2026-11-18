# Operon Studio 5.5.1 test report

Drafted 2026-11-18. Application 5.5.1, operator library main-v0.1.29.

## Scope

This report records the verification performed for Operon Studio 5.5.1 on
Windows. The release changes the environment preparation pipeline, the runtime
status panel, and large-resource linking, so the acceptance run concentrates on
those surfaces: clean installation, the headless desktop API, the preparation
queue and cancellation, resource linking, the MCP tool surface, and the frontend
build. It is a test record rather than release notes: each phase states what
ran, what was measured, and where the evidence lives.

| Surface | What was exercised |
|---|---|
| Installation | silent installer, version directory, server start, `/api/version` |
| Desktop API | `/api/version`, `/api/bootstrap`, `/api/libraries`, `/api/environments`, `/api/resources`, `/api/v1/capabilities` |
| Preparation queue | size-ordered serial start, `queued` state, positions, cancel while queued, cancel while running, queue advancement |
| Resources and linking | link, repeat link, unlink twice, re-link; unknown remote profile on HTTP and MCP |
| MCP | handshake, 71 tools, resource tool inventory, unknown job and unknown profile rejections |
| Frontend | `npm run build`, `npm test`, `tsc -b`, bundled assets, headless browser smoke test |
| Backend | targeted environment/resource/remote/bridge/control suites, full suite for regression comparison |

Build under test: application 5.5.1, operator library main-v0.1.29, sha256
`9de0ac44a71997b2ef146de86b164a2c5045568f46e042ad504d3588caa96ea2`, 6,924,765
bytes, 7 packages, 1,069 operators, 108 readers, 1,177 descriptors.

## Environment under test

| Item | Value |
|---|---|
| Host | `DESKTOP-AUKHPNK`, AMD Ryzen 7 7700 (8 cores), 63.2 GiB RAM |
| OS | Windows 11 Pro 10.0.26200 (build 26200), 64-bit |
| Authoring host | WSL2 Ubuntu 24.04.4 LTS, kernel 6.18.33.2-microsoft-standard-WSL2 |
| Python, installed product | 3.11.18, bundled runtime `current\runtime\python\python.exe` |
| Python, backend suite | 3.12.14, `operon` conda interpreter |
| Installer | `Operon_Setup-5.5.1.exe`, silent mode |
| Install root | a disposable directory outside the source tree; version directory `versions\5.5.1-<short build>` |
| Desktop API | `http://127.0.0.1:5769` |
| MCP transport | stdio, `-I -m operon ... mcp --allow-run --allow-plugins` |
| Evidence directory | one JSON file per probe, written next to the installer output |

The four Windows artifacts of this build and their sizes and SHA-256 values are
recorded in `SHA256SUMS-5.5.1.txt`, which is published next to the downloads.
The library and route artifacts are unchanged from 5.5.0:

| Artifact | Bytes | SHA-256 |
|---|---:|---|
| Operator library bundle `main-v0.1.29` | 6,924,765 | `9de0ac44a71997b2ef146de86b164a2c5045568f46e042ad504d3588caa96ea2` |
| Route collection `main-v0.1.29` | 201,489 | `de55edc34741d0d7e3d3dc9bb6b94e56130892ea1777fb3dfaadac82c184af11` |

## Results by phase

### Phase 1 - Clean installation

The silent installer created a fresh install root in about 20 s; clean installs of
this build recorded 20.3 s, 20.2 s and 22.3 s. The managed layout recorded a
version directory named `5.5.1-<short build>` under `versions\`, the launcher
started the headless server on port 5769, and `/api/version` answered:

```json
{"version": "5.5.1", "build": "<short build>", "display": "5.5.1 (<short build>)"}
```

The non-empty-directory notice and the flat desktop layout are unchanged from
5.5.0 and were re-exercised there (`[1%] 提示: ... 已有其他内容, 本次安装到 ...`).

### Phase 2 - API surface

| Endpoint | Result |
|---|---|
| `/api/bootstrap` | 5,070,441 bytes of JSON (about 5.07 MB), session token present |
| `/api/version` | `5.5.1` with the build hash that names the installed version directory |
| `/api/libraries` | one library `main-v0.1.29`, sha256 `9de0ac44...`, 7 packages, 1,069 operators, 108 readers, 1,177 descriptors |
| `/api/environments` | 7 environments, each with `expected_bytes`; 7 recorded operations |
| `/api/resources` | 16 resources, 7 with `downloads`, 16 with `expected_files`, 18 `used_by` entries, 80 `link_roots` |
| `/api/v1/capabilities` | `api_version` 1, `operator_protocol` 3, `headless` false, capability list present |

Expected sizes reported by `/api/environments`, in the order the queue uses them:

| Environment | `expected_bytes` |
|---|---:|
| openmm81 | 145,000,000 |
| esmfold | 2,100,000,000 |
| antifold | 2,200,000,000 |
| colabfold | 2,600,000,000 |
| openfold | 3,100,000,000 |
| boltz | 3,900,000,000 |
| esm3 | 5,400,000,000 |

### Phase 3 - Preparation queue

A single `POST /api/environments/prepare` with an empty body answered `200` and
queued all seven environments in ascending order of expected size; `prepared`
reported openmm81, esmfold, antifold, colabfold, openfold, boltz, esm3 in that
order. Immediately afterwards exactly one entry was `installing`
(`running = ["openmm81"]`) and the remaining six reported `queued` with
consecutive `queue_position` values 1-6 (esmfold, antifold, colabfold, openfold,
boltz, esm3). No staging failure appeared in the server log.

### Phase 4 - Cancellation

| Action | HTTP | Observed result |
|---|---|---|
| Cancel queued `esm3` | 200 | operation `cancelled`, environment back to `missing`, positions compacted |
| Cancel running `openmm81` | 200 | environment fell back in 1.3 s, progress `phase: "cancelled"` / `detail: "cancelled by user"`, queue started `esmfold` 2.2 s later |
| Final state | - | all 7 environments `missing`; all 7 operations `cancelled` |

Both cancellation paths return 200; the 500 recorded against an earlier
candidate (F-17) no longer reproduces.

### Phase 5 - Resource linking

The local round trip on an existing checkout:
`link` answered `already_linked` (leftover from an earlier candidate),
`unlink` answered `200` with `mode: "junction"`, a second `unlink` answered `200`
with `mode: null`, and `link` again answered `200` with `status: "linked"`.
`/api/resources` then reported `present: true`, `status: "ok"`,
`linked: true`, `mode: "junction"`, `size_bytes: 2060` for `proteinmpnn`.

Remote dispatch rejects an unknown profile with `404` and the message
`找不到服务器连接配置。` on `GET`, `POST` and `DELETE`
`/api/remote/nosuchprofile/resources[/{name}/link]`.

### Phase 6 - MCP surface

| Probe | Result |
|---|---|
| `serverInfo` | `{"name": "Operon", "version": "5.5.1"}` |
| Tool inventory | 71 tools |
| Resource tools | `operon_resource_cancel`, `operon_resource_download`, `operon_resource_link`, `operon_resource_log`, `operon_resource_unlink`, `operon_resources` |
| Unknown job id | `Error executing tool operon_job: unknown job or resource operation: 0` |
| Unknown job results | `Error executing tool operon_result_files: unknown job: 0` |
| `operon_resources(profile_id="nosuchprofile")` | `404` surfaced as `找不到服务器连接配置。` |
| `operon_resource_link(..., profile_id="nosuchprofile")` | `404` surfaced as `找不到服务器连接配置。` |
| Local `operon_resources` | returns the installed library record `main-v0.1.29` |

The unknown-profile probes previously reached `404 Not Found` and
`405 Method Not Allowed` because the agent bridge lacked the routes (F-18); both
now reach the remote manager and return its message.

### Phase 7 - Frontend

`npm run build` produced `dist/assets/index-Jccm5CPR.js` (872,828 bytes),
`flow-ETaHuzwz.js` (192,934 bytes) and `index-CxNXcA-j.css` (126,653 bytes); the
entry bundle contains the literal `5.5.1`, no developer drive paths, and no
unsubstituted `{n}` placeholder. `npm test` passed 42 files / 261 tests and
`tsc -b` passed. The bundle carries the four environment states, the
queue-position badge, the determinate progress bar from
`progress.bytes / expected_bytes`, the used-by dropdown with a substituted count,
and the link dialog that lists linkable resources and accepts a local or remote
target.

A headless browser smoke test (Microsoft Edge 157 via the DevTools protocol,
viewport 1440x900) opened the running application and confirmed: the header shows
`5.5.1`; the runtime-status panel lists 7 cards, all in the 未安装 state with the
未安装 chip, no progress bar, and the 刷新 / 全部安装 actions; the settings page
lists 16 large resources with one linked badge; the link dialog offers 16
linkable resources, a host selector holding only the local target while no remote
server is connected, the first allowed root as the default path, and closes
without console or body errors. Screenshots were captured for the status panel
and the link dialog.

### Phase 8 - Backend suites

| Suite | Result |
|---|---|
| Environment/resource/remote/bridge/control suites (11 files) | 77 passed, 1 skipped, 45.80 s |
| Same selection before F-18 | 94 passed, 1 skipped, 54.69 s |
| `test_environment_install`, `test_environment_api_runtime`, `test_environment_queue`, `test_environment_estimates` | 24 passed, 40.41 s |
| `test_environment_install`, `test_environment_api_runtime`, `test_environment_queue` after F-17 | 20 passed, 38.79 s |
| `test_environment_api_runtime`, `test_environment_install` after the used-by cap change | 17 passed, 26.13 s |
| `test_environment_estimates`, `test_environment_queue`, `test_remote_resources` | 12 passed, 13.92 s |
| `test_bridge_remote_resources` | 2 passed, 0.57 s |
| Full suite | 97 failed, 4,723 passed, 282 skipped, 10 errors in 3,485.62 s (5,112 collected) |

The full suite was executed on this tree with the repository interpreter. It
collected 5,112 tests; the same command collected 5,081 during 5.5.0
acceptance, the difference being the tests added in this release. The failures
and errors cluster in suites that need optional packages (`lightgbm`, `econml`,
`xgboost`, `hdbscan`, `numba` on NumPy <= 2.1), a reachable SSH target
(`test_remote*`, `test_remote_cache_*`, `test_remote_handshake`), the repository
git history (`test_library_branches`, `test_b92`, `test_v3_studio_integration`),
the historical route fixtures (`test_extension*`), and the repository hygiene
checks (`test_portability`, `test_docs_links`, `test_reference_docs`). No test
file that covers a module changed in this release failed; those suites are the
rows above and they all pass.

## Defects found and fixed in this release

| Id | Symptom | Root cause | Fix |
|---|---|---|---|
| F-11 | five of seven environments failed with `[WinError 5] Access is denied` | six parallel preparations raced to replace the shared micromamba executable | process lock, retry with backoff, reuse of an installed executable |
| F-12 | "disk usage" row blank before install | value computed from the final directory only | `missing`, in-flight bytes, or measured size |
| F-13 | used-by list clipped to one line with an ellipsis | single-line `text-overflow` rule | collapsible dropdown; API cap raised from 8 to 64 |
| F-14 | failed cards showed only the word "failed" | recorded error neither returned consistently nor rendered | error surface plus rendered summary |
| F-15 | cancelling a queued environment left it queued | cancellation only handled running entries | queued entries are removable and positions compact |
| F-16 | a stalled download froze the whole queue | blocking `urlopen` + `copyfileobj`, no cancellation, no deadline | 1 MiB chunks with cancellation checks and a 420 s deadline; cancellation writes a `cancelled` progress state |
| F-17 | cancelling a running environment returned HTTP 500 | progress helper called with `name, progress, root` against `name, root, value` | call order fixed, regression test added |
| F-18 | MCP resource tools with `profile_id` answered 404/405 | agent bridge lacked the remote resource routes | three routes forward to the remote manager, regression test added |
| F-19 | the status card printed `{n} 个算子` instead of a number | the translation template expects `{n}` but the call passed `count` | the matching name is passed and a render test asserts the substituted number |
| F-20 | a cancelled environment could still be reported as `failed` with `[WinError 5]` | the request thread and the worker wrote the progress file through the same fixed temporary name | thread-unique temporary files with retries, a recorded cancellation is never replaced by a failure, and the stale error file is removed |

## Defects found and not fixed

| Id | Symptom | Status |
|---|---|---|
| D-01 | `verify_code` hashes the registered wheel copy while execution uses the unpacked tree | pre-existing, unrelated to this release |
| D-02 | the MCP layer flattens every failure into `Error executing tool <name>: <text>` | pre-existing; the text now carries the server message |
| D-03 | on Windows, deleting a staging tree immediately after cancellation can fail on open handles | mitigated by the sweep at the next preparation |

## Not tested

- Linking through a real remote SSH profile: no reachable profile was configured
  during acceptance, so the remote paths were exercised through unit tests and
  through the `404` rejection path only.
- Preparation of a multi-gigabyte environment to completion: the queue and
  cancellation were measured on openmm81 (145 MB); larger environments were
  cancelled instead of downloaded in full.
- Manual visual review of the panels: the headless screenshot pass checks text,
  state and structure, not typography or spacing on other viewport sizes.

## Verification commands

```
# install
Operon_Setup-5.5.1.exe --quiet --install-dir <stage> --no-register --result <evidence>\install-result.json

# queue and cancellation acceptance
python features551f.py                 # writes <evidence>\features551.json

# API surface
python api551b.py                      # writes <evidence>\api551.json

# resource linking
python linkprobe3.py                   # writes linkprobe.json

# MCP handshake and rejection probes
runtime\python\python.exe mcpnod4.py   # writes <evidence>\mcpcheck.json

# headless UI smoke test
runtime\python\python.exe ui551b.py    # writes <evidence>\ui551.json

# backend suites
python -m pytest tests/test_environment_install.py tests/test_environment_api_runtime.py tests/test_environment_queue.py tests/test_environment_estimates.py -q
python -m pytest tests -q --basetemp=/tmp/pt551

# frontend
npm.cmd run build && npm.cmd test && npx tsc -b
```
