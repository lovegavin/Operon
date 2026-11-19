# Operon Studio 5.7.11

5.7.11 closes the control-plane gap between the desktop UI and MCP, fixes two
resource-download defects that made the Boltz weights impossible to fetch, and
records the Windows availability evidence for the five Linux-only environments.

## Added

- **MCP now covers every front-end operation.** `frontend/src/api.ts` has 106
  methods; 65 were already reachable, 33 are added here, 2 map to
  `operon_write_binary`, and 6 are explicitly not applicable to an agent (GUI
  folder pickers, browser multi-file upload, the bootstrap/url/agent client
  protocol). MCP grows from 107 to **141 tools**, and 33 new `/api/v1` routes
  reuse the same `authorize(request, scope)` capability model as the desktop.
  The audit table lives in `docs/verification/mcp-coverage-5.7.11.md`.
- **Platform support audit.** `docs/verification/platform-support-5.7.11.md`
  records the `micromamba search --platform win-64` evidence showing that
  `hmmer`, `infernal`, `antismash`, `viennarna`, `cooler`, `prodigal`,
  `samtools` and `blast` have no Windows builds, which is why five environments
  are declared for Linux and macOS only.

## Changed

- `resources.json` Boltz entries now carry the real download URLs and sizes
  (`ccd.pkl` 345,859,128 B and `boltz1_conf.ckpt` 3,595,352,714 B) behind the
  Hugging Face mirror and the upstream host.
- UniRef30 now tries `opendata.mmseqs.org` first and falls back to
  `mmseqs.com`, because the first mirror answers `429` for automated clients.

## Fixed

- **F-90** `POST /api/resources/boltz/download` always failed: both download
  entries were bare file names (`"ccd.pkl"`, `"boltz1_conf.ckpt"`) with no URL,
  so the planner had nothing to fetch and the unit could never become ready.
- **F-91** `operon_environment_retry` called a client helper that does not
  exist and prefixed the path with `/api` a second time, so every MCP retry
  raised instead of returning a job. It now uses `client.request` and the same
  paths as the HTTP surface, locally and through an agent.
- **F-92** The UniRef30 download failed with `429` from the primary mirror; the
  fallback mirror answers `206` and the file downloads.

## Verification

- Clean install on Windows: 18 environments, 1,074 operators, 16 resources,
  library `main-v1.1.6`; every environment attempted, five refused with the
  platform note, the rest reach `ready` or report a concrete dependency error.
- Alphafold2 shows `afdb` as an external link with 9 expected files and 8
  download sources; the resource state is `partial` until the missing files are
  linked or downloaded.
- MCP reports 141 tools; `tests/test_parity_control_plane.py` and
  `tests/test_mcp_server.py` pass (96 tests), and the resource suites pass
  (34 tests).
- Artifacts, hashes and the operator coverage snapshot are in
  `docs/releases/operon-5.7.11-test-report.md`.
