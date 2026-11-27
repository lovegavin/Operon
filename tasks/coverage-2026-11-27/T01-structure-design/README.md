# T01-structure-design · 蛋白质骨架与序列设计

## 目标
3DI3.cif 链 B → structure_extract_chain → rfdiffusion_design(4 设计) → proteinmpnn_design(每设计 2 序列) → 导出 PDB/FASTA

## 输入
`input/`（生成脚本 `gen_inputs.py`；真实样例见 `evidence/`）

## 覆盖
- 算子 38 个：见 `operators.txt`
- reader 3 个：见 `readers.txt`
- 机器可读清单：`coverage.json`（验收后把 status 从 planned 改成 passed/failed 并记录 job id）

## 验收标准
1) 设计坐标真实（原子不全为 1.000）；2) binder 到靶标最小距离 <5 Å；3) MPNN 序列非低复杂度（最大单残基占比 <35%、无 ≥8 连续重复）

## 运行方式
1. `python gen_inputs.py`（生成最小合法输入）
2. 用 `graphs/` 里的路线图提交作业（GUI / CLI / HTTP / MCP 均可）
3. 产物落 `expected/`，指标写 `evidence/report.md`（含 job id、起止时间、算子清单、失败原因）
4. 更新 `coverage.json` 的 status 与 evidence
