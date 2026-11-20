# Operon Studio 5.7.18 test report

Date 2026-11-20. Library `1.1.12`.

## Builds

| Artifact | Bytes | SHA-256 |
|---|---:|---|
| `Operon-Studio-v5.7.18-Windows-x64.zip` | 357,816,096 | `68ae9a58bb59174b58d3bf093d61d99bcd2918663d5eb1cc5c609eb5ea0a0bf3` |
| `Operon_Setup-5.7.18.exe` | 429,593,460 | `60971bd91f46170f14b920fc73f53af34ec76ca01123c1ebaaf59754d5e2d49f` |
| `Operon-5.7.18-Server.zip` | 9,926,243 | `e034487f05a7945ea0763e0d20a545f17c4851aabef0ceb2b1e3649af4c67926` |
| `operon_studio-5.7.18-py3-none-any.whl` | 1,017,766 | `32579b5cf10ec7fe0826dca1f9a881b51047eb335c3ca5f0fa47f841fcfbbf92` |
| `operon_builtin_library-1.1.12-py3-none-any.whl` | 5,784,658 | `ad319c96a4c4d813869227e5f60d4b32c240e717468197fb4fa6cfb5ada3b8e4` |
| `operon-library-main-v1.1.12.operon-library.zip` | 7,022,927 | `0668b94b387d35b935f307d8c11b52ac681db4c00718f79d86761283952f977e` |
| `operon-routes-main-v1.1.12.zip` | 201,356 | `067cba69f9036a78ac8d8f4b866fb3dea07e291787b0bf759838cf0b53943964` |

Front-end bundle `index-w-b9eOKI.js` (896,993 B, contains the literal `5.7.18`).

## Clean install

| Check | Result |
|---|---|
| Installer | exit 0, 20.4 s |
| Version directory | `5.7.18-e70aedfce9f5` |
| `/api/version` | `5.7.18 (e70aedfc)` after 68.5 s |
| Library | `main-v1.1.12`, 1,074 operators / 1,182 descriptors / 7 packages / 108 readers |
| Environments | 18, five fields each |
| MCP tools | 141, including `operon_environment_retry` |
| Interface checks | 22/22 passing |

## Installer actions

| Action | Endpoint | Result |
|---|---|---|
| Prepare | `POST /api/environments/prepare` | 200, job queued, card shows "正在安装" |
| Cancel | `POST /api/environments/{name}/cancel` | 200, `cancelled: true`, card returns to "未就绪" |
| Retry | `POST /api/environments/{name}/retry` | 200 |
| Dependency install | `POST /api/v1/environments/{name}/dependencies/download` | 200 with a job, 409 with a readable reason when the environment is not ready |
| Resource download | `POST /api/resources/{name}/download` | 200, unit-scoped, downloads only missing files |
| Log | `GET /api/environments/{name}/log` | 200 with real text |

## Physical-machine isolation

- Remote targets render `dependencies`, `units`, `interpreter`, `location`,
  `progress`, `size_bytes` and `status` exclusively from that machine's
  snapshot.
- Local metadata is used only for `title`, `notes`, `planned`,
  `operator_count`, `operators` and `expected_bytes`.
- AlphaFold2 on a remote machine reports its own dependency row (`numpy`
  installed) and its eight download sources.

## Automation

- `tests/test_file_artifacts.py`, `tests/test_result_viewers.py`,
  `tests/test_operator_input_errors.py`: 32 passed.
- `tests/test_operator_input_validation.py tests/test_operator_input_errors.py`:
  21 passed.

## Known limitations

- `operon environment status <name>` still resolves relative to the current
  working directory unless the environment root is configured.
- The disk precheck estimates from the manifest; it does not reserve inodes.
- Real-data operator coverage on the Linux host is 459 of 1,074 operators
  (42.7%). The remaining failures are dominated by fixture/contract mismatches
  and missing external binaries, not by environment installation.
- Platforms without bioconda builds (hmmer, antismash, genomics, hic, rna) are
  reported as unsupported on Windows rather than failing at install time.

## Not tested

- A full one-click download of every tensor-sized AlphaFold2 database.
- Remote installs over a slow link.
