# Library 7.0.12

Audit-evidence release for Studio 3.1.6. Operator, port and protocol contracts are
unchanged from 7.0.11.

7.0.11 shipped its audit archive without the per-operator table because `*.csv` is ignored by the repository. 7.0.12 only fixes that packaging omission: the
archive now carries
`verification/operator-audit-7.0.12/operator_table.csv`
(1063 operators + 108 Readers).

- L3 route coverage: **653/1063**, 410 uncovered (unchanged from 7.0.11).
- L0 1171/1171; L1 358 PASS / 0 FAIL; L2 13/13; L4 spill/wire; L5 CLI/HTTP/MCP
  describe parity.
- Full pytest was run on the identical operator code for 7.0.11: 3722 passed,
  209 skipped, 0 failed; one stochastic OpenMM test needed an isolated rerun.
