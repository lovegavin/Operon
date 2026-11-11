# Operator audit for library 8.0.2

Library 8.0.2 ships **1063 operators and 108 Readers** for Operon Studio
**3.1.9 and newer**. This audit is the per-operator five-layer record. A layer
is complete only when every catalog entry has a measured result: `PASS`,
`ROUTE`/`INSTALL`, or an explicit `SKIP` with a documented precondition.

Per-operator status: `verification/coverage-8.0.1/operator_coverage.csv`
Machine-readable counts: `verification/coverage-8.0.1/summary.json`
L3 skip evidence: `verification/coverage-8.0.1/l3_skips.json`
Trust sheets: `docs/operators/<operator>.md`

| layer | scope | result |
| --- | --- | --- |
| L1 declaration and manifest | 1063 operators | **1063 PASS, 0 FAIL, 0 SKIP** |
| L2 unit/oracle evidence | 1063 operators | **11 oracle, 8 smoke, 1044 referenced unit tests; 0 SKIP** |
| L3 route or execution | 1063 operators | **223 local executions, 47 server executions, 789 compiled routes; 4 SKIP** |
| L4 memory/determinism | 1063 operators | **37 measured (23 new determinism runs), 1026 resource estimates; 0 SKIP** |
| L5 install/adapter | 1063 operators | **984 installed descriptors, 79 route bundles validated; 0 SKIP** |

## L1 — declaration and manifest

All 1063 operator descriptors pass AST-literal declaration checks, id and
entry-point agreement, arity/output checks, `data_formats`, adjacent Markdown,
and the built-in package manifest `code_sha` check. `registry check --json`
reports 0 errors and 1171 descriptors (1063 operators + 108 Readers).

## L2 — unit and oracle evidence

The 12 remaining unit-test gaps were closed by `tests/test_l2_gap.py`
(12 passed, 3.02 s): ATAC peak calling, foldseek clustering, GC skew, gene-list
hits, gradient boosting, interval overlap, interval statistics, logistic
regression, motif scan, nearest gene, random forest, and SVM. Numeric oracles
cover 11 operators; 8 more have smoke evidence; 1044 have direct unit-test
references. The trust sheets state exactly which level applies and never
promote a reference to an execution.

## L3 — route or execution

- 223 operators were executed locally from archived routes under
  `verification/coverage-8.0.1/routes/` with `scripts/run.py` (exit 0 and
  `Task finished`).
- 47 operators were executed on the server against the same source hashes
  (srv evidence in `evidence/srv_runs.json`).
- 789 operators have a compiled built-in route and passed the Studio 4.0.0
  registration path; they are not claimed as re-executed here.
- 4 SKIPs remain, each with a concrete precondition in `l3_skips.json`:
  `boltz_predict`, `boltz_complex_confidence`, `boltz_affinity_summary`
  (no boltz runtime or weights), and `rfdiffusion_design` (no compatible
  generic checkpoint: antibody checkpoints fail; official GPU hits a DGL ABI
  error; CPU exceeded the 1800 s designer timeout).

## L4 — memory and determinism

37 operators have measured determinism: the original 14 plus 23 previously
unmeasured operators, all re-executed twice with byte-identical exports and
step JSON. 1026 operators carry `resources.estimate` but no measured memory
trace; they are marked `ESTIMATE`, not `MEASURED`.

## L5 — install and adapters

The 8.0.2 native bundle installs on Studio 3.1.9 and 4.0.0. 984 descriptors
come from the installed package and 79 built-in route bundles were validated
with `workflow validate` (79/79 `valid=true`). CLI/HTTP/MCP parity and Studio UI
automation are not part of this round; UI remains an explicit SKIP.

The isolated reinstall check is recorded in
`verification/coverage-8.0.1/application-3.1.9.json` and
`verification/coverage-8.0.1/application-4.0.0.json`: 1063 operators, 108
readers, 98 passed/1 skipped/7 deselected, idempotent install, preserved old
pin, and a stream-planned worker run. The 4.0.0 run relaxes the exact build
application assertion to `>= minimum_application`; 4.0.0 is newer than the
3.1.9 build target.

## Full test suite (8.0.2)

`python -m pytest -q -rs --tb=short` (bp-numpy21, NumPy 2.1.3) completed with
**3722 passed, 209 skipped, 0 failed in 2435.17 s**. The 209 skips are
environment gates, not failures. Every skip reason is recorded verbatim in
`verification/coverage-8.0.1/pytest-8.0.2-skips.txt` (209 tests, 196 pytest
report lines); the aggregate is:

| Reason | Skipped tests |
| --- | ---: |
| Rscript not available | 131 |
| Model checkpoint or executable not configured | 36 |
| Real SOP fixture not present | 13 |
| Windows-only test | 6 |
| fair-esm shadowed by the ESM-3 package | 5 |
| Missing optional Python module: allel | 4 |
| Missing optional Python modules: mudata | 2 |
| torch_scatter ABI-incompatible | 1 |
| Missing optional Python module: mrcfile | 1 |
| Missing optional Python module: pgenlib | 1 |
| Local ProteinMPNN checkout not configured | 1 |
| Official ProteinMPNN checkout/weights or fixture unavailable | 1 |
| Official ProteinMPNN checkout or weights missing | 1 |
| Official LigandMPNN checkout or weights missing | 1 |
| DockQ CLI not installed | 1 |
| plink not available | 1 |
| Empty parameter set (route fixture absent) | 1 |
| Explicit clean Linux installation acceptance | 1 |
| Explicit Linux installation without a usable Python | 1 |

## Reproduce

```bash
cd /path/to/Operon-worktree
python -m operon registry check --json
python scripts/operator_audit/coverage_ledger.py
python scripts/build_operator_trust_docs.py
python scripts/build_operator_docs.py --check
python -m pytest -q tests/test_l2_gap.py tests/test_library_release.py
python scripts/release_library.py --tag library-v8.0.2 --output /tmp/build802
python scripts/verify_library_release.py --bundle /tmp/build802/Operon-Library-v8.0.2-Linux.operon-library.zip
```
