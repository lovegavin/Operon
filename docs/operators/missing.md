# 缺失值过滤 (`missing`)

**Category:** 质量控制  
**Entry point:** `src.task.step.steps.missing:MissingStep`  
**Source:** [`library/seed/src/task/step/steps/missing.py`](../../library/seed/src/task/step/steps/missing.py) (128 lines)  
**Trust level: C — 专用测试引用 + 可编译路线**

## 1. 代码说明

按指定维度过滤缺失比例过高的样本或特征。

> Missingness filter along one

关键符号：

- `class MissingStep (line 13)`

协议：v3 / revision `3.7`；输出参数 `output`。

### 输入与输出

- 输入 1: ndim=?, numeric=True, dims=(dim), info=(missing_code)
- 输出: mode=subset, schema={}

### 参数

| 参数 | 默认值 | 含义/约束 |
| --- | --- | --- |
| `dim` | `` | 过滤维度 |
| `threshold` | `0.1` | 最大缺失比例; min 0; max 1 |

## 2. 用途与解释

Missingness filter along one dimension.

Filter positions along one dimension by missing rate.

Params:
dim       : dimension to filter on
threshold : maximum allowed missing rate
output    : context key for the result (default: step name)

## 3. 正确性依据

**结论：C 级。** 路线已编译进 79 条内置路线，并有专用测试引用；没有记录为本算子单独执行过真实数据。

| 层 | 状态 | 证据 |
| --- | --- | --- |
| L1 契约/清单 | PASS | verification/operator-audit-8.0.1/operator_table.csv |
| L2 单元/oracle | UNIT | tests/test_builtin_pins.py,test_candidate_delivery.py,test_conditional_logistic.py,test_dependencies.py,test_dependency_contract.py,test_desktop.py,test_execution_plan.py,test_extension102.py,test_extension110.py,test_extension115.py,test_extension120.py,test_extension121.py,test_extension125.py,test_extension132.py,test_extension138.py,test_extension139.py,test_extension158.py,test_extension164.py,test_extension170.py,test_extension173.py,test_extension175.py,test_extension176.py,test_extension177.py,test_extension179.py,test_extension180.py,test_extension182.py,test_extension183.py,test_extension185.py,test_extension19.py,test_extension190.py,test_extension22.py,test_extension225.py,test_extension23.py,test_extension233.py,test_extension237.py,test_extension24.py,test_extension241.py,test_extension244.py,test_extension247.py,test_extension25.py,test_extension251.py,test_extension263.py,test_extension266.py,test_extension268.py,test_extension27.py,test_extension300.py,test_extension301.py,test_extension302.py,test_extension309.py,test_extension31.py,test_extension310.py,test_extension311.py,test_extension312.py,test_extension315.py,test_extension318.py,test_extension319.py,test_extension320.py,test_extension321.py,test_extension322.py,test_extension323.py,test_extension324.py,test_extension326.py,test_extension330.py,test_extension341.py,test_extension347.py,test_extension350.py,test_extension351.py,test_extension352.py,test_extension353.py,test_extension354.py,test_extension355.py,test_extension356.py,test_extension366.py,test_extension369.py,test_extension378.py,test_extension383.py,test_extension386.py,test_extension388.py,test_extension39.py,test_extension393.py,test_extension396.py,test_extension397.py,test_extension40.py,test_extension401.py,test_extension402.py,test_extension405.py,test_extension407.py,test_extension41.py,test_extension410.py,test_extension43.py,test_extension49.py,test_extension50.py,test_extension51.py,test_extension58.py,test_extension61.py,test_extension67.py,test_extension81.py,test_extension82.py,test_extension87.py,test_extension89.py,test_extension92.py,test_figure_contract.py,test_headless_application.py,test_isolation.py,test_job_admission.py,test_localization_v35.py,test_packages.py,test_preferences.py,test_protocol_v2.py,test_r_oracles.py,test_r_oracles12.py,test_r_oracles3.py,test_r_oracles4.py,test_r_oracles49.py,test_r_oracles7.py,test_r_oracles8.py,test_r_runtime.py,test_reader_selection.py,test_readers_sop.py,test_registry_maintenance.py,test_remote_handshake.py,test_remote_install_readiness.py,test_remote_provision.py,test_result_viewers.py,test_run_logging.py,test_script_operators_v3.py,test_server_cli.py,test_studio.py,test_task_preflight.py,test_vcf_windows.py,test_workflow_import_errors.py |
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
grep '^missing,' verification/coverage-8.0.1/operator_coverage.csv
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
