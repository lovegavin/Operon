# Operon Studio 5.1.9 to 5.1.16

This note covers the changes after 5.1.9 through 5.1.16. Per-version details remain in
`operon-5.1.10.md` through `operon-5.1.16.md`; 5.1.15 was folded into 5.1.16 and
was not published on its own.

## 5.1.9


### Relocatable operator library

The library builder now emits `library_name` in `library.json`, so a bundle
installs as `<name>-v<version>` without asking the user to type a name. The
application rejects duplicate primary names and duplicate operator ids.

### Vendored PDBFixer

The 8.0.x experiment with an isolated PDBFixer download was replaced by a
vendored copy inside `operon_core`. The builder used to copy only `_*.py`
files, so `_pdbfixer/pdbfixer.py`, `soft.xml`, templates and `resources.json`
were missing from the wheel and OpenMM routes failed at import time. The
builder now copies the whole `_*` directory and top-level JSON resources, and
`main-v0.1.1` is the first library that imports PDBFixer from the installed
wheel.

## 5.1.10


### Managed-server library layout

The application only recognized `<install>/versions/<version>/library`. Remote
servers installed under `<install>/code-<id>/library` therefore returned `None`
for the library root, and environment lookup fell back to
`operon/_no_library/operon/environments.json`.

`installation.library_root()` now accepts both layouts: a candidate with
`registry.json` or a `libraries/` directory is treated as a library. The same
path normalization handles `\\?\` and `\\?\UNC\` prefixes.

### Scoped dependency repair

`POST /api/remote/{key}/install` used to run dependency repair with no operator
ids, which expanded to all 1174 installed ids and held the library lock for
tens of minutes. Submissions waiting behind that lock timed out without
creating a job.

`environment_prepare` now derives the affected operators from the requested
environment's `used_by` list and checks only those ids. It skips the repair
thread entirely when the list is empty.

## 5.1.11


### Stale remote build cache

`RemoteManager.status()` could return a cached `<profile>.catalog.json` even
while disconnected, so the UI showed the previous server version after an
upgrade. Now:

- catalog files whose `build.application.version` differs from the local
  application are deleted at manager startup;
- `forget_cache(key)` removes the catalog, pool snapshot and in-memory build;
- connecting with `install=True` clears the catalog before the SSH handshake.

### Remote poll paths

Remote polling assumed every event path was under
`.studio/jobs/<job-id>`. Task-folder runs write `events.jsonl` under
`<workspace>/<task>/results/<job>/runs/...`, so `relative_to()` raised
`ValueError` and aborted the poll with a bare `remote_error`.

The poll now keys launcher events under `.studio/jobs/<id>`, run events under
`results/...`, and any other path under `external/<hash>-<name>`. Local HTTP
streaming was already keying by absolute path and is unchanged.

## 5.1.12


### Remote provisioning and optional files

`source_archive()` unconditionally read `requirements-hic-linux.txt`. Packages
without the optional Hi-C requirements failed "install / upgrade server" with
`FileNotFoundError`. The archive now includes each fixed file only if it
exists, and the 5.1.12 payload ships the file again.

### Version label

The packaged `frontend/dist` had been built at 5.1.5 and copied as-is, so the
footer kept an old version after upgrades. 5.1.12 packages the corrected
version literal. A full Vite rebuild and a dist-vs-package.json packaging guard
are still TODO.

## 5.1.13


- Added `GET /api/v1/jobs/{key}/results` and `results/file` for complete result
  inventory and download, including composite `stages/<index>/...` paths.
- Added MCP tools `operon_result_files`, `operon_download_result`,
  `operon_download_results`, `operon_download_artifact`, and `operon_download_report`.
- Downloads are confined to the workspace; absolute paths and `..` are rejected.

## 5.1.14


### Local result download

`Application.artifacts.result()` calls `JobService.result_file()`, but the 5.1.13
implementation defined only `result_path()`. Every local result download
returned HTTP 500 while listing worked. `result_file()` now aliases
`result_path()` with the same containment and existence checks.

Remote and composite listing still requires a 5.1.14 server; older servers do
not expose the `result_files` RPC.


## 5.1.15


### Composite result listing

Composite jobs store child results under `stages/<index>/...`. The remote call
`RemoteManager.result_files()` was invoked with three arguments, and child ids
were raw remote ids rather than references known to `reference()`. Listing a
composite therefore returned HTTP 500.

`result_files_for(profile_id, job_id)` now resolves each child stage and the
composite endpoint uses it. A 5.1.15 remote returned 10 files (19,211 bytes) for
the measured three-stage job; `icB.csv` was 3,130 bytes.

### Direct server upload

Server provisioning used 768-character base64 chunks, about 13,000 SSH round
trips for a 9 MB package. It now uploads the archive with a single SFTP
`putfo` and verifies a SHA-256 checksum; the chunk path remains only as a
fallback. 5.1.15 was not published separately.

## 5.1.16


### Single-flight deployment

Two upgrade clicks could run two `install_linux.py` processes in the same
managed root. One won; the other left an orphan `env-*` directory and repeated
`tail: cannot open ...setup-*.log` messages.

`provision()` now takes `managed-v1/deploy.lock`. A concurrent non-force call
returns `另一个部署正在进行，请等待完成后再试。`; `force=True` clears a stale lock and
proceeds. The lock is removed in `finally`.

### Uninstall first

`_provision_body()` computes the archive and build identity first, returns
early when the receipt already records the same `build.source_sha256`, and
otherwise stops the old server, removes every `code-*`, `env-*`, `source-*`,
`install-*` and `setup-*` entry plus `server.json`, and only then uploads. One
managed root therefore holds exactly one application version.

### Fast upload

The SFTP upload from 5.1.15 is the primary path; base64 chunking is only a
fallback.

### Known limitation

The 5.1.16 cleanup assumes the previous installer has already exited. If an
`install_linux.py` from an earlier attempt is still running inside `env-*`,
removal can fail with `Directory not empty` after `code-*` has been deleted,
leaving a broken environment. Stop the old installer and remove
`managed-v1/env-*` manually before retrying; do not start a second deployment
while the first is still repairing dependencies.

## Compatibility


- `bundle_format` 1; operator protocol 3 / revision 3.7.
- Bundled library `main` 0.1.1: 7 packages, 1174 descriptors, 79 routes.
- Legacy 8.x libraries remain rejected.

## 5.1.16 artifacts


| Asset | Size | SHA-256 |
| --- | ---: | --- |
| `Operon_Setup.exe` | 426,754,774 | `34f9ed4c0f278d744c15fc44c76257a7ca87a96e1f6e3ed82ee784c0bb25416d` |
| `Operon-5.1.16-Server.zip` | 9,170,004 | `2c0ea821409ef6a75f0b0a7ed79198d15934eb5279444e1c89d8c7104960f159` |
| `operon_studio-5.1.16-py3-none-any.whl` | 675,711 | `aa3c87f82ceff13de5c094616ca8526f726786307bed380d77ce162b0ae84ddb` |

The published release is `v5.1.16` (release id 444814901), which is the
`latest` release at the time of this note.
