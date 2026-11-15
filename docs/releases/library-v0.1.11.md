# Operon Library 0.1.11

CPU-only ESMFold environment.

- `esmfold` now declares `torch_cpu: true`; Operon installs torch from
  `https://download.pytorch.org/whl/cpu`, so no CUDA wheel is downloaded.
- The `torch==2.3.1` requirement was removed because it resolved to the default
  CUDA wheel on Linux.
- `fair-esm==2.0.0`, numpy 1.26.4, scipy 1.13.1, biopython 1.83 and the
  remaining dependencies stay unchanged.
- The 2.5 GB ESMFold checkpoint remains an external resource and is not
  installed by `prepare`.
