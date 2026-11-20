# Operon Studio 5.7.21 test report

## Scope

5.7.21 fixes five defects found while driving environment installs from the
panel: a dependency row that could not be installed on its own, a 500 from
`GET /api/jobs/{id}` for environment jobs, misparsed PEP 427 dist-info names, a
remote log route that ran the retry handler, and AlphaFold2 readiness that
ignored missing files. The builds below are the ones this report covers.

## Builds

| Artifact | File | Bytes | SHA256 |
| --- | --- | --- | --- |
| Installer payload | `Operon-Studio-v5.7.21-Windows-x64.zip` | 357,904,485 | `3bacd2fff3afb6a32626eb144942314d2bb7f38d5c6307f198cdb63db4315306` |
| Windows installer | `Operon_Setup-5.7.21.exe` | 429,681,850 | `ee60bed6634fb016246d88482fc9e695adf41b4febfac7a7dc88f43146abb8da` |
| Server bundle | `Operon-5.7.21-Server.zip` | 9,979,736 | `bc041271ae93516ea1e186d6d85ad077e5084fc53ccb74cf467542ef2a02fae7` |
| Application wheel | `operon_studio-5.7.21-py3-none-any.whl` | 1,021,965 | `8abcfc25a6652d3578d5e5b436104450d87ff4d9cef88f9fd8367a9e3454032e` |
| Library wheel | `operon_builtin_library-1.1.13-py3-none-any.whl` | 5,784,930 | `5ee55f4ec178024310ea65fe9c841e2139e6141b2bafad57cf4e813a6211ce21` |
| Library package | `operon-library-main-v1.1.13.operon-library.zip` | 7,024,801 | `8660f31a63000f57c4594018f740f4b796b601695b69fc62e8d3f53b909e4d0c` |
| Route collection | `operon-routes-main-v1.1.13.zip` | 201,439 | `711d5417f8357d360353bdb8dab272a9ae6299044acc698df46ec47ff85d0906` |
| Checksums | `SHA256SUMS-5.7.21.txt` | 712 | `868aba940bbbd6997bd0a7e4bb73111d50a296e0eb3bee60dc2dc75907dfdb29` |
| Library checksums | `library-1.1.13-SHA256SUMS.txt` | 323 | `0dfd20e607021d185cfc4165396bb09937008efb0c55396b0e96204a79ba6606` |

## Clean install

| Step | Result |
| --- | --- |
| Installer | exit 0, 22.2 s |
| Version directory | `5.7.21-e7a202b9b426` |
| Ready | 64.5 s after launch |
| Version | `{"version":"5.7.21","build":"e7a202b9b426","display":"5.7.21 (e7a202b9)"}` |
| Library | `main-v1.1.13` (1,074 operators, 1,182 descriptors, 7 packages, 108 readers) |
| Environments | 18 listed; 5 platform-restricted entries carry a Chinese explanation |
| `/api/resources` | 16 resources; `afdb` lists 9 sources, including `pdb_mmcif/mmcif_files` over rsync |
| MCP | 141 tools |
| `check95.py` | 34/34 PASS, `failed: []` |

## Installer actions

| Action | Endpoint | Result |
| --- | --- | --- |
| Prepare | `POST /api/environments/prepare` | 200, job queued |
| Cancel | `POST /api/environments/{name}/cancel` | 200, `cancelled: true` |
| Retry | `POST /api/environments/{name}/retry` | 200 |
| Dependency install | `POST /api/v1/environments/{name}/dependencies/download` | 200 with a queued job |
| Job lookup | `GET /api/jobs/{id}` | 200 for the dependency job id (was 500); 404 `unknown_job` for an unknown id |
| Log | `GET /api/environments/{name}/log` | 200 with real text; a 404 from `GET /api/remote/{key}/environments/{name}/log` no longer triggers a retry |

The prepare → cancel → retry sequence was run on `proteinmpnn`; all three calls
returned 200.

## Dependency rows

The manifest carries six requirement buckets: `pip_wheels`, `pip_pypi`,
`conda_packages`, `requirements`, `no_deps` and `no_build_isolation`. The panel
labels rows with display kinds (`wheel`, `pypi`, `conda`), which the installer
rejected because the bucket names differ. `_KIND_ALIASES` now resolves the
display kinds before validation, and a dependency request that arrives without
a kind is matched against the manifest row by bare requirement name. Installing
a row now queues a job instead of failing with
`dependency kind 'wheel' cannot be installed one by one`.

`GET /api/jobs/{id}` follows the same ids. The environment queue publishes
`app.state.environment_jobs`; the route reads the run-job store first, then that
dict, and answers 404 `unknown_job` only when both miss. Unknown ids are
reported as `{"code": "unknown_job", "message": "unknown job or resource
operation: …"}` rather than a 500.

Installed-version detection uses `metadata_name()`, which splits a `.dist-info`
directory at the first hyphen after PEP 427 normalises `-`, `.` and `_` to `_`
in the project name, and splits a legacy `.egg-info` directory at the first
segment that starts with a digit. The panel now reports the version that is
actually installed for packages such as `torch_geometric`.

## Remote log routing

`GET /api/remote/{key}/environments/{name}/log` was decorated above the
`POST …/retry` route, so the retry handler claimed the GET path and opening a
remote log restarted the install. The decorators are reordered: the GET path
serves the log and returns 404 for an unknown environment without starting a
job. The two operations keep separate `operationId`s in the OpenAPI document.

## Resource readiness

`/api/resources` now reports `files_present` and `files_missing` per unit,
resolved against the resource root or, for a linked unit, the link target. A
unit whose state claims presence but whose files are missing is reported as
`partial`, and an environment with such a gap is downgraded to `incomplete`
with the Chinese reason (`资源未齐备（n/m）：afdb`). Readiness in the remote
snapshot follows `files_missing` as well, so the local and remote cards agree.

## Automation

- `tests/test_environment_dependencies.py` installs a dependency through the
  queue and asserts the job reaches a terminal state with the package present.
- `tests/test_environment_api.py::test_unknown_job_id_reports_unknown_job`
  pins the 404 `unknown_job` payload.
- `tests/test_mcp_source_passthrough.py` covers the remote source call path for
  both the HTTP adapter and MCP.
- `check95.py` 34/34 PASS on the installed build.

## Known limitations

- A unit that still ships without a declared file list cannot report
  `files_missing`; its card keeps the previous `未校验` state.

## Not tested

- macOS and Linux desktop packages; this release was accepted on Windows x64
  only.
- An in-place upgrade from 5.7.20 over an installed 5.7.20 tree, and uninstall.
- Remote install, dependency download and cancel on a second physical machine;
  only the remote log route and its 404 path were exercised.
- Concurrent installs from two panels against one installation.
