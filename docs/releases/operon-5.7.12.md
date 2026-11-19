# Operon Studio 5.7.12

Patch release on top of 5.7.11 that makes a fresh Windows install finish every
environment it can build, and reports the environments it cannot build honestly.

## Fixed

- **F-93** — a step that prints nothing while it resolves dependencies was killed
  by the 60 s silence watchdog. Large `pip` resolutions (`colabfold` and its JAX
  stack) need minutes before the first line, so the watchdog now grants a 300 s
  start-up window and keeps the 60 s silence limit after the first output.
- **F-94** — a platform-gated environment was shown as *installed failed*.
  It now stays `missing` with the platform note, matching its badge.

- **F-95** `operon_sdk.figures.register_figure` crashed with `'Context' object has no attribute 'out_dir'` when an operator ran through the environment bridge; the output directory now comes from `context.memory.run_dir` and only falls back to `context.out_dir`.
## Verification

- Clean Windows install: 12 of 18 environments ready, 1 genuine dependency
  failure (`colabfold`, F-93) and 5 platform-gated environments (expected).
- `tests/test_environment_install.py` 19 passed; environment suites 47 passed.

The library is unchanged (`main-v1.1.6`), so no library release accompanies this
patch.
