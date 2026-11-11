# 数据概览 (`describe`)

**Category:** 数据整理  
**Entry point:** `src.task.step.steps.describe:DescribeStep`  
**Source:** [`library/seed/src/task/step/steps/describe.py`](../../library/seed/src/task/step/steps/describe.py) (170 lines)
**Trust level: C — 专用测试引用 + 可编译路线**

## 1. 代码说明

查看形状、标签、缺失情况与全局统计。支持分块读取。

> Describe step: print and export a summary of an input

关键符号：

- `class DescribeStep (line 12)`

协议：v3 / revision `3.7`；输出参数 `None`。

### 输入与输出

- 输入 1: ndim=?, numeric=True, dims=(—), info=(—)
- 输出: mode=report, schema={}

## 2. 用途与解释

Describe step: print and export a summary of an input form.

Print a summary of one input form.

Params: none.

## 3. 正确性依据

**结论：C 级。** 路线已编译进 79 条内置路线，并有专用测试引用；没有记录为本算子单独执行过真实数据。

| 层 | 状态 | 证据 |
| --- | --- | --- |
| L1 契约/清单 | PASS | verification/operator-audit-8.0.1/operator_table.csv |
| L2 单元/oracle | UNIT | tests/test_agent_guidance.py,test_audit_fixes.py,test_builtin_pins.py,test_catalog_integrity.py,test_compressed_inputs.py,test_contracts.py,test_execution_service.py,test_export_contract.py,test_export_results.py,test_format_adaptation.py,test_headless_application.py,test_library_bundle.py,test_manifest_v3.py,test_memory_runtime.py,test_microbiome.py,test_operator_docs.py,test_packages.py,test_plugin_refresh.py,test_reader_selection.py,test_remote_transfer.py,test_route_parameters.py,test_routes.py,test_sdk_agent.py,test_service_long_paths.py,test_storage.py,test_storage_runtime.py,test_studio.py,test_task_tools.py,test_transfers.py,test_wheel_execution.py |
| L3 真实执行 | ROUTE | operator_table.csv:builtin_route |
| L4 资源 | ESTIMATE | definition resources.estimate=estimate_memory |
| L5 应用安装 | INSTALL | 8.0.1 bundle install (3.1.9/4.0.0) |

### 这个证据证明什么、不证明什么

- 证明：契约可解析、输入输出维度一致；有执行记录时，真实数据能跑到 `Task finished` 并产生可校验产物。
- 不证明：该算子在该数据集上的生物学结论正确；统计假设是否成立仍需使用者判断。
- 注意：该算子没有独立数值 oracle， correctness 仅到“契约/测试/执行”层级。

## 4. 限制与失败模式

Declared memory modes: full, stream. Operon retains the existing planner, disk-backed
inputs and emergency spill behavior; full-mode operators still require their
declared working set. This generated reference has not been independently
scientifically reviewed.

## 5. 复现

```bash
cd /path/to/Operon-worktree
python -m operon registry check --json
grep '^describe,' verification/coverage-8.0.1/operator_coverage.csv
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
