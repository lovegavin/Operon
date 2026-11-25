# Operon Studio 5.8.0 acceptance report

Release `5.8.0` ships with operator library `main-v1.2.0`. Everything below was
measured on the acceptance pair: the desktop application installed under
`<install dir>` (served on <http://127.0.0.1:5882>) and the managed server
`licai-srv-test` (`172.22.149.42`, deployment root
`/public/home/lihj/Operon test`, 56 CPUs, RTX 3090 24 GB).

The desktop build under test is the one whose `source_commit` (recorded in the
payload manifest and in `/api/version` as the 12-character build id) is the
commit that carries this report; the server ran `code-70cce1db1f67eccaed39`
during the acceptance and was upgraded to the release build afterwards.

## Operator coverage — 1074 of 1074

Coverage is counted from every recorded run in `<workdir>\p6\runs\*.csv`, keeping
only names that exist in the shipped catalog (`catalog_names.txt`, 1074
operators). 9,450 runs were recorded; 1,074 distinct operators were attempted
and 1,074 reached `complete` at least once.

| Metric | Value |
| --- | --- |
| Operators in the catalog | 1074 |
| Operators attempted | 1074 |
| Operators completed at least once | 1074 |
| Routes declared by the library | 79 |

The final operator, `alphafold2_batch_predict`, completes on the GPU with the
`full_dbs` preset after its database paths point at the shared AlphaFold-2 tree
(`/public5/home/tianjy/alphafold-2.3.1/afdb`). The batch runner keeps its own
conda environment (`/public/home/lihj/miniforge3/envs/alphafold2`) because the
managed `alphafold2` environment cannot host `pdbfixer` and the hh-suite
binaries that the script imports at start-up; the operator exposes this through
`python_executable`, so the workaround is configuration, not patched code.

The measured run is job `exec-ffe707f72de6454b9a812a6c686783db`: 4 h 02 m of
AlphaFold-2 time for one 76-residue chain, of which 3 h 48 m is MSA (the
`hhblits` pass over BFD plus UniRef30 alone takes 2 h 41 m) and 13 minutes the
five-model inference. It writes `ranked_0.pdb` with pLDDT **95.60** and holds
2,302–3,476 MiB on the device, because the wrapper keeps
`XLA_PYTHON_CLIENT_PREALLOCATE=false` so the 3090 stays shareable.

## GPU

Deep-learning operators default to `device: auto` and resolve to CUDA when the
target interpreter reports an available device.

| Operator | Device | Time |
| --- | --- | --- |
| `alphafold2_predict` | CUDA | 5,089 s |
| `esmfold_predict` | CUDA | 58 s (CPU 538 s) |
| `ligandmpnn_side_chain_packing` | CUDA | 185 s |
| `proteinmpnn_design` | CUDA | 83 s |
| `boltz_predict` | CUDA (`--accelerator gpu`) | 1,394 s for 20 sampling steps, cancelled |
| `alphafold2_batch_predict` | CUDA | 14,528 s end to end (MSA 3 h 48 m, inference 13 min) |

AlphaFold-2 and ColabFold run on CUDA JAX: `jaxlib==0.4.23+cuda12.cudnn89`
together with the `cuda-cudart=12.2` / `cuda-cupti=12.2` conda packages and
`LD_LIBRARY_PATH=<env>/lib:<env>/lib64`. `jax.devices()` reports
`[cuda(id=0)]` in that environment. Ten small tabular networks
(`mlp_*`, `gcn_node_classifier`, `vae_anomaly`, …) declare
`supports_cuda: false` because a GPU cannot help them.

## Environments — 20 declared, all ready

`vina310` is new in this release: the conda-forge Vina bindings stop at Python
3.10, so the operator gets its own 3.10 environment instead of downgrading the
shared runtime.

All twenty environments were installed from the desktop UI alone, by pointing
the runtime panel at `licai-srv-test` and pressing **全部安装**. There is no wall
clock on any transfer, build or conda transaction, so a slow machine finishes
instead of being killed: `antismash` used to die at the old 1800 s cap and now
completes, and the `core` environment (35 requirements plus the conda
`swig`/`boost`/`libdeflate` stack) takes about 42 minutes.

Upgrading the server interrupts environments that are still being installed;
their status becomes 「上次安装已中断（安装进程已退出），请重新准备该环境。」 and one
further **全部安装** finishes the queue. This is recorded as D32 below because it
is a rough edge, not a silent failure.

## Resources — 19 resources, nothing missing

Every resource reports `missing: []`. The nine AlphaFold-2 units are linked from
the shared tree with `operon_resource_link` per unit:
`params`, `uniref90`, `uniref30`, `bfd`, `mgnify`, `pdb70`, `pdb_seqres`,
`uniprot`, `pdb_mmcif`. Declared file names were aligned with the real layout
(`UniRef30_2021_03_*`, `bfd_metaclust_*_hhm`, `mgy_clusters_2022_05.fa`,
`uniprot_sprot.fasta`), and `check_library_alias.py` now verifies unit leaves
rather than a flattened name list.

The same panel downloads and stops through the UI (`运行状态` → environment card
→ `数据与资源` → `下载缺失文件` / `取消下载`) and through MCP
(`operon_resource_download`, `operon_resource_cancel`), and linking refuses a
directory that does not provide the unit's files:

```
source does not exist: /public/home/lihj/operon-resources/absent
target holds existing data; remove it explicitly: .../resources/vina
```

## Desktop UI acceptance

1. **Add a server** — 设置 → 添加服务器 → `licai-srv-test`, `172.22.149.42`,
   `lihj`, port 22, managed, `/public/home/lihj/Operon test`, private key.
   The fingerprint `SHA256:ng1XCOIMIBQYUDJRMQ0zRDtvWbl6eex8rH4aJ/rjWxU` must be
   accepted with 信任并连接 before the profile is stored.
2. **Install and upgrade the server** — 服务端维护 → 安装 / 升级服务端 uploaded the
   build, installed `operon-studio-5.8.0`, installed the delivered library
   bundle (`packages: 7, descriptors: 1183`) and reconnected.
3. **Install the environments** — 运行状态 → 执行位置 `licai-srv-test` → 全部安装.
4. **Inspect resources** — each environment card lists its units and the
   download/link controls described above.
5. **Run a route on the canvas** — `CsvReader` (`iris.csv`, `sample` × `feature`)
   connected to `pca` (`n_components: 2`) and 运行:

   | Time | State |
   | --- | --- |
   | 60 s | 正在自动准备 · server:environment |
   | 1,140 s | server:code |
   | 1,200 s | 固定计划 `bb16a7b1f1bc4c2d`, 任务状态 · 运行中 |
   | 2,040 s | 任务状态 · 已完成 |

   The run lands in `workspace/.studio/invocations/runs/run-1c15af1ae3bb46818ca196ca4ce1ffd8/`:
   receipt `art-db06cfeb1513917eef570be2006fa031`, digest
   `9fd0a4b98fc390a64af684bc4cb6a21880331f7e7de8cf208a4977e3bb609393`,
   `total_bytes 19670`, `total_elapsed 4.7816 s`,
   `n_observations 10`, `explained_variance_ratio [0.6880894553627709, 0.15741042745295353]`.
6. **Environment card hover** — a real pointer over a card now yields
   `border-color rgb(36,36,36)` with a 7%→14% action-tinted gradient instead of
   flat white.

## MCP acceptance

The server exposes 146 tools, and the four acceptance paths were driven through
them only (`OPERON_MCP_PYTHON/WORKSPACE/DATA` pointing at the same instance):

* **read** — `operon_status` returns
  `connected: true, url: http://127.0.0.1:5882, scopes: [context, edit, run, plugins]`;
  `operon_sessions` returns the canvas document (`revision 13`).
* **resource** — `operon_resource_download {"name":"vina","profile_id":…}` starts a
  job, `operon_resource_cancel` reports `bytes 4,089,576`;
  `operon_resource_link` rejects a missing source and an already-populated
  target with the messages quoted above.
* **environment** — `operon_environments_prepare {"names":[…],"profile_id":…}`
  queues the same work the button does.
* **canvas** — `operon_sessions` → `operon_graph` → `operon_run` produced a
  `complete` job and `operon_artifacts` returned `pca_1_out` shaped `[10, 2]`.

## Defect ledger

| Id | Symptom | Root cause | Fix |
| --- | --- | --- | --- |
| D31 | Pool rejects a second application | one pool per admission root | documented |
| D32 | Upgrading a server marks installing environments interrupted | restart drops the installer's job | documented |
| D33 | `resource_link` accepted an incomplete link | `already_linked` shortcut skipped validation | `aec2e0431` |
| D34 | Canvas plan failed with `Duplicate archive member` | archive extraction refused repeated members | `949c83226` |
| D35 | Closure check failed with `EEXIST` on `libpython3.11.so` | links were created after regular files | `be18f682b` |
| D36 | Repacked archive kept the first member | extraction refused conflicting duplicates | `5cfe57b9c` |
| D37 | `run_process`/`FileLock` had hidden deadlines | hard-coded 900–5400 s timeouts | `00ba85d5b`, `066f8ee07` |
| D38 | Every canvas run repacks the `core` environment | no content-addressed reuse of closures | open |
| D39 | Install-all ran locally while the profile was offline | the panel collapsed to 「本地」 | open |
| D40 | A quarantined worker held its lease forever | `RECOVERY_REQUIRED` attempts were never revisited | `ed2a11a77` |
| D41 | A queued install was reaped after three minutes | the age check ignored live bootstrap waits | `12efa66f3` |
| D42 | A dead torch mirror blocked three environments | `torch_index_url` had no fallback | `7a37fba78` |

## Tests

`pytest` suites covering the changed areas: `tests/test_archive_extraction.py`
(5), `tests/test_environment_install.py` (40), `tests/test_environment_reap.py` (2), `tests/test_resource_link.py`,
`tests/test_coordinator_quarantine_release.py` (2),
`tests/test_cluster_terminal_recovery.py`, `tests/test_engine_pool.py` (14 in
total for the last three). The build pipeline runs the frontend suite and the
`verify580.py --require-docs` payload check, both green for the release commit.
