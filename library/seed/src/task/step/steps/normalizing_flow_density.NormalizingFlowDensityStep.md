# RealNVP 归一化流密度估计（normalizing_flow_density）

用 RealNVP 仿射耦合（affine coupling）把一张样本 × 特征的数值表映射到潜空间，按最大似然训练，输出单行的平均对数密度与潜空间诊断量（不输出逐样本密度）。

## Inputs

| 名称 | 类型/维度 | 必填 | 说明 |
| --- | --- | --- | --- |
| `inputs[0]` | 2-D numeric Form，`row_dim` × `field_dim`（默认 `row` × `field`） | 是 | 唯一输入端口（`inputs_arity = 1`）。每行一个样本，每列一个连续特征；行数即样本量，列数即特征维数 d。所有列都参与建模，没有标签列或忽略列。 |

特征维数 d 必须 ≥ 2（见 Notes）；d = 1 时诊断量计算会抛 `IndexError`。输入为空时会因 `mean()` 作用于空数组而得到 NaN 或报错。

## Outputs

| 名称 | 类型/维度 | 说明 |
| --- | --- | --- |
| `output`（参数 `output` 指定，无默认值） | ndim = 2 的 numeric Form，dims 固定为 `entry` × `statistic` | 恒为 **1 行 × 6 列**：`entry` 唯一标签为 `result`；`statistic` 依次为 `log_likelihood`、`n_samples`、`n_params`、`latent_mean`、`latent_std`、`latent_corr`。四舍五入到 3 位小数。 |

- `log_likelihood`：**样本内**平均对数密度（nats/sample，自然对数），越大越好；它是每样本平均，不是总和。
- `n_samples`：样本行数；`n_params`：耦合网络的可训练参数总数。
- `latent_mean` / `latent_std`：把所有样本、所有潜变量坐标**合在一起**统计的均值与标准差（各一个标量）。
- `latent_corr`：潜变量**第 0 列与第 1 列**之间的 Pearson 相关系数（只此一对，不是完整相关矩阵）。

输出中没有逐样本的 log-prob、潜变量矩阵或采样结果；也没有“每个特征一行的密度”。需要逐样本密度或生成样本时，本算子不提供。

## Parameters

| 参数 | 类型 | 默认 | 说明 |
| --- | --- | --- | --- |
| `row_dim` | string | `row` | 输入表第 0 维名称。 |
| `field_dim` | string | `field` | 输入表第 1 维名称（列维度）。 |
| `output` | string | — | 输出端口名；代码直接读取该键，请显式给出。 |
| `layers` | integer | `2` | 仿射耦合层数；第 i 层的被变换坐标固定为 `i % d`。 |
| `hidden` | integer | `8` | 每层耦合网络（scale/shift 预测）的隐层宽度。 |
| `epochs` | integer | `300` | 全批量 Adam 的梯度步数。 |
| `learning_rate` | number | `0.05` | Adam 学习率。 |
| `seed` | integer | `0` | 初始化与训练过程的随机种子。 |

## Notes

- 模型：每层对坐标 `m = i % d` 做 `z_m = (x_m - t) * exp(-s)`，其余坐标作为条件输入一个 `Linear(d-1→hidden) → Tanh → Linear(hidden→2)` 网络得到 `s`、`t`；`s` 被截断到 [-3, 3] 以防止指数爆炸；log-det 累积 `-s`。
- **当 `layers < d` 时，编号 ≥ layers 的坐标在每一层都只当条件变量、从不被变换**，它们的潜变量等于原始值，密度估计会有系统偏差。经验上取 `layers >= d`（例如 d = 5 时 `layers = 5`）。
- **d 必须 ≥ 2**：`latent_corr` 只算第 0、1 列的相关，d = 1 时索引越界抛 `IndexError`，这是硬限制而非提示。
- 训练目标是平均负对数似然 `-0.5*Σz² - 0.5*d*ln(2π) + logdet`，因此 `log_likelihood` 的量纲是 nats/sample；跨不同 d 的数据集不可直接比较。
- 输入**未做标准化**：若各列量级差异很大（例如一列 0–1、一列 1e6），耦合网络很难学出合理的 scale/shift，建议在上游把特征标准化到同量级。
- `latent_mean`/`latent_std` 是把所有维度混在一起统计的标量，拟合良好时接近 0 与 1；但单个维度的偏差会互相掩盖，不要把它当作逐维拟合诊断。
- `latent_corr` 只覆盖前两个坐标；若关心其他坐标对的耦合，需要自己在上游重排特征列后重复运行。
