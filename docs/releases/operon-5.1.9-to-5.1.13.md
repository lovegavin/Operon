# Operon Studio 5.1.9 to 5.1.12

This note covers only the changes after 5.1.9. Per-version details remain in
`operon-5.1.10.md`, `operon-5.1.11.md` and `operon-5.1.12.md`.

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

## 5.1.13

- Added `GET /api/v1/jobs/{key}/results` and `results/file` for complete result
  inventory and download, including composite `stages/<index>/...` paths.
- Added MCP tools `operon_result_files`, `operon_download_result`,
  `operon_download_results`, `operon_download_artifact`, and `operon_download_report`.
- Downloads are confined to the workspace; absolute paths and `..` are rejected.

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

## Compatibility

- `bundle_format` 1; operator protocol 3 / revision 3.7.
- Bundled library `main` 0.1.1: 7 packages, 1174 descriptors, 79 routes.
- Legacy 8.x libraries remain rejected.

## 5.1.12 artifacts

| Asset | Size | SHA-256 |
| --- | ---: | --- |
| `Operon_Setup.exe` | 396,537,538 | `a604b98852168f079de82fed4420602e992fb93c026c0bdbbeca3e647008a72e` |
| `Operon-5.1.12-Server.zip` | 9,158,813 | `8c2a1d488216f7a0a8a73bb0f662187a5d1bb48718df7208abdfadb4ad2241c8` |
| `operon_studio-5.1.12-py3-none-any.whl` | 673,249 | `acbd155f9f393b4047bad57b512106934563945900cb5a23cef086564eee3b6c` |