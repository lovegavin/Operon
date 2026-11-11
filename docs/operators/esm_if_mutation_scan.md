# ESM-IF Mutation Scan (`esm_if_mutation_scan`)

**Category:** Machine Learning  
**Entry point:** `src.task.step.steps.esm_if_mutation_scan:EsmIfMutationScanStep`  
**Source:** [`library/seed/src/task/step/steps/esm_if_mutation_scan.py`](../../library/seed/src/task/step/steps/esm_if_mutation_scan.py) (241 lines)  
**Trust level: B — 真实执行（本地或 srv）**

## 1. 代码说明

Score every single-residue substitution of a protein chain with the official ESM-IF1 inverse-folding model and report the log-likelihood ratio of each mutant against the native

> Scan every single-residue substitution of a backbone chain with

关键符号：

- `def parse_positions() (line 18)`
- `def context_log_probs() (line 50)`
- `def mutation_rows() (line 69)`
- `class EsmIfMutationScanStep (line 98)`

协议：v3 / revision `3.7`；输出参数 `output`。

### 输入与输出

- 输入 1: ndim=2, numeric=True, dims=(atom_dim, field_dim), info=(—)
- 输出: mode=declare, schema={"ndim": 2, "numeric": true, "info_open": true, "axis_info_open": true}

### 参数

| 参数 | 默认值 | 含义/约束 |
| --- | --- | --- |
| `atom_dim` | `atom` | 原子维度 |
| `field_dim` | `field` | 字段维度 |
| `chain` | `A` | 扫描链 |
| `model_path` | `` | ESM-IF 权重路径 |
| `positions` | `` | 扫描位点; advanced |
| `max_positions` | `256` | 最大位点数; min 1; advanced |
| `output` | `mutations` | 输出名称; advanced |

## 2. 用途与解释

Scan every single-residue substitution of a backbone chain with ESM-IF1.

Score all single-residue substitutions of a backbone chain with ESM-IF1.

## 3. 正确性依据

**结论：B 级。** 服务器真实运行通过（69.1466 s），1 个步骤产物，首个 sha256 ed718b712a631d70…。

| 层 | 状态 | 证据 |
| --- | --- | --- |
| L1 契约/清单 | PASS | verification/operator-audit-8.0.1/operator_table.csv |
| L2 单元/oracle | UNIT | tests/test_extension139.py,test_extension144.py,test_extension359.py |
| L3 真实执行 | EXECUTED_SRV | srv:/public/home/lihj/operon715/cov_ml2/esm_if_mutation_scan/output/run_summary.json |
| L4 资源 | ESTIMATE | definition resources.estimate=estimate_memory |
| L5 应用安装 | INSTALL | 8.0.1 bundle install (3.1.9/4.0.0) |

服务器执行细节：

- 状态：complete，总耗时 69.1466 s，步骤 1。
- 路线：`/public/home/lihj/operon715/cov_ml2/esm_if_mutation_scan`；run_id `20261110T143655-5b5afcbb9868`。

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
grep '^esm_if_mutation_scan,' verification/coverage-8.0.1/operator_coverage.csv
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
