# Library 0.1.7

## Fixes

- Removed `libstdcxx-ng` from the `boltz` conda package list. It has no
  `win-64` build, so `micromamba` failed on Windows with
  `libstdcxx-ng =* does not exist`. Linux now gets the environment library path
  from Operon's `LD_LIBRARY_PATH` injection (5.1.17-rc4 and newer), so the
  explicit conda package is unnecessary.
- `boltz_predict` now resolves the cache from, in order: explicit `cache_dir`,
  `OPERON_BOLTZ_CACHE`, or the library resource root (`resources.json`), so MCP
  jobs use the deployed weights without a per-run path.
- Updated `docs/deployment/resource-configs/boltz_predict.json` to pass
  `cache_dir` (the operator passes it as `boltz --cache`) instead of an unused
  environment-only setting.

## Compatibility

- `minimum_application` 5.1.6, build application 5.1.16.
- No application release; this is a library-only patch.
- `esmfold` still downloads the CUDA torch wheel; slow or reset external
  downloads are a host/network limitation, not an operator change.
