# Operon Studio 5.4.3

Released: 2026-11-17

This release changes the order and the completeness of the teardown that a
reinstall or an uninstall performs. It does not change operator behaviour, the
operator library format, or the workflow protocol.

## Fixed

| Defect | Fix |
| --- | --- |
| Replacing an installation deleted files while MCP adapters and the desktop backend were still running. | `PrepareReplacement` now stops every `python.exe`/`pythonw.exe` under the install root before it clears the shared pool or removes a version directory, and logs `Stopped N MCP/backend process(es) before replacing files.` |
| A killed MCP adapter was started again immediately by its client, so files stayed locked and the replacement failed with a sharing violation. | `operon/installation_maintenance.require_idle()` refuses to start while Setup holds the maintenance window. `operon mcp`, every CLI command, `scripts/desktop_server.py` and the MCP stdio entry point call it first and exit with `Operon is being updated or uninstalled; start again after Setup finishes.` |
| Uninstall closed the window and then waited up to 30 s for the remaining processes to leave on their own. | `InstallUpgrade.Prepare(..., stopAgents)` stops the non-host processes as soon as the window closes; `Uninstall` passes `TerminateAgents(root)`. The 30 s wait remains only as a fallback. |
| `UninstallManagedOnly` killed agents only after the token revocation and before deleting files, without a retry loop. | It now calls `TerminateAgents(root)` (up to 25 passes, 200 ms apart) before `TerminateManagedProcesses`. |

## Verification

| Check | Result |
| --- | --- |
| `pytest tests/test_installation_idle.py tests/test_mcp_installation_guard.py` | 6 passed |
| `dotnet build tests/native_setup/SetupTests.csproj -c Release` | 0 warnings, 0 errors |
| Native installer harness | `PASS: 94 native installer checks` |
| Idle start | `require_idle()` returns without raising when no maintenance event is set |
| Maintenance start | `require_idle()` raises `SystemExit` with `updated or uninstalled` while Setup holds the window |
| Clean install | not run here (the requester verifies installation) |
| Artifact hashes | recorded in the table below |

## Artifacts

| Asset | Bytes | SHA-256 |
| --- | ---: | --- |
| `Operon_Setup-5.4.3.exe` | 428,834,027 | `c4b80f8b50b70c49fe0823f43d44e19ed688c9c9ea94c21bbe1ff6e35b16b452` |
| `Operon-5.4.3-Server.zip` | 4,665,298 | `94bc7bd37fe5e0e4d7c2dee48c78f1d50fcb12d0bdd178dfd9973df4e7c8cf58` |
| `operon_studio-5.4.3-py3-none-any.whl` | 977,835 | `b402e932689b47cd81a36ffab0f2e064f9e51c166d0094a53c661070d71464ca` |

## Upgrading

Run the 5.4.3 Setup over the existing installation. Setup stops the old
installation's MCP adapters and backend before it removes the old version
directory, and each adapter that is restarted during the window exits instead of
holding the directory; the client reconnects when the window closes.

The installation directory, workspace, saved workflows and the operator library
are preserved. `main-v0.1.28` remains the bundled baseline library.

## Known limits

- A second, independent installation that is still running keeps its own MCP
  adapters; only agents rooted in the installation being replaced are stopped.
- `tests/test_job_admission.py::test_actual_scientific_workers_...` is sensitive
  to test ordering because the upstream launcher registers a process after it
  reports `running`.
