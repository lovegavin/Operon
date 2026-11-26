# ColabFold structure prediction

## Purpose

> 用官方 `colabfold_batch` 从一条序列预测结构并读取置信度。

该算子把序列交给 ColabFold 的批处理入口，返回 rank-001 的 PDB 结构，以及
pLDDT、pTM 和 PAE 的汇总。它只负责调用：不训练模型、不合并多条比对，也不判断
折叠结果是否具有生物学意义。

实际使用中最容易卡住的是 MSA 搜索。`mmseqs2_uniref_env` 和 `mmseqs2_uniref`
都需要可达的 MSA 服务器，或本机已下载的 uniref/环境序列数据库；`colabfold`
解释器默认不附带这些搜索数据库，所以未额外配置时 `colabfold_batch` 会请求公共
服务器 `https://api.colabfold.com`。只要该地址可达，这两种模式就是可用的，不需要
在本机准备数据库。`msa_host` 用来改指私有或镜像服务器；确实不需要比对时再退回
`single_sequence`。

## Inputs and outputs

Kind: `operator`. Operator ID: `colabfold_predict`. Input count: `1`.

输入端口是 `sequence` × `position` 的序列表。Reader 保留的原始 FASTA 文本优先，
因此多聚体的 `:` 链分隔符不会被解码成未知残基。

输出端口是 `atom` × `field` 的 Form，来自 rank-001 的 PDB。`info` 记录
`mean_plddt`、`ptm`、`max_pae`、`n_residues`、`model_path`、`scores_path`、
`sequences`、`msa_mode` 和 `msa_host`。PDB 与 ColabFold 的 scores JSON 作为
native results 保留为 `structure` 和 `scores`。

## Parameters

| 参数 | 默认值 | 说明 |
| --- | --- | --- |
| `colabfold_path` | `colabfold_batch` | 可执行文件；以 `.py` 结尾时用当前解释器启动。 |
| `num_models` | `1` | `--num-models`，取值 1-5。 |
| `num_recycles` | `3` | `--num-recycle`，取值 1-48。 |
| `msa_mode` | `mmseqs2_uniref_env` | `--msa-mode`，见下文。 |
| `msa_host` | 空 | `--host-url`；MSA 服务器地址。留空时不传该参数，沿用 ColabFold 的默认值。 |
| `device` | `auto` | `auto`、`cpu` 或 `cuda`；`cpu` 会清空 `CUDA_VISIBLE_DEVICES`。 |
| `timeout_seconds` | `3600` | 整次运行的墙钟上限，包含 MSA 搜索。 |
| `output` | `structure` | 输出端口名。 |

`msa_host` 为空或全为空白时视为未设置，命令中不出现 `--host-url`，行为与旧版本
完全一致。非空值必须是 `http://` 或 `https://` 开头的 URL；否则在启动
`colabfold_batch` 之前就以 `StepError` 拒绝，避免把拼写错误变成难懂的连接失败。
校验后的地址会写入输出 `info` 的 `msa_host`，便于确认某次运行实际用了哪台服务器。

## MSA modes

| 模式 | 搜索范围 | 前提 |
| --- | --- | --- |
| `mmseqs2_uniref_env` | UniRef 加环境序列（ColabFold 默认） | MSA 服务器，或本地 uniref/环境数据库 |
| `mmseqs2_uniref` | 仅 UniRef | 同上 |
| `single_sequence` | 不搜索，序列本身作为比对 | 无 |

两种 `mmseqs2_*` 模式并非天然离线：本机没有数据库时，`colabfold_batch` 会把查询
提交到 `--host-url` 指向的服务器（默认 `https://api.colabfold.com`）。那是共享的
公共服务，可能排队、限流或暂时不可达；搜索失败会表现为非零退出码，算子会把退出
码和 stderr 末尾一并报出。要避开公共服务的波动，就在 `msa_host` 填一个私有或
镜像地址。

`single_sequence` 完全不联网，适合确认预测链路本身是否正常，也适合既不联网又没有
数据库的机器。代价是真实存在的：没有共进化信号，pLDDT 和 pTM 通常更低，多聚体
几乎拿不到链间信号（ipTM），因此它的输出应视为冒烟测试而非科研结果。

`msa_host` 非空时，算子把 `--host-url` 追加到命令末尾，例如：

```text
colabfold_batch query.fasta out --num-models 1 --num-recycle 3 --msa-mode mmseqs2_uniref_env --overwrite --host-url https://msa.example.org
```

`colabfold_path` 指向 `.py` 时，命令行最前面还会多一个 `sys.executable`。

## Runtime environment

声明依赖为 `numpy>=1.24`；算子运行在专用的 `colabfold` 解释器中，解析和覆盖方式见
docs/large_resources.md。`colabfold_batch` 必须在可执行路径上（默认参数就是这个
名称）。搜索数据库（uniref 等）体积很大，默认不会安装，因此 MSA 要么走服务器，
要么用 `single_sequence`，要么另行准备本地数据库。

## Notes

每次运行使用独立的临时目录（`operon_colabfold_*`），结束后删除，因此搜索产生的
`.a3m` 不会保留：同一序列重复预测会重复付 MSA 的代价。`colabfold_batch` 本身也
接受 `.a3m` 作为 query，但本算子固定写入 `query.fasta`，无法复用已有比对；需要
复用时应在本算子之外完成搜索。在本项目的验证中，一个测试复合物经公共服务器的
`mmseqs2_uniref_env` 搜索约 76 秒返回 1,147 条 a2m 序列，说明该路径在联网主机上
是可用且可等待的。

## Limitations

- 一次只预测一条 query：算子写一个 `query.fasta`、调用一次 runner，不批量、不合并
  多种 `msa_mode`、不做模板搜索。
- 不暴露 Amber/relaxation 等开关，runner 自身默认值生效。
- 只汇总 `ptm` 与 `max_pae`：多聚体的 ipTM 仍在保留的 `scores.json` 里，需要链间
  置信度时应直接读该文件。
- 评分来自 ColabFold 的模型输出，算子不做校准，也不评估生物学有效性。
- MSA 服务器属于外部设施，公共服务器故障不代表序列或本机安装有问题。

## Examples

```python
from src.task.step.steps.colabfold_predict import ColabfoldPredictStep
```

把该步骤接在 FASTA Reader 之后；先以 `msa_mode = "single_sequence"` 做一次不联网的
冒烟测试，确认链路可用后，再改为 `mmseqs2_uniref_env` 并视需要设置 `msa_host`。

命令拼装由 tests/test_extension244.py（`--msa-mode`、模型数、循环数）和
tests/test_colabfold_msa_host.py（`--host-url` 的有无与 URL 校验）覆盖；序列拼接规则
见 tests/test_colabfold_sequence.py。

## Source

Implementation: `src/task/step/steps/colabfold_predict.py` (`ColabfoldPredictStep`).
