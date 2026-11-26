# 线性分位数回归（deep_quantile_regressor）

对**单个预测变量**拟合线性分位数回归（linear quantile regression），用线性规划直接求解 pinball 损失的极小值，输出斜率、截距、分位点与样本内平均 pinball 损失。名字里的 “deep” 与实现无关：它没有神经网络，也不使用 Adam。

## Inputs

| 名称 | 类型/维度 | 必填 | 说明 |
| --- | --- | --- | --- |
| `inputs[0]` | 2-D numeric Form，`row_dim` × `field_dim`（默认 `row` × `field`） | 是 | 唯一输入端口（`inputs_arity = 1`）。按**列名**取两列：`feature_column`（预测变量 x）与 `target_column`（响应 y），列名在最后一维 `field_dim` 的标签中查找。其余列被忽略。 |

列名缺失时抛 `ValueError`，信息形如 `missing column x; have ['a', 'b']`，不会静默使用第 0/1 列。

## Outputs

| 名称 | 类型/维度 | 说明 |
| --- | --- | --- |
| `output`（参数 `output` 指定，无默认值） | ndim = 2 的 numeric Form，dims 固定为 `entry` × `statistic` | 恒为 **1 行 × 5 列**：`entry` 唯一标签为 `result`；`statistic` 依次为 `slope`、`intercept`、`quantile`、`pinball_loss`、`n_train`。数值四舍五入到 3 位小数。 |

- `slope` / `intercept`：分位回归直线 `y ≈ slope * x + intercept` 的两个系数。
- `quantile`：回显参数 `quantile`（例如 0.5 表示中位数回归）。
- `pinball_loss`：在拟合系数下、**训练样本内**的平均 pinball 损失（分位损失），越小越好，但不同数据之间不可直接比较。
- `n_train`：参与拟合的样本行数。

输出**没有**标准误、置信区间、p 值、R²，也没有逐行预测值；如需区间请在上游用不同 `quantile` 多次调用。样本量不足或列缺失时抛异常，不会返回空表。

## Parameters

| 参数 | 类型 | 默认 | 说明 |
| --- | --- | --- | --- |
| `row_dim` | string | `row` | 输入表第 0 维名称。 |
| `field_dim` | string | `field` | 输入表第 1 维名称（列维度）；列名在该维标签中查找。 |
| `output` | string | — | 输出端口名；代码直接读取该键，未提供时会因缺少键而失败，请显式给出。 |
| `feature_column` | string | `x` | 预测变量列名（必填项，但默认值可用）。 |
| `target_column` | string | `y` | 响应变量列名（必填项，但默认值可用）。 |
| `quantile` | number | `0.5` | 目标分位点，0.5 为中位数回归；建议保持在 (0, 1) 内（代码未做范围校验）。 |
| `epochs` | integer | `500` | **不参与计算**：求解器是线性规划，没有迭代轮数概念，该参数为历史遗留。 |
| `learning_rate` | number | `0.05` | **不参与计算**：没有梯度下降，该参数为历史遗留。 |
| `seed` | integer | `0` | **未使用**：HiGHS 线性规划求解是确定性的，同一输入必得同一结果。 |

## Notes

- 模型形式固定为 `y = slope * x + intercept`，**只支持一个预测变量**，没有交互项、多项式项或正则化；要多个自变量需要自己构造复合特征列或改用其他算子。
- 求解方式：把 `slope`、`intercept` 与 n 个残差变量放进一个线性规划，最小化 `sum(rho_quantile(residual))`，由 `scipy.optimize.linprog(method="highs")` 求解；因此结果对离群点稳健（分位损失线性增长），但也可能在大规模或退化数据上出现求解器失败。
- 分位数越高，拟合越靠近响应分布的上尾；`quantile = 0.9` 得到的 `slope` 与 `0.1` 不同是正常现象，不能用“系数应一致”来判断对错。
- `pinball_loss` 是样本内指标且依赖 `quantile`，不能跨分位点直接比较，也不能与最小二乘的 MSE 比较。
- 由于 `epochs`/`learning_rate`/`seed` 实际被忽略，改动它们**不会**改变输出，这也是旧文档最容易误导的地方。
- 若 x 为常数或样本数极少，设计矩阵退化，线性规划可能给出 `slope = 0` 或直接失败；请在上游检查方差与样本量。
