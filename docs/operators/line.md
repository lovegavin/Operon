# 折线图 (`line`)

**Category:** 可视化  
**Entry point:** `src.task.step.steps.line:LineStep`  
**Source:** [`library/seed/src/task/step/steps/line.py`](../../library/seed/src/task/step/steps/line.py) (144 lines)  
**Trust level: B — 真实执行（本地或 srv）**

## 1. 代码说明

选择两个数值标签，按横坐标排序后绘制曲线。

> Line plot operator. Input is a single 2D form. One dimension holds the attributes (columns); the other holds the observations. The operator reads two labeled columns as x and y, sorts by x, and draws a

关键符号：

- `class LineStep (line 19)`

协议：v3 / revision `3.7`；输出参数 `None`。

### 输入与输出

- 输入 1: ndim=2, numeric=True, dims=(dim), info=(—)
- 输出: mode=report, schema={}

### 参数

| 参数 | 默认值 | 含义/约束 |
| --- | --- | --- |
| `dim` | `feature` | 维度 |
| `x_label` | `` | 横坐标标签 |
| `y_label` | `` | 纵坐标标签 |
| `filename` | `` | 文件名 |
| `sort` | `True` | Sort by X |
| `title` | `` | Title |
| `xlabel` | `` | X axis label |
| `ylabel` | `` | Y axis label |
| `figure_width_mm` | `` | Figure width (mm) |
| `figure_height_mm` | `` | Figure height (mm) |
| `figure_dpi` | `300` | Figure resolution (DPI); min 72 |
| `figure_font_size` | `8` | Figure font size (pt) |

## 2. 用途与解释

Line plot operator.

Input is a single 2D form. One dimension holds the attributes
(columns); the other holds the observations. The operator reads two
labeled columns as x and y, sorts by x, and draws a line.

Draw a line plot.

Params:
dim      : attribute dimension (default "feature")
x_label  : column label for the x axis
y_label  : column label for the y axis
filename : output file name
title    : optional plot title
xlabel   : optional x-axis label (default: x_label)
ylabel   : optional y-axis label (default: y_label)
sort     : sort points by x before drawing (default True)

## 3. 正确性依据

**结论：B 级。** 真实运行通过（1.86 s），导出 None 行，产物 sha256 n/a…。

| 层 | 状态 | 证据 |
| --- | --- | --- |
| L1 契约/清单 | PASS | verification/operator-audit-8.0.1/operator_table.csv |
| L2 单元/oracle | UNIT | tests/test_audit_fixes.py,test_builtin_pins.py,test_candidate_delivery.py,test_crlf.py,test_desktop.py,test_docs_links.py,test_environment_agent_permissions.py,test_execution_api.py,test_extension110.py,test_extension113.py,test_extension117.py,test_extension118.py,test_extension121.py,test_extension126.py,test_extension128.py,test_extension130.py,test_extension131.py,test_extension140.py,test_extension145.py,test_extension149.py,test_extension155.py,test_extension160.py,test_extension179.py,test_extension191.py,test_extension194.py,test_extension226.py,test_extension244.py,test_extension247.py,test_extension252.py,test_extension255.py,test_extension295.py,test_extension296.py,test_extension297.py,test_extension298.py,test_extension299.py,test_extension304.py,test_extension305.py,test_extension313.py,test_extension315.py,test_extension322.py,test_extension324.py,test_extension326.py,test_extension327.py,test_extension330.py,test_extension331.py,test_extension332.py,test_extension333.py,test_extension334.py,test_extension335.py,test_extension338.py,test_extension339.py,test_extension341.py,test_extension342.py,test_extension354.py,test_extension356.py,test_extension361.py,test_extension363.py,test_extension365.py,test_extension381.py,test_extension387.py,test_extension410.py,test_genotype_readers_sop.py,test_isolation.py,test_memory_runtime.py,test_plot_artifacts_sop.py,test_portability.py,test_r_oracles.py,test_r_oracles10.py,test_r_oracles11.py,test_r_oracles12.py,test_r_oracles13.py,test_r_oracles14.py,test_r_oracles15.py,test_r_oracles16.py,test_r_oracles17.py,test_r_oracles18.py,test_r_oracles19.py,test_r_oracles20.py,test_r_oracles21.py,test_r_oracles22.py,test_r_oracles23.py,test_r_oracles24.py,test_r_oracles25.py,test_r_oracles26.py,test_r_oracles27.py,test_r_oracles28.py,test_r_oracles29.py,test_r_oracles3.py,test_r_oracles30.py,test_r_oracles31.py,test_r_oracles32.py,test_r_oracles33.py,test_r_oracles34.py,test_r_oracles35.py,test_r_oracles36.py,test_r_oracles37.py,test_r_oracles38.py,test_r_oracles39.py,test_r_oracles4.py,test_r_oracles40.py,test_r_oracles41.py,test_r_oracles42.py,test_r_oracles43.py,test_r_oracles44.py,test_r_oracles48.py,test_r_oracles49.py,test_r_oracles5.py,test_r_oracles52.py,test_r_oracles53.py,test_r_oracles54.py,test_r_oracles55.py,test_r_oracles56.py,test_r_oracles57.py,test_r_oracles58.py,test_r_oracles6.py,test_r_oracles7.py,test_r_oracles79.py,test_r_oracles8.py,test_r_oracles83.py,test_r_oracles84.py,test_r_oracles85.py,test_r_oracles86.py,test_r_oracles87.py,test_r_oracles88.py,test_r_oracles89.py,test_r_oracles9.py,test_r_oracles90.py,test_r_oracles92.py,test_r_oracles93.py,test_r_oracles94.py,test_r_oracles95.py,test_reader_conformance.py,test_readers_sop.py,test_remote.py,test_remote_provision.py,test_remote_transfer.py,test_report_contracts_sop.py,test_run_logging.py |
| L3 真实执行 | EXECUTED | verification/coverage-8.0.1/routes/line |
| L4 资源 | ESTIMATE | definition resources.estimate=estimate_memory |
| L5 应用安装 | INSTALL | 8.0.1 bundle install (3.1.9/4.0.0) |

本次执行细节：

- 状态：PASS，耗时 1.86 s，导出 None 行。
- 归档路线：`/tmp/cov_sequence/line`。
- 命令：`/home/gavin/bp-numpy21/bin/python scripts/run.py /tmp/cov_sequence/line`。

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
grep '^line,' verification/coverage-8.0.1/operator_coverage.csv
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
