# dN/dS ratio (Nei-Gojobori) (`sequence_dnds`)

**Category:** Sequence  
**Entry point:** `src.task.step.steps.sequence_dnds:SequenceDndsStep`  
**Source:** [`library/seed/src/task/step/steps/sequence_dnds.py`](../../library/seed/src/task/step/steps/sequence_dnds.py) (103 lines)
**Trust level: B — 真实执行（本地或 srv）**

## 1. 代码说明

dN/dS ratio

> dN/dS ratio

关键符号：

- `class SequenceDndsStep (line 16)`

协议：v3 / revision `3.7`；输出参数 `output`。

### 输入与输出

- 输入 1: ndim=2, numeric=True, dims=(row_dim, field_dim), info=(—)
- 输出: mode=declare, schema={"ndim": 2, "numeric": true, "info_open": true, "axis_info_open": true}

### 参数

| 参数 | 默认值 | 含义/约束 |
| --- | --- | --- |
| `row_dim` | `row` | — |
| `field_dim` | `field` | — |
| `output` | `dnds` | — |

## 2. 用途与解释

Computes pairwise synonymous and non-synonymous substitution rates with the Nei-Gojobori site-counting method and Jukes-Cantor correction, reporting dN, dS and their ratio.

## 3. 正确性依据

**结论：B 级。** 真实运行通过（1.49 s），导出 None 行，产物 sha256 546682b43c26f92d…。

| 层 | 状态 | 证据 |
| --- | --- | --- |
| L1 契约/清单 | PASS | verification/operator-audit-8.0.1/operator_table.csv |
| L2 单元/oracle | UNIT | tests/test_b81.py |
| L3 真实执行 | EXECUTED | verification/coverage-8.0.1/routes/sequence_dnds |
| L4 资源 | ESTIMATE | definition resources.estimate=estimate_memory |
| L5 应用安装 | INSTALL | 8.0.1 bundle install (3.1.9/4.0.0) |

本次执行细节：

- 状态：PASS，耗时 1.49 s，导出 None 行。
- 归档路线：`/tmp/cov_sequence/sequence_dnds`。
- 命令：`python scripts/run.py /tmp/cov_sequence/sequence_dnds`。

### 这个证据证明什么、不证明什么

- 证明：契约可解析、输入输出维度一致；有执行记录时，真实数据能跑到 `Task finished` 并产生可校验产物。
- 不证明：该算子在该数据集上的生物学结论正确；统计假设是否成立仍需使用者判断。

## 4. 限制与失败模式

The implementation works on small alignments, treats stop codons as
non-synonymous and does not model gap characters.

## 5. 复现

```bash
cd /path/to/Operon-worktree
python -m operon registry check --json
grep '^sequence_dnds,' verification/coverage-8.0.1/operator_coverage.csv
```

未补齐证据：`L4_MEASURED`。

---

由 `scripts/build_operator_trust_docs.py` 生成；审计基线 8.0.1。
