# T13-reader-formats · 全 reader 格式转换矩阵

## 目标
每个 reader 读最小合法样例 → Form → export_results CSV → 校验行列/列名

## 输入
`input/`（生成脚本 `gen_inputs.py`；真实样例见 `evidence/`）

## 覆盖
- 算子 0 个：见 `operators.txt`
- reader 110 个：见 `readers.txt`
- 机器可读清单：`coverage.json`（验收后把 status 从 planned 改成 passed/failed 并记录 job id）

## 验收标准
1) 110 个 reader 全部有结果行；2) 失败项写明原因；3) coverage.csv 记录 reader/status/rows

## 运行方式
1. `python gen_inputs.py`（生成最小合法输入）
2. 用 `graphs/` 里的路线图提交作业（GUI / CLI / HTTP / MCP 均可）
3. 产物落 `expected/`，指标写 `evidence/report.md`（含 job id、起止时间、算子清单、失败原因）
4. 更新 `coverage.json` 的 status 与 evidence
