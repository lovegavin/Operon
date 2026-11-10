# Library 7.0.11

Audit-evidence release for Studio 3.1.6. Operator, port and protocol contracts are
unchanged from 7.0.10.

- L3 route coverage: **653/1063**, 410 uncovered. New in 7.0.11: 33 single-table
  regression/GLM routes (linear, GLM, survival, IV, RDD, spline, ordinal and
  multinomial models) that actually executed.
- L0 1171/1171; L1 358 PASS / 0 FAIL; L2 13/13; L4 spill/wire evidence; L5
  CLI/HTTP/MCP describe parity.
- Full pytest: 3722 passed, 209 skipped, 0 failed. One stochastic OpenMM
  return-to-equilibrium test hit a NaN in the full run and passed when rerun in
  isolation.

The per-operator table is `verification/operator-audit-7.0.11/operator_table.csv`.
Audit narrative: `docs/verification/operator-audit-7.0.11.md`.
