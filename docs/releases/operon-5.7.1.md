# Operon Studio 5.7.1

Released 2026-11-19. Library **1.1.1**.

## Added

- **Per-file resource downloads.** A maintenance unit can now declare one
  download source per file (`path`, `url`, optional `archive`/`member`,
  `bytes`, `unit`). `POST /api/v1/large-resources/{name}/download` with a
  `unit` downloads only the files of that unit that are still missing and
  skips files that already exist, so a linked directory keeps working while a
  single absent file is fetched.
- **Archive member extraction.** Tarballs are streamed and only the declared
  member is written; the produced file is size-checked against the manifest.
- MCP: `operon_resource_download` gained `unit` and `profile_id`, and three
  tools were added for the operator-library synchronisation introduced in
  5.7.0 — `operon_remote_library_plan`, `operon_remote_library_sync` and
  `operon_remote_library_status` (72 → 75 tools).
- CLI: `operon resources download --unit` and `--overwrite` are now forwarded
  to the service instead of being ignored.

## Fixed

- **A unit that only documents a project page is no longer downloaded as a
  file.** Previously the resource downloader fetched the upstream repository
  page (for example the AlphaFold-2 GitHub page) and stored the HTML under the
  unit name, which looked like a no-op in the interface. Such a unit now
  returns `409` with a message that asks for a link or a declared per-file
  source.
- **Environment bridge no longer imports NumPy eagerly.** Environments that do
  not ship NumPy previously failed before reading any input; `operon/env_worker.py`
  imports it only when an ndarray has to be read or written.
- The `alphafold2` environment declares `numpy`, so a fresh installation can run
  the AlphaFold-2 operators without a manual `pip install`.
- The environment card shows `取消中…` immediately after a cancel request and
  disables the button until the service reports the new state.

## Compatibility

- Application 5.7.1 requires library 1.1.1 or newer.
- Published 5.7.0 assets stay immutable; 5.7.1 supersedes them.
