# T04-expression · bulk 转录组差异表达与富集

## 目标
counts 矩阵 + 样本表 → 过滤/归一化 → PCA/聚类 → 差异表达 → GO/KEGG 富集 → 火山图/热图

## 输入
`input/`（生成脚本 `gen_inputs.py`；真实样例见 `evidence/`）

## 覆盖
- 算子 41 个：见 `operators.txt`
- reader 4 个：见 `readers.txt`
- 机器可读清单：`coverage.json`（验收后把 status 从 planned 改成 passed/failed 并记录 job id）

## 验收标准
1) 差异表含 logFC/p 值；2) 富集结果非空；3) 两张图落盘

## 运行方式
1. `python gen_inputs.py`（生成最小合法输入）
2. 用 `graphs/` 里的路线图提交作业（GUI / CLI / HTTP / MCP 均可）
3. 产物落 `expected/`，指标写 `evidence/report.md`（含 job id、起止时间、算子清单、失败原因）
4. 更新 `coverage.json` 的 status 与 evidence
