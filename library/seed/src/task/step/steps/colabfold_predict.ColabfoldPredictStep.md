# ColabFold 结构预测（colabfold_predict）

调用本机安装的 `colabfold_batch` 跑 AlphaFold2/ColabFold 预测，把 rank-001 结构读回成“每原子一行”的结构表，并把 pLDDT、pTM、最大 PAE 等指标写进该表的 `info`。

## Inputs

| 名称 | 类型/维度 | 必填 | 说明 |
| --- | --- | --- | --- |
| `inputs[0]` | 2-D numeric Form，dims 为 `sequence_dim` × `position_dim`（默认 `sequence` × `position`） | 是 | 唯一输入端口（`inputs_arity = 1`）。内容是**序列编码**（`info.representation` 必须为 `sequence_codes`），即用字母表编号表示的氨基酸序列；本算子只接受**一条**序列，多行或多条链会被拒绝（`expected exactly one sequence, got N`）。 |

若上游在 `info["sequences"]` 里放了原始字符串（单条、非空），会优先使用它——这样多聚体用 `:` 分隔链的写法（如 `ACDE:FG`）可以保留；否则由编码矩阵解码。

## Outputs

| 名称 | 类型/维度 | 说明 |
| --- | --- | --- |
| `output`（参数 `output` 可改名，默认 `structure`） | ndim = 2 的 numeric Form，dims 为 `atom` × `field` | **每行一个 PDB 原子**（不是指标汇总表）：`atom` 维是原子序号/标签，`field` 维是结构字段（坐标 x/y/z、元素、残基名等，与 `structure_pdb` 读入的结构表一致）。 |
| 原生文件（副作用） | `prediction.pdb`、`scores.json` | 写到本次运行的输出目录；同时登记为结果文件（结构 PDB，以及存在时的打分 JSON）。 |

`info` 中携带的指标：`mean_plddt`（pLDDT 均值，0–100）、`ptm`（pTM，0–1，单链时可能缺失）、`max_pae`（**PAE 的最大值**，不是平均值）、`n_residues`（残基数）、`model_path`、`scores_path`、`sequences`、`msa_mode`、`msa_host`、`msa_db1`、`msa_db2`。

打分文件缺失时不会失败：`mean_plddt` / `ptm` / `max_pae` 全部为 NaN、`n_residues` 为 0，且不登记 scores 结果文件。输入序列为空、找不到可执行文件、预测超时、返回码非 0、或没有产出 rank-001 结构时都会抛异常，不会返回空表。

## Parameters

| 参数 | 类型 | 默认 | 说明 |
| --- | --- | --- | --- |
| `sequence_dim` | string | `sequence` | 输入表第 0 维名称。 |
| `position_dim` | string | `position` | 输入表第 1 维名称（残基位置维）。 |
| `colabfold_path` | string | `colabfold_batch` | 可执行文件名或路径；以 `.py` 结尾时会用当前 `sys.executable` 启动。 |
| `num_models` | integer | `1` | 每个 MSA 训练/预测的模型数（1–5）；只读取 rank-001 的结果。 |
| `num_recycles` | integer | `3` | 循环次数（1–48），越大越慢。 |
| `msa_mode` | enum | `mmseqs2_uniref_env` | 三选一：`mmseqs2_uniref_env`（UniRef30 + 环境数据库，默认，最全）、`mmseqs2_uniref`（仅 UniRef30，更快）、`single_sequence`（不做 MSA，仅单序列）。 |
| `msa_host` | string | `""` | 远程 MSA 服务地址，例如 `https://api.colabfold.com`；留空则用 ColabFold 自己的默认值。必须是 http(s) URL。 |
| `device` | enum | `auto` | `auto` 自动探测 CUDA（torch 或 JAX 任一可用即可），否则 CPU；也可强制 `cpu` / `cuda`。 |
| `timeout_seconds` | integer | `3600` | 子进程超时（60–86400 秒），超时抛 `timed out after N s`。 |
| `output` | string | `structure` | 输出端口名，同时作为原生文件的结果名。 |
| `msa_databases` | string | `""` | 本地 MMseqs2 数据库**根目录**：其下需有 `uniref30_2302/uniref30_2302_db` 与 `colabfold_envdb_202108/colabfold_envdb_202108_db`。给出后解析成 `--db1`（环境库有索引时再加 `--db2 --use-env 1`）指向本地 MMseqs2 库；`msa_host` 非空时仍会同时传 `--host-url`，两者并存时由 `colabfold_batch` 自行取舍。 |
| `msa_db1` | string | `""` | 显式指定 `--db1` 的数据库前缀，**优先级高于** `msa_databases`。 |
| `msa_db2` | string | `""` | 显式指定 `--db2` 的数据库前缀，优先级最高；给出时会自动追加 `--use-env 1`。 |

## Notes

- **`msa_mode` 三种取值的实际差别**：`mmseqs2_uniref_env` 同时搜 UniRef30 与环境库（默认，慢但召回最好）；`mmseqs2_uniref` 只搜 UniRef30（快，适合孤儿蛋白/大复合体）；`single_sequence` 完全不生成 MSA，只用单条序列。**单序列模式下 pTM/ipTM 与 PAE 明显偏悲观**，多聚体界面尤其不可信，不要用它来比较界面质量。
- **数据库参数的优先级**：`msa_db1` / `msa_db2`（显式）> `msa_databases`（根目录推导）> `msa_host`（远程）。`msa_databases` 只在“没给显式 db 且模式不是 `single_sequence`”时才解析：`uniref30_2302_db` 缺失会直接报错；`colabfold_envdb_202108_db` 若没有 `.dbtype`/`.index` 索引则静默跳过，退化成只用 UniRef30（`mmseqs2_uniref_env` 名义上仍是双库，但实际只查了单库）。
- 本算子**从不读取** `colabfold_msa` 资源目录（该约 221 GB 的资源只被 `boltz_predict` 使用），也不会自己下载数据库；要用本地库只能通过 `msa_databases` 或 `msa_db1`/`msa_db2` 显式指定。
- 只读 rank-001：优先 `*_relaxed_rank_001_*.pdb`，没有则退回 `*_unrelaxed_rank_001_*.pdb`；`num_models > 1` 也只是多算几个模型，输出仍只有 rank-001。
- `mean_plddt` 是全部残基的平均；`max_pae` 是**最大** PAE，反映最不可信的那一段界面，比平均 PAE 更保守。
- 复合体请用 `:` 分隔链并让上游写入 `info["sequences"]`；只有编码矩阵时链边界会丢失。
- 运行目录是临时目录，结束后清理；要保留中间文件请用原生结果文件（`prediction.pdb` / `scores.json`）。
- 可执行文件找不到时的报错会提示 `pip install colabfold[alphafold]` 并指向 `docs/large_resources.md`；`device=cpu` 时会把 `CUDA_VISIBLE_DEVICES` 置空，速度极慢，仅适合冒烟测试。
