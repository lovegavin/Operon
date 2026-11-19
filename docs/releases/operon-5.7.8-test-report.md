# Operon Studio 5.7.8 test report

## Scope

- Runtime dependency installs became asynchronous: the endpoint validates the target
  environment, queues a tracked job, returns immediately, and writes the command output to
  the environment log (F-84). Unprepared environments are rejected with HTTP 409 and a
  readable message instead of receiving a stub staging tree (F-85).
- The remote agent stops blocking its bridge on dependency installs and answers with a
  `queued` acknowledgement (F-86).
- Every installer step is supervised by a 60 second silence watchdog (F-87), so a stalled
  mirror fails fast instead of staying `installing` for up to 40 minutes.
- CLI parity: `operon environment dependency` and `operon environment log` (F-88).
- MCP parity: `operon_environment_log`; the tool surface is 78 tools (F-89).
- Environment cards now flag a runtime that is ready while its databases or weights are
  still missing (`资源 <ready>/<total>` with the missing ids in the tooltip). This is the
  difference the AF2 card used to hide: the runtime was installed, its MSA/parameter
  bundles were not.

## Builds

Artifacts for this release are listed with sizes and digests in `SHA256SUMS-5.7.8.txt`
(payload, Setup, Server, wheel) and `library-1.1.5-SHA256SUMS.txt` (library collection,
routes). The library is unchanged since 1.1.5 and only the application version advanced.

| Artifact | Notes |
| --- | --- |
| `Operon-Studio-v5.7.8-Windows-x64.zip` | runtime 40, library 1.1.5 seed, frontend bundle with the resource gap chip |
| `Operon_Setup-5.7.8.exe` | per-user installer wrapping the payload |
| `Operon-5.7.8-Server.zip` | server bundle (app wheel, library wheel, routes) |
| `operon_studio-5.7.8-py3-none-any.whl` | app wheel embedded in the runtime |
| `operon-library-main-v1.1.5.operon-library.zip` | library collection (unchanged data) |
| `operon-routes-1.1.5.zip` | route collection |

## Clean install

| Check | Result |
| --- | --- |
| installer exit | 0 |
| `/api/version` | `5.7.8` |
| environments | 18 |
| `/api/resources` | 16 resources, `expected_files` are plain strings, AF2 shows `mgnify/mgy_clusters_2022_05.fa` and `pdb_seqres/pdb_seqres_2022_09_28.fasta` |
| platform gate | `antismash`, `genomics`, `hic`, `hmmer`, `rna` report `supported=false` with the Chinese note and refuse within ~1 s |
| MCP surface | 78 tools, including `operon_environment_log` |

## Dependency behaviour

| Case | Result |
| --- | --- |
| dependency install on a missing environment | HTTP 409, `环境 alphafold2 还没有准备好…请先点击「准备」`, no staging directory created, response under 2 s |
| dependency install on a ready environment | queued job, `{status, job, name}`, log lines appended, operation record reaches `complete` |
| remote dependency install | agent returns immediately with `queued`, the desktop shows the queue notice and the log drawer reads the remote log |
| silent installer step | killed after 60 s with `<command> produced no output for 60s; aborted instead of waiting for the <timeout>s limit` (unit-verified with `stall=2.0`, abort observed at 2.0 s) |

## Interface parity

| Operation | HTTP | MCP | CLI |
| --- | --- | --- | --- |
| dependency install | `POST /api/environments/{name}/dependencies/download`, `POST /api/remote/{key}/environments/{name}/dependencies/download` | `operon_environment_dependency_install` (`profile_id`) | `operon environment dependency <name> <kind> <requirement> [--profile]` |
| environment log | `GET /v1/environments/{name}/log`, `GET /api/remote/{key}/environments/{name}/log` | `operon_environment_log` (`profile_id`) | `operon environment log <name> [--limit]` |
| environment actions | `GET /v1/environment`, `POST /api/environments/{name}/{cancel,retry}` | `operon_environments`, `operon_environments_cancel`, `operon_environments_retry` | `operon environment list`, `operon environment cancel` |

## Automated checks

- `pytest tests/test_environment_install.py tests/test_environment_install_lock.py tests/test_environment_api_runtime.py` — 17 passed.
- `pytest tests/test_resource_fetch.py tests/test_resource_api.py tests/test_resource_link.py` — 52 passed, 1 skipped (library manifest and download behaviour from 5.7.7 still holds).
- Frontend `npm test -- --run` — 43 files, 265 tests.
- Frontend `npm run build` — clean, bundle `index-*.js` carries the 5.7.8 literal.

## Known limitations

- An environment that is `ready` still needs its documents before the operators that read
  them can run; the new card chip reports that gap but does not install the documents.
- `alphafold2` ships a numpy-based heuristic operator set. Its runtime dependency list is
  `numpy`, so the dependency card shows 1/1 for a prepared environment; the real AF2 models
  are the linked `afdb` bundle, which is reported by the resource card instead.
- The 60 second watchdog treats any installer step that prints nothing for a minute as
  stalled. Very slow links that keep the connection open but print nothing will be killed
  and can be retried.
- `operon environment status <name>` still resolves a workflow directory rather than an
  environment name.

## Not tested

- Public PyPI and conda mirrors were not re-benchmarked; the watchdog was verified with a
  synthetic silent child process.
- Remote verification used a configured server profile with the new agent routes; a fresh
  server bootstrap over SSH was not repeated for this release.
