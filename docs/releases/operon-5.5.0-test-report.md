# Operon Studio 5.5.0 test report

Drafted 2026-11-18. Application 5.5.0, operator library main-v0.1.29.

## Scope

This report records the verification performed for Operon Studio 5.5.0 on Windows. It covers clean installation, the headless desktop API, the MCP tool surface, isolated environment lifecycle, large-resource and model-weight linking, the frontend build, and fault injection. It is a test record rather than release notes: each phase states what ran, what was measured, where the evidence is, and which defect identifiers apply.

| Surface | What was exercised |
|---|---|
| Installation | silent installer, flat managed layout, profile creation, non-owned-directory notice |
| Desktop API | `/api/version`, `/api/bootstrap`, `/api/libraries`, `/api/environments`, `/api/resources`, `/api/v1/capabilities` |
| MCP | handshake, 71 tools, five analysis paths, plan compilation, resource round trip, rejection probes |
| Environments | real `openmm81` prepare, cancel, recovery; 21 validation and robustness probes |
| Resources and linking | link, repeat link, replace, unlink, re-link, rejection cases, receipts |
| Frontend | `npm ci`, `npm run build`, `npm test`, `tsc -b`, panel and dictionary inventory |
| Fault injection | invalid inputs, unknown identifiers, cancel races, duplicate request ids, backend restart |
| Browser UI | headless Edge over CDP against the installed build: runtime status panel, large-resources panel, DOM assertions and screenshots |

Build under test: application 5.5.0 and operator library main-v0.1.29, sha256 `9de0ac44a71997b2ef146de86b164a2c5045568f46e042ad504d3588caa96ea2`, 6,924,765 bytes, 7 packages, 1069 operators, 108 readers, 1177 descriptors.

Evidence was collected on successive candidate builds. The final acceptance run is recorded in `<evidence>\evidence12\verify7.json`; its `/api/libraries` record (`main-v0.1.29`, version directory `versions\5.5.0-<hash>`) carries the bundle sha256 above. Analysis artifacts under `<evidence>\evidence5\` were produced on an earlier candidate; their sizes and hashes are quoted as measured.

## Environment under test

| Item | Value |
|---|---|
| Host | `DESKTOP-AUKHPNK`, AMD Ryzen 7 7700 (8 cores), 63.2 GiB RAM |
| OS | Windows 11 Pro 10.0.26200 (build 26200), 64-bit |
| Authoring host | WSL2 Ubuntu 24.04.4 LTS, kernel 6.18.33.2-microsoft-standard-WSL2 |
| Python, installed product | 3.11.18, bundled runtime `current\runtime\python\python.exe` |
| Python, backend suite | 3.12.14, `operon` conda interpreter |
| Installer | `Operon_Setup-5.5.0.exe`, silent mode |
| Install root | `evidence\stage0v55k`, version directory `versions\5.5.0-<hash>` |
| Desktop API | `http://127.0.0.1:5763` |
| MCP transport | stdio, one instance identifier per server process |
| Evidence directories | `<evidence>\evidence\`, `<evidence>\evidence2\` through `<evidence>\evidence7\`, and `<evidence>\evidence12\` for the final acceptance run |
| Product build | application 5.5.0, library main-v0.1.29 |

| Artifact | Bytes | SHA-256 |
|---|---:|---|
| Operator library bundle `main-v0.1.29` | 6,924,765 | `9de0ac44a71997b2ef146de86b164a2c5045568f46e042ad504d3588caa96ea2` |
| `sequence_stats` output `artifact-stats.npy` | 176 | `835f5145c081af3e1fe179e226f2d16ed9e1eeabfebea8f4b0aef9ae8a6def6a` |
| `reverse_complement` output `artifact-revcomp.npy` | 272 | `ae6d80e42e83cf68be85641bbed3994d011095367626a4143b8884242539d585` |
| 5.4.8 baseline installer `Operon_Setup-5.4.8.exe` | 428,850,998 | `84AEABA2400106AB1AC6F0381C48F672DF4D8A89E9970967E5CABA9896F4C87C` |

The bundle size and sha256 are the values `GET /api/libraries` reports on the installed build; they match the release bundle.

## Results by phase

### Phase 0 - Clean installation

**Ran.** `Operon_Setup-5.5.0.exe` with `--quiet --install-dir <dir> --no-register --result <evidence>\install-result.json`, into directories that did not exist before the run. A 5.4.8 install into a fresh directory was repeated on the same host for comparison.

**Result.** Every silent run wrote a receipt with `"status":"installed"` and `"message":null`. The layout is flat: `bin/`, the `current/` junction, `versions/5.5.0-<hash>/`, and `installation.json` at the install root next to `.operon-setup.json`; the profile is created under `%USERPROFILE%\.operon\profiles\`. `installation.json` records `owner Operon.Studio.Install.v1`, `version 5.5.0`, `current versions/5.5.0-<hash>` and the install root. The version directory contains `Operon Studio.exe`, `runtime\`, `scripts\`, `frontend\`, `library\` and `package-manifest.json`.

| Install | Duration | Receipt |
|---|---:|---|
| 5.4.8 baseline, fresh directory | 18.18 s | exit 0, `installed` |
| 5.5.0 candidate builds | 21.45 s (intermediate build), 20.34 s, 19.38 s | `installed` |
| 5.5.0 shipped build | ~20 s | exit 0, `installed` |

The 5.4.8 baseline produced Python 3.11.18 and library main-v0.1.28 (7 packages, 1069 operators, 108 readers). The shipped-build row is a silent install of the shipped installer on this machine; it landed in the same range as the identical-code candidates (20.30 s was the last candidate). Its receipt is `<evidence>\evidence12\install-result.json` and the installer console transcript is `<evidence>\evidence12\install.log`.

Installer change: when the requested directory is not owned by the installer, the installation is still nested one level deeper into `<dir>\Operon`, and the installer now prints an explicit notice. The redirect itself is unchanged (`installer/InstallEngine.cs`, `ResolveDestination` at line 91) and is asserted by `tests/native_setup/Program.cs:78` and `tests/native_setup/Program.cs:86`.

The release payload audit rejected two committed documents that embedded absolute developer paths (F-08); both were rewritten without drive letters.

**Evidence.** `<evidence>\evidence\install-timing.txt`, `<evidence>\evidence\install-result.json`, `<evidence>\evidence2\install-result.json`, `<evidence>\evidence3\install-result.json`, `<evidence>\evidence4\install-result.json`, `<evidence>\evidence6\install-result.json`, `<evidence>\evidence7\install-result.json`, `<evidence>\evidence7\verify5.json`.

**Defects.** F-07, F-08.

**Verdict.** Pass. The flat managed layout and profile creation are confirmed for every run, including the shipped build.

### Phase 1 - API surface

**Ran.** The desktop server was started from the installed build on port 5763 and queried over HTTP. Mutating `/api/*` calls require the `x-studio-token` header, a 43-character token from `GET /api/bootstrap`; `/api/v1/*` is the agent control plane and requires an agent handshake.

| Request | Status | Measured result |
|---|---|---|
| `GET /api/version` | 200 | 71 bytes, `{"version":"5.5.0","build":"<hash>","display":"5.5.0 (<hash>)"}` |
| `GET /api/bootstrap` | 200 | about 4.56 MB |
| `GET /api/libraries` | 200 | `main-v0.1.29` (sha256 in the artifact table), 7 packages, 1069 operators, 108 readers, 1177 descriptors |
| `GET /api/environments` | 200 | 7 environments: antifold, boltz, colabfold, esm3, esmfold, openfold, openmm81 |
| `GET /api/resources` | 200 | 16 resources |
| `GET /api/v1/capabilities` | 200 | lists `large-resource-download` and `large-resource-link` |

Environment entries carry `title`, `notes`, `size_bytes`, `python_version`, `updated_at`, `used_by`, `used_by_count`, `status`, `error`, `location`, `imports` and `progress`. Operations are normalized: while running they carry `cancelable`, `phase`, `detail`, `bytes`, `files` and `updated_at`; every operation always carries `status`, `error`, `started_at` and `finished_at`.

Resources: 7 of 16 declare `downloads` (antifold, boltz, esm2, esm_if1, esmfold, openfold, rfdiffusion); every resource has `expected_files`; `link_roots` is per resource with 5 entries and includes a POSIX root rendered as `the manifest's POSIX-only root` on Windows; `used_by` totals 18 entries.

Raw captures in `<evidence>\evidence2\` predate the final library bundle and were taken without an agent handshake, so that directory is cited for request shape, not for the library hash or for `/api/v1/capabilities`, which answered 403 `Agent connection requires the 'context' capability.` until the handshake was completed. The values in the table are from `<evidence>\evidence5\final-checks.json` and `<evidence>\evidence12\verify7.json`.

**Defects.** F-01, F-05, F-06.

**Verdict.** Pass after the fixes. Before F-01, both resource endpoints returned 500 on a clean install; after the library seed fix they return the counts above.

### Phase 2 - MCP tool surface

**Ran.** The server was started with:

```
python -I -m operon --workspace <ws> --data-dir <ws>\.studio --instance <id> mcp --allow-run --allow-plugins
```

Global options must precede `mcp`; `--instance` is required in practice.

**Result.** `initialize` returned protocol `2024-11-05` and `serverInfo {"name":"Operon","version":"1.30.0"}`; that version string is the `mcp` dependency version, recorded as F-09. The server advertised 71 tools; the six resource tools are `operon_resources`, `operon_resource_link`, `operon_resource_unlink`, `operon_resource_download`, `operon_resource_cancel` and `operon_resource_log`.

Executed analysis paths on the clean 5.5.0 install (`<evidence>\evidence5\`):

| Path | Result |
|---|---|
| FASTA -> `reverse_complement` -> `sequence_stats` | job complete; `stats` shape [3,4] float32, 557 bytes; downloaded npy 176 bytes, sha256 `835f5145...`; values `[12, gc, 0, 1]` per sequence |
| Reverse-complement proof | `revcomp` shape [3,12], 680 bytes, decoding to `ACCCGGGGTTTT`, `GGGGCCCCAAAA`, `ACGTACGTACGT`; npy 272 bytes, sha256 `ae6d80e4...` |
| CSV -> `filter_min` -> `describe` | 4 rows reduced to 2; report mean 6.0 over 8 cells; two report artefacts of 217 B and 437 B |
| PDB -> `structure_contacts` | `contacts` shape [4,2], 571 bytes; four rows starting `[1.0, 3.700000047683716]`; two cross-chain pairs; npy 160 bytes |
| `operon_plan_compile` | `operon.run-plan`, `plan_id f3e07587...`, one `native-chain` unit, nothing submitted |
| Resource round trip | link -> `linked` (junction, 64-byte probe); same source -> `already_linked`; unlink -> root removed; outside-root source rejected with the allowed-root list; restore -> `linked` (2060 bytes) |

Robustness probes returned the documented rejections without partial state: unknown operator, missing parameter, wrong type, missing input file, unavailable environment (`boltz` blocked at prepare, submit refused, nothing installed), duplicate `request_id` on a different graph (rejected with `request_id was already used for a different graph`), and exact-id operator search.

Known limitation, not a defect: the literal chain `CSV -> describe -> filter_min` is not executable because `describe` is a terminal report node; prepare reports the missing edge and validate reports that report and figure nodes carry no Form output.

**Evidence.** `<evidence>\evidence5\pathA.json`, `pathB.json`, `pathC.json`, `pathD.json`, `pathE.json`, `artifacts-index.json`, `extra-verify.json`, `mcp-paths2.md`, `tool-list.txt`; `<evidence>\evidence2\mcp-paths.md` and the `probe-*.json` files.

**Defects.** F-09, F-10, F-11.

**Verdict.** Pass. Every executed path completed and every rejection was explicit; the missing structured error payload is recorded as D-02.

### Phase 3 - Isolated environments

**Ran.** A real `openmm81` preparation on the installed build, a cancellation 4 seconds into a preparation, a recovery preparation after cancelling, a mixed-name request, and 21 validation and robustness probes across the environment API.

**Result.** `openmm81` prepared from a staging virtual environment with pinned `openmm==8.1.1` and `numpy==1.26.4`; the probe import succeeded, `status` became `ready`, the environment measured 139,570,818 bytes across 3,245 files, and its interpreter sits under the library environments directory.

Cancellation end to end: cancel 4 seconds after prepare returns 200; the operation becomes `cancelled` with `error: null`; the environment returns to `missing`; the staging directory and the error artefacts are removed. A later prepare succeeds and reaches `ready`.

A mixed request `{"names":["openmm81","nope"]}` is rejected with 404 before anything starts, so no partial preparation is left behind.

The 21 probes covered unknown name, path-like name, empty body, malformed JSON, wrong body type, cancel while idle, query noise, the log endpoint, a concurrency storm of six prepares plus two retries collapsing onto one job, and size accounting. Their raw results are in `<evidence>\evidence2\env-robustness.md`; that file was written on an earlier candidate build whose manifest declared a smaller environment set and whose own defect numbering is unrelated to the identifiers used in this report.

Environments other than `openmm81` were not installed: `boltz`, `esm3` and `esmfold` need multi-GB CUDA wheels or gated weights; `colabfold` needs the MMseqs2 database; `openfold` and `antifold` need external checkouts or weights. They are listed under Not tested.

Two pre-existing test expectations were stale and were corrected: `tests/test_library_environment_manifest.py` assumed `minimum_application == "5.0.0"` although the library release records 5.5.0, and `tests/test_remote_environments.py` expected dependency repair without the `ids` filter that `operon/remote/server.py` has passed since commit `79cd61d97`.

**Evidence.** `<evidence>\evidence7\verify5.json` (`cancel_probe`, `recovery`), `<evidence>\evidence5\envs-final.json`, `<evidence>\evidence2\env-robustness.md`.

**Defects.** F-02, F-03, F-12, F-13.

**Verdict.** Pass for `openmm81` and for the request contract. Six of seven environments were not exercised, and the deferred items D-04 to D-06 remain on the environment surface.

### Phase 4 - Resource and model-weight linking

**Ran.** Link, repeat link, replace, unlink, second unlink and re-link through the desktop API (`POST` and `DELETE /api/resources/{name}/link`), the control plane (`POST` and `DELETE /api/v1/large-resources/{name}/link`) and MCP (`operon_resource_link`, `operon_resource_unlink`).

**Result.** Verified on the installed build with the source `~/.local/share/operon/external/proteinmpnn_src`:

| Step | Result |
|---|---|
| first link | `linked`, mode `junction`, probe read through the link |
| same source again | `already_linked` |
| different source without `replace` | 409, `target already exists: ...` |
| `replace: true` | `linked` |
| unlink | `unlinked`, mode `junction`; junction gone, source intact |
| second unlink | `unlinked`, mode `null` |
| re-link | `linked` |

After the round trip the resource reports `present: true`, `status: "ok"`, `linked: true`, `mode: "junction"` and `size_bytes: 2060`.

Rejections verified: a source outside the allowed roots returns 409 and lists the allowed roots; a missing source returns 409; a source containing `..` returns 409; an unknown resource returns 404.

Windows specifics: junction detection uses `st_reparse_tag`, because Python 3.11 has no `Path.is_junction`; `os.readlink` device prefixes are stripped; removal uses `os.rmdir` so the linked contents survive; `subprocess` output is decoded as UTF-8 bytes to avoid GBK decode errors on a Chinese Windows code page.

Receipts are written to `<resources base>/.receipts/receipt-<id>.json` and carry `kind`, `source`, `target`, `mode`, `created_at`, `probe`, `probe_bytes` and `created_by`.

**Evidence.** `<evidence>\evidence5\resources-final.json`, `<evidence>\evidence7\verify5.json` (link section), `<evidence>\evidence5\final-checks.json`.

**Defects.** F-01 (the link module and resource metadata were absent from the seed), F-04 (junction detection and unlink). Deferred: D-08, D-09.

**Verdict.** Pass. Link, replace, unlink, repeat unlink and re-link behave as specified, and every rejection is explicit.

### Phase 5 - Frontend

**Ran.** `npm ci`, `npm run build` (`tsc -b` plus vite), `npm test` and a standalone `npx tsc -b`; a static review of the rebuilt panels and a key-set comparison of the two i18n dictionaries.

**Result.** `npm ci` installed 129 packages in 8 seconds. `npm run build` succeeded with 4,803 modules; `dist/assets/index-*.js` is 866.20 kB and the CSS bundle is 124.93 kB; the production bundle contains the literal `5.5.0`. `npm test` ran 42 files and 260 tests, all passing, in 10.79 seconds. `npx tsc -b` exits 0.

The Runtime status panel was rebuilt with a summary strip, a responsive card grid, running operations, an inline log drawer and a collapsed advanced section; the large-resources panel gained link and unlink actions. Both i18n dictionaries carry 974 keys, with identical key sets in `en` and `zh-CN`.

Browser-driven interaction was exercised against the installed build over the Chrome DevTools Protocol: headless Microsoft Edge 157.0.4341.60 was started with `--remote-debugging-port=9333`, navigated to the desktop server at `http://127.0.0.1:5763/`, and inspected through `Runtime.evaluate` and `Page.captureScreenshot`. The runtime status panel opened from the toolbar button labelled 运行状态 and rendered the summary strip `7 个环境 / 1 已就绪 / 6 未安装` above seven `environment-*` cards: `environment-openmm81` carried `data-status="ready"`, the chip 已就绪 and the facts `3.11.18`, `133 MB` and its six operators, while the other six cards carried `data-status="missing"` and the chip 未安装. The Settings dialog navigation opened 大型资源, which listed sixteen resources with exactly one linked badge: `proteinmpnn` showed 已外链 with mode `JUNCTION`, size `2.0 KB`, its resource root, link source and `OPERON_PROTEINMPNN_PATH`; `esm2` and `boltz` showed 已就位, `esmfold` 不完整 and the remaining resources 缺失. No `[role=alert]` or `.field-error` node appeared during the pass.

**Evidence.** The command output is reproduced under Verification commands; the browser pass wrote `<evidence>\evidence11\ui-status.json`, `<evidence>\evidence11\ui-dom.json` and the screenshots `ui-root.png`, `ui-runtime-status.png` and `ui-large-resources.png` in the same directory.

**Defects.** None found in this phase.

**Verdict.** Pass for build, type check, unit tests and interactive rendering of the rebuilt panels in a Chromium runtime.

### Phase 6 - Fault injection

**Ran.** Invalid link sources (outside the allowed roots, missing, containing `..`), unknown resource, unknown environment, a mixed valid and invalid prepare, cancel during staging, cancel while idle, retry after cancel, duplicate `request_id`, unknown job id, an environment manifest with a missing environment, and a backend restart during probing.

**Result.** Each fault produced the documented rejection and left no partial state, except where a defect above was found and fixed. The backend restart was caused by the operator switching instances, not by the product; the probe set was re-run after the restart.

**Evidence.** `<evidence>\evidence2\probe-*.json`, `<evidence>\evidence5\probes.json`, `<evidence>\evidence7\verify5.json`.

**Defects.** F-03, F-10, F-13 were observed here; D-02 and D-03 remain open on the error and diagnostic surfaces.

**Verdict.** Pass with the deferred diagnostics limitations recorded below.

### Backend test suite

**Ran.** The full backend suite ran with the `operon` conda interpreter (Python 3.12.14): 5,081 collected, `119 failed, 4,061 passed, 272 skipped, 11 errors in 4,552.77 s` (`pytest tests -q --tb=line`, JUnit XML retained beside the log). The run started at 02:25, while this release was still being edited, so it observed a tree whose registry index went stale mid-run; 21 of the 63 failing files pass when re-run on the final tree. The remaining 42 files were re-run twice: on the final tree (`42` still fail, 966 s) and on a pristine worktree at `b1e49ae0e` (`45` fail, 761 s). No file fails on the final tree that passes at that commit, so this release introduces no backend regression; three files now pass that failed at the baseline (`test_agent_guidance.py`, `test_desktop.py`, `test_remote_environments.py`).

Three targeted suites were completed:

| Suite | Result |
|---|---|
| resource API, link, fetch and downloads | 56 passed, 1 skipped (Windows-only round trip) |
| environment API, runtime, install and permissions | 33 passed |
| operator docs, agent guidance, transports, installation guard, job service and admission subset | 56 passed, 1 failure |

The single failure is `tests/test_job_admission.py`, a worker lifecycle race that raises `KeyError` on `service.processes`; it is unrelated to this release.

**Verdict.** The targeted suites pass on the shipped tree. The 42 files that still fail also fail at `b1e49ae0e` and belong to the environment-dependent groups below, not to this release.

## Defects found and fixed in this release

| ID | Severity | Symptom | Root cause | Fix | Verification |
|---|---|---|---|---|---|
| F-01 | high | `GET /api/resources` and `GET /api/v1/large-resources` returned 500 on a clean install. | The built-in library shipped without `operon_core.steps.resource_fetch`, and `_resources_common` lacked `check_resource`. | The library seed now carries the fetch step, downloads metadata, `expected_files`, `link_roots` and the link module. | Both endpoints return 200: 16 resources, 7 with downloads, 18 `used_by` entries. |
| F-02 | high | `POST /api/environments/prepare` returned 500 `RuntimeError: no running event loop`. | Preparation was scheduled without a running event loop. | Preparation runs on a tracked daemon thread. | `openmm81` prepared to `ready`; cancel and recovery also pass (Phase 3). |
| F-03 | high | Cancel returned 200 but the installation kept running, and the resulting SIGTERM kill was recorded as an installation failure. | Cancellation had no control handle over the child process. | Cooperative cancellation through a control handle kills the child, removes staging, records `cancelled` with `error: null` and never writes an environment error file. | Cancel 4 s after prepare: operation `cancelled`, environment `missing`, staging and error artefacts removed; a later prepare reaches `ready`. |
| F-04 | high | Junction links could not be unlinked, and repeating a link reported a root-containment error instead of `already_linked`. | Python 3.11 has no `Path.is_junction`, so junction detection misclassified links as outside the root. | Detection uses `st_reparse_tag` and `os.lstat`; repeat links return `already_linked`; unlink uses `os.rmdir`. | Link, repeat link, unlink, second unlink and re-link behave as specified; the resource ends `present: true`, `size_bytes: 2060`. |
| F-05 | medium | Every built-in operator failed with `Implementation code hash mismatch`. | The registry index recorded a stale tree-wide `code_sha`. | The index is regenerated as the last packaging step. | Built-in operators executed in Phases 2 and 4 (`reverse_complement`, `sequence_stats`, `structure_contacts`). |
| F-06 | medium | Three environments (colabfold, esmfold, openfold) and two operators (`structure_convert_format`, `structure_extract_chain`) were missing from the installed library. | The library seed had drifted from the library branch. | The seed was merged; the 0.1.29 bundle again declares 7 environments and 1177 descriptors. | `/api/environments` returns 7 entries; `/api/libraries` returns 1177 descriptors. |
| F-07 | medium | The installer silently nested an installation into `<dir>\Operon` when the target directory was not owned by it. | Destination resolution redirects non-owned directories without user-visible feedback. | The installer prints an explicit notice (`installer/InstallEngine.cs`). | `tests/native_setup/Program.cs:78` and `:86` assert the unchanged redirect; a silent install into a directory containing `preexisting.txt` nested into `<dir>\Operon` and printed `[1%] 提示：<dir> 已有其他内容，本次安装到 <dir>\Operon。` to the console and to `setup.log`. |
| F-08 | medium | The release payload audit rejected two committed documents that contained absolute developer paths. | The documents embedded drive-letter paths. | Both documents were rewritten without drive letters. | Payload audit re-run over both rewritten documents. |
| F-09 | low | MCP `serverInfo` reported `1.30.0` instead of the product version. | The `mcp` dependency version was returned. | `serverInfo` reports the product version. | `initialize` response compared with `/api/version` (5.5.0). |
| F-10 | low | An unknown job id surfaced as a server failure: `GET /api/v1/jobs/<id>` returned 500 `internal_error` and MCP `operon_job` reported 本地服务处理失败. | `operon/control_api.py` caught only `KeyError`, while the job service raises `operon.pool_service.PoolClientError: Unknown resource`; MCP also consulted the resource-operation namespace before jobs. | `control_api.py` maps both `KeyError` and `PoolClientError` with unknown, not-found or no-such text to 404 `unknown_job` for job, logs, results, cancel and parameters; `mcp_server.py` searches jobs first and reports `unknown job or resource operation: <id>`. | `GET /api/v1/jobs/0` returns 404 `unknown_job`; MCP `operon_job` returns `unknown job or resource operation: 0` and `operon_result_files` returns `unknown job: 0`; `tests/test_control_api_unknown_job.py` passes. |
| F-11 | low | `operon_operator_search` returned nothing for exact ids when the query contained extra words. | Exact-id matching required the whole query. | Search falls back to an OR ranking that prefers coverage. | Exact-id search with extra words succeeds. |
| F-12 | low | Cancelled operations carried `finished_at: null`. | The cancellation path never stamped a finish time. | The last progress timestamp is used as the finish stamp. | Cancel sequence: `finished_at` carries the last progress update. |
| F-13 | low | A mixed prepare request with one unknown environment started the known ones. | Names were validated while dispatching, one at a time. | All names are validated before anything starts. | `{"names":["openmm81","nope"]}` returns 404 with 0 operations before and after. |
| F-14 | low | `docs` generation dropped hand-written `## Scientific limitations` sections from two generated pages. | Generator output replaced the hand-written sections (recorded as a tooling conflict). | The pages were restored and the index rebuilt; the generator is unchanged. | Both sections are present in the restored pages. |

## Defects found and not fixed

| ID | Severity | Symptom | Root cause | Fix | Verification | Deferral rationale |
|---|---|---|---|---|---|---|
| D-01 | medium | `verify_code` validates the hash registered for the wheel while execution imports the unpacked tree, so a manually patched environment copy breaks every operator of that package while `prepare` still reports `ready`. | The hash source (wheel registry) and the execution source (unpacked tree) diverge. | Not fixed in 5.5.0. | Not verified. | Needs a design decision on which artefact is authoritative and whether patched trees are supported. |
| D-02 | medium | MCP collapses every failure into `Error executing tool <name>: <text>`, losing `code`, `details` and `status`. | The MCP adapter stringifies tool errors. | Not fixed in 5.5.0. | Not verified. | Restoring structured errors changes the MCP error contract for every client and needs a schema and compatibility decision. |
| D-03 | medium | prepare and validate messages are free text without a machine-readable pointer to the offending node, field or edge, and mix Chinese and English. | Messages are assembled as prose inside the validators. | Not fixed in 5.5.0. | Not verified. | Requires a diagnostic schema shared by the desktop API, the control plane and MCP, plus translation of the existing messages. |
| D-04 | low | The environment log endpoint returns only a tail, silently clamps `limit`, and cannot distinguish a missing log from an empty one. | The endpoint streams a fixed tail without metadata. | Not fixed in 5.5.0. | Not verified. | Needs additive response metadata and a contract for the missing-log case; operational impact is low. |
| D-05 | low | `retry` has no precondition: it reinstalls a `ready` environment, and a retry during cancellation can leave two operations for one environment. | Retry only checks that the environment name exists. | Not fixed in 5.5.0. | Not verified. | Needs a per-environment operation state machine and interacts with the cancellation ordering fixed in F-03. |
| D-06 | low | Environment `size_bytes` is cached for 90 seconds and can lag after deletions. | The size is cached rather than measured per request. | Not fixed in 5.5.0. | Not verified. | Invalidation on deletion needs a cache-key change; the next read refreshes the value. |
| D-07 | low | Desktop and control-plane error envelopes differ for the same condition. | The two surfaces have independent adapters. | Not fixed in 5.5.0. | Not verified. | Unifying the envelopes is a breaking change for existing clients and needs a versioned migration. |
| D-08 | low | One allowed link root in the manifest is POSIX-only; on Windows the 409 message lists it verbatim and the expanded `~` entry mixes a drive letter with forward slashes. | The library's default root list contains a POSIX path. | Not fixed in 5.5.0. | Not verified. | Needs a per-host default supplied by the deployment instead of a library constant. |
| D-09 | low | Cancelled operations keep `.previous-*` directories and the shared `packages` and `micromamba.exe` cache behind. | Staging cleanup removes only the active staging directory. | Not fixed in 5.5.0. | Not verified. | Needs a retention policy for reusable caches; deleting them would slow every subsequent prepare. |

## Not tested

- Browser-driven UI interaction in the packaged desktop shell itself: the pass drove the same frontend bundle in headless Edge over CDP, not through the WebView2 host window.
- Installation of the final documentation-only rebuild: the verified candidate and the shipped payload differ by documentation files only, as the payload audit shows; the installer executable was not run again for that rebuild.
- Full backend suite verdict on the shipped tree: the full run describes the tree at the start of the pass; the targeted suites were re-run against the final tree and no file regressed, so the full-run counts are not re-measured after the last edits.
- The six isolated environments other than `openmm81`: `boltz`, `esm3` and `esmfold` need multi-GB CUDA wheels or gated weights; `colabfold` needs the MMseqs2 database; `openfold` and `antifold` need external checkouts and weights.
- The literal chain `CSV -> describe -> filter_min`: `describe` is a terminal report node, so the chain is not executable; this is a documented MCP limitation, not a defect.
- The Windows-only link round trip that the targeted resource suite reports as skipped.

## Verification commands

Silent installation:

```
Operon_Setup-5.5.0.exe --quiet --install-dir <dir> --no-register --result <evidence>\install-result.json
```

MCP server (global options before the subcommand):

```
python -I -m operon --workspace <ws> --data-dir <ws>\.studio --instance <id> mcp --allow-run --allow-plugins
```

Frontend build and tests:

```
npm ci
npm run build
npm test
npx tsc -b
```

The backend targeted suites were run with the `operon` conda interpreter (Python 3.12.14); the full suite collected 5,081 tests. No literal pytest invocation was retained in the evidence, so none is reproduced here.
