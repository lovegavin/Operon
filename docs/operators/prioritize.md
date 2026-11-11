# prioritize (`prioritize`)

**Category:** data  
**Entry point:** `src.task.step.steps.prioritize:PrioritizeStep`  
**Source:** [`library/seed/src/task/step/steps/prioritize.py`](../../library/seed/src/task/step/steps/prioritize.py) (196 lines)  
**Trust level: B — 真实执行（本地或 srv）**

## 1. 代码说明

Keep the top positions along a dimension, ranked by an info

> Keep the top positions along an axis, ranked by an info field. Positions are sorted by a numeric info field declared parallel to ``dim``. The top ``top_n`` are retained. Their order in the output matches their order in the source, so downstream label alignment stays stable. This pairs with ``annotate``: annotate writes reference columns into ``info``; prioritize selects the positions whose annotation matters most. Layout ------ input dims: [..., dim, ...] output dims: same as input, with ``dim`` shortened to ``top_n`` Ranking ------- Missing values (NaN) are ranked last regardless of…

关键符号：

- `class PrioritizeStep (line 41)`

协议：v3 / revision `3.7`；输出参数 `output`。

### 输入与输出

- 输入 1: ndim=?, numeric=True, dims=(dim), info=(—)
- 输出: mode=subset, schema={}

### 参数

| 参数 | 默认值 | 含义/约束 |
| --- | --- | --- |
| `dim` | `` | Dimension to sort |
| `by` | `` | Ranking field |
| `top_n` | `` | Top N; min 1 |
| `ascending` | `False` | Ascending |
| `output` | `` | Output key |

## 2. 用途与解释

Keep the top positions along an axis, ranked by an info field.

Positions are sorted by a numeric info field declared parallel to
``dim``. The top ``top_n`` are retained. Their order in the output
matches their order in the source, so downstream label alignment
stays stable.

This pairs with ``annotate``: annotate writes reference columns into
``info``; prioritize selects the positions whose annotation matters
most.

Layout
------
input   dims: [..., dim, ...]
output  dims: same as input, with ``dim`` shortened to ``top_n``

Ranking
-------
Missing values (NaN) are ranked last regardless of direction.
Ties keep their source order (stable sort).

Params:
dim        : dimension to sort along (required)
by         : info field to rank by (required)
top_n      : number of positions to keep (required)
ascending  : False ranks largest first (default); True ranks
smallest first
output     : con

## 3. 正确性依据

**结论：B 级。** 真实运行通过（1.39 s），导出 None 行，产物 sha256 n/a…。

| 层 | 状态 | 证据 |
| --- | --- | --- |
| L1 契约/清单 | PASS | verification/operator-audit-8.0.1/operator_table.csv |
| L2 单元/oracle | UNIT | tests/test_operator_metadata.py |
| L3 真实执行 | EXECUTED | verification/coverage-8.0.1/routes/prioritize |
| L4 资源 | ESTIMATE | definition resources.estimate=estimate_memory |
| L5 应用安装 | INSTALL | 8.0.1 bundle install (3.1.9/4.0.0) |

本次执行细节：

- 状态：PASS，耗时 1.39 s，导出 None 行。
- 归档路线：`/tmp/cov_sequence/prioritize`。
- 命令：`/home/gavin/bp-numpy21/bin/python scripts/run.py /tmp/cov_sequence/prioritize`。

### 这个证据证明什么、不证明什么

- 证明：契约可解析、输入输出维度一致；有执行记录时，真实数据能跑到 `Task finished` 并产生可校验产物。
- 不证明：该算子在该数据集上的生物学结论正确；统计假设是否成立仍需使用者判断。

## 4. 限制与失败模式

Declared memory modes: full. Operon retains the existing planner, disk-backed
inputs and emergency spill behavior; full-mode operators still require their
declared working set. This generated reference has not been independently
scientifically reviewed.

## 5. 复现

```bash
cd /home/gavin/Operon-7015-native
python -m operon registry check --json
grep '^prioritize,' verification/coverage-8.0.1/operator_coverage.csv
```

算子手册中的示例：

```text
Use the registry to discover compatible Readers and validate a complete workflow
before execution. This generated page does not claim an executable scientific
example. Add a tested example and replace this generated page with authored
guidance when extending this operator.
```

未补齐证据：`L4_MEASURED`。

---

由 `scripts/build_operator_trust_docs.py` 生成；审计基线 8.0.1。
