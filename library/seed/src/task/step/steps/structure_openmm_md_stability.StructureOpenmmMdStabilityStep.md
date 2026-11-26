# OpenMM 短程 MD 稳定性（structure_openmm_md_stability）

用 OpenMM 对隐式溶剂体系做能量最小化 + 短程 Langevin 动力学，按采样间隔输出每一帧的温度、势能、RMSD 与回旋半径（radius of gyration），并给出漂移汇总。

## Inputs

| 名称 | 类型/维度 | 必填 | 说明 |
| --- | --- | --- | --- |
| `inputs[0]` | 2-D numeric Form，dims 为 `atom_dim` × `field_dim`（默认 `atom` × `field`） | 是 | 唯一输入端口（`inputs_arity = 1`）。每行一个原子，必须含按名查找的 8 个字段列：`x`、`y`、`z`、`residue_number`、`resname`、`chain`、`atom_name`、`element`；缺列时报 `the structure form has no ... column(s)`。 |

默认会先丢弃水分子（`resname` 为 `HOH`/`WAT`/`DOD` 的行），再交给 PDBFixer 补残基、补原子、按 pH 补氢。

## Outputs

| 名称 | 类型/维度 | 说明 |
| --- | --- | --- |
| `output`（参数 `output` 可改名，默认 `frames`） | ndim = 2 的 numeric Form，dims 为 `frame` × `statistic` | **每采样帧一行**：`frame` 维标签为 `frame0`、`frame1`…；`statistic` 维固定 5 列：`time_ps`、`temperature_k`、`potential_energy_kj`、`rmsd_angstrom`、`radius_of_gyration_angstrom`。 |

行数：第 0 帧（平衡后、生产前）1 行，之后每 `sample_every` 步 1 行，末尾若不足一个间隔再补 1 行；默认 `steps=500`、`sample_every=50` 时共 11 行。

单位与含义：`time_ps` 为生产段累计时间（ps）；`temperature_k` 由动能按自由度反算（K）；`potential_energy_kj` 为势能（kJ/mol）；`rmsd_angstrom` 为对**平衡后第 0 帧**的 Kabsch 拟合 RMSD（Å，故第 0 行恒为 0）；`radius_of_gyration_angstrom` 为回旋半径（Å）。

输出中没有逐原子坐标、没有轨迹文件、没有能量分项（键角/二面角/静电各自贡献）；这些只能通过其他算子（如 `structure_openmm_energy`）获得。结构为空时抛 `the structure form is empty`，轨迹发散时抛 `the trajectory diverged ...`，不会返回空表。

## Parameters

| 参数 | 类型 | 默认 | 说明 |
| --- | --- | --- | --- |
| `atom_dim` | string | `atom` | 输入结构表的原子维名称。 |
| `field_dim` | string | `field` | 输入结构表的字段维名称。 |
| `ph` | number | `7.0` | 质子化 pH，用于 `addMissingHydrogens`（0–14）。 |
| `temperature` | number | `300.0` | 目标温度（K，250–450）。 |
| `friction` | number | `1.0` | Langevin 摩擦系数（1/ps，0.1–50）。 |
| `step_size_fs` | number | `2.0` | 积分步长（fs，0.5–4）；含氢体系不要超过 2 fs。 |
| `steps` | integer | `500` | **生产段**步数（10–200000）；默认 500 × 2 fs = 1 ps。 |
| `sample_every` | integer | `50` | 每多少步采一帧（1–10000）。 |
| `minimize_iterations` | integer | `500` | 能量最小化最大迭代数（0–100000）。 |
| `seed` | integer | `0` | 随机数种子（0–1e6），影响初速度与积分噪声。 |
| `platform` | enum | `auto` | `auto`/`CUDA`/`OpenCL`/`CPU`/`Reference`；`auto` 由 OpenMM 选平台。 |
| `threads` | integer | `0` | CPU 平台线程数，0 表示由 OpenMM 决定（0–256）。 |
| `forcefield` | string | `amber14-all.xml,implicit/gbn2.xml` | 逗号分隔的力场文件列表，第一项为蛋白力场，第二项为隐式溶剂模型；用显式水模型会因 `NoCutoff` 而失败。 |
| `frame_dim` | string | `frame` | 输出表的帧维名称。 |
| `output` | string | `frames` | 输出端口名。 |
| `remove_water` | boolean | `true` | 是否在建模前删除水分子行。 |
| `equilibrate_steps` | integer | `500` | 最小化之后、采样之前的**预平衡**步数（0–100000），这些步不进入输出。 |

## Notes

- **RMSD 的参考帧不是输入结构**：参考坐标取自“能量最小化 + `equilibrate_steps` 预平衡之后”的第 0 帧，因此 `frame0` 的 RMSD 恒为 0，且 RMSD 只反映生产段的漂移，不能解读为“相对实验结构的偏差”。
- **默认 1 ps 太短**：`steps=500`、`step_size_fs=2.0` 只有 1 ps 生产段，蛋白质在 1 ps 内几乎不动，`rmsd_final_angstrom` 往往只有零点几 Å、`rg_change_angstrom` 接近 0，这只说明“没有爆炸”，不能当作稳定性结论。做有意义的判断建议至少 ns 量级（如 `steps=500000`）并配合多次重复。
- **长度单位混用**：本算子的 `rmsd_angstrom` 与 `radius_of_gyration_angstrom` 都是 **Å**；而同目录的 `structure_openmm_md_rmsf` 用 **nm**，两者不可直接拼接比较。
- 温度是从动能反算的瞬时值（`2KE/(dof·R)`，`dof = 3N − 约束数`），会围绕目标温度涨落；`HBonds` 约束会减少自由度，若不考虑约束数，手算温度会对不上。
- 力场组合是 `amber14-all.xml` + `implicit/gbn2.xml`（GBneck2 隐式溶剂，`NoCutoff` 无截断）；换力场文件请保持“蛋白力场 + 隐式溶剂”的写法，且列表用英文逗号分隔、不带空格更稳妥。
- 体系在真空中没有周期性边界与显式水，界面/疏水效应被隐式模型近似；跨体系比较能量没有意义（势能不能直接比较）。
- 轨迹发散（坐标或能量出现非有限值）会立刻报错并建议降低步长或温度；若最小化后仍有原子重叠，先把 `minimize_iterations` 调大。
- 输出不含逐原子坐标，无法据此重绘构象；需要轨迹请另存（本算子不写轨迹文件）。
