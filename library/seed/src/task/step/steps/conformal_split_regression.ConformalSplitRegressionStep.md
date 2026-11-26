# 分裂共形回归区间（conformal_split_regression）

用一张已经含“真实值 / 预测值 / 阶段标记”三列的表做分裂共形预测（split conformal prediction）：用校准行算残差分位数，为每个测试行给出有限样本覆盖的预测区间。**本算子不拟合任何模型**。

## Inputs

| 名称 | 类型/维度 | 必填 | 说明 |
| --- | --- | --- | --- |
| `inputs[0]` | 2-D numeric Form，`row_dim` × `field_dim`（默认 `row` × `field`） | 是 | 唯一输入端口（`inputs_arity = 1`）。列**按位置**解释，不看列名：第 0 列 = 真实值 `y_true`，第 1 列 = 上游给出的预测值 `y_pred`，第 2 列 = 阶段标记 `phase`（`phase == 0` 为校准集 calibration，**其他任何值**都算测试集 test）。第 4 列及以后被忽略。 |

上游必须先自己完成训练/预测并把预测值写进第 1 列；本算子只负责“把点预测变成区间”。`phase` 用 0/1 标记即可，但任何非 0 值都会被当作测试行。

## Outputs

| 名称 | 类型/维度 | 说明 |
| --- | --- | --- |
| `output`（参数 `output` 可改名，默认 `output`） | ndim = 2 的 numeric Form，dims 固定为 `entry` × `statistic` | **每个测试行一行**（行数 = 测试行数，不是 1 行汇总）；`entry` 维度标签取输入表的行名，取不到时用行号字符串；`statistic` 依次为 `y_true`、`y_pred`、`lower`、`upper`、`width`、`covered`。数值保留 9 位小数。 |

- `lower` / `upper`：区间下界与上界，`[y_pred - q, y_pred + q]`。
- `width`：`upper - lower`（恒等于 `2q`，保留列是为了下游筛选）。
- `covered`：0/1 标记，`y_true` 是否落在 `[lower, upper]` 内。

输出**没有**汇总行（没有覆盖率、平均宽度、q 值这些列）；要整体覆盖率需在上游对 `covered` 求均值。校准行少于 2 行、测试行少于 1 行时抛 `StepError("need at least two calibration and one test row")`，不会返回空表。

## Parameters

| 参数 | 类型 | 默认 | 说明 |
| --- | --- | --- | --- |
| `row_dim` | string | `row` | 输入/输出表第 0 维名称。 |
| `field_dim` | string | `field` | 输入表第 1 维名称（列维度）。 |
| `output` | string | `output` | 输出端口名。 |
| `alpha` | number | `0.1` | 误覆盖率，取值必须严格在 (0, 1) 内（schema 限制 0.001–0.999）；`alpha = 0.1` 对应约 90% 边际覆盖。 |

## Notes

- 校准分位数：`level = ceil((n_cal + 1) * (1 - alpha)) / n_cal`（裁剪到 [0, 1]），再取校准残差 `|y - y_pred|` 的 `level` 分位（`method="higher"`，即取不小于该分位的实际残差值）。这就是标准的 split-conformal 有限样本修正，n_cal 很小时 `level` 会顶到 1.0，区间变成“最大校准残差”。
- **校准集与测试集必须可交换（exchangeable）**：同一批数据随机切分才成立。若校准行与测试行来自不同分布/不同时间段，覆盖保证失效。
- 保证的是**边际覆盖**（对所有测试行平均而言约 `1 - alpha`），**不是条件覆盖**：某些子群体（如预测值很大或很小的行）可能明显欠覆盖。需要分组诊断时，把组别作为额外列带出来自行统计。
- 本算子不训练模型、不访问特征，`y_pred` 完全由上游决定；因此“区间好不好”首先取决于点预测质量，其次才是校准集大小。
- 列位置是硬约定：把 `phase` 放在第 0 列、或漏掉预测列，都会静默产生错误结果（不会报错），这是最常见的误用。
- 行名取自输入表的 `row` 维标签；若上游把行维改名，`entry` 会退回行号字符串，下游按名连接时需要注意。
- `covered` 是 0/1 数值而不是布尔值，求均值即得经验覆盖率。
