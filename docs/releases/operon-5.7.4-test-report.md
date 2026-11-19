# Operon Studio 5.7.4 test report

Date: 2026-11-19. Baseline: v5.7.3 (751c9b63a).

## Builds

| Artifact | Bytes | SHA-256 |
| --- | --- | --- |
| Operon-Studio-v5.7.4-Windows-x64.zip | 357493213 | 52114ba27cf7d70d5a61da3ac198f12e18c3e4b232cc6e893da794441a6d4f9c |
| Operon_Setup-5.7.4.exe | 429270570 | 49db39e5ec47634e5ee10726bd77a3417e871c7af3c6a1c69b09b15d48a2dd81 |
| Operon-5.7.4-Server.zip | 9825037 | c1243903205de16feb356cb37279bd3d9536366a820514c5aa3b3974996224e6 |
| operon_studio-5.7.4-py3-none-any.whl | 998408 | 68c2249a42ba0327b52789a0c5fcfa0b3766941828edd79118660345ab2ecea6 |
| operon_builtin_library-1.1.3-py3-none-any.whl | 5773890 | unchanged from 5.7.3 |
| operon-library-main-v1.1.3.operon-library.zip | 6993483 | f1337340d8a909c8fb5e199cf91c1e24919b9128f6dd64636a486b7a8f9a9fb0 |
| operon-routes-main-v1.1.3.zip | 201389 | 9a5cb56b405cd0cb657c546d7eba90ff8a78c86901c8c6bd6c32dbe90e61dda9 |

## Clean installation

Installed with the published setup into a fresh directory, headless server on
port 5802 with a private admission directory.

| Check | Result |
| --- | --- |
| installer exit code | 0 |
| installed version | 5.7.4 (7201e7f65ce5) |
| server ready | 32 s |
| operator library | main-v1.1.3 |
| environments listed | 18 |
| resources listed | 16 |
| resources without a download source | 0 |

## Behaviour checks

- Remote environment cancel: with a token, `POST /api/remote/nosuch/environments/esm3/cancel`
  answers 404 (unknown connection) instead of 404 from a missing route; the
  route is present in the installed build, as are the remote dependency and
  remote log routes.
- Local cancel from the panel: preparing `rna` shows `安装中 · 1% · 创建环境 · 9.5 MB`;
  clicking `取消` turns the card into `未安装` within 8 s and the operation
  records `cancelled`.
- Progress reporting: creation bytes and pip download sizes both feed the
  card, so the label moves from `创建环境` to dependency installation while the
  elapsed time keeps increasing.
- Resource units: `alphafold2` exposes 8 downloadable files and 1 link-only
  file (`pdb_mmcif/mmcif_files`, rsync only); the unit button reads
  `下载可用文件（8/9）` and lists the file without an HTTP source.
- Log drawer: `查看日志` opens the drawer and shows `暂无日志` for an
  environment that was never installed, rather than failing silently.

## Automated suites

| Suite | Result |
| --- | --- |
| tests/test_environment_install.py | 25 passed |
| tests/test_remote_environments.py | 9 passed |
| tests/test_resource_download_units.py tests/test_resource_api.py tests/test_environment_api_runtime.py | 28 passed |

## Known limitations

- The task list and the results panel address local jobs only.
- Resource downloads on a server cannot be cancelled from the desktop; the
  agent has no `resources_cancel` method.
- `operon environment status <name>` still resolves against the working
  directory.

## Not tested

- A real remote server end to end (no SSH target from this machine); the
  remote routes were verified to exist and to answer with a structured error.
- GPU hosts: the CPU fallback path was exercised by unit tests, not on a
  machine without `nvidia-smi`.
