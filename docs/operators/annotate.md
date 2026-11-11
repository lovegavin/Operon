# annotate (`annotate`)

**Category:** data  
**Entry point:** `src.task.step.steps.annotate:AnnotateStep`  
**Source:** [`library/seed/src/task/step/steps/annotate.py`](../../library/seed/src/task/step/steps/annotate.py) (297 lines)  
**Trust level: B — 真实执行（本地或 srv）**

## 1. 代码说明

Attach reference fields onto a target by key

> Attach reference fields onto a target by key label. Aligns two forms on a shared key dimension by label, then copies the requested reference fields into the target's ``info``, declaring them parallel to the target key axis. A reference field may come from either: * a data column: its label on ``field_dim``; encoded columns carry their encoder across so codes stay comparable. * an info field: declared parallel to ``source_dim`` in ``axis_info``; typically read verbatim by ``info_columns``. This is the standard way to enrich a table with an external lookup table (variant annotations, gene…

关键符号：

- `class AnnotateStep (line 53)`

协议：v3 / revision `3.7`；输出参数 `output`。

### 输入与输出

- 输入 1: ndim=?, numeric=True, dims=(target_dim), info=(—)
- 输入 2: ndim=2, numeric=True, dims=(source_dim), info=(—)
- 输出: mode=unknown, schema={}

### 参数

| 参数 | 默认值 | 含义/约束 |
| --- | --- | --- |
| `target_dim` | `` | Target key dimension |
| `source_dim` | `` | Reference key dimension |
| `fields` | `` | Fields to attach |
| `field_dim` | `` | Reference field dimension |
| `output` | `` | Output key |

## 2. 用途与解释

Attach reference fields onto a target by key label.

Aligns two forms on a shared key dimension by label, then copies the
requested reference fields into the target's ``info``, declaring them
parallel to the target key axis.

A reference field may come from either:

* a data column: its label on ``field_dim``; encoded columns carry
their encoder across so codes stay comparable.
* an info field: declared parallel to ``source_dim`` in
``axis_info``; typically read verbatim by ``info_columns``.

This is the standard way to enrich a table with an external lookup
table (variant annotations, gene descriptions, taxon metadata,
sample covariates) without merging data dimensions.

Layout
------
target     dims: [key_dim, ...]
reference  dims: [key_dim_ref, field_dim]
output     dims: same as target

Alignment
---------
Matching is by label, not by position. For every target label on
``target_dim`

## 3. 正确性依据

**结论：B 级。** 真实运行通过（1.38 s），导出 None 行，产物 sha256 bd636230e95f0076…。

| 层 | 状态 | 证据 |
| --- | --- | --- |
| L1 契约/清单 | PASS | verification/operator-audit-8.0.1/operator_table.csv |
| L2 单元/oracle | UNIT | tests/test_extension381.py,test_operator_metadata.py |
| L3 真实执行 | EXECUTED | verification/coverage-8.0.1/routes/annotate |
| L4 资源 | ESTIMATE | definition resources.estimate=estimate_memory |
| L5 应用安装 | INSTALL | 8.0.1 bundle install (3.1.9/4.0.0) |

本次执行细节：

- 状态：PASS，耗时 1.38 s，导出 None 行。
- 归档路线：`/tmp/cov_sequence/annotate`。
- 命令：`/home/gavin/bp-numpy21/bin/python scripts/run.py /tmp/cov_sequence/annotate`。

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
grep '^annotate,' verification/coverage-8.0.1/operator_coverage.csv
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
