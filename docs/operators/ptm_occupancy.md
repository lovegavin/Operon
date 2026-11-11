# PTM site occupancy (`ptm_occupancy`)

**Category:** Proteomics  
**Entry point:** `src.task.step.steps.ptm_occupancy:PtmOccupancyStep`  
**Source:** [`library/seed/src/task/step/steps/ptm_occupancy.py`](../../library/seed/src/task/step/steps/ptm_occupancy.py) (130 lines)
**Trust level: C — 专用测试引用 + 可编译路线**

## 1. 代码说明

Site occupancy computed from modified and unmodified peptide

> Site occupancy computed from modified and unmodified peptide

关键符号：

- `def field_index() (line 14)`
- `def numeric_column() (line 21)`
- `def strings() (line 45)`
- `def form_labels() (line 49)`
- `def result() (line 54)`
- `class PtmOccupancyStep (line 61)`

协议：v3 / revision `3.7`；输出参数 `output`。

### 输入与输出

- 输入 1: ndim=2, numeric=True, dims=(row_dim, field_dim), info=(—)
- 输出: mode=declare, schema={"ndim": 2, "numeric": true, "info_open": true, "axis_info_open": true}

### 参数

| 参数 | 默认值 | 含义/约束 |
| --- | --- | --- |
| `row_dim` | `site` | 行维度 |
| `field_dim` | `field` | 字段维度 |
| `output` | `occupancy` | 输出名称 |

## 2. 用途与解释

Site occupancy computed from modified and unmodified peptide intensities.

## 3. 正确性依据

**结论：C 级。** 路线已编译进 79 条内置路线，并有专用测试引用；没有记录为本算子单独执行过真实数据。

| 层 | 状态 | 证据 |
| --- | --- | --- |
| L1 契约/清单 | PASS | verification/operator-audit-8.0.1/operator_table.csv |
| L2 单元/oracle | UNIT | tests/test_b77.py |
| L3 真实执行 | ROUTE | operator_table.csv:builtin_route |
| L4 资源 | ESTIMATE | definition resources.estimate=estimate_memory |
| L5 应用安装 | ROUTE | library/seed/routes/proteomics_ibaq_cai_ptm/task.yaml |

### 这个证据证明什么、不证明什么

- 证明：契约可解析、输入输出维度一致；有执行记录时，真实数据能跑到 `Task finished` 并产生可校验产物。
- 不证明：该算子在该数据集上的生物学结论正确；统计假设是否成立仍需使用者判断。
- 注意：该算子没有独立数值 oracle， correctness 仅到“契约/测试/执行”层级。

## 4. 限制与失败模式

Values must be non-negative where they represent intensities.  Missing or
zero denominators produce `nan` rather than an error so downstream filtering
can decide how to treat them.

## 5. 复现

```bash
cd /path/to/Operon-worktree
python -m operon registry check --json
grep '^ptm_occupancy,' verification/coverage-8.0.1/operator_coverage.csv
```

未补齐证据：`L4_MEASURED`。

---

由 `scripts/build_operator_trust_docs.py` 生成；审计基线 8.0.1。
