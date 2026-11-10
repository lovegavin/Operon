# Library 7.0.13

This release consolidates the L0-L5 audit evidence gathered after 7.0.12 and
fixes one structure operator found by that audit. No protocol, route-template
or `export_results` contract changed.

## Operator fix

- `structure_aromatic_stacking` now suffixes duplicate aromatic bond labels
  (`C5-C6#2`) instead of emitting an unlabeled row, which previously made the
  exported Form unreadable. Found by the PDB geometry batch.

## Audit result

- L0: 1171/1171 descriptors PASS.
- L1: 1063 operators, 358 PASS and 0 FAIL; 705 explicit SKIP with precondition
  (587 domain fixture, 53 file input, 42 external, 22 harness, 1 timeout).
- L2: 13 deterministic operators checked against independent oracles, 13/13
  PASS (max delta 4.8e-4 for the Bayesian/OLS comparison, all others <= 2e-7).
- L3: 79/79 route bundles import on Studio 3.1.6; **779/1063 operators have a
  passing route**. The remaining 284 are SKIP with a concrete reason
  (195 domain fixture, 41 structure/reference data, 24 model checkpoint,
  12 external dependency, 9 not executable from synthetic input, 3 external
  tool). Per-operator results are in `operator_table.csv`.
- L4: spill recomputation is lossless and deterministic (same md5 across three
  runs), `DiskBudgetError` is enforced, and `ExchangeWire` round-trips a Form.
  Changing a source file after `prepare` is **not** rejected; this remains a
  known limitation.
- L5: direct runner, CLI, HTTP and MCP produce the same CSV md5 for the same
  graph; CLI/HTTP/MCP `describe` canonical output matches. Studio UI remains
  untested.

The audit scripts and raw JSONL/JSON evidence ship in the
`Operon-Operator-Audit-v7.0.13.zip` asset, together with the per-operator table.

## Compatibility

Built and verified against Operon Studio 3.1.6 (`minimum_application` and
`build_application` are 3.1.6). Full pytest: 3722 passed, 209 skipped, 0 failed.
