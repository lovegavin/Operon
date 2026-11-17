# Operon Studio 5.4.1

5.4.1 is a defect-fix release on top of 5.4.0. It does not change the operator
library contract, the pool protocol, or any workflow format, so saved canvases,
routes and operator libraries keep working unchanged.

## Fixed

### Installing an operator library no longer times out

`library install` took the library lock and then asked the shared pool for its
environment-gate path. Registering a workspace in the pool builds a
`PluginManager` for it, and that manager takes the same `.install.lock` file.
The application therefore waited for the pool while holding the lock the pool
needed, and the request failed after the 60 s socket timeout with
`本地服务处理失败，请检查服务日志。`

This only happened when the pool had not yet registered that workspace, which is
why a fresh installation accepted libraries and a pool restart made every later
import fail.

`JobService.execution_environment_guard()` now derives the gate path from the
admission directory (`<admission>/../environment-gate.json`) instead of asking
the pool, so installing a library never triggers a pool registration. All
library imports — including a second library such as `fork1-v0.0.0` next to
`main-v0.1.28` — complete without touching the pool.

### Version numbers render everywhere

- `operon/build_info.py` resolves the build identifier from `OPERON_BUILD`, the
  version directory name (`<semver>-<hex>`), or `installation.json.current`.
- `GET /health` returns `studio: {version, build, display}`; `GET /api/version`
  is new; `GET /api/bootstrap` carries the same `studio` object.
- The footer shows the application version with its short build id, for example
  `5.4.1 (0bbcaa57)`, instead of a bare constant baked into the bundle.
- The runtime status panel shows `应用 (application)`, `构建 (build)` and
  `共享池 (shared pool)` separately, and warns when the shared pool runs a
  different version than the desktop application.

### The operator list refreshes after import or deletion

`CatalogUpdates` silently dropped a catalog response when a five-second poll had
advanced the revision in between, so deleting or importing a library left the
left-hand operator panel unchanged until the window was reloaded. `force()`
applies the response unconditionally and advances the revision, and
`App.onChanged` uses it after every library action.

## Verification

| Check | Result |
| --- | --- |
| `tests/test_build_info.py` | 4 passed |
| `frontend/src/catalogUpdates.test.ts` (`vitest run`) | 2 passed |
| `tests/test_job_admission.py` | 14 passed |
| `tests/test_engine_pool.py` + `tests/test_engine_resume.py` | 14 passed |
| `tests/test_engine_abandon.py` | 4 passed |
| `tests/test_resource_api.py` | 10 passed |
| Import `main-v0.1.28` on a pool-less installation | 7 packages, 1177 descriptors, succeeded |
| Import `fork1-v0.0.0` next to `main-v0.1.28` | succeeded, two library records |
| Delete a library, then read the catalog | revision advanced, panel refreshed without reload |
| `/health`, `/api/version`, `/api/bootstrap` | all three return the same `studio` object |
| Clean install of the published payload | `<test-dir>`, version directory `5.4.1-65bbb2e466b2`, `operon --version` = `Operon 5.4.1` |
| `GET /health` on the installed build | `{"status": "ok", "studio": "5.4.1", "version": "5.4.1", "build": "65bbb2e466b2", "display": "5.4.1 (65bbb2e4)"}` |
| Built-in operator library after first start | `main-v0.1.28`, 7 packages, 1069 operators, 108 Readers, 1177 descriptors |
| `operon library install operon-library-fork1-v0.0.0.operon-library.zip` | `fork1-v0.0.0` added next to `main-v0.1.28`, no pool interaction, exit 0 |
| `operon library remove fork1-v0.0.0`, then read `/api/bootstrap` | catalog `plugin_generation` changed from `e1d956d6…` to `78599948…` |
| MCP stdio handshake on the installed build | 69 tools, `operon_resources` returns 16 resources, `GET /api/v1/large-resources` 200 |

## Artifacts

| Asset | Size | SHA-256 |
| --- | ---: | --- |
| `Operon_Setup-5.4.1.exe` | 428,821,982 | `85f0988b25d1b1d64f51e6bb95e98795f12e00177854d2820cc63cc5c19792d0` |
| `Operon-5.4.1-Server.zip` | 4,658,123 | `30a9d3123491df27ec2986effbfe242900c99e734259eb27c1aa14a1af66ec94` |
| `operon_studio-5.4.1-py3-none-any.whl` | 977,295 | `9792014bf80ef8bbfc9262380ed6092029cecf568742a1a73e2aba4d3e93cf95` |

## Known issues

- `tests/test_job_admission.py::test_actual_scientific_workers_keep_independent_memory_and_logs`
  is order sensitive: the test reads `service.processes` right after the job
  turns `running`, and the dispatcher registers the process a moment later. It
  passes on its own and in the regular suite order; it can fail when a suite
  mixes unrelated modules that submit jobs.
- The shared pool runs one job at a time on a 16-thread host because each
  scientific job reserves roughly half of the memory ceiling.
- The desktop runtime still ships Python 3.11; operator environments may pin
  their own interpreter version.
