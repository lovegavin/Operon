# Operon Studio 5.1.11

Released 2026-11-14. Library and routes stay at 0.1.1.

## Fixes

- **Stale server cache is rejected.** `RemoteManager` deletes any
  `<profile>.catalog.json` whose recorded application version differs from the
  running desktop build, and an install/upgrade removes the profile catalogue
  and pool snapshot before connecting. A status card can no longer show an old
  version after the server has been updated.
- **Remote polls handle task-folder run events.** `operon/remote/server.py`
  now keys run events under `<workspace>/<task>/results/<job>/runs/...` relative
  to the job output directory. The previous `relative_to(.studio/jobs/<job>)`
  raised `ValueError` and surfaced as `remote_error` with empty artifacts.
- Added `tests/test_remote_cache_5111.py` and `tests/test_remote_poll_paths.py`.

## Verification

- Focused tests: cache invalidation, stable poll keys for launcher, task-run and
  external event files.
- Published artifacts: Setup, Server zip, wheel and `SHA256SUMS.txt`.