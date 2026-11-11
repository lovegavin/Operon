# pseudotime_dpt (`pseudotime_dpt`)

**Category:** Omics  
**Entry point:** `src.task.step.steps.pseudotime_dpt:PseudotimeDptStep`  
**Source:** [`library/seed/src/task/step/steps/pseudotime_dpt.py`](../../library/seed/src/task/step/steps/pseudotime_dpt.py) (185 lines)
**Trust level: C — 专用测试引用 + 可编译路线**

## 1. 代码说明

Diffusion pseudotime over a low-dimensional cell

> Diffusion pseudotime over a low-dimensional embedding. Input: 2D numeric Form [cell, component] (for example PCA scores). Output: 2D Form [cell, pseudotime] with one column in [0, 1]. The implementation builds an adaptive Gaussian kNN graph, symmetrises it and uses the leading diffusion components of the random-walk matrix, weighted by lambda / (1 - lambda) as in Haghverdi et al. (2016), Eq. 15. Pseudotime is the Euclidean distance to the root cell in that diffusion space, normalised by its

关键符号：

- `def diffusion_pseudotime() (line 28)`
- `class PseudotimeDptStep (line 75)`

协议：v3 / revision `3.7`；输出参数 `output`。

### 输入与输出

- 输入 1: ndim=2, numeric=True, dims=(cell, component), info=(—)
- 输出: mode=declare, schema={"kind": "form", "numeric": true, "ndim": 2, "dims": ["cell", "pseudotime"], "info_open": true, "axis_info_open": true}

### 参数

| 参数 | 默认值 | 含义/约束 |
| --- | --- | --- |
| `root_cell` | `` | Cell label used as the pseudotime root; the first cell is used when |
| `n_neighbors` | `15` | Number of nearest neighbours in the diffusion; min 2 |
| `n_dcs` | `10` | Number of diffusion components used for the; min 1 |
| `output` | `` | Output port name; defaults to the operator |

## 2. 用途与解释

Diffusion pseudotime over a low-dimensional embedding.

Input: 2D numeric Form [cell, component] (for example PCA scores).
Output: 2D Form [cell, pseudotime] with one column in [0, 1].

The implementation builds an adaptive Gaussian kNN graph, symmetrises it and
uses the leading diffusion components of the random-walk matrix, weighted by
lambda / (1 - lambda) as in Haghverdi et al. (2016), Eq. 15. Pseudotime is the
Euclidean distance to the root cell in that diffusion space, normalised by its
maximum.

Diffusion pseudotime from a cell-by-component embedding.

## 3. 正确性依据

**结论：C 级。** 路线已编译进 79 条内置路线，并有专用测试引用；没有记录为本算子单独执行过真实数据。

| 层 | 状态 | 证据 |
| --- | --- | --- |
| L1 契约/清单 | PASS | verification/operator-audit-8.0.1/operator_table.csv |
| L2 单元/oracle | UNIT | tests/test_extension366.py |
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
cd /path/to/Operon-worktree
python -m operon registry check --json
grep '^pseudotime_dpt,' verification/coverage-8.0.1/operator_coverage.csv
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
