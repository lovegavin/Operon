# RealNVP normalizing flow density (`normalizing_flow_density`)

**Category:** Machine Learning  
**Entry point:** `src.task.step.steps.normalizing_flow_density:NormalizingFlowDensityStep`  
**Source:** [`library/seed/src/task/step/steps/normalizing_flow_density.py`](../../library/seed/src/task/step/steps/normalizing_flow_density.py) (68 lines)  
**Trust level: B — 真实执行（本地或 srv）**

## 1. 代码说明

RealNVP affine-coupling flow trained by maximum likelihood on a 2-D table, reporting latent Gaussianity and

关键符号：

- `class NormalizingFlowDensityStep (line 6)`

协议：v3 / revision `3.7`；输出参数 `output`。

### 输入与输出

- 输入 1: ndim=2, numeric=True, dims=(row_dim, field_dim), info=(—)
- 输出: mode=declare, schema={"ndim": 2, "numeric": true, "info_open": true, "axis_info_open": true}

### 参数

| 参数 | 默认值 | 含义/约束 |
| --- | --- | --- |
| `row_dim` | `row` | — |
| `field_dim` | `field` | — |
| `output` | `` | — |
| `layers` | `2` | — |
| `hidden` | `8` | — |
| `epochs` | `300` | — |
| `learning_rate` | `0.05` | — |
| `seed` | `0` | — |

## 2. 用途与解释

RealNVP affine-coupling flow trained by maximum likelihood on a 2-D table, reporting latent Gaussianity and parameters. The operator trains on the supplied table with a fixed seed and returns summary
statistics on a single output row.

## 3. 正确性依据

**结论：B 级。** 真实运行通过（4.83 s），导出 None 行，产物 sha256 2925868038cd8d9b…。

| 层 | 状态 | 证据 |
| --- | --- | --- |
| L1 契约/清单 | PASS | verification/operator-audit-8.0.1/operator_table.csv |
| L2 单元/oracle | UNIT | tests/test_b89.py |
| L3 真实执行 | EXECUTED | verification/coverage-8.0.1/routes/normalizing_flow_density |
| L4 资源 | ESTIMATE | definition resources.estimate=estimate_memory |
| L5 应用安装 | INSTALL | 8.0.1 bundle install (3.1.9/4.0.0) |

本次执行细节：

- 状态：PASS，耗时 4.83 s，导出 None 行。
- 归档路线：`/tmp/cov_mltab/normalizing_flow_density`。
- 命令：`cd /home/gavin/Operon && /home/gavin/bp-numpy21/bin/python scripts/run.py /tmp/cov_mltab/normalizing_flow_density`。

### 这个证据证明什么、不证明什么

- 证明：契约可解析、输入输出维度一致；有执行记录时，真实数据能跑到 `Task finished` 并产生可校验产物。
- 不证明：该算子在该数据集上的生物学结论正确；统计假设是否成立仍需使用者判断。

## 4. 限制与失败模式

相邻算子 Markdown 是参数约束与失败模式的权威说明；未找到单独的限制段。

## 5. 复现

```bash
cd /home/gavin/Operon-7015-native
python -m operon registry check --json
grep '^normalizing_flow_density,' verification/coverage-8.0.1/operator_coverage.csv
```

未补齐证据：`L4_MEASURED`。

---

由 `scripts/build_operator_trust_docs.py` 生成；审计基线 8.0.1。
