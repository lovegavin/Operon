# GCN 节点分类器（gcn_node_classifier）

在给定的无向图上跑两层图卷积（GCN），用**全部节点**的标签做全批量训练，输出单行的训练集分类指标。输入是两张表：节点特征/标签表与边表。

## Inputs

| 名称 | 类型/维度 | 必填 | 说明 |
| --- | --- | --- | --- |
| `inputs[0]`（节点表） | 2-D numeric Form，`row_dim` × `field_dim` | 是 | 每行一个节点，行顺序即节点索引 0..n-1（边表里的端点编号指向这里）。`label_column` 按列名给出类别标签；**特征取该表除最后一列之外的所有列**，所以标签列必须是物理上的最后一列。 |
| `inputs[1]`（边表） | 2-D integer Form，形状 `(n_edges, 2)` | 是 | 每行一条边的两个端点 `(u, v)`，按 `inputs[1].data` **位置**读取，不做列名查找。边会被自动对称化（同时加入 `u→v` 与 `v→u`）并补自环，重复边无副作用。 |

`inputs_arity = 2`，两个端口都必须连接；只连一个端口会在校验阶段失败。

## Outputs

| 名称 | 类型/维度 | 说明 |
| --- | --- | --- |
| `output`（参数 `output` 指定，无默认值） | ndim = 2 的 numeric Form，dims 固定为 `entry` × `statistic` | 恒为 **1 行 × 6 列**：`entry` 唯一标签为 `result`；`statistic` 依次为 `accuracy`、`log_loss`、`n_nodes`、`n_edges`、`n_classes`、`n_params`。四舍五入到 3 位小数。 |

- `accuracy`：全部节点上的 argmax 命中率（**样本内**）。
- `log_loss`：全部节点上的平均交叉熵（nats/node）。
- `n_nodes`：节点表行数；`n_edges`：边表**输入行数**（对称化之前的原始条数，不是 2 倍）。
- `n_classes`：`max(label) + 1`，不是不同标签值的个数。
- `n_params`：两层权重与偏置的参数总数。

输出中没有逐节点预测、嵌入向量或邻接矩阵；没有 per-node 行，永远只有一行汇总。输入为空、标签越界或边端点超出节点范围时会抛异常，不会返回空表。

## Parameters

| 参数 | 类型 | 默认 | 说明 |
| --- | --- | --- | --- |
| `row_dim` | string | `row` | 两张输入表第 0 维名称。 |
| `field_dim` | string | `field` | 输入表第 1 维名称；标签列名在这一维上查找。 |
| `output` | string | — | 输出端口名；代码直接读取该键，请显式给出。 |
| `label_column` | string | `label` | 节点表里的类别列名（必填项，默认值可用）。 |
| `hidden` | integer | `8` | 隐层宽度；参数量约 `f*hidden + hidden*K`。 |
| `epochs` | integer | `300` | 全批量 Adam 的梯度步数（每步使用全部节点）。 |
| `learning_rate` | number | `0.05` | Adam 学习率。 |
| `seed` | integer | `0` | 权重初始化的随机种子。 |

## Notes

- 名称里的 “semi-supervised” 与实现不符：代码对**所有节点**的标签计算交叉熵，没有 train mask，也没有验证集；`accuracy`/`log_loss` 都是样本内指标，偏高是必然的。
- 归一化方式：`A_hat = A + I`（对称化并补自环），`Â = D^{-1/2} A_hat D^{-1/2}`，前向为 `Â · ReLU(Â · X · W1) · W2`。没有 dropout、没有 batch norm、没有注意力。
- **标签列必须在最后一列**：特征列是 `X[:, :-1]`，如果标签列在中间，最后一列会被当作特征，而标签列同时又会混进特征，且不会报错。
- 边端点不校验范围：超上界抛索引错误；**负数端点会按 Python 负索引回绕**到末尾节点，静默错误，务必在上游保证 `0 <= u, v < n_nodes`。
- 边表必须是整数类型；浮点端点会被 `astype(int)` 截断。
- 邻接矩阵按 `n × n` 稠密张量构建，内存随节点数平方增长；只适合小图（数百到数千节点）。
- 类别标签必须是从 0 开始连续的非负整数：空洞会让 `n_classes` 偏大并产生永不预测的类；负标签会直接让交叉熵报错。
