# OpenMM 势能与能量最小化（structure_openmm_energy）

用 OpenMM 对输入结构建系，计算单点势能（potential energy）与力范数（gradient norm），可选再跑一次能量最小化并输出最小化前后的对比。

## Inputs

| 名称 | 类型/维度 | 必填 | 说明 |
| --- | --- | --- | --- |
| `inputs[0]` | 2-D numeric Form，dims 为 `atom_dim` × `field_dim`（默认 `atom` × `field`） | 是 | 唯一输入端口（`inputs_arity = 1`）。每行一个原子，必须含 8 个**按列名**查找的字段：`x`、`y`、`z`、`residue_number`、`resname`、`chain`、`atom_name`、`element`；缺列时报 `the structure form has no ... column(s)`。 |

坐标按列名取，因此 x/y/z 不必位于前三列（与 `structure_openmm_md_rmsf` 的位置约定不同）。建模前 PDBFixer 会补缺失原子、补末端、按 pH 补氢，所以实际参与计算的原子数可能多于输入行数。

## Outputs

| 名称 | 类型/维度 | 说明 |
| --- | --- | --- |
| `output`（参数 `output` 可改名，默认 `energy`） | ndim = 2 的 numeric Form，dims 为 `stage` × `statistic` | **1 行或 2 行**：`minimize = false` 时只有 `initial` 一行；`minimize = true` 时依次为 `initial`、`minimized`。`statistic` 维固定 2 列：`potential_energy_kj`、`gradient_norm`。 |

- `potential_energy_kj`：势能（kJ/mol）。
- `gradient_norm`：全部原子受力向量的欧氏范数 `sqrt(Σf²)`，单位 kJ/(mol·nm)；最小化收敛后应显著变小。

`info` 中另有 `n_atoms`（输入原子数）、`n_particles`、`n_forces`、`missing_atoms`、`missing_terminals`、`initial_energy`、`final_energy`、`delta_energy`、`forcefield`、`implicit_model`、`ph`、`minimized`、`platform`、`platform_properties`。

输出中没有能量分项（键长/键角/二面角/静电/范德华各自的贡献）、没有逐原子受力表、没有轨迹；结构为空、缺列、`ph` 越界时抛异常，不会返回空表。

## Parameters

| 参数 | 类型 | 默认 | 说明 |
| --- | --- | --- | --- |
| `atom_dim` | string | `atom` | 输入结构表原子维名称。 |
| `field_dim` | string | `field` | 输入结构表字段维名称。 |
| `forcefield` | string | `amber14-all.xml` | 蛋白力场文件（OpenMM 数据目录内的相对名或绝对路径）。 |
| `implicit_model` | string | `implicit/gbn2.xml` | 隐式溶剂力场文件；与 `forcefield` 一起传给 `ForceField`。 |
| `ph` | number | `7.0` | 质子化 pH（0.1–13.9）；代码要求严格 `0 < ph < 14`。 |
| `platform` | enum | `auto` | `auto`/`CUDA`/`OpenCL`/`CPU`/`Reference`。 |
| `threads` | integer | `0` | CPU 平台线程数，0 由 OpenMM 决定（0–256）。 |
| `minimize` | boolean | `false` | 是否执行能量最小化；关闭时 `final_*` 与 `initial_*` 相同、`delta_energy` 为 0。 |
| `max_iterations` | integer | `100` | 最小化最大迭代数（1–100000），小于 1 报错。 |
| `tolerance` | number | `10.0` | 最小化收敛容差（kJ/mol/nm），必须为正。 |
| `stage_dim` | string | `stage` | 输出表阶段维名称。 |
| `output` | string | `energy` | 输出端口名。 |

## Notes

- **不跑动力学**：虽然内部构造了 `LangevinMiddleIntegrator`（仅仅是 `Context` 创建时需要一个积分器），但它一步都不执行。这里得到的是**单点**势能（以及可选的最小化），不是 MD 平均能量，也不是自由能。
- 体系为真空/隐式溶剂近似：`createSystem(..., nonbondedMethod=NoCutoff, constraints=HBonds)`，`implicit_model` 只是追加的隐式溶剂力场文件。换力场或换隐式模型后能量**不可直接比较**，只能在同一组参数下比较不同构象或最小化前后。
- 最小化是否收敛不保证：`max_iterations` 用尽仍会返回结果，请同时看 `delta_energy` 是否足够小、`gradient_norm` 是否已降到与 `tolerance` 同量级；只凭“没有报错”判断收敛是常见错误。
- `ph` 只影响加氢（质子化）状态，不影响其他参数；同一条结构在 pH 5 与 pH 8 下的能量不可比。
- `platform` 选择时**没有传 precision**，因此默认单精度；同一结构重复运行的能量会有小的平台相关差异（通常远小于 kJ/mol 级的构象差异，但比较极小差值时要注意）。
- `missing_atoms` / `missing_terminals` 是重要的质量信号：数值大说明输入结构缺原子严重，此时补全后的体系可能与原始结构相差很大，能量也就失去参考意义。
- 输入必须是完整的 8 字段结构表；只有坐标列而没有 `element` 时无法建系，会直接报缺列。
