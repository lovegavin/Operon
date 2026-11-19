# Operon Studio 5.7.5

Released 2026-11-19.

This release finishes the runtime status panel work started in 5.7.4: the
panel now reports installation progress from the phase a preparation is in,
keeps a remote card in step with the server, and reconciles a cancellation
that arrives after the environment was already committed.

## Fixed

- F-64: an environment that had not written any bytes yet showed a fixed 0%.
  The card now renders an indeterminate bar while the stage reports no byte
  count, and prints the phase plus the bytes in use instead of a fake
  percentage.
- F-65: a remote environment card kept the percentage captured when the last
  action returned, because the three second refresh only queried the local
  installation. The panel now polls the selected server as well, so the card
  follows the remote state.
- F-66: cancelling a preparation that had already been committed replaced the
  finished environment with a cancelled one. The installer keeps a terminal
  phase, and the cancel response now reports `completed: true`; the panel
  tells the operator that the environment finished installing and that the
  cancellation had no effect.
- F-67: pip download sizes were ignored, so dependency installation looked
- F-68: cancelling an environment that was not preparing returned 404 instead of a readable outcome; the response is now 200 with completed/cancelled flags and a reason.
  frozen. Lines such as `Downloading ... (201.4 MB)` are parsed and folded
  into the byte counter, which now only grows.
- The disk usage sampler no longer lowers the byte counter that dependency
  output already advanced.
- The pip progress pattern accepts `1.2/2.4 GB` as well as `1.2 GB`.

## Verification

- `pytest tests/test_environment_install.py` (16 tests), 
  `tests/test_environment_api_runtime.py`, `tests/test_remote_environments.py`
  and `tests/test_environment_requirements.py` pass.
- `npm test` in `frontend`: 43 files, 265 tests pass.
- `npm run build`: 5.7.5 bundle.
- A clean installation of the packaged setup installs 18 environments and 16
  resources, cancels a running preparation within seconds, and reports a
  committed installation as completed rather than cancelled.

## Known limitations

- `operon environment status <name>` still resolves names against the current
  working directory instead of the installation environment root.
- Cancelling a resources download on a remote server has no agent method yet.
- The operator coverage sweep still runs against a test installation; the
  numbers reported in the test report are the ones recorded there.
