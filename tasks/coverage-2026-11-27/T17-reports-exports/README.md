# T17-reports-exports · 报告、导出与工作流特性

## 目标
汇总表 → 报告生成(markdown/html) → 批量导出/清单 → 缓存与重试路径

## 输入
`input/`（生成脚本 `gen_inputs.py`；真实样例见 `evidence/`）

## 覆盖
- 算子 7 个：见 `operators.txt`
- reader 2 个：见 `readers.txt`
- 机器可读清单：`coverage.json`（验收后把 status 从 planned 改成 passed/failed 并记录 job id）

## 验收标准
1) 报告文件落盘；2) 导出清单完整；3) 工作流特性有日志证据

## 运行方式
1. `python gen_inputs.py`（生成最小合法输入）
2. 用 `graphs/` 里的路线图提交作业（GUI / CLI / HTTP / MCP 均可）
3. 产物落 `expected/`，指标写 `evidence/report.md`（含 job id、起止时间、算子清单、失败原因）
4. 更新 `coverage.json` 的 status 与 evidence
