# Operon Library 0.1.10

## Boltz environment: binary wheels only

The `boltz` environment no longer uses conda packages and no longer needs
`libstdcxx-ng`. All native dependencies are installed from PyPI binary wheels:

- numpy 1.26.4, pandas 2.2.3, scipy 1.13.1, scikit-learn 1.6.1
- numba 0.61.0, rdkit 2024.3.2, gemmi 0.6.5, dm-tree 0.1.8
- torch CPU wheel, pytorch-lightning 2.5.0, hydra-core 1.3.2
- boltz 2.2.1 (`--no-deps`)

`ihm` and `fairscale` are pure-Python sdists; everything else is a wheel.
The environment works on Windows and Linux Python 3.11 and keeps
`~/.local/share/operon/resources/boltz` as the cache root.

## Verification

- Windows Python 3.11 clean venv: all packages installed from wheels.
- `import boltz` and `python -m boltz.main --help` pass.
- Library registry: 1069 operators / 108 readers / 1177 descriptors.
