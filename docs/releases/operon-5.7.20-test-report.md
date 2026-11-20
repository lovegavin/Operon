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

| Artifact | File | Bytes | SHA256 |
| --- | --- | --- | --- |
| Installer payload | `Operon-Studio-v5.7.20-Windows-x64.zip` | 357,856,025 | `3c44512efa37963517031afa7e1eb2cb50f3dca61485147f1d197e52356ffac0` |
| Windows installer | `Operon_Setup-5.7.20.exe` | 429,633,391 | `2565f94e2cd37e9483322c88ac66a21add7e4169b9700e36d886a557d40e146e` |
| Server bundle | `Operon-5.7.20-Server.zip` | 9,943,951 | `b5c7217ed391b4cb824c854193bddaec5a318971b3ff6cc13bf284540e18c491` |
| Application wheel | `operon_studio-5.7.20-py3-none-any.whl` | 1,020,721 | `90457b14c2e9c5ed1b554f79bdd054a0093f2fec558afe5279ea06f43b590287` |
| Library wheel | `operon_builtin_library-1.1.13-py3-none-any.whl` | 5,784,930 | `5ee55f4ec178024310ea65fe9c841e2139e6141b2bafad57cf4e813a6211ce21` |
| Library package | `operon-library-main-v1.1.13.operon-library.zip` | 7,024,801 | `8660f31a63000f57c4594018f740f4b796b601695b69fc62e8d3f53b909e4d0c` |
| Route collection | `operon-routes-main-v1.1.13.zip` | 201,439 | `711d5417f8357d360353bdb8dab272a9ae6299044acc698df46ec47ff85d0906` |

## Clean install

| Step | Result |
| --- | --- |
| Installer | exit 0, 20.2 s (`D:\ot55\stage0v55fe`) |
| Version | `5.7.20 (41a0fc79)` |
| Library | `main-v1.1.13` (1,074 operators, 1,182 descriptors, 7 packages, 108 readers) |
| Environments | 18, alphafold2 `resources_total 1 / ready 0` |
| `check94.py` | 28/28 PASS, `failed: []` |

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
