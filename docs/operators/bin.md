# Bin (`bin`)

**Category:** 数据整理  
**Entry point:** `src.task.step.steps.bin:BinStep`  
**Source:** [`library/seed/src/task/step/steps/bin.py`](../../library/seed/src/task/step/steps/bin.py) (326 lines)  
**Trust level: B — 真实执行（本地或 srv）**

## 1. 代码说明

Discretize a continuous axis into

> Discretize a continuous axis into bins. For each position along ``dim``, computes a bin index by cutting the values along the other axes into equal-width or equal-frequency intervals. The output has one row per position along ``dim`` and a single integer bin id per row. This is the standard way to turn a continuous quantity (age, expression, allele frequency, distance) into a categorical one that can be used by grouping operators such as ``aggregate`` or ``compare_groups``. Value per position ------------------ Two ways to decide the value used to bin each position: 1. ``value_label`` : if…

关键符号：

- `class BinStep (line 80)`

协议：v3 / revision `3.7`；输出参数 `output`。

### 输入与输出

- 输入 1: ndim=?, numeric=True, dims=(dim), info=(—)
- 输出: mode=project, schema={}

### 参数

| 参数 | 默认值 | 含义/约束 |
| --- | --- | --- |
| `dim` | `` | — |
| `bins` | `10` | min 1 |
| `method` | `quantile` | choices: quantile, uniform |
| `value_label` | `` | — |
| `stat` | `mean` | choices: mean, median, min, max, first |

## 2. 用途与解释

Discretize a continuous axis into bins.

For each position along ``dim``, computes a bin index by cutting the
values along the other axes into equal-width or equal-frequency
intervals. The output has one row per position along ``dim`` and a
single integer bin id per row.

This is the standard way to turn a continuous quantity (age,
expression, allele frequency, distance) into a categorical one that
can be used by grouping operators such as ``aggregate`` or
``compare_groups``.

Value per position
------------------
Two ways to decide the value used to bin each position:

1. ``value_label`` : if given, the operator reads that column from
the "other" axis (the one that is not ``dim``) and uses its
values directly. This is the right choice when the input is a
table whose second axis is a "statistic" axis with a single
named column.

2. ``stat`` : if ``value_label`` is not given, the operator

## 3. 正确性依据

**结论：B 级。** 真实运行通过（1.38 s），导出 None 行，产物 sha256 699a979f67856d97…。

| 层 | 状态 | 证据 |
| --- | --- | --- |
| L1 契约/清单 | PASS | verification/operator-audit-8.0.1/operator_table.csv |
| L2 单元/oracle | UNIT | tests/test_axis_adapters.py,test_compressed_inputs.py,test_dependencies.py,test_dependency_contract.py,test_exchange.py,test_export_contract.py,test_extension164.py,test_extension244.py,test_extension309.py,test_extension345.py,test_extension346.py,test_extension347.py,test_extension350.py,test_extension353.py,test_extension357.py,test_extension366.py,test_hic_workflow.py,test_operator_docs.py,test_remote_handshake.py,test_remote_installation.py,test_remote_provision.py,test_resource_downloads.py,test_server_setup.py,test_wheel_execution.py |
| L3 真实执行 | EXECUTED | verification/coverage-8.0.1/routes/bin |
| L4 资源 | ESTIMATE | definition resources.estimate=estimate_memory |
| L5 应用安装 | INSTALL | 8.0.1 bundle install (3.1.9/4.0.0) |

本次执行细节：

- 状态：PASS，耗时 1.38 s，导出 None 行。
- 归档路线：`/tmp/cov_sequence/bin`。
- 命令：`/home/gavin/bp-numpy21/bin/python scripts/run.py /tmp/cov_sequence/bin`。

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
grep '^bin,' verification/coverage-8.0.1/operator_coverage.csv
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
