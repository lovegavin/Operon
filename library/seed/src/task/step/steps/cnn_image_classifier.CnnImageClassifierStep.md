# CNN 图像分类器（cnn_image_classifier）

把 2-D 表中的一行当作一张扁平灰度图（像素按列顺序展开），用两层卷积网络做全批量训练，返回单行的训练集分类指标。

## Inputs

| 名称 | 类型/维度 | 必填 | 说明 |
| --- | --- | --- | --- |
| `inputs[0]` | 2-D numeric Form，`row_dim` × `field_dim`（默认 `row` × `field`） | 是 | 唯一输入端口（`inputs_arity = 1`）。标签列由 `label_column` 在 `field_dim` 上指定，取值直接当类别 id（须为非负、从 0 开始连续的整数，`n_classes = max + 1`）。**除标签列之外所有带列名的列**都按列名索引顺序当作像素，因此像素列数必须恰好等于 `height * width`。 |

行优先展开（row-major）：列顺序即像素顺序，第 1 个像素是图像左上角，之后逐行向右、向下排。像素列的实际先后由 `field_dim` 的列名索引顺序决定，不由参数决定。

## Outputs

| 名称 | 类型/维度 | 说明 |
| --- | --- | --- |
| `output`（参数 `output` 可改名，默认 `output`） | ndim = 2 的 numeric Form，dims 固定为 `entry` × `statistic` | 恒为 **1 行 × 7 列**：`entry` 唯一标签为 `cnn`；`statistic` 依次为 `accuracy`、`log_loss`、`n_train`、`n_classes`、`n_params`、`height`、`width`。四舍五入到 3 位小数。 |

- `accuracy`：训练集逐行 argmax 命中率。
- `log_loss`：训练集平均交叉熵（nats/sample）。
- `n_train`：样本行数；`n_classes`：类别数；`n_params`：可训练参数总数。
- `height` / `width`：本次实际使用的图像尺寸（回显参数，便于核对表结构）。

输出中没有预测标签、概率图、特征图或混淆矩阵；没有“每张图一行”的结果，永远只有一行汇总。像素列数与 `height * width` 不一致时抛 `ValueError`（信息形如 `expected 16 pixels, got 12`），不会返回空表。

## Parameters

| 参数 | 类型 | 默认 | 说明 |
| --- | --- | --- | --- |
| `label_column` | string | `label` | 类别列名（在 `field_dim` 上查找）。 |
| `height` | integer | `4` | 图像高（像素行数）。 |
| `width` | integer | `4` | 图像宽（像素列数）；`height * width` 必须等于像素列数。 |
| `epochs` | integer | `200` | 全批量 Adam 的梯度步数（每步使用全部样本）。 |
| `learning_rate` | number | `0.01` | Adam 学习率。 |
| `seed` | integer | `7` | 初始化与打乱顺序的随机种子。 |
| `output` | string | `output` | 输出端口名。 |
| `row_dim` | string | `row` | 输入表第 0 维名称，必填。 |
| `field_dim` | string | `field` | 输入表第 1 维名称（列维度），必填。 |

## Notes

- 网络结构固定：`Conv2d(1→4, 3×3, padding=1) + ReLU` → `Conv2d(4→8, 3×3, padding=1) + ReLU` → `AdaptiveAvgPool2d(1)` → `Linear(8→n_classes)`。没有 BatchNorm、Dropout 或数据增强，`epochs`、`learning_rate` 之外没有可调的网络结构参数。
- **不做像素归一化**：原始数值直接进入卷积。若上游是 0–255 的灰度值，请先缩放到 0–1 左右，否则训练几乎不收敛。
- 指标同样是**样本内**指标：无 train/validation 划分、无早停，`accuracy` 与 `log_loss` 在同一批行上计算。
- 尺寸约束来自代码而非提示：`height * width` 必须与“带列名的列数 - 1（标签列）”完全相等；改 `height`/`width` 而不改表结构会立即报错。
- 只适合小图（默认 4×4）与少量样本：两层卷积、全批量，样本数上千后速度下降明显。
- 标签列若不是整数或不是从 0 连续，会出现类别数偏大或索引越界；这类错误不会在参数校验阶段被拦下。
