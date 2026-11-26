# Transformer 表格分类器（transformer_classifier）

在一个 2-D 数值表 Form 内指定标签列，用小型的单 token Transformer 编码器做全批量训练，并返回单行的训练集分类指标（accuracy / log_loss / 规模统计），不返回预测结果。

## Inputs

| 名称 | 类型/维度 | 必填 | 说明 |
| --- | --- | --- | --- |
| `inputs[0]` | 2-D numeric Form，`row_dim` × `field_dim`（默认 `row` × `field`） | 是 | 唯一输入端口（`inputs_arity = 1`）。整个数据集就是这一张表：标签列 `label_column` 必须在这张表里、且在 `field_dim` 上有列名；标签值被直接当作类别 id 使用，必须是非负整数且从 0 开始连续（`n_classes = max(label) + 1`）。其余**带列名**的列按列名索引顺序组成特征矩阵；没有列名的列被忽略。 |

注意：本算子只有一个输入端口，不接受“特征表 + 标签表”两张表。若标签单独存在另一张表中，需先在上游按行合并（join）成一张表。

## Outputs

| 名称 | 类型/维度 | 说明 |
| --- | --- | --- |
| `output`（参数 `output` 可改名，默认 `output`） | ndim = 2 的 numeric Form，dims 固定为 `entry` × `statistic` | 恒为 **1 行 × 5 列**：`entry` 维度只有一个标签 `transformer`；`statistic` 维度依次是 `accuracy`、`log_loss`、`n_train`、`n_classes`、`n_params`。数值统一四舍五入到 3 位小数。 |

列的含义：

- `accuracy`：训练集上的逐行 argmax 命中率（0–1）。
- `log_loss`：训练集上的平均交叉熵 cross-entropy（自然对数，单位 nats/sample）。
- `n_train`：参与训练的样本行数。
- `n_classes`：类别数，等于标签最大值 + 1（不是标签列里出现的不同取值个数）。
- `n_params`：模型可训练参数总数（含特征投影、类别位置嵌入、编码器层与输出头）。

输出中**没有**逐样本预测、概率、混淆矩阵或置信区间；需要预测时应在同一表上重新拟合并自行前向计算。输入表为空或标签列缺失时不会返回空表，而是直接抛出异常。

## Parameters

| 参数 | 类型 | 默认 | 说明 |
| --- | --- | --- | --- |
| `label_column` | string | `label` | 标签列在 `field_dim` 上的列名；该列不参与特征。 |
| `d_model` | integer | `8` | 编码器隐藏宽度（token 维度），不是特征数。 |
| `nhead` | integer | `2` | 多头注意力的头数；必须整除 `d_model`，否则 PyTorch 报错。 |
| `layers` | integer | `1` | `TransformerEncoderLayer` 的层数；每层前馈维度固定为 `2 * d_model`。 |
| `epochs` | integer | `200` | 全批量梯度下降的步数（每步用全部样本），不是 epoch 意义上的 mini-batch 轮数。 |
| `learning_rate` | number | `0.01` | Adam 学习率。 |
| `seed` | integer | `7` | 初始化与训练过程的随机种子，用于复现。 |
| `output` | string | `output` | 输出端口名。 |
| `row_dim` | string | `row` | 输入/输出表的第 0 维名称，必填。 |
| `field_dim` | string | `field` | 输入表的第 1 维名称（列维度），必填；标签列名就在这一维上查找。 |

## Notes

- **指标全是样本内（in-sample）指标**：训练过程没有 train/validation 划分、没有早停、没有正则化之外的模型选择，`accuracy` 与 `log_loss` 直接在同一批行上计算，通常会明显偏乐观，不能当作泛化性能。
- 结构与规模：`Linear(特征数 → d_model)` → 类别位置嵌入 → `layers` 层自注意力（`nhead` 头，前馈 `2*d_model`）→ 单 token 均值池化 → `Linear(d_model → n_classes)`。整表放在一次前向里，显存/内存随行数线性增长，适合小表（数百到数千行）。
- 标签类型：代码执行 `x[:, label_index].astype(int)`，浮点标签会被截断；负值或空洞（例如只有 1 和 3 两类）会得到错误的 `n_classes`，并可能让训练目标越界。
- 特征列数由“带列名的列数减 1”决定；列名缺失的列不会被使用，但也不报错，容易出现“少了一列特征却无提示”的静默错误。
- `nhead` 不整除 `d_model` 时异常来自 PyTorch 而不是本算子；`d_model` 与 `nhead` 同改时请保持整除关系。
- 训练在 CPU 上即可完成，但每步都是全批量，`epochs` 增大到数千会线性变慢。
