# Operon Studio 5.1.9 to 5.1.14

This note covers only the changes after 5.1.9. Per-version details remain in
`operon-5.1.10.md` through `operon-5.1.14.md`.

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

## 5.1.14

### Local result download

`Application.artifacts.result()` calls `JobService.result_file()`, but the 5.1.13
implementation defined only `result_path()`. Every local result download
returned HTTP 500 while listing worked. `result_file()` now aliases
`result_path()` with the same containment and existence checks.

Remote and composite listing still requires a 5.1.14 server; older servers do
not expose the `result_files` RPC.

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

## 5.1.14 artifacts

| Asset | Size | SHA-256 |
| --- | ---: | --- |
| `Operon_Setup.exe` | 426,748,388 | `090135dcc88afe9e2bee3615ccb2de6413db3a789d56c1efd96913055e31bee6` |
| `Operon-5.1.14-Server.zip` | 9,166,996 | `8956e5c27418b0c83c486402384977fb4b0beb5128da28a7a00b83ff4c2fa9ed` |
| `operon_studio-5.1.14-py3-none-any.whl` | 674,968 | `0aa742b5a829378bfffe179968c4a00f4ee6eba68984789ef73091a292b3e8a8` |