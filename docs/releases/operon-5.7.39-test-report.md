# Operon Studio 5.7.39 acceptance

Release 5.7.39, library main-v1.1.26. Every item below was produced on the
licai-srv deployment (/public/home/lihj/Operon, managed micromamba Python 3.11,
one NVIDIA RTX 3090) driven through the local desktop service, the MCP tools and
the operator library.

## Environments

Twenty isolated environments, prepared from the UI and verified through
`GET /api/remote/{rid}/environments`: `alphafold2 antifold antismash boltz
colabfold core dssp esm2 esm3 esmfold genomics hic hmmer ligandmpnn openfold
openmm81 proteinmpnn rfdiffusion rna vina310`. Nineteen are `ready`; `alphafold2`
is `incomplete` by design because its nine declared library units are still
downloading (the readiness gate reports `resources_declared 0/9`).

Two environments were added for this release. `vina310` pins Python 3.10 for the
AutoDock Vina bindings (conda-forge publishes them up to 3.10 only) and
`vina_dock_python` is assigned to it in `environment_assignments.json`, which is
the map the registry uses for `resources.environment`. The assignment mattered:
before it, the operator's own declaration was overwritten with `core`, and the
readiness probe kept reporting `ModuleNotFoundError: No module named 'vina'`.

A promoted environment no longer keeps the staging path: `tRNAscan-SE` from
`genomics` reports `2.0.12` after the fix (it used to fail with `Can't locate
tRNAscanSE/Configuration.pm in @INC`). The conda metadata repair is what lets
`vina310` finish at all: the conda-forge `vina` package ships
`Version: aafe735-mod`, and every `pip install` in that environment aborted with
`InvalidVersion` until the installer rewrote it from `conda-meta`.

## Operator coverage

1070 of 1074 catalog operators have at least one complete job on a real
reader-to-operator route (the registry reports `1074 operators / 109 readers /
79 routes / 0 errors`). The last six are classified below.

| class | operators | why |
| --- | --- | --- |
| library still downloading | alphafold2_predict, alphafold2_batch_predict | the operator has no precomputed-alignment or db-preset parameter, so it needs the full 220 GB database; `params` (5.6 GB), `uniref90` (22 of 30.7 GB), `bfd`, `mgnify` (72.7 GB), `pdb70` (28.6 GB) and the rest are being fetched from the manifest links |
| library still downloading | colabfold_predict | needs the ColabFold envdb (110 GB) which is queued behind the AlphaFold set |
| upstream source cannot compile here | openfold_predict | `openfold/utils/kernel/attention_core.py` imports `attn_core_inplace_cuda` at module level, the checkout carries no `.cu` source for it (only `softmax_cuda_kernel.cu`), so the kernel cannot be built and the CPU path still imports it |
| job sandbox breaks the child tree | flye_assemble | outside a job the assembler returns 0 with 1 contig and 21x coverage on the same reads under three different `LD_LIBRARY_PATH` settings; inside a job it aborts with `multiprocessing ... _recv → EOFError` even with `threads=1` |
| GPU run still in flight | boltz_predict | the boltz1 checkpoint, `ccd.pkl` and `jsonschema` are all local; the job is running with `--accelerator gpu` and `--sampling_steps 5` |

`vina_dock_python` and `ligandmpnn_side_chain_packing`, listed as gaps in earlier
reports, both complete on this build (97 s and 102 s).

## Fixes verified on this build

- `tRNAscan-SE` (genomics) runs after promotion; `xgboost_regressor` resolves
  xgboost from conda-forge; `structure_pocket_detect` finds `fpocket 4.2.3`.
- `analyze_contacts` runs with the default `method=expected` (previously
  `No module named 'operon_hic.readers.tsv_reader'`).
- `build_contacts` runs on a TAB-separated pairs file with `min_mapq=0`.
- `mlp_classifier`, `mlp_regressor` and `autoencoder_anomaly` pass the readiness
  probe (previously `CXXABI_1.3.9 not found`).
- `boltz_complex_confidence` completes offline with `model=boltz1`; `boltz_predict`
  reaches the predictor with the GPU accelerator.
- `alphafold2` reports `incomplete` with `resources_declared 0/9` while a shared
  resource such as `colabfold_msa` only raises a warning for `boltz`.

## Tests

`pytest tests/test_environment_install.py` 31 passed, `pytest
tests/test_environment_resources.py` 7 passed, `pytest
tests/test_import_autolocate.py tests/test_hic_workflow.py` 20 passed (3 skipped
without h5py), `pytest tests/test_dependencies.py` 11 passed 1 skipped. The
frontend suite and the packaging self-check run inside `build5739.ps1`; the
payload reports `problems: []` for `source_commit … dirty=False`.

## Late fixes verified on the managed server

- `flye_assemble` completed in 127 s once worker temp roots were shortened; the
  failure mode was an AF_UNIX path limit, not a sandbox resource cap.
- `colabfold_predict` completed in 156 s with `msa_mode=single_sequence` after
  the jax/dm-haiku pins.
- `ligandmpnn_side_chain_packing` completed in 102 s and `vina_dock_python` in
  97 s, both on the GPU defaults introduced in this release.
- The runtime panel now opens on the local target, and a channel that fails with
  a timeout or a disconnect is retired instead of reporting `connected: true`.
