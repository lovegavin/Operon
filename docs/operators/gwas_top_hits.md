# GWAS top hits (`gwas_top_hits`)

**Category:** Statistics  
**Entry point:** `src.task.step.steps.gwas_top_hits:GwasTopHitsStep`  
**Source:** [`library/seed/src/task/step/steps/gwas_top_hits.py`](../../library/seed/src/task/step/steps/gwas_top_hits.py) (110 lines)  
**Trust level: C — 专用测试引用 + 可编译路线**

## 1. 代码说明

Select independent lead variants below a p-value threshold using distance-based

> Lead variants from a GWAS association table with distance-based

关键符号：

- `class GwasTopHitsStep (line 16)`

协议：v3 / revision `3.7`；输出参数 `output`。

### 输入与输出

- 输入 1: ndim=2, numeric=True, dims=(variant_dim, statistic_dim), info=(—)
- 输出: mode=declare, schema={"ndim": 2, "numeric": true, "info_open": true, "axis_info_open": true}

### 参数

| 参数 | 默认值 | 含义/约束 |
| --- | --- | --- |
| `threshold` | `5e-08` | P-value threshold for lead; min 0.0; max 1.0 |
| `clump_distance` | `1000000` | Distance in bases used to clump nearby; min 0 |
| `max_hits` | `0` | Maximum number of lead variants (0 means; min 0 |
| `variant_dim` | `variant` | Dimension that labels association |
| `statistic_dim` | `statistic` | Dimension that labels association |
| `output` | `hits` | Output parameter |

## 2. 用途与解释

Lead variants from a GWAS association table with distance-based clumping.

## 3. 正确性依据

**结论：C 级。** 路线已编译进 79 条内置路线，并有专用测试引用；没有记录为本算子单独执行过真实数据。

| 层 | 状态 | 证据 |
| --- | --- | --- |
| L1 契约/清单 | PASS | verification/operator-audit-8.0.1/operator_table.csv |
| L2 单元/oracle | UNIT | tests/test_extension405.py |
| L3 真实执行 | ROUTE | operator_table.csv:builtin_route |
| L4 资源 | SKIP | no memory estimate |
| L5 应用安装 | ROUTE | library/seed/routes/gwas_association/task.yaml |

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
grep '^gwas_top_hits,' verification/coverage-8.0.1/operator_coverage.csv
```

算子手册中的示例：

```text
Use the registry to discover compatible Readers and validate a complete workflow
before execution. This generated page does not claim an executable scientific
example. Add a tested example and replace this generated page with authored
guidance when extending this operator.
```

未补齐证据：`L4`。

---

由 `scripts/build_operator_trust_docs.py` 生成；审计基线 8.0.1。
