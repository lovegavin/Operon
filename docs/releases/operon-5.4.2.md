# Operon Studio 5.4.2

5.4.2 makes a forced reinstall or uninstall really end the processes that belong
to the installation being replaced. 5.4.1 could still leave an MCP adapter (and
the shared pool it had started) running from a version directory that no longer
existed; those survivors held the pool registration the new installation needed,
so the first library operation after an upgrade waited for the pool forever.

## Fixed

| Area | Change |
| --- | --- |
| Removed versions | `InstallEngine.TerminateOrphanAgents()` stops `python.exe`/`pythonw.exe` processes whose image lives under `versions/<id>/runtime/python` while `<id>` no longer exists, so an adapter from a replaced build cannot outlive it. |
| Replacement sequence | Orphan cleanup runs inside `PrepareReplacement` (after the disconnect pass, before the pool is cleared) and in both uninstall paths. |
| Disconnect scope | `DisconnectAgents(profile, everything)`: a receipt-backed replacement revokes only that installation's profile; the all-profile sweep is reserved for legacy trees without a receipt. Replacing one installation no longer revokes agents of another. |
| MCP adapter | `operon/mcp_server.py` exposes `installation_root()` and `require_installation()`; `serve()` refuses to start when `operon/managed_pool.py` is gone, printing `the installation at <root> was removed or replaced; restart the MCP client` and exiting. Clients reconnect instead of blocking on a dead code root. |

The first 5.4.2 build classified a path by the `versions` directory itself, so
an adapter from a removed release was only recognised when the whole `versions`
tree was gone. The classifier now reads the `<id>` segment and tests
`versions/<id>`; the harness gained the case that catches this (one removed id
beside a live `versions` directory) and the rebuilt installer passes it.

## Verification

| Check | Result |
| --- | --- |
| Native installer harness | `PASS: 94 native installer checks` (4 orphan-classifier checks, including one removed version id beside a live `versions` directory) |
| MCP guard tests | `tests/test_mcp_installation_guard.py` 3 passed |
| Clean install | `<test-dir>`, version directory `5.4.2-90d343c140d7`, `operon --version` = `Operon 5.4.2` |
| Version rendering | `/health`, `/api/version` and bootstrap all report `5.4.2 (90d343c1)` |
| Built-in library | `main-v0.1.28`, 7 packages, 1,177 descriptors, 1,069 operators, 108 readers |
| Library operations | `fork1-v0.0.0` imported beside `main-v0.1.28` and removed again; catalog generation changed on removal |
| MCP adapters | 69 tools, `operon_resources` reports 16 resources |
| Orphan cleanup | an adapter started from `<foreign-root>\versions\<id>\runtime\python\python.exe` survived the pre-build upgrade and was stopped by the next one: `Stopped 1 orphaned agent process(es) with removed code roots.` |
| Upgrade in place | second install produced `5.4.2-1c07d87f487d`; `/health` reported `5.4.2 (1c07d87f)` |

## Artifacts

| Asset | Bytes | SHA-256 |
| --- | ---: | --- |
| `Operon_Setup-5.4.2.exe` | 428,828,067 | `654d15ba1ec909344a77bc1b450ae2da971feb2c328e5e5591924832d6f5e6ce` |
| `Operon-5.4.2-Server.zip` | 4,661,176 | `87f4647820eafd8f3c9811bdb8971a7d095463aa53641d49813d53bd50f49d4b` |
| `operon_studio-5.4.2-py3-none-any.whl` | 977,643 | `d76db75e3ebb6068b96cb1b0e32816b92dc073e3106ad0c843c063c87484650b` |

## Upgrade notes

Install 5.4.2 over the existing tree; the installer replaces the previous
version in place. A running MCP client is disconnected and its process is
stopped, so restart the client after the installer reports completion. Workspace
data, profiles and results are untouched.

## Known limits

- The shared pool is single-owner per machine: an adapter from a *live* second
  installation still competes for it. Orphan cleanup only removes processes
  whose version directory is gone.
- `test_actual_scientific_workers_keep_independent_memory_and_logs` remains
  order-sensitive under randomized test ordering; it is an upstream launch race,
  not a product defect.
