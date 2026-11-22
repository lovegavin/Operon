# Operon Studio 5.7.29

This release closes the two gaps between the desktop surface and the MCP
surface, and fixes the last environment declaration that made a Boltz route
fail on a clean server.

## Added

- `operon_upload_file(source_path, path, overwrite=True)` streams a file from the
  agent's machine into the workspace. The previous `operon_write_binary` carried
  the body as base64 and refused anything above 50 MiB, so FASTQ, BAM and
  reference archives could not be handed to a run at all. The new route
  (`POST /api/v1/workspace/files/raw`) streams the request body into the same
  validated, atomic sink as the buffered path and returns bytes plus sha256.
- `operon_job_figure(job_id, index, format='png', figure_id=None, destination=None)`
  downloads the rendered figure a step produced. The desktop already served
  `GET /api/v1/jobs/{key}/reports/{index}/figure`; only JSON reports were
  reachable from MCP.

Both are covered by `tests/test_workspace_upload.py` (chunked write, overwrite
semantics, no temporary file left behind on failure, four rejected path shapes)
and pinned in `tests/test_mcp_parity.py`, which now also pins `preferences` and
the two resource-cancel methods that had drifted since 5.7.27.

## Fixed

- The `boltz` environment did not declare `pydantic`, although the Boltz CLI
  imports it while parsing its schema. `boltz_predict` and
  `boltz_complex_confidence` therefore failed with `No module named 'pydantic'`
  on a freshly prepared server.

## Library

`main-v1.1.17` carries that declaration change. Routes, readers and operators
are unchanged: 1074 operators, 108 readers, 79 routes.

## Verification

- `pytest tests/test_workspace_upload.py tests/test_task_files.py -q` → 32 passed.
- `pytest tests/test_mcp_parity.py tests/test_parity_control_plane.py
  tests/test_workspace_upload.py -q` → 73 passed.
- `python3 -m operon registry build --scope routes` → 1074 operators / 108
  readers / 79 routes / 0 errors.
