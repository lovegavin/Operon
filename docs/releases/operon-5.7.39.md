# Operon Studio 5.7.39

Released 2026-11-23. Library: main-v1.1.25.

## Fixed

- **A promoted environment forgets its staging prefix.** Installing an
  environment happens in a .staging-<name>-<hash> directory that is renamed
  once the install succeeds. micromamba bakes absolute paths into wrapper
  scripts, .pc files and module loaders, so tools that read those paths failed
  after the rename: 	RNAscan-SE reported
  Can't locate tRNAscanSE/Configuration.pm in @INC and then
  Fail to open configuration file .../.staging-genomics-.../bin/tRNAscan-SE.conf.
  Promoting an environment now rewrites those paths (text files and symlinks,
  binaries are left alone) and 
epair does the same for an environment
  installed by an older build.
- **A failed environment preparation records why.** _validate() rejected a bare
  requirement that also asked for 
o_build_isolation
  (ValueError: only https package sources are allowed: cooltools>=0.6) and the
  worker silently swallowed the exception, so the UI reported a preparation that
  never started. Bare requirements are accepted, and failures are written to the
  environment state with their message.
- **The readiness probe sees the environment libraries.** probe_environment
  exported PATH but not LD_LIBRARY_PATH; torch then loaded the host
  libstdc++ and numpy failed with CXXABI_1.3.9 not found, which reported a
  ready environment as unusable. <env>/lib and <env>/lib64 are now on
  LD_LIBRARY_PATH.
- **A run keeps its workflow input paths absolute.** Launching a workflow called
  
elative_manifest() with the job directory, which rewrote x-operon-path:
  workflow parameters such as chromsizes into ../../../.... Export keeps the
  relative form (a workflow must stay movable); a run keeps the absolute path.
- **The packaged TSV reader is imported from where it lives.** The Hi-C adapter
  imported operon_hic.readers.tsv_reader, a module that does not exist in the
  built package, so nalyze_contacts failed for every method except pileup.

## Library

library main-v1.1.25 carries the Hi-C import fix and declares xgboost for
xgboost_regressor: the operator declared no imports, so the readiness probe
never checked the dependency, and the PyPI wheels need glibc 2.28 while this host
is CentOS 7. It is installed from conda-forge instead.

The library also declares two packages the operators need at run time:
jsonschema>=4.0 for boltz (boltz predict refuses to start without it) and
fpocket>=3.1 for core (structure_pocket_detect resolves the binary through the
shared runtime). boltz_predict defaults to model=boltz2 while the downloadable
resource set only carries the Boltz-1 checkpoint, so a boltz2 run downloads
weights at run time; pass model=boltz1 for an offline run.

## Added

- The deep-learning operators now default `device` to `auto`: the resolver asks
  the environment that runs the model whether torch can see a CUDA device and
  picks `cuda` when it can, so a machine with a GPU no longer runs every model
  on the CPU. `cpu` and `cuda` still work when pinned, and an unknown value is
  rejected instead of silently falling back. Verified on the acceptance host
  (RTX 3090): `ligandmpnn_side_chain_packing` completes in 185 s and
  `boltz_predict` runs with `--accelerator gpu`.
