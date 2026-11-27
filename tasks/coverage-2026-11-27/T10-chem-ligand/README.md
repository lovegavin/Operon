# T10-chem-ligand · 小分子结构与对接

## 目标
SMILES/SDF → 描述符/指纹 → 相似性/聚类 → ADMET/Lipinski → 对接

## 输入
`input/`（生成脚本 `gen_inputs.py`；真实样例见 `evidence/`）

## 覆盖
- 算子 22 个：见 `operators.txt`
- reader 5 个：见 `readers.txt`
- 机器可读清单：`coverage.json`（验收后把 status 从 planned 改成 passed/failed 并记录 job id）

## 验收标准
1) 描述符表非空；2) 相似性矩阵输出；3) 对接打分存在（或明确环境缺失）

## 运行方式
1. `python gen_inputs.py`（生成最小合法输入）
2. 用 `graphs/` 里的路线图提交作业（GUI / CLI / HTTP / MCP 均可）
3. 产物落 `expected/`，指标写 `evidence/report.md`（含 job id、起止时间、算子清单、失败原因）
4. 更新 `coverage.json` 的 status 与 evidence
