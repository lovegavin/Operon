# Join (`join`)

**Category:** 数据整理  
**Entry point:** `src.task.step.steps.join:JoinStep`  
**Source:** [`library/seed/src/task/step/steps/join.py`](../../library/seed/src/task/step/steps/join.py) (300 lines)  
**Trust level: C — 专用测试引用 + 可编译路线**

## 1. 代码说明

Join two forms along a shared dim by

> Join two forms along a shared dim by label. Attaches selected columns from a "metadata" form to a "data" form. Both forms must have the shared dim as their first axis. The columns of the metadata form are appended to the data form's second axis, so the output is a wider form whose labels combine the two. This is the natural way to bring grouping columns next to the values they describe, e.g. to color a scatter plot, to split a barplot, or to feed a violin plot. Alignment --------- inner keep rows whose label is present in both forms left keep rows whose label is present in the data form,…

关键符号：

- `class JoinStep (line 53)`

协议：v3 / revision `3.7`；输出参数 `output`。

### 输入与输出

- 输入 1: ndim=2, numeric=True, dims=(dim), info=(—)
- 输入 2: ndim=2, numeric=True, dims=(dim), info=(—)
- 输出: mode=project, schema={}

### 参数

| 参数 | 默认值 | 含义/约束 |
| --- | --- | --- |
| `dim` | `` | — |
| `columns` | `all` | — |
| `how` | `inner` | choices: inner, left |
| `prefix` | `` | — |

## 2. 用途与解释

Join two forms along a shared dim by label.

Attaches selected columns from a "metadata" form to a "data" form.
Both forms must have the shared dim as their first axis. The
columns of the metadata form are appended to the data form's second
axis, so the output is a wider form whose labels combine the two.

This is the natural way to bring grouping columns next to the
values they describe, e.g. to color a scatter plot, to split a
barplot, or to feed a violin plot.

Alignment
---------
inner   keep rows whose label is present in both forms
left    keep rows whose label is present in the data form,
filling meta cells with NaN when the row is missing
from the metadata form

Both forms must be 2D with the shared dim as the first axis. To use
a form whose shared dim is second, transpose it first.

Output
------
dims    = [shared_dim, <data_other_dim>]
labels  = {shared_dim:  <common row labels

## 3. 正确性依据

**结论：C 级。** 路线已编译进 79 条内置路线，并有专用测试引用；没有记录为本算子单独执行过真实数据。

| 层 | 状态 | 证据 |
| --- | --- | --- |
| L1 契约/清单 | PASS | verification/operator-audit-8.0.1/operator_table.csv |
| L2 单元/oracle | UNIT | tests/test_agent_transports.py,test_audit_fixes.py,test_builtin_pins.py,test_compressed_inputs.py,test_crlf.py,test_dependencies.py,test_dependency_processes.py,test_docs_links.py,test_execution_plan.py,test_extension11.py,test_extension110.py,test_extension112.py,test_extension113.py,test_extension116.py,test_extension117.py,test_extension121.py,test_extension124.py,test_extension125.py,test_extension126.py,test_extension127.py,test_extension129.py,test_extension130.py,test_extension132.py,test_extension135.py,test_extension142.py,test_extension144.py,test_extension149.py,test_extension151.py,test_extension154.py,test_extension157.py,test_extension161.py,test_extension164.py,test_extension170.py,test_extension171.py,test_extension173.py,test_extension176.py,test_extension177.py,test_extension179.py,test_extension180.py,test_extension181.py,test_extension182.py,test_extension183.py,test_extension184.py,test_extension185.py,test_extension189.py,test_extension194.py,test_extension202.py,test_extension218.py,test_extension225.py,test_extension232.py,test_extension233.py,test_extension234.py,test_extension237.py,test_extension244.py,test_extension246.py,test_extension247.py,test_extension252.py,test_extension259.py,test_extension262.py,test_extension264.py,test_extension266.py,test_extension268.py,test_extension271.py,test_extension278.py,test_extension288.py,test_extension293.py,test_extension295.py,test_extension296.py,test_extension297.py,test_extension298.py,test_extension299.py,test_extension304.py,test_extension305.py,test_extension308.py,test_extension313.py,test_extension314.py,test_extension318.py,test_extension319.py,test_extension320.py,test_extension321.py,test_extension323.py,test_extension324.py,test_extension327.py,test_extension328.py,test_extension329.py,test_extension330.py,test_extension331.py,test_extension332.py,test_extension333.py,test_extension334.py,test_extension335.py,test_extension338.py,test_extension339.py,test_extension341.py,test_extension342.py,test_extension354.py,test_extension356.py,test_extension357.py,test_extension363.py,test_extension364.py,test_extension365.py,test_extension366.py,test_extension373.py,test_extension376.py,test_extension382.py,test_extension387.py,test_extension389.py,test_extension390.py,test_extension393.py,test_extension395.py,test_extension398.py,test_extension400.py,test_extension402.py,test_extension405.py,test_extension406.py,test_extension409.py,test_extension8.py,test_extension92.py,test_extension93.py,test_genotype_readers_sop.py,test_headless_application.py,test_hic_real.py,test_library_release.py,test_memory_system.py,test_microbiome.py,test_plink2_native.py,test_profile.py,test_r_oracles12.py,test_r_oracles52.py,test_r_oracles70.py,test_r_oracles79.py,test_r_oracles86.py,test_r_oracles87.py,test_r_oracles88.py,test_r_oracles89.py,test_r_oracles90.py,test_r_oracles93.py,test_r_oracles94.py,test_r_oracles95.py,test_r_oracles96.py,test_r_oracles97.py,test_r_oracles98.py,test_readers_sop.py,test_remote.py,test_remote_handshake.py,test_remote_installation.py,test_remote_provision.py,test_remote_transfer.py,test_resource_downloads.py,test_route_parameters.py,test_run_logging.py,test_service_long_paths.py,test_studio.py,test_vcf_windows.py |
| L3 真实执行 | ROUTE | operator_table.csv:builtin_route |
| L4 资源 | ESTIMATE | definition resources.estimate=estimate_memory |
| L5 应用安装 | ROUTE | library/seed/routes/vhh_cdr_quantification/task.yaml |

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
grep '^join,' verification/coverage-8.0.1/operator_coverage.csv
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
