# Polygenic risk score (`prs`)

**Category:** Omics  
**Entry point:** `src.task.step.steps.prs:PrsStep`  
**Source:** [`library/seed/src/task/step/steps/prs.py`](../../library/seed/src/task/step/steps/prs.py) (116 lines)  
**Trust level: C — 专用测试引用 + 可编译路线**

## 1. 代码说明

Polygenic risk score：接收 2 个输入，输出 Form；主要参数：Variant Dim、样本维度、统计维度、Weight

> Polygenic risk score from aligned genotype dosages and variant weights. Inputs ------ genotype : [variant, sample] allele dosage (0/1/2 or continuous dosage) weights : [variant, statistic] with a beta-weight column The operator assumes the genotype dosage and weight are already aligned to the same effect allele. It deliberately does not guess strand or effect-allele orientation. Missing genotypes contribute zero and are counted in the export; the score is therefore a complete-case dosage sum over the variants present in both

关键符号：

- `class PrsStep (line 26)`

协议：v3 / revision `3.7`；输出参数 `output`。

### 输入与输出

- 输入 1: ndim=2, numeric=True, dims=(variant_dim, sample_dim), info=(—)
- 输入 2: ndim=2, numeric=True, dims=(variant_dim, stat_dim), info=(—)
- 输出: mode=declare, schema={"ndim": 2, "numeric": true, "info_open": false, "axis_info_open": false, "info": {"missing_code": {"type": ["number", "null"]}}}

### 参数

| 参数 | 默认值 | 含义/约束 |
| --- | --- | --- |
| `variant_dim` | `variant` | Variant Dim |
| `sample_dim` | `sample` | 样本维度 |
| `stat_dim` | `statistic` | 统计维度; advanced |
| `weight_label` | `beta` | Weight Label |
| `output` | `` | 输出名称 |

## 2. 用途与解释

Polygenic risk score from aligned genotype dosages and variant weights.

Inputs
------
genotype : [variant, sample] allele dosage (0/1/2 or continuous dosage)
weights  : [variant, statistic] with a beta-weight column

The operator assumes the genotype dosage and weight are already aligned
to the same effect allele. It deliberately does not guess strand or
effect-allele orientation. Missing genotypes contribute zero and are
counted in the export; the score is therefore a complete-case dosage
sum over the variants present in both inputs.

## 3. 正确性依据

**结论：C 级。** 路线已编译进 79 条内置路线，并有专用测试引用；没有记录为本算子单独执行过真实数据。

| 层 | 状态 | 证据 |
| --- | --- | --- |
| L1 契约/清单 | PASS | verification/operator-audit-8.0.1/operator_table.csv |
| L2 单元/oracle | UNIT | tests/test_extension_operators.py |
| L3 真实执行 | ROUTE | operator_table.csv:builtin_route |
| L4 资源 | ESTIMATE | definition resources.estimate=estimate_memory |
| L5 应用安装 | INSTALL | 8.0.1 bundle install (3.1.9/4.0.0) |

### 这个证据证明什么、不证明什么

- 证明：契约可解析、输入输出维度一致；有执行记录时，真实数据能跑到 `Task finished` 并产生可校验产物。
- 不证明：该算子在该数据集上的生物学结论正确；统计假设是否成立仍需使用者判断。
- 注意：该算子没有独立数值 oracle， correctness 仅到“契约/测试/执行”层级。

## 4. 限制与失败模式

Declared memory modes: full. Operon retains the existing planner, disk-backed
inputs and emergency spill behavior; full-mode operators still require their
declared working set. This generated reference has not been independently
scientifically reviewed.

## 5. 复现

```bash
cd /home/gavin/Operon-7015-native
python -m operon registry check --json
grep '^prs,' verification/coverage-8.0.1/operator_coverage.csv
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
