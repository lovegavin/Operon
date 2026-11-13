# Operon Studio 5.1.16

## Remote upgrades are single-flight

- A remote deployment now takes `managed-v1/deploy.lock`; a second upgrade without force reports that another deployment is running instead of starting a competing install.
- `force=True` clears a stale lock, stops the old server, and removes the previous `code-*`, `env-*`, `source-*`, `install-*`, and `setup-*` entries before uploading. One managed root therefore contains exactly one version.
- The setup log is created only after cleanup, so the UI cannot tail a log from a failed prior attempt.

## Direct upload

- The server archive is uploaded with one SFTP request instead of hundreds of base64 SSH chunks. A checksum is still verified before extraction; chunked upload remains only as a fallback.

## Result downloads

- `operon_result_files` and `operon_download_result(s)` now work for remote composite jobs by addressing child jobs with their profile and remote job id.

## Compatibility

Bundle format 1; operator protocol 3 / revision 3.7; built-in library main-v0.1.1; 79 routes. No operator or graph contract changed.
