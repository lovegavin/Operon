# Random Forest classifier (`random_forest_classifier`)

**Category:** Machine Learning  
**Entry point:** `src.task.step.steps.random_forest_classifier:RandomForestClassifierStep`  
**Source:** [`library/seed/src/task/step/steps/random_forest_classifier.py`](../../library/seed/src/task/step/steps/random_forest_classifier.py) (59 lines)  
**Trust level: E — 仅静态契约（尚无行为证据）**

## 1. 代码说明

Random Forest classifier：接收 2 个输入，输出

> Random Forest

关键符号：

- `class RandomForestClassifierStep (line 6)`

协议：v3 / revision `3.7`；输出参数 `output`。

### 输入与输出

- 输入 1: ndim=2, numeric=True, dims=(sample_dim, feature_dim), info=(—)
- 输入 2: ndim=2, numeric=True, dims=(sample_dim, label_dim), info=(—)
- 输出: mode=declare, schema={"ndim": 2, "numeric": true, "info_open": true, "axis_info_open": true}

### 参数

| 参数 | 默认值 | 含义/约束 |
| --- | --- | --- |
| `sample_dim` | `sample` | 样本维度 |
| `feature_dim` | `feature` | 特征维度 |
| `label_dim` | `label` | 标签维度 |
| `target_label` | `` | 目标字段 |
| `test_size` | `0.25` | 测试集比例; min 0.05; max 0.5; advanced |
| `cv_folds` | `5` | 交叉验证折数; min 2; advanced |
| `random_state` | `0` | 随机种子; advanced |
| `scale` | `True` | 标准化 |
| `output` | `` | 输出名称 |
| `valid_labels` | `` | 有效标签; advanced |
| `n_estimators` | `100` | 树数量; min 1; advanced |
| `max_depth` | `None` | 最大深度; advanced |
| `class_weight` | `None` | 类别权重; choices: balanced, None; advanced |

## 2. 用途与解释

Random Forest classifier.

## 3. 正确性依据

**结论：E 级。** 目前只有静态契约，没有行为证据；不要把它当成已验证算子。

| 层 | 状态 | 证据 |
| --- | --- | --- |
| L1 契约/清单 | PASS | verification/operator-audit-8.0.1/operator_table.csv |
| L2 单元/oracle | SKIP | operator_table.csv:SKIP_DOMAIN |
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
cd /home/gavin/Operon-7015-native
python -m operon registry check --json
grep '^random_forest_classifier,' verification/coverage-8.0.1/operator_coverage.csv
```

算子手册中的示例：

```text
Use the registry to discover compatible Readers and validate a complete workflow
before execution. This generated page does not claim an executable scientific
example. Add a tested example and replace this generated page with authored
guidance when extending this operator.
```

未补齐证据：`L2,L4_MEASURED`。

---

由 `scripts/build_operator_trust_docs.py` 生成；审计基线 8.0.1。
