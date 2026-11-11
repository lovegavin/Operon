# Per-sample genotype call rate (`genotype_call_rate_qc`)

**Category:** Population genetics  
**Entry point:** `src.task.step.steps.genotype_call_rate_qc:GenotypeCallRateQcStep`  
**Source:** [`library/seed/src/task/step/steps/genotype_call_rate_qc.py`](../../library/seed/src/task/step/steps/genotype_call_rate_qc.py) (43 lines)  
**Trust level: A- — 独立 oracle（未记录真实执行）**

## 1. 代码说明

Reports called fraction and a pass flag per

> Definition for the genotype_call_rate_qc

关键符号：

- `class GenotypeCallRateQcStep (line 7)`

协议：v3 / revision `3.7`；输出参数 `output`。

### 输入与输出

- 输入 1: ndim=2, numeric=True, dims=(variant_dim, sample_dim), info=(—)
- 输出: mode=declare, schema={"ndim": 2, "numeric": true, "info_open": true, "axis_info_open": true}

### 参数

| 参数 | 默认值 | 含义/约束 |
| --- | --- | --- |
| `output` | `output` | — |
| `min_call_rate` | `0.9` | — |
| `variant_dim` | `variant` | — |
| `sample_dim` | `sample` | — |

## 2. 用途与解释

Reports called fraction and a pass flag per sample.

## 3. 正确性依据

**结论：A- 级。** 独立实现「manual call-rate arithmetic with NaN as missing」，实测差值 0.000e+00。

| 层 | 状态 | 证据 |
| --- | --- | --- |
| L1 契约/清单 | PASS | verification/operator-audit-8.0.1/operator_table.csv |
| L2 单元/oracle | ORACLE | operator_table.csv:l2_oracle |
| L3 真实执行 | ROUTE | operator_table.csv:generated_route |
| L4 资源 | ESTIMATE | definition resources.estimate=estimate_memory |
| L5 应用安装 | INSTALL | 8.0.1 bundle install (3.1.9/4.0.0) |

独立 oracle 细节：

- 参考实现：manual call-rate arithmetic with NaN as missing
- 结果：pass=True, delta=0.0, tolerance=None

### 这个证据证明什么、不证明什么

- 证明：契约可解析、输入输出维度一致；有执行记录时，真实数据能跑到 `Task finished` 并产生可校验产物。
- 不证明：该算子在该数据集上的生物学结论正确；统计假设是否成立仍需使用者判断。

## 4. 限制与失败模式

No phasing; assumes unique labels.

## 5. 复现

```bash
cd /home/gavin/Operon-7015-native
python -m operon registry check --json
grep '^genotype_call_rate_qc,' verification/coverage-8.0.1/operator_coverage.csv
```

未补齐证据：`L4_MEASURED`。

---

由 `scripts/build_operator_trust_docs.py` 生成；审计基线 8.0.1。
