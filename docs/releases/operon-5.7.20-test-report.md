# Operon Studio 5.7.20 test report

## Scope

5.7.20 closes three card/regression issues reported after 5.7.19: the remote
resource card claiming 无下载源 although the service served eight sources, an
environment card saying 已准备 while its declared resources were missing, and a
resource that only publishes an rsync endpoint (PDB mmCIF) having no way to be
fetched at all.

## Builds

Artifact sizes are listed below; the SHA-256 digests of the same files are in
`SHA256SUMS-5.7.20.txt` next to them in the download folder.

| Artifact | File | Bytes |
| --- | --- | --- |
| Installer payload | `Operon-Studio-v5.7.20-Windows-x64.zip` | missing |
| Windows installer | `Operon_Setup-5.7.20.exe` | missing |
| Server bundle | `Operon-5.7.20-Server.zip` | missing |
| Application wheel | `operon_studio-5.7.20-py3-none-any.whl` | missing |
| Library wheel | `operon_builtin_library-1.1.12-py3-none-any.whl` | 5,784,658 |
| Library package | `operon-library-main-v1.1.12.operon-library.zip` | 7,022,927 |
| Route collection | `operon-routes-main-v1.1.12.zip` | 201,356 |

## Clean install

| Step | Result |
| --- | --- |
| Installer | see `install94.log` |
| Version | 5.7.20 |
| Library | main-v1.1.12 |
| Environments | 18 |
| `check94.py` | see `check94.log` |

## Resource readiness

`/api/environments` now returns `resources_total`, `resources_ready` and
`resources_missing` for every environment. `alphafold2` reports a non-zero
`resources_total` and its status is downgraded to `incomplete` with a readable
`资源未齐备（n/m）：afdb` message while the `afdb` unit is incomplete.

`/api/resources` reports for `alphafold2` unit `afdb`: `downloadable` 8 entries,
`undownloadable` 1 entry (`pdb_mmcif`, rsync-only upstream) and
`download_supported` true, so the card offers 下载可用文件（8/9）.

## rsync fetching

Resources that only publish an rsync endpoint declare it in `resources.json`:

```json
"rsync": {"url": "rsync://rsync.ebi.ac.uk/pdb/data/structures/divided/mmCIF/"}
```

`/api/resources` exposes the declaration on the resource and on each unit, the
resource card offers a `rsync 拉取` action, and `POST /api/resources/{name}/download`
runs the system `rsync` client in the same background job as HTTP downloads with
progress in the resource log and the usual cancel path. When no `rsync` binary
is available the job fails with a readable message (`rsync 不可用：… 可以链接已有
目录，或安装 rsync（Windows 上可用 cwRsync）后重试。`), so the unit still offers
the linking route.

## Automation

- `tests/test_environment_resources.py` (5 tests): unit counting, fully present
  unit, snapshot downgrade for a ready environment with missing resources, and
  the rsync fallback for both a named unit and a whole resource.
- `tests/test_remote_environments.py tests/test_environment_api.py
  tests/test_resource_api.py` (26 tests) pass.

## Known limitations

- `pdb_mmcif` has no HTTP archive upstream; on a machine without `rsync` only
  the linking route is available.
- `operon_remote_source` remains a documented degraded endpoint.
