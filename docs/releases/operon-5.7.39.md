# Operon Studio 5.7.39

Released 2026-11-24. Library: main-v1.1.26.

## Fixed

- **A promoted environment forgets its staging prefix.** Installing an
  environment happens in a `.staging-<name>-<hash>` directory that is renamed
  once the install succeeds. micromamba bakes absolute paths into wrapper
  scripts, `.pc` files and module loaders, so tools that read those paths failed
  after the rename: `tRNAscan-SE` reported
  `Can't locate tRNAscanSE/Configuration.pm in @INC` and then
  `Fail to open configuration file .../.staging-genomics-.../bin/tRNAscan-SE.conf`.
  Promoting an environment now rewrites those paths (text files and symlinks,
  binaries are left alone) and `repair` does the same for an environment
  installed by an older build.
- **A conda package with a non-PEP-440 version no longer breaks pip.** The
  conda-forge `vina` build ships a legacy `egg-info` whose `Version:` is
  `aafe735-mod`; every later `pip install` in that environment aborted with
  `InvalidVersion: Invalid version: 'aafe735-mod'` before installing anything.
  After the conda step the installer now rewrites such metadata from the
  `conda-meta` record and renames the directory to `<project>-<version>`.
- **A failed environment preparation records why.** `_validate()` rejected a bare
  requirement that also asked for `no_build_isolation`
  (`ValueError: only https package sources are allowed: cooltools>=0.6`) and the
  worker silently swallowed the exception, so the UI reported a preparation that
  never started. Bare requirements are accepted, and failures are written to the
  environment state with their message.
- **The readiness probe sees the environment libraries.** `probe_environment`
  exported `PATH` but not `LD_LIBRARY_PATH`; torch then loaded the host
  `libstdc++` and numpy failed with `CXXABI_1.3.9 not found`, which reported a
  ready environment as unusable. `<env>/lib` and `<env>/lib64` are now on
  `LD_LIBRARY_PATH`.
- **A run keeps its workflow input paths absolute.** Launching a workflow called
  `relative_manifest()` with the job directory, which rewrote `x-operon-path:
  workflow` parameters such as `chromsizes` into `../../../...`. Export keeps the
  relative form (a workflow must stay movable); a run keeps the absolute path.
- **The packaged TSV reader is imported from where it lives.** The Hi-C adapter
  imported `operon_hic.readers.tsv_reader`, a module that does not exist in the
  built package, so `analyze_contacts` failed for every method except `pileup`.

## Readiness

An environment's own declared resources are now part of its readiness: if
`alphafold2` declares nine library units and none are present, the environment
reports `incomplete` with `resources_declared 0/9` instead of `ready`. A resource
that merely lists the environment as a consumer (the shared ColabFold MSA
database, 206 GB, consumed by `boltz` and `colabfold`) stays a warning, so
downloading it does not block a working environment.

## Library

`library main-v1.1.26` carries the Hi-C import fix and the environment changes
behind the runs above:

- `vina310` is a new environment pinned to Python 3.10 with the conda-forge
  `vina=1.2.2` bindings, and `vina_dock_python` is assigned to it. The assignment
  map (`environment_assignments.json`) is the registry's source for
  `resources.environment`; an operator's own declaration does not override it, so
  the assignment is what makes the readiness probe look in the right place.
  `numpy==1.23.5` is pinned there because the bindings still call `np.int`.
- `xgboost` moved from PyPI to conda-forge (the PyPI wheels need glibc 2.28 while
  this host is CentOS 7), `fpocket>=3.1` for `structure_pocket_detect`,
  `jsonschema>=4.0` for `boltz` and `ligandmpnn` (both tools import it at run
  time), and `pandas>=1.5,<2` for the side-chain packer, which needs the
  numpy-1.23 ABI.

## Added

- The deep-learning operators now default `device` to `auto`: the resolver asks
  the environment that runs the model whether torch can see a CUDA device and
  picks `cuda` when it can, so a machine with a GPU no longer runs every model
  on the CPU. `cpu` and `cuda` still work when pinned, and an unknown value is
  rejected instead of silently falling back. Verified on the acceptance host
  (RTX 3090): `ligandmpnn_side_chain_packing` completes in 185 s,
  `proteinmpnn_design` in 83 s, `esmfold_predict` in 58 s (538 s on CPU), and
  `boltz_predict` runs with `--accelerator gpu`.

## Coverage

Every bundled operator is now exercised through a real reader -> operator route
on the managed server: **1071 of 1074 (99.7%)** completed in this cycle. The
four that remain are accounted for:

- `alphafold2_predict`, `alphafold2_batch_predict`: the databases are linked as
  downloads and are still arriving (about 220 GB); the operator only accepts a
  full `--data_dir`, so they cannot finish before the tree is complete.
- `openfold_predict`: the bundled OpenFold checkout has no
  `attn_core_inplace_cuda` kernel source, and `openfold/utils/kernel/attention_core.py`
  imports that extension at module import time, so the model cannot load even on
  CPU. This is recorded as an offline gap, not an operator defect.
- `boltz_predict`: completes in 129 s once the CUDA kernels are off; boltz imports `cuequivariance_torch` when they are on, and the managed environment does not ship it. The operator now defaults to `--no_kernels`.


