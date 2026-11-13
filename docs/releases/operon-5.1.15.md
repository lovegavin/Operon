# Operon Studio 5.1.15

## Remote result retrieval

- Composite jobs now list remote child results with `(profile, remote job id)` instead of reusing the desktop state key, fixing the HTTP 500 / `找不到远程运行记录` failure.
- `RemoteManager.result_files_for(profile_id, job_id)` calls the remote `result_files` RPC directly; remote downloads no longer depend on a locally cached job record.

## Faster server deployment

- Remote source upload chunks are 16 KiB instead of 576 bytes, cutting a ~7.5 MB deployment from roughly 13,000 acknowledged SSH writes to about 600.
- Upload content is unchanged: allowlisted source, two library archives, no workspace, profiles, environments, data or credentials.

## Verification

- Local composite result listing/download over HTTP and MCP was verified on 5.1.14 with a real copied job.
- A real SSH result listing returned 10 files / 19,211 B and fetched `icB.csv` with exact 3,130 B.
