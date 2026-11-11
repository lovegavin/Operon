# Centered log-ratio transform (`metagenomics_clr`)

**Category:** Metagenomics  
**Entry point:** `src.task.step.steps.metagenomics_clr:MetagenomicsClrStep`  
**Source:** [`library/seed/src/task/step/steps/metagenomics_clr.py`](../../library/seed/src/task/step/steps/metagenomics_clr.py) (110 lines)
**Trust level: C — 专用测试引用 + 可编译路线**

## 1. 代码说明

Centered log-ratio transform of a non-negative count table with a

> Centered log-ratio transform of a non-negative count table with a

关键符号：

- `def field_index() (line 12)`
- `def numeric_column() (line 19)`
- `def form_labels() (line 23)`
- `def result() (line 28)`
- `class MetagenomicsClrStep (line 35)`

协议：v3 / revision `3.7`；输出参数 `output`。

### 输入与输出

- 输入 1: ndim=2, numeric=True, dims=(row_dim, field_dim), info=(—)
- 输出: mode=declare, schema={"ndim": 2, "numeric": true, "info_open": true, "axis_info_open": true}

### 参数

| 参数 | 默认值 | 含义/约束 |
| --- | --- | --- |
| `row_dim` | `sample` | 行维度 |
| `field_dim` | `feature` | 字段维度 |
| `pseudocount` | `0.5` | 伪计数; min 1e-09; advanced |
| `output` | `clr` | 输出名称 |

## 2. 用途与解释

Centered log-ratio transform of a non-negative count table with a pseudocount.

## 3. 正确性依据

**结论：C 级。** 路线已编译进 79 条内置路线，并有专用测试引用；没有记录为本算子单独执行过真实数据。

| 层 | 状态 | 证据 |
| --- | --- | --- |
| L1 契约/清单 | PASS | verification/operator-audit-8.0.1/operator_table.csv |
| L2 单元/oracle | UNIT | tests/test_b76.py |
| L3 真实执行 | ROUTE | operator_table.csv:builtin_route |
| L4 资源 | ESTIMATE | definition resources.estimate=estimate_memory |
| L5 应用安装 | ROUTE | library/seed/routes/structure_rg_metagenome/task.yaml |

### 这个证据证明什么、不证明什么

- 证明：契约可解析、输入输出维度一致；有执行记录时，真实数据能跑到 `Task finished` 并产生可校验产物。
- 不证明：该算子在该数据集上的生物学结论正确；统计假设是否成立仍需使用者判断。
- 注意：该算子没有独立数值 oracle， correctness 仅到“契约/测试/执行”层级。

## 4. 限制与失败模式

The operator accepts numeric tables only.  Negative values are rejected, and
the caller is responsible for any upstream filtering or normalisation.

## 5. 复现

```bash
cd /path/to/Operon-worktree
python -m operon registry check --json
grep '^metagenomics_clr,' verification/coverage-8.0.1/operator_coverage.csv
```

未补齐证据：`L4_MEASURED`。

---

由 `scripts/build_operator_trust_docs.py` 生成；审计基线 8.0.1。
