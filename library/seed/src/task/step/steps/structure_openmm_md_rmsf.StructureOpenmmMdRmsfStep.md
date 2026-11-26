# OpenMM 短程 MD 残基柔性（structure_openmm_md_rmsf）

用 OpenMM 跑一段隐式溶剂的短程动力学，对每个 Cα 原子计算沿时间的均方根涨落（RMSF, root mean square fluctuation），并附带整条轨迹的平均回旋半径。

## Inputs

| 名称 | 类型/维度 | 必填 | 说明 |
| --- | --- | --- | --- |
| `inputs[0]` | 2-D numeric Form，dims 为 `atom_dim` × `field_dim`（默认 `atom` × `field`） | 是 | 唯一输入端口（`inputs_arity = 1`）。每行一个原子，需含 `atom_name`、`resname`、`chain`、`residue_number`、`element` 五个字段列；**坐标取该表的前三个数据列，按 x、y、z 位置解释**（不按列名）。 |

`chains` 非空时只保留列出的链（逗号或分号分隔）；链名不在结构中会报 `chain(s) ... are not in the structure`。水分子在建模前被移除，缺失原子/氢由 PDBFixer 补齐。

## Outputs

| 名称 | 类型/维度 | 说明 |
| --- | --- | --- |
| `output`（参数 `output` 可改名，默认 `flexibility`） | ndim = 2 的 numeric Form，dims 为 `residue` × `statistic` | **每个 Cα（即每个残基）一行**：`residue` 维标签形如 `A:ALA:12`（链:残基名:残基号）；`statistic` 维固定 2 列：`rmsf_nm`、`mean_rg_nm`。 |

- `rmsf_nm`：该残基 Cα 的 RMSF，单位 **nm**（乘 10 得 Å）。
- `mean_rg_nm`：整条轨迹的平均回旋半径，单位 **nm**——注意这是**一个标量被广播到每一行**，不是逐残基的量；对整列取均值即得该标量。

逐帧的回旋半径序列、最小值/最大值、Cα 原子索引与轨迹路径在 `info` 中（`mean_rg_nm`、`max_rg_nm`、`min_rg_nm`、`n_frames`、`mean_rmsf_nm`、`max_rmsf_nm`、`n_residues`、`temperature_k`、`steps`、`timestep_fs`、`trajectory`、`prepared_pdb`、`ca_indices`）。

输出中没有除 Cα 以外的原子、没有逐帧坐标表、没有 B-factor 列；选出少于 3 个 Cα 时抛 `fewer than three C-alpha atoms remain after chain selection`，不会返回空表。

## Parameters

| 参数 | 类型 | 默认 | 说明 |
| --- | --- | --- | --- |
| `atom_dim` | string | `atom` | 输入结构表原子维名称。**声明了但当前实现未读取**。 |
| `field_dim` | string | `field` | 输入结构表字段维名称。**声明了但当前实现未读取**（写 PDB 时硬编码为 `field`）。 |
| `chains` | string | `""` | 只分析的链，逗号/分号分隔；留空表示全部链。 |
| `temperature` | number | `300.0` | 目标温度（K，200–400）。 |
| `timestep_fs` | number | `2.0` | 积分步长（fs，0.5–4）。 |
| `steps` | integer | `5000` | 生产段总步数（100–100000）；默认 5000 × 2 fs = 10 ps。 |
| `report_interval` | integer | `50` | 每多少步采集一帧（10–5000）；帧数 = `steps / report_interval`。 |
| `platform` | enum | `auto` | `auto`/`CUDA`/`OpenCL`/`CPU`/`Reference`。 |
| `threads` | integer | `0` | CPU 线程数，0 由 OpenMM 决定（0–256）。 |
| `residue_dim` | string | `residue` | 输出表的残基维名称。 |
| `output` | string | `flexibility` | 输出端口名。 |

## Notes

- **没有预平衡段**：与 `structure_openmm_md_stability` 不同，本算子只做能量最小化（500 步、容差 1.0）就进入生产段，第一帧已经是“生产段跑完 `report_interval` 步之后”的构象。因此轨迹前段仍带最小化后的弛豫，RMSF 会被系统性抬高。
- **RMSF 的参考不是输入结构**：先把每帧按 Kabsch 叠合到**第一帧记录**，再对每个 Cα 求其位置相对“时间平均位置”的均方根偏差。它衡量的是轨迹内部的涨落，不能与“相对实验结构的 RMSD”混为一谈。
- **默认 10 ps 太短**：5000 × 2 fs 只有 10 ps，环区与末端几乎来不及采样，RMSF 普遍偏小且不稳定；要做柔性分析建议 ns 级并至少重复 2–3 条独立轨迹，同时报告 `n_frames`。
- 力场固定为 `amber14-all.xml` + `implicit/gbn2.xml`（GBneck2 隐式溶剂、`NoCutoff`），**没有**力场参数可改；`platform` 选择 `CUDA` 时用双精度上下文（`precision="double"`），比默认单精度慢但更稳。
- 只保留 Cα：输出行数等于所选链的残基数（不是原子数）；侧链柔性完全看不到，需要全原子 RMSF 时必须改用其他算子。
- `mean_rg_nm` 被广播到每一行，做下游聚合（求均值、画散点）时不要把它当成逐残基特征；逐帧 Rg 请从 `info` 或原生轨迹读取。
- 坐标读取是位置约定：前三个数据列必须是 x/y/z，列顺序变了不会报错但会算出无意义的 RMSF；写 PDB 时也固定用 `field` 维做字段查找，改 `field_dim` 不会生效。
- 输入 `rmsf_nm` 与 `structure_openmm_md_stability` 的 `rmsd_angstrom` 单位不同（nm vs Å），跨算子比较前先换算。
