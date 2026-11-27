# T06-genetics · 变异、基因型与 GWAS

## 目标
VCF/PLINK → QC/HWE/LD 剪枝 → GWAS → 注释 → PRS → Manhattan/QQ

## 输入
`input/`（生成脚本 `gen_inputs.py`；真实样例见 `evidence/`）

## 覆盖
- 算子 41 个：见 `operators.txt`
- reader 5 个：见 `readers.txt`
- 机器可读清单：`coverage.json`（验收后把 status 从 planned 改成 passed/failed 并记录 job id）

## 验收标准
1) QC 表非空；2) GWAS p 值列存在；3) 图落盘

## 运行方式
1. `python gen_inputs.py`（生成最小合法输入）
2. 用 `graphs/` 里的路线图提交作业（GUI / CLI / HTTP / MCP 均可）
3. 产物落 `expected/`，指标写 `evidence/report.md`（含 job id、起止时间、算子清单、失败原因）
4. 更新 `coverage.json` 的 status 与 evidence
