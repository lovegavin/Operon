# InterPro domain summary (`interpro_domain_summary`)

**Category:** Genome annotation  
**Entry point:** `src.task.step.steps.interpro_domain_summary:InterproDomainSummaryStep`  
**Source:** [`library/seed/src/task/step/steps/interpro_domain_summary.py`](../../library/seed/src/task/step/steps/interpro_domain_summary.py) (119 lines)  
**Trust level: C — 专用测试引用 + 可编译路线**

## 1. 代码说明

Per-protein domain count, covered bases and best

> InterPro domain

关键符号：

- `class InterproDomainSummaryStep (line 15)`

协议：v3 / revision `3.7`；输出参数 `output`。

### 输入与输出

- 输入 1: ndim=2, numeric=True, dims=(hit_dim, field_dim), info=(missing_code)
- 输出: mode=declare, schema={"ndim": 2, "numeric": true, "info_open": true, "axis_info_open": true, "info": {"missing_code": {"type": ["number", "null"]}}}

### 参数

| 参数 | 默认值 | 含义/约束 |
| --- | --- | --- |
| `output` | `interpro_domain_summary` | Output name |
| `hit_dim` | `hit` | Hit axis |
| `field_dim` | `field` | Field axis |

## 2. 用途与解释

Per-protein domain count, covered bases and best e-value.

## 3. 正确性依据

**结论：C 级。** 路线已编译进 79 条内置路线，并有专用测试引用；没有记录为本算子单独执行过真实数据。

| 层 | 状态 | 证据 |
| --- | --- | --- |
| L1 契约/清单 | PASS | verification/operator-audit-8.0.1/operator_table.csv |
| L2 单元/oracle | UNIT | tests/test_annotation_panel_b61.py |
| L3 真实执行 | ROUTE | operator_table.csv:generated_route |
| L4 资源 | ESTIMATE | definition resources.estimate=estimate_memory |
| L5 应用安装 | INSTALL | 8.0.1 bundle install (3.1.9/4.0.0) |

### 这个证据证明什么、不证明什么

- 证明：契约可解析、输入输出维度一致；有执行记录时，真实数据能跑到 `Task finished` 并产生可校验产物。
- 不证明：该算子在该数据集上的生物学结论正确；统计假设是否成立仍需使用者判断。
- 注意：该算子没有独立数值 oracle， correctness 仅到“契约/测试/执行”层级。

## 4. 限制与失败模式

The operator is a table summary. It does not validate gene models, resolve
isoforms, or replace a full annotation-quality pipeline.

## 5. 复现

```bash
cd /home/gavin/Operon-7015-native
python -m operon registry check --json
grep '^interpro_domain_summary,' verification/coverage-8.0.1/operator_coverage.csv
```

未补齐证据：`L4_MEASURED`。

---

由 `scripts/build_operator_trust_docs.py` 生成；审计基线 8.0.1。
