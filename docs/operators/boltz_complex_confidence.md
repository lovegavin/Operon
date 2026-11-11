# Boltz complex prediction confidence (`boltz_complex_confidence`)

**Category:** Machine Learning  
**Entry point:** `src.task.step.steps.boltz_complex_confidence:BoltzComplexConfidenceStep`  
**Source:** [`library/seed/src/task/step/steps/boltz_complex_confidence.py`](../../library/seed/src/task/step/steps/boltz_complex_confidence.py) (287 lines)
**Trust level: D — 专用测试引用（无真实执行）**

## 1. 代码说明

Predict a two-chain protein complex with Boltz and report per-residue confidence plus interface

> boltz_complex_confidence: Boltz-2 complex prediction with confidence

关键符号：

- `def write_yaml() (line 32)`
- `def complex_yaml() (line 38)`
- `def boltz_command() (line 50)`
- `def run_boltz() (line 79)`
- `def find_outputs() (line 96)`
- `def parse_confidence() (line 109)`
- `def interface_rows() (line 127)`
- `def plddt_from_pdb() (line 149)`

协议：v3 / revision `3.7`；输出参数 `output`。

### 输入与输出

- 输入 1: ndim=2, numeric=True, dims=(sequence_dim, position_dim), info=(—)
- 输出: mode=declare, schema={"ndim": 2, "numeric": true, "info_open": true, "axis_info_open": true}

### 参数

| 参数 | 默认值 | 含义/约束 |
| --- | --- | --- |
| `sequence_dim` | `sequence` | 序列维度 |
| `position_dim` | `position` | 位点维度 |
| `boltz_path` | `boltz` | Boltz 可执行文件 |
| `cache_dir` | `` | 权重缓存目录 |
| `model` | `boltz2` | 模型; choices: boltz1, boltz2 |
| `device` | `cpu` | 设备; choices: cpu, cuda |
| `sampling_steps` | `50` | 采样步数; min 10; max 500 |
| `diffusion_samples` | `1` | 扩散样本数; min 1; max 8 |
| `interface_cutoff` | `8.0` | 界面距离阈值 (Å); min 3.0; max 20.0 |
| `timeout_seconds` | `3600` | 超时 (秒); min 60; max 7200 |
| `report_dim` | `residue` | 输出维度 |
| `output` | `confidence` | 输出参数名 |

## 2. 用途与解释

boltz_complex_confidence: Boltz-2 complex prediction with confidence parsing.

## 3. 正确性依据

**结论：D 级。** 只有专用/冒烟测试引用；没有记录真实执行。

| 层 | 状态 | 证据 |
| --- | --- | --- |
| L1 契约/清单 | PASS | verification/operator-audit-8.0.1/operator_table.csv |
| L2 单元/oracle | UNIT | tests/test_extension345.py |
| L3 真实执行 | SKIP | no route in audit, archive, or srv evidence |
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
grep '^boltz_complex_confidence,' verification/coverage-8.0.1/operator_coverage.csv
```

算子手册中的示例：

```text
Use the registry to discover compatible Readers and validate a complete workflow
before execution. This generated page does not claim an executable scientific
example. Add a tested example and replace this generated page with authored
guidance when extending this operator.
```

未补齐证据：`L3,L4_MEASURED`。

---

由 `scripts/build_operator_trust_docs.py` 生成；审计基线 8.0.1。
