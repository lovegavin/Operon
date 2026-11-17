# Operon Studio 5.4.4

Replacing an installation no longer fails when an agent restarts while Setup
removes the previous version. This restores the 5.1.17 behaviour (log and keep
going) while keeping the newer maintenance gate for versions that ship it.

## Fixed

| Symptom | Cause | Fix |
|---|---|---|
| `软件文件仍被以下程序占用，尚未开始删除` aborts the update | 5.3.0 added `PreflightVersion` before removal; any file held by a respawned agent threw and stopped the whole install. 5.1.17 had no such preflight. | Preflight is advisory at both call sites: failures are logged as `Preflight delayed: …` and removal continues. |
| Old version directory survives because an agent was restarted mid-cleanup | Cleanup retried 15 times but only terminated processes, never the respawned Python agents. | `RemoveVersionTrees` now calls `TerminateAgents(root)` on every round, retries 40 times with 500 ms back-off. |
| Leftover old version after a successful switch | Removal only ran once, before extraction. | After the new version is committed and current, `RemoveVersionTrees` runs again to sweep anything that survived. |

The maintenance gate (`require_idle`) is unchanged: installations that contain
it refuse to start agents while Setup holds the maintenance event, so future
updates do not race against a restarting client.

## Verification

| Check | Result |
|---|---|
| `dotnet build installer/OperonSetup.csproj -c Release` | 0 warnings, 0 errors |
| `SetupTests.exe <fresh-dir>` | `PASS: 94 native installer checks` |
| `PackageRelease` audit | clean (no developer paths) |
| Installed-run test | not executed here; performed by the requester |

## Artifacts

| Asset | Bytes | SHA-256 |
|---|---:|---|
| `Operon_Setup-5.4.4.exe` | 428,834,350 | `b675009e470b5f526e13cfcfa417e910cac0029f3ecb1d44b35d5a21ae30b77b` |
| `Operon-5.4.4-Server.zip` | 4,665,487 | `e5c0c70a6ff2927fae3712b120e2db2c1261b4b2eff7398ac660446689875003` |
| `operon_studio-5.4.4-py3-none-any.whl` | 977,834 | `94837d871cf4e537622b4537210f53f0ed3076f25c0d173bd2c8a7c5f560d2ca` |

Payload: `Operon-Studio-v5.4.4-Windows-x64.zip`, 357,057,235 bytes,
`1bfc22b30d7e0d4149b15e28b61548a6d3495caacd11766b47de58b695593022`,
25,581 files. Base operator library: `operon-library-main-v0.1.28.operon-library.zip`.

## Upgrading

Install 5.4.4 over the existing installation. If the previous version predates
the maintenance gate, Setup still terminates the restarted agents; the update
now completes even if one is briefly alive, and the leftover directory is
removed after the switch.

## Known limits

- An agent that keeps restarting for the whole removal window can still delay
  cleanup; the new version is installed regardless and the sweep runs again.
- `tests/test_job_admission.py::test_actual_scientific_workers_…` remains
  order-sensitive under parallel test execution (pre-existing upstream race).
