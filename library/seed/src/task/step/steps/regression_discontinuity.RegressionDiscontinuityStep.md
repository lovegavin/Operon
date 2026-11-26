# 尖锐回归断点（regression_discontinuity）

在断点 cutoff 两侧各拟合一条直线（局部线性），用两侧截距之差估计跳跃幅度，并给出标准误、t 值与 p 值。输出是一行汇总统计量，不是逐样本结果。

## Inputs

| 名称 | 类型/维度 | 必填 | 说明 |
| --- | --- | --- | --- |
| `inputs[0]` | 2-D numeric Form，`row_dim` × `field_dim`（默认 `row` × `field`） | 是 | 唯一输入端口（`inputs_arity = 1`）。按**列名**取 `y_column`（响应）与 `running_column`（驱动变量 running variable），列名在 `field_dim` 标签中查找；其余列被忽略，也不作为协变量进入模型。 |

列名缺失时抛 `ValueError`，信息形如 `missing column 'y' on dim 'field'`。当 `bandwidth > 0` 时，只有 `|run - cutoff| <= bandwidth` 的行参与估计；其余行被整行丢弃。

## Outputs

| 名称 | 类型/维度 | 说明 |
| --- | --- | --- |
| `output`（参数 `output` 指定，默认 `regression_discontinuity_out`） | ndim = 2 的 numeric Form，dims 为 `stat` × `statistic` | 恒为 **1 行 × 8 列**：第 0 维只有一个标签，字面值就是 `stat`；`statistic` 依次为 `jump`、`stderr`、`t`、`p`、`n_left`、`n_right`、`slope_left`、`slope_right`。数值保留 **9 位**小数。 |

- `jump`：断点跳跃估计 `截距_right − 截距_left`，单位与 y 相同。
- `stderr`：跳跃的标准误 `sqrt(var_left_intercept + var_right_intercept)`，来自两侧各自 OLS 的经典（同方差）协方差矩阵。
- `t`：`jump / stderr`；`p`：双侧 p 值，用**正态近似** `2 * Φ(-|t|)` 计算，不是 t 分布。
- `n_left` / `n_right`：断点两侧实际参与拟合的行数。
- `slope_left` / `slope_right`：两侧直线的斜率（对 run 的斜率）。

输出没有逐样本拟合值、断点图、置信区间上下限，也没有协变量调整后的估计；只有这一行。任一侧有效行数少于 3 时抛 `ValueError("need at least 3 observations on each side of the cutoff")`，不会返回空表。

## Parameters

| 参数 | 类型 | 默认 | 说明 |
| --- | --- | --- | --- |
| `output` | string | `regression_discontinuity_out` | 输出端口名。 |
| `row_dim` | string | `row` | 输入表第 0 维名称。 |
| `field_dim` | string | `field` | 输入表第 1 维名称；两个列名都在这一维上查找。 |
| `y_column` | string | `y` | 响应变量列名。 |
| `running_column` | string | `run` | 驱动变量（running variable）列名。 |
| `cutoff` | number | `0.0` | 断点位置；代码会先做 `run -= cutoff` 再按符号分左右。 |
| `bandwidth` | number | `0.0` | 窗口半宽。**0 表示使用全部行**（不做任何裁剪），不是“零宽窗口”。 |

## Notes

- **`bandwidth = 0` 的语义**：代码是 `keep = |run - cutoff| <= bandwidth if bandwidth > 0 else 全部行`。因此默认 0 时全样本参与，两侧可能离断点很远，局部线性的“局部”假设被削弱；要真正的近邻估计必须显式给正数。
- **不是三角核**：旧文档/注释说 “triangular window”，实现是对带宽的**硬截断**（uniform kernel），没有 `1 - |r|/bw` 权重。带宽内的行等权。
- 拟合方式：两侧各做一次 `y ~ 1 + run` 的普通最小二乘（`np.linalg.solve` 解正规方程），跳跃 = 右截距 − 左截距；标准误来自经典 OLS 方差，**未做稳健/聚类修正**，异方差或聚类数据下会低估不确定性。
- p 值用正态近似而非 t 分布，小样本（每侧十几行）时偏小（更容易显著）；报告时不要当成精确的 t 检验。
- 没有协变量调整、没有多项式阶数选择、没有最优带宽选择（如 IK/CCT）、没有密度/操纵检验（McCrary）；这些都需要在上游另行完成。
- `cutoff` 必须落在驱动变量范围内，且两侧各至少 3 行；否则直接报错。跳跃的因果解释依赖“断点处无操纵、其他协变量连续”等识别假设。
- 输出行的第 0 维标签是字符串 `stat`（不是 `result`），下游按名取行时注意这一点。
