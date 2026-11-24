# Operon Studio 5.8.0

Released 2026-11-24. Library: main-v1.2.0.

5.8.0 closes the operator campaign: every one of the 1074 operators in the
catalog has run to `complete` at least once through a real reader, and the
deep-learning operators now choose the GPU by themselves.

## Highlights

- **All 1074 operators verified.** The last gap was `alphafold2_batch_predict`,
  which needs a real AlphaFold-2 database tree; it now runs on the GPU together
  with `alphafold2_predict`. Every other operator already ran to `complete`
  against public data (PDB, GTEx, PBMC3k, ClinVar, chr21 annotation, E. coli
  reads, UniProt, BiGG, Pfam, GO, Hi-C pairs, docking ligands).
- **Deep learning runs on the GPU by default.** Forty-seven operators took a
  `device` parameter that defaulted to `cpu`. The schema now defaults to `auto`
  and `_device_common.resolve_device()` asks the interpreter that will execute
  the step whether CUDA is visible, so a GPU host uses it and a CPU host still
  works. On the test host (RTX 3090) `esmfold_predict` dropped from 538 s to
  58 s and `proteinmpnn_design` runs in 83 s.
- **AlphaFold-2 and ColabFold use CUDA jax.** Both environments installed the CPU
  `jaxlib` wheel, so model inference ignored the GPU (`use_gpu` only reached
  `--use_gpu_relax`). The library now pins `jaxlib 0.4.23+cuda12.cudnn89` from the
  JAX CUDA-12 index plus `cuda-cudart=12.2` and `cuda-cupti=12.2`, which is what
  the wheel is linked against; `jax.devices()` reports `[cuda(id=0)]` in both
  environments and `alphafold2_batch_predict` holds 18.9 GB of device memory
  while it runs.

## Fixed

- **A resource unit is checked in the directory it declares.** `expected_files()`
  flattened a unit's files into the resource root and the panel then reported
  `pdb_mmcif/mmcif_files` as missing although the link was complete. Files are
  looked up under `<unit.path>/<file>` on both sides (library and desktop).
- **The panel's per-file verdict follows the unit verdict.** The mirror code
  matched bare file names against `files_present`, which carries the unit prefix,
  so a complete unit still showed `present: false` for every file and the
  environment stayed `incomplete`. The comparison now uses the leaf name.
- **A stale resource reason is cleared.** An environment that became ready kept
  the old `资源未齐备（8/9）` message because the snapshot only wrote a reason
  when one was absent. A ready gate now clears it.
- **Linking a whole resource tree understands unit directories.** The published
  AlphaFold-2 tree keeps every unit in its own directory; the tree link used to
  require a flat layout. It now looks in the root and one level down, and
  `link_units` expands the declared units instead of collapsing them into one
  `tree` entry (the module is imported from the built wheel, so the source copy
  was never the one running).
- **`alphafold2` declares its library as a resource again.** The nine units are
  listed with their real names (`UniRef30_2021_03_*`, `bfd_metaclust_*_hhm`,
  `mgy_clusters_2022_05.fa`, `uniprot_sprot.fasta`) so a server that already has
  the tree links it instead of downloading 205 GB.
- **Deployment no longer loses a running job silently.** A job whose connection
  drops now fails with a reason instead of sitting in `waiting_connection`
  forever (`OPERON_DISCONNECT_SECONDS`, default 900 s).
- **The pool reports a busy application as retryable.** Submitting a second
  application while a long job holds the shared pool used to raise
  `engine_unavailable`; it now answers `pool_busy` with `retryable: true`.
- **`vina_dock_python` gets Python 3.10.** The conda-forge Vina bindings stop at
  3.10, so the operator is assigned to the new `vina310` environment through
  `environment_assignments.json`; the previous build silently sent it to `core`
  and the probe kept reporting `No module named 'vina'`.
- **Environments installed by an older build can be repaired.** `repair` rewrites
  `.staging-*` paths baked into wrappers, `.pc` files and module loaders, and
  rewrites a conda `egg-info` whose version is not PEP 440 (`vina` ships
  `aafe735-mod`), which used to abort every later `pip install`.
- **The readiness probe exports the environment libraries.** `<env>/lib` and
  `<env>/lib64` now join `LD_LIBRARY_PATH`, so `torch` no longer loads the host
  `libstdc++` and reports `CXXABI_1.3.9 not found`.
- **A launch keeps workflow input paths absolute.** Export still writes relative
  paths (a workflow must stay movable), but a run no longer rewrites
  `x-operon-path: workflow` parameters into `../../../…`.
- **The packaged TSV reader is imported from where it lives.** The Hi-C adapter
  imported `operon_hic.readers.tsv_reader`, which the built package does not
  contain, so `analyze_contacts` failed for every method except `pileup`.
- **A session token that went stale is refreshed once instead of failing the
  page.** A write that answers 401/403 re-reads `/api/bootstrap` and retries
  once, so an open page survives a desktop restart.
- **`operon_submit` accepts many graphs and unlimited concurrency.**
  `operon_submit_many`/`operon_jobs_many` submit a batch over one session and
  `max_parallel_tasks: 0` means "use the host", which the desktop already
  allowed.

- **A quarantined worker frees its lease instead of blocking the pool.** A worker
  killed while its descendants were still alive is parked in `recovery_required`
  with its lease still granted, and the tick only walked the live states: the
  lease charged capacity no process could use and every later unit waited behind
  it until the pool restarted. The tick now polls the quarantined attempts and
  abandons the ones whose recorded process identity is provably dead.
- **A repeated archive member no longer aborts an environment closure.** Both a
  portable CPython archive and a conda-pack closure list some members twice; the
  extractor refused the whole archive. Members are now applied in order, so the
  later entry wins, and a genuinely conflicting member is still refused when the
  bytes differ.
- **A closure symlink replaces the file it renames.** A closure that carries
  `lib/libpython3.11.so` both as a file and as a link to
  `libpython3.11.so.1.0` failed the canvas closure check with `EEXIST`. Links are
  created after the regular members and in their own order, so the last entry
  wins exactly like `tar -x`.
- **Linking a unit verifies the unit.** A unit link that pointed at a directory
  without the unit's files was reported as already linked; the link now lists the
  missing files and refuses.
- **No transfer has a wall-clock deadline.** Environment downloads, uv, conda,
  micromamba and archive extraction run until they finish; only the local
  readiness probes keep a short bound so a hung probe cannot stall the installer.
- **The environment card lifts on hover.** The card now carries the same
  gradient as the primary actions, in both themes.
- **A queued install is no longer reaped by age.** Each environment in a batch
  writes `queued` and then waits for the shared bootstrap lock, and the snapshot
  treated that silence as death after three minutes: "install all" turned a
  healthy queue into a wall of "the last install was interrupted" failures. The
  snapshot now tells the age check which environments still own a worker, so an
  entry that is genuinely waiting is left alone.
