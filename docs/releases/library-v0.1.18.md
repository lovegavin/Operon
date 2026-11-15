# Library 0.1.18 - CPU-only esmfold, pinned Boltz, environment repair

Released 2026-11-15 as `operon-library-v0.1.18`.

## Changes

- `esmfold` no longer pins `torch==2.3.1` in `requirements`; it uses `torch_cpu: true` and `torch_version: 2.3.1`, so Linux installs the CPU wheel instead of resolving the default CUDA wheel (the 2.17 GB download that stalled on the shared server).
- `boltz` uses the pure-wheel environment: no conda packages, no `libstdcxx-ng` on Windows, `torch_cpu: true`, `torch_version: 2.3.1`, `omegaconf==2.3.0`, `antlr4-python3-runtime==4.9.3`, and the exact wheel set already validated locally (numpy 1.26.4, scipy 1.13.1, pandas 2.2.3, scikit-learn 1.6.1, numba 0.61.0, rdkit 2024.3.2, gemmi 0.6.5, dm-tree 0.1.8, pytorch-lightning 2.5.0, wandb 0.18.7).
- `environment_install` installs the pinned CPU torch (`torch_version`) so torch 2.6's `weights_only=True` default cannot reject `DictConfig` checkpoints.
- Declared environments remain: antifold, boltz, colabfold, esm3, esmfold, openmm81.

## Verification

- `tests/test_rc6_new.py` covers Boltz pins, no `libstdcxx-ng`, `omegaconf`/`antlr4` and script timeout/LD paths.
- Real environment install on Windows: `boltz` ready, 2,181,501,790 B / 51,221 files, `import boltz` succeeds; `spec_sha256 4fcc0530fca6a79ae3cd3e8e171e1525521afd01df118b93726c3b3ccef907df`.
- The 20-operator minibinder panel reproduces the previous sequence metrics with zero differences under app 5.1.17-rc6.

## Compatibility

- Minimum application: 5.1.6.
- Built with application: 5.1.17.
- Bundle format 1, operator protocol 3 (revision 3.7).
