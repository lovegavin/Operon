# T07-hic · Hi-C 与三维基因组

## 目标
接触矩阵 → 平衡/校正 → 区室 → TAD/绝缘 → 环 table

## 输入
`input/`（生成脚本 `gen_inputs.py`；真实样例见 `evidence/`）

## 覆盖
- 算子 10 个：见 `operators.txt`
- reader 3 个：见 `readers.txt`
- 机器可读清单：`coverage.json`（验收后把 status 从 planned 改成 passed/failed 并记录 job id）

## 验收标准
1) 矩阵统计输出；2) 区室/TAD 表非空；3) 图落盘

## 运行方式
1. `python gen_inputs.py`（生成最小合法输入）
2. 用 `graphs/` 里的路线图提交作业（GUI / CLI / HTTP / MCP 均可）
3. 产物落 `expected/`，指标写 `evidence/report.md`（含 job id、起止时间、算子清单、失败原因）
4. 更新 `coverage.json` 的 status 与 evidence
