# Operon Studio 5.1.13

## Summary

5.1.13 adds complete result retrieval over HTTP and MCP. Any file below a job's result
directory can be listed and downloaded, whether the job ran locally, on an SSH server,
or as a composite workflow.

## Results API

- `GET /api/v1/jobs/{key}/results` returns the result root and every file with a
  workspace-relative path, size, and modification time.
- `GET /api/v1/jobs/{key}/results/file?path=...` streams one file. Paths are resolved
  inside the job result root; absolute paths and `..` are rejected.
- Composite jobs expose child files as `stages/<index>/<path>` and route each download
  to the child backend (local or SSH).

## MCP tools

- `operon_result_files(job_id)` lists all result files with sizes.
- `operon_download_result(job_id, path, destination=None)` downloads one file.
- `operon_download_results(job_id, destination=None, paths=None)` downloads all or
  selected files, preserving relative paths under `results/<job_id>`.
- `operon_download_artifact(...)` and `operon_download_report(...)` cover retained
  artifact files and stored report JSON.

Every destination is workspace-relative; absolute paths, `..`, and escapes outside the
workspace are rejected.

## Compatibility

- Bundle format 1, operator protocol 3 / revision 3.7.
- Built-in operator library: `main-v0.1.1` (0.1.1), 79 route templates.
- No operator, route, or graph contract change.
