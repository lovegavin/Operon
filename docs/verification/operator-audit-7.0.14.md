# Operator audit for library 7.0.14

Audit of the **1063 operators and 108 Readers** shipped in library 7.0.14
against Operon Studio **3.1.6**. Layers are reported independently; a layer is
complete only when every catalog entry has a measured result (PASS or an
explicit `SKIP_*` with a stated precondition).

| layer | scope | result |
| --- | --- | --- |
| L0 static | all 1171 descriptors | **complete, 1171/1171 PASS** |
| L1 contracts | all 1063 operators | **complete, 0 FAIL** (358 PASS, 705 explicit SKIP) |
| L2 oracle | 13 deterministic operators | partial, 13/13 PASS |
| L3 routes | all 1063 operators | **complete, 794 routed + 269 SKIP with reason** |
| L4 memory/transfer | sampled route and Form | partial (spill, quota, wire, determinism, source-mutation limit) |
| L5 entry points | one operator, four entry points | partial (CLI/HTTP/MCP parity; Studio not run) |

Raw evidence is under `verification/operator-audit-7.0.14/`; the per-operator
table is `operator_table.csv` (1063 operators plus 108 Readers).

## L0 - static declaration consistency

AST literal `definition` inside the Step class, `entry_point` and id agreement,
independent parameters JSON, arity/port counts, declared outputs, dims binding
parameters, `data_formats`, and canonical documentation hashes + sections.

- **1171/1171 PASS, 0 failures** (`l0_static.jsonl`, `l0_summary.json`).
- Reader descriptors legitimately omit `inputs_arity`/`outputs`; file operators
  may declare `outputs: null`; streaming operators may declare
  `output_parameter: null`; polymorphic legacy operators bind dims by reference.
  These supported shapes are accepted (warnings only).

## L1 - contract behaviour

Each operator is imported from its descriptor, fed a synthetic Form satisfying
its declared contracts, and run through the real Step. Every `info` predicate
is then violated deliberately and must be rejected with `StepError` before
computation.

- **358 PASS, 0 FAIL, 587 SKIP_DOMAIN, 53 SKIP_FILE, 42 SKIP_EXTERNAL,
  22 SKIP_HARNESS, 1 SKIP_TIMEOUT.**
- Negative checks: 102 pass, 34 fail, 787 N/A.
- SKIPs state the missing precondition (domain columns, sample design, external
  checkpoint, file input, harness limitation), not an operator defect.

Evidence: `l1_full/l1_contract.jsonl`.

## L2 - independent oracle sample

Thirteen deterministic operators are compared against independent
implementations (SciPy/NumPy/linearmodels/hand calculations), with explicit
tolerances:

| operator | oracle | max delta | tolerance |
| --- | --- | --- | --- |
| kalman_local_level | scalar recursion | 4.89e-10 | 1e-8 |
| image_gaussian_blur | scipy.ndimage | 5.00e-10 | 1e-8 |
| pca | NumPy SVD | corr > 0.999999 | 1e-6 |
| conformal_split_regression | empirical quantile | 4.3e-10 | 1e-8 |
| bayesian_linear_regression | NumPy OLS | 4.8e-4 | 1e-2 |
| cohens_kappa | hand contingency table | 1.9e-8 | 1e-7 |
| image_sobel_gradient | hand 3x3 kernel | 0 | 1e-9 |
| genotype_call_rate_qc | hand NaN-aware arithmetic | 0 | 1e-9 |
| zscore | NumPy axis semantics | 5.83e-8 | 1e-6 |
| min_max_scale | NumPy axis semantics | 2.91e-8 | 1e-6 |
| ttest_one_sample | SciPy ttest_1samp | 4.24e-8 | 1e-6 |
| chi_square | scipy.stats.chi2_contingency | 2.01e-7 | 1e-6 |
| fisher_exact | scipy.stats.fisher_exact | 8.51e-10 | 1e-8 |

Evidence: `l2_oracle.json`.

## L3 - route replay

`scripts/package_routes.py` builds **79** built-in bundles, each containing
exactly `graph.json`, `parameters.json`, `execution.json`; all **79/79** import
through `src.web.parameters.import_bundle(bytes)` on Studio 3.1.6.

Built-in templates replay on WSL: **13 PASS, 65 SKIP_DATA** (input data is not
redistributed with the template); the 13 also replay on Windows with semantic
parity (11 PASS and 2 SKIP_DEP for missing anndata/scanpy, verified by
normalised JSON comparison).

Generated audit routes (kept in `/tmp`, not added to the library) contribute
**547 previously uncovered operators**; 578 route executions were run in total
(overlaps included) across: L1-derived CSV routes (305), sequence routes (37),
zero-input routes (11), regression/GLM (33), group statistics (25), ML
classification/clustering (25), PDB geometry (8 + 31), RDKit (26), ligand (10),
diagnostics (4), classification/CCA (4), survival (2), causal inference (8),
additional statistics batches (34), narrowPeak (7), advanced statistics (4),
flow/PTM (2). Union:

- **794 / 1063 operators have at least one passing route**
- **269 operators are SKIP with a concrete reason**:
  151 domain-specific fixture (factor levels, paired samples, reference
  tables), 72 structure/trajectory/reference data, 26 model runtime or
  checkpoint, 20 external dependency unavailable.

Evidence: `l3_builtin_routes.json`, `l3_generated_routes.json`,
`l3_sequence_routes.json`, `l3_three_end_routes.json`,
`l3_group_stats_routes.json`, `l3_ml_routes.json`, `l3_pdb_routes.json`,
`l3_regression_routes.json`, `l3_extra_routes.json`, `l3_extra_routes_v2.json`, `l3_route_skips.json`,
`l3_route_coverage.json`.

## L4 - memory, spill, transfer

- 24-source spill run (24 distance matrices, 100 MiB RAM / 500 MiB disk):
  24 spill events, 59,186,515 B on disk, managed peak 63,998,644 B.
- Three runs (two in-budget, one `--no-auto-spill`) produced the same
  `pca.csv` md5 `84a92e0063bc840ccc8ce7e81d6f8766`, i.e. spill recomputation is
  lossless and deterministic.
- `--disk-mb 1` raises `DiskBudgetError: Spill quota exhausted; original RAM
  copy retained`.
- `ExchangeWire` round-trips a 100x3 Form with identical data, dims and labels.
- 13 of 14 sampled generated routes produced identical CSV on a second run
  (`l4_determinism.json`); the remaining route reuses a template that is
  invalid independently of determinism.
- **Known limitation:** changing a source file after `workflow prepare` is not
  rejected; the run re-reads the changed file (L4 requirement not met).

Evidence: `l4_advanced.json`, `l4_determinism.json`.

## L5 - entry-point parity

Using the same workspace and operator (`kalman_local_level`):

- Direct runner, CLI, HTTP and MCP submitted the same graph and produced the
  same `role=data` CSV md5 `bcd6eb65514a79b19ffe25f55585c691`.
- CLI/HTTP/MCP `describe` return the same canonical descriptor subset
  (sha256 `e71d6fb91c3f7d0b`).
- Studio UI was not exercised in this environment; it remains a SKIP.

Evidence: `l5_cli_parity.json`, `l5_describe_parity.json`.

## Reproduction

```bash
# L0 / L1 / L2
python scripts/operator_audit/l0_static.py --out verification/operator-audit-7.0.14
python scripts/operator_audit/l1_contract.py --out verification/operator-audit-7.0.14/l1_full
OPERON_AUDIT_VERSION=7.0.13 python scripts/operator_audit/l2_oracle.py

# L3
python scripts/package_routes.py --output /tmp/routes
python scripts/operator_audit/run_routes.py

# table
OPERON_AUDIT_VERSION=7.0.13 python scripts/operator_audit/report_table.py
```
