# T02-structure-analysis · 结构预测、复合物与 MD

## 目标
binder FASTA → colabfold_predict(single_sequence) → pLDDT/界面 → openmm MD(stability+rmsf) → 指标 CSV 与图

## 输入
`input/`（生成脚本 `gen_inputs.py`；真实样例见 `evidence/`）

## 覆盖
- 算子 122 个：见 `operators.txt`
- reader 3 个：见 `readers.txt`
- 机器可读清单：`coverage.json`（验收后把 status 从 planned 改成 passed/failed 并记录 job id）

## 验收标准
1) 8 个折叠完成且 pLDDT 有值；2) MD 两算子完成并输出 CSV；3) 汇总表含长度/pLDDT/Rg/RMSD

## 运行方式
1. `python gen_inputs.py`（生成最小合法输入）
2. 用 `graphs/` 里的路线图提交作业（GUI / CLI / HTTP / MCP 均可）
3. 产物落 `expected/`，指标写 `evidence/report.md`（含 job id、起止时间、算子清单、失败原因）
4. 更新 `coverage.json` 的 status 与 evidence
