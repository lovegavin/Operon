# Library 7.0.14

Final operator-audit evidence for Operon Studio 3.1.6. No protocol, route
template or export contract changed. The audit corpus and its per-operator
table were extended, and one operator hardening fix is included:
`ligand_pdbqt_prepare` now confines a user-supplied `output_path` basename to
the step artifact directory instead of writing an arbitrary path.

## Audit result

- L0 static: 1171/1171 PASS.
- L1 contracts: 358 PASS, 0 FAIL, 705 explicit SKIP with precondition.
- L2 oracle: 13/13 PASS.
- L3 routes: **794 / 1063 operators routed**, 269 SKIP with a reason
  (151 domain fixture, 72 structure/reference, 26 model checkpoint,
  20 external dependency). 79 built-in route bundles import 79/79.
- L4 memory/transfer: spill, quota, wire round-trip and determinism sampled;
  prepared-source mutation is still not rejected by the engine (documented
  limitation).
- L5 entry points: CLI, HTTP and MCP produce the same artifact hash and the
  same canonical describe payload; Studio UI not exercised.

New route batches since 7.0.13: narrowPeak (7), advanced statistics (4),
ligand chain/PDBQT (2 executed, 5 already counted), flow transform and PTM
localization (2). Full details are in
`docs/verification/operator-audit-7.0.14.md`.

## Assets

Linux/Windows library bundles, routes collection, quickstart, wheel, audit
archive and `SHA256SUMS.txt`, built by the tagged release workflow.
