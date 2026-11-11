# Peptide spectrum annotation (`peptide_spectrum_annotation`)

**Category:** Proteomics MS  
**Entry point:** `src.task.step.steps.peptide_spectrum_annotation:PeptideSpectrumAnnotationStep`  
**Source:** [`library/seed/src/task/step/steps/peptide_spectrum_annotation.py`](../../library/seed/src/task/step/steps/peptide_spectrum_annotation.py) (136 lines)
**Trust level: C — 专用测试引用 + 可编译路线**

## 1. 代码说明

Theoretical b/y ion matching and coverage for each

> Peptide spectrum

关键符号：

- `class PeptideSpectrumAnnotationStep (line 11)`

协议：v3 / revision `3.7`；输出参数 `output`。

### 输入与输出

- 输入 1: ndim=?, numeric=?, dims=(peptide_dim, field_dim), info=(—)
- 输入 2: ndim=?, numeric=?, dims=(peak_dim, field_dim), info=(—)
- 输出: mode=declare, schema={"ndim": 2, "numeric": true, "info_open": true}

### 参数

| 参数 | 默认值 | 含义/约束 |
| --- | --- | --- |
| `output` | `output` | Output name |
| `peptide_dim` | `peptide` | peptide axis |
| `field_dim` | `field` | field axis |
| `peak_dim` | `peak` | peak axis |
| `tolerance_da` | `0.02` | Fragment tolerance (Da); min 0.0; max 1.0 |

## 2. 用途与解释

Theoretical b/y ion matching and coverage for each peptide.

## 3. 正确性依据

**结论：C 级。** 路线已编译进 79 条内置路线，并有专用测试引用；没有记录为本算子单独执行过真实数据。

| 层 | 状态 | 证据 |
| --- | --- | --- |
| L1 契约/清单 | PASS | verification/operator-audit-8.0.1/operator_table.csv |
| L2 单元/oracle | UNIT | tests/test_proteomics_panel_b66.py |
| L3 真实执行 | ROUTE | operator_table.csv:generated_route |
| L4 资源 | ESTIMATE | definition resources.estimate=estimate_memory |
| L5 应用安装 | INSTALL | 8.0.1 bundle install (3.1.9/4.0.0) |

### 这个证据证明什么、不证明什么

- 证明：契约可解析、输入输出维度一致；有执行记录时，真实数据能跑到 `Task finished` 并产生可校验产物。
- 不证明：该算子在该数据集上的生物学结论正确；统计假设是否成立仍需使用者判断。
- 注意：该算子没有独立数值 oracle， correctness 仅到“契约/测试/执行”层级。

## 4. 限制与失败模式

Synthetic test data only; no retention time, charge state or noise model is
inferred. The implementation reports the stated algebra, not a biological
identification.

## 5. 复现

```bash
cd /path/to/Operon-worktree
python -m operon registry check --json
grep '^peptide_spectrum_annotation,' verification/coverage-8.0.1/operator_coverage.csv
```

未补齐证据：`L4_MEASURED`。

---

由 `scripts/build_operator_trust_docs.py` 生成；审计基线 8.0.1。
