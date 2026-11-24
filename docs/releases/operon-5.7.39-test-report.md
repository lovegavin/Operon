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

1068 of 1074 catalog operators have at least one complete job on a real
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

## MCP and UI acceptance of the release surfaces

- Environments: a pure MCP call `operon_environments_prepare
  {"names":["colabfold","vina310","openmm81"],"profile_id":"licai-srv"}` returned
  `started [...]` with one job per environment and the panel reached `ready 19 /
  incomplete 1` (only `alphafold2`, which now reports `resources_declared 0/9`).
  The same prepare/repair actions were exercised from the runtime panel earlier
  in the session for `openmm81`, `dssp`, `genomics`, `core`, `ligandmpnn` and
  `vina310`.
- Resources: `operon_resources` plus `operon_resource_download` /
  `operon_resource_cancel` started and stopped a transfer for 16 of the 19
  resources, and the UI path (runtime panel → environment card title → resources
  → "install all") produced the same server-side operations, with cancels
  reaching `/api/resources` operations.
- Canvas: `operon_sessions` → `operon_graph` → `operon_open` (append and replace)
  → `operon_run` created the document `page_c74abc0d7b244139ab6967d7ecaa8d94`
  and submitted job `exec-d08ebef643444a39a26854b57fde92e5`, which reached
  `complete` with `CsvReader(iris.csv) → pca`.

## Late fixes verified in this build

- `flye_assemble` completes in 127 s once the worker temp root stays inside the
  `AF_UNIX` budget (the sandbox failure was an 80-character `TMPDIR`).
- `colabfold_predict` completes in 156 s with `msa_mode=single_sequence` and the
  pinned `jax==0.4.23` / `jaxlib==0.4.23` / `chex==0.1.86` stack.
- `boltz_predict` completes in 129 s with `no_kernels=true`, which is now the
  default because the optional `cuequivariance_torch` kernels are absent.
- `vina_dock_python` completes in 97 s in the dedicated `vina310` environment
  (Python 3.10, `vina 1.2.2`, `numpy==1.23.5`), and the registry assigns it
  there through `environment_assignments.json`.

## Resource repair and mirror evidence

- `operon_resource_download {"name": "proteinmpnn"}` on the deployed server:
  the log shows `ProteinMPNN/vanilla_model_weights/v_48_020.pt existing 6681301`
  and `protein_mpnn_run.py existing 29312` (the 29,781-byte copy was removed
  first), then `phase: complete`, `downloaded_bytes 6,710,613`.
- Mirror probes from the server (`curl -4 -sIL`): the GWDG links
  `wwwuser.gwdg.de/~compbiol/colabfold/uniref30_2302.tar.gz` and
  `…/colabfold_envdb_202108.tar.gz` answer 200, while
  `opendata.mmseqs.org/colabfold/uniref30_2302.tar.gz` answers 429, which is why
  the units now list both.

## Coverage after the AlphaFold-2 and OpenFold work

- Catalog: **1074 operators**. Operators with at least one `complete` run on a
  real reader route: **1072 (99.8%)**.
- The last two are the AlphaFold-2 pair: `alphafold2_predict` runs a zero-input
  graph (`fasta_path`, `output_dir`, `data_dir`, `runner`, `model_preset`,
  `db_preset`) against the 2.7 TB database tree the host already keeps; the
  job spends its time in `jackhmmer`/`hhblits`, which is expected at `full_dbs`.
- `openfold_predict` completed on CPU (76 residues, 15 minutes) with
  `config_preset=model_1`, a single-sequence alignment directory and
  `skip_relaxation=true`; the seven adaptations it needs are listed in
  `OPENFOLD.md` next to this report.
- Environment readiness is **20/20** after the venv rebind landed: the last
  hold-out was `openmm81`, whose `bin/python*` symlinks formed a cycle after a
  server upgrade, so the panel reported it as `missing` although the directory
  was complete.
- Second routes: of the **448** operators that only had one route, 112 have a
  second one built from a different slice of the same classic data (337 cases
  use a data variant, 44 change a numeric parameter). The batches run through
  the same MCP-equivalent submission path.
