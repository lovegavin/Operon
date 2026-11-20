# Operon Studio 5.7.20

## Added

- The remote environment snapshot now reports `resources_total`,
  `resources_ready` and `resources_missing` for every environment, computed
  from the declared resource units of the installed library.
- The PDB mmCIF archive (`alphafold2` → `pdb_mmcif/mmcif_files`) can now be
  fetched with `rsync`, which is the only transport the PDB publishes for that
  tree; the entry lives in `resources.json` next to the HTTP sources, so the
  card lists nine sources and the button reads `rsync 拉取`.
- Resource cards decide whether a download is possible from the
  `download_supported` flag returned by the service instead of the presence of
  the `downloadable` list.

## Changed


- An environment whose interpreter and dependencies are ready but whose
  declared resources are incomplete now reports `incomplete` with a readable
  reason (for example `资源未齐备（4/9）：afdb`) instead of `ready`.

## Fixed

- F-131: the remote unit payload could render as 无下载源 even though the
  service listed eight download sources for the unit, because the card only
  looked at `downloadable.length` after the payload crossed the remote bridge.
- F-132: an environment card could claim 已准备 while its resources were still
  missing, because the environment status did not take resource readiness into
  account.

## Verification

- `tests/test_environment_resources.py` (3 tests) covers unit counting, a fully
  present unit, and the status downgrade in `environment_snapshot`.
- `tests/test_remote_environments.py tests/test_environment_api.py
  tests/test_resource_api.py` pass (26 tests).
- Clean install acceptance and the asset hashes are recorded in
  `docs/releases/operon-5.7.20-test-report.md`.

## Known limitations

- Ten resources still ship without a declared file list
  (`ligandmpnn`, `esm_if1`, `esmfold`, `colabfold`, `rfdiffusion`, `prodigal`,
  `boltz`, `antismash`, `openfold`, `antifold`). Their cards cannot report which
  file is missing yet; the manifests and the `未校验` state land in 5.7.21.
- `rsync` is still taken from the host `PATH`; bundling the MSYS2 build with the
  runtime is part of 5.7.21.
