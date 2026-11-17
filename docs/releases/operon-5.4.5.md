# Operon Studio 5.4.5

Released 2026-11-17. Software-only update; no library or route changes.

## Fixed

| Problem | Cause | Fix |
|---|---|---|
| Installing 5.4.4 deleted the version it had just installed (`versions/5.4.4-<id>` missing, launcher reports "系统找不到指定的文件") | The post-commit sweep added in 5.4.4 called `RemoveVersionTrees(root)`, which removes every directory under `versions/` except staging trees, so it also removed the newly promoted version and then `versions/` itself | `RemoveVersionTrees(root, keep)` now skips the tree named by `keep`; the post-commit sweep passes the new version, while old-version cleanup keeps the previous behaviour. New `InstallEngine.IsStaleVersion(directory, keep)` is the single predicate used by both filter and retry loop |
| A restarted agent could still block the pre-extraction cleanup for 20 s or more | Unchanged in this release; 5.4.4 lowered the barrier by making `PreflightVersion` advisory and killing agents on every retry | No further change; the retry loop already terminates agents, waits 500 ms and retries up to 40 times |

## Verification

| Item | Result |
|---|---|
| Installer build | `dotnet build installer/OperonSetup.csproj -c Release`, 0 warnings, 0 errors |
| Native installer checks | `PASS: 97 native installer checks` (three new checks: staging tree is not stale, the current version is not stale, an older version is stale) |
| Payload audit | No developer paths; 25,583 files, `75d786ea…51db` |
| Desktop host | `ProductVersion 5.4.5`, `FileVersion 5.4.5.0` |
| Management runtime | `application_version 5.4.5`, Python 3.11.18 |
| Installed acceptance | Not run here; the requester verifies installation |

## Artifacts

| Asset | Size | SHA-256 |
|---|---:|---|
| `Operon_Setup-5.4.5.exe` | 428,838,045 | `f89aea2beeab217d6472ee29602a5caf409ba83cca08ece23df4352ca69c498a` |
| `Operon-5.4.5-Server.zip` | 4,668,927 | `26d5aee1373d67ca0d71b8ab9b807d0eac0bef5325781a716c5ef71528ff2984` |
| `operon_studio-5.4.5-py3-none-any.whl` | 977,834 | `371100406c1ed741a93de75cbc44521534d4ee42f35a3da45a3249ff98c7f352` |

## Upgrading

Run the 5.4.5 Setup over the existing installation. It reads the receipt, retires the previous version tree, extracts the new one and points `current` at it. An installation whose `versions/` directory is already empty — the 5.4.4 failure mode — is treated as "no live version": the pre-flight check only warns, the replacement continues, and the new version tree is written before `current` is updated.

## Known limits

- A second installation rooted elsewhere can still hold the shared pool; the installer only stops agents rooted in its own install directory.
- `tests/test_job_admission.py::test_actual_scientific_workers_...` is order-sensitive under randomized collection; unrelated to installation.