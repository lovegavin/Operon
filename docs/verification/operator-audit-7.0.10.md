# Operator audit for library 7.0.10

Audit of the 1063 operators and 108 Readers shipped in library 7.0.10 against
Studio 3.1.6. Layers are reported independently; a layer is marked complete
only when every catalog entry has a measured result (PASS or an explicit
`SKIP_*` with a stated precondition). **L0 is complete; L1-L5 are partial and
the exact scope is stated below.**

> Coverage: built-in route graphs cover 247 operators (export_results is a
> sink, not an operator), generated routes add 373 operator executions, and the
> union is 511 / 1063 with 552 operators uncovered. The
> per-operator table is verification/operator-audit-7.0.10/operator_table.csv
> (1063 operators plus 108 Readers).

## L0 - static declaration consistency

Command: `python scripts/operator_audit/l0_static.py`

Result: **1171 / 1171 PASS** (1063 operators, 108 Readers), failures 0.

Checked per entry: entry point resolves to a class with a literal
`definition`, `id`/`kind`/`protocol_version` agree with the descriptor,
`parameters_schema` is reproduced from the adjacent JSON, arity matches
`contracts.inputs`, declared outputs and `output_parameter` are consistent,
dimension bindings reference declared schema parameters, `data_formats`
logical types and representations are valid, documentation hash matches the
canonical document content, and documented section anchors exist.

Evidence: `verification/operator-audit-7.0.10/l0_static.jsonl` and
`l0_summary.json`.

## L1 - contract behaviour

Command: `python scripts/operator_audit/l1_contract.py`

Positive case: synthesize a Form for each input port from the resolved
contract, resolve parameter bindings exactly as the engine does, validate,
then call `run`. Negative cases: mutate each `info` predicate on a valid Form
and require `validate_form` to raise a `StepError` before execution.

| result | count |
| --- | --- |
| PASS | 358 |
| FAIL | 0 |
| SKIP_DOMAIN (domain precondition, e.g. missing required column or too few samples) | 587 |
| SKIP_FILE (file port; no fixture) | 53 |
| SKIP_EXTERNAL (model/weight download) | 42 |
| SKIP_HARNESS (no dimensional contract) | 22 |
| SKIP_TIMEOUT | 1 |

Negative predicates: 102 PASS, 34 FAIL, 787 not applicable.

Zero failures remain. The 587 domain skips are inputs the generic fixture
cannot satisfy (rank-deficient designs, required factor levels, exact 2x2
tables, sequence/structure semantics); they are listed with their step error
in `verification/operator-audit-7.0.10/l1_full/l1_contract.jsonl` and are not
counted as verified. The negative-predicate failures are recorded in the same
file and are not counted as verified.

## L2 - independent numeric oracles

Oracle pairs accumulated in `docs/verification/routes-5.x.md` and
`docs/verification/three-end-audit-7.0.1.md` cover the route-level operators
(statsmodels/linearmodels, scipy, Biopython, bedtools/samtools/bcftools,
plink2, RDKit/Vina, HMMER/Prodigal, etc.). A per-operator oracle matrix for all
1063 entries is **not** complete; the current coverage is the route evidence
plus the numeric checks recorded in those files.

`scripts/operator_audit/l2_oracle.py` adds independent, deterministic checks
for thirteen operators (`verification/operator-audit-7.0.10/l2_oracle.json`, 13/13):
Kalman local level against a hand-written scalar recursion (delta 4.9e-10),
Gaussian image blur against `scipy.ndimage.gaussian_filter` (delta 5.0e-10),
PCA against NumPy SVD on the transposed standardized matrix (component
correlations > 0.999999), split conformal regression against an empirical
quantile (width delta < 1e-9), Bayesian linear regression posterior means
against NumPy OLS (max delta 4.8e-4), Cohen's kappa against a hand-computed
contingency-table formula (delta 1.9e-8, output rounded to 8 decimals), Sobel
gradient against hand-written 3x3 kernels (delta 0), and genotype call rate
against manual NaN-aware arithmetic (delta 0), chi-square against
`scipy.stats.chi2_contingency` (delta 2.0e-7), and Fisher exact against
`scipy.stats.fisher_exact` (delta 8.5e-10).

## L3 - route replay

Package: `scripts/package_routes.py --output <dir>` builds 79 bundles, each
containing exactly `graph.json`, `parameters.json`, `execution.json`. Import
through `src.web.parameters.import_bundle(bytes)` succeeds for **79/79** on
Studio 3.1.6.

Replay on WSL with `python scripts/run.py library/seed/routes/<name>`:

| result | count |
| --- | --- |
| PASS | 13 |
| SKIP_DATA (input data not distributed with the template) | 65 |

Generated coverage routes (`scripts/operator_audit/gen_l1_routes.py`) reuse
the L1 fixtures and write a CSV-backed template plus `export_results` for
operators whose L1 case passed. 348 templates were generated, 314 pass static
validation and 305 execute successfully. A second batch of 40 operators was
exercised: 27 through multi-sequence `FastaReader` routes, 10 through
single-sequence refinements, and 3 shared multi-input routes (codon adaptation,
k-mer enrichment, variance partitioning). The union of builtin route coverage
(247 operators in the graphs), generated routes that cover previously
uncovered operators (325 route executions, including 11 zero-input routes) and 58 additional batch
routes (25 group-comparison, 25 machine-learning and 8 PDB geometry) is **620 / 1063**; 443 operators still have no passing route. The blocking reasons
are one-dimensional Form ports that `CsvReader` cannot declare, sequence ports
handled only by the second batch, structure/atom tables requiring real records,
file-only ports, external tools or model checkpoints, and statistical designs
needing factor levels or paired samples.

Evidence: `verification/operator-audit-7.0.10/l3_builtin_routes.json`,
`l3_generated_routes.json`, `l3_route_coverage.json`,
`l3_three_end_routes.json`.


### Group, ML and PDB batches (7.0.10)

Three route batches were generated outside the library (audit artifacts only):

- 25 two-CSV group-comparison routes (`/tmp/groupstats`) - one data table
  `[feature, sample]` and one metadata table `[sample, feature]`; `group_dim`
  binds to the metadata sample axis.
- 25 three-CSV classifier and clustering-agreement routes (`/tmp/mlroutes`) -
  `features [sample, feature]`, `truth [sample, label]`, `pred [sample, label]`.
- 8 PDB geometry routes (`/tmp/pdbroutes`) reading `1MEL` through `PdbReader`.

All 25 + 25 + 8 executed successfully on WSL. The other 20 PDB routes stop on
domain prerequisites (OpenMM has no HOH template, no LIG ligand, cavity volume
below the configured minimum, fpocket missing, `reference_path` required,
`[atom, atom]` PAE matrix). Evidence:
`verification/operator-audit-7.0.10/l3_group_stats_routes.json`,
`l3_ml_routes.json`, `l3_pdb_routes.json`.

Windows and srv replay of the same routes:

| end | PASS | SKIP | evidence |
| --- | --- | --- | --- |
| WSL Ubuntu-24.04 | 13 / 13 | 0 | per-route wall time 1.07-9.30 s |
| Windows D:\Operon, py 3.12 | 11 / 13 | 2 SKIP_DEP | `combat` and `doublet_detect` need anndata/scanpy |
| srv | 0 | all | SKIP: no SSH host configured in this session |

Raw output hashes are not comparable across ends (absolute roots, run ids,
CRLF, last-bit float differences). Step and figure JSON were compared after
normalizing roots and export ids, with numeric fields required to agree within
`rel=abs=1e-9`; **11 / 11** runnable routes pass. Evidence:
`verification/operator-audit-7.0.10/l3_three_end_routes.json`.

Additional L4 probe: a 20000 x 60 PCA route (11.5 MB CSV) under a 4 MiB
managed budget fails with MemoryBudgetError at actual_input_size; under
13 MiB it fails at full_step_admission. The runner creates per-run spill
directories, but full-mode admission rejects the reservation before spill
can be exercised, so no spill-recompute equivalence claim is made.

### Zero-input route probe

Of the 552 uncovered operators, 94 take no inputs. Default-parameter routes were
generated in `/tmp/zroutes` and 89 passed static validation; 11 executed and
produced artifacts (`ligand_efficiency`, `pains_filter`, `power_anova`,
`power_t_test`, `rdkit_admet_rules`, `rdkit_conformer_energy`, `rdkit_mcs`,
`rdkit_scaffold`, `rdkit_similarity`, `resource_preflight`, `tree_ultrametric`).
The remaining 78 stop on domain prerequisites (structure/affinity paths, model
weights) and are recorded as SKIP_DOMAIN. These routes are audit artifacts and
are not registered templates.

## L4 - memory, determinism, transfer

Double-run determinism was sampled for 14 generated routes; 13 produced
byte-identical exported CSV hashes on both runs (the remaining template is a
one-dimensional input that `CsvReader` rejects, so it is not a determinism
failure). Evidence: `verification/operator-audit-7.0.10/l4_determinism.json`.

Peak RSS for the `pca` generated route is 144724 kB (141 MiB) with a 64 MiB
managed-memory budget. Running the same route with `--memory-mb 0.001` raises
`MemoryBudgetError` before execution ("required>=20148, budget=1048, reason=
actual_input_size"), confirming admission is enforced.

Per-operator estimate-versus-RSS tables, spill-recompute equality and wire
round-trip rejection are not yet measured.

A prepared graph pins operator implementation hashes, not source-file hashes.
Changing `input.csv` between prepare and run does not abort the run: the second
run re-read the changed file and exported a different matrix
(`1806a277...` instead of `bcd6eb65...`). This is recorded as a failed L4
source-mutation probe, not as a pass; fixing it belongs to the application run
layer. Evidence: `l5_cli_parity.json`.

## L5 - entry points

Route bundles import through the Studio 3.1.6 HTTP parameter API
(`import_bundle(bytes)`, 79/79).

A three-way sample on the `correlation` route compares the direct development
runner, two `operon run` CLI jobs and a repeated CLI job:

- `python scripts/run.py /tmp/l5task` -> `bcd6eb65514a79b19ffe25f55585c691`
- CLI job `20261109T232004-b6c71553` -> same hash
- CLI job `20261109T232043-618265c8` -> same hash

The HTTP entry point (job `20261109T232242-811c4236`) and the MCP adapter
(`operon_submit`, job `20261109T232353-fe429063`) both exported the same hash.
CLI, HTTP, MCP and the direct runner are byte-identical for this route. Studio
uses the same `POST /api/v1/operators/describe` handler; the UI dialog itself
was not automated.

A `describe` sample on `kalman_local_level` was compared across CLI, HTTP and
MCP from one checkout and one service. The canonical subset (id, kind, title,
parameters_schema, contracts, data_formats, outputs, inputs_arity,
output_parameter) hashed to `e71d6fb91c3f7d0b` on all three. Evidence:
`l5_describe_parity.json`. The installed 3.1.6 wheel speaks the legacy
`biopipe` bridge header and cannot be mixed with this checkout's `operon`
bridge in the same comparison.

## Defects fixed in 7.0.2-7.0.10

- `graph_pseudotime`: clamp `n_neighbors` to `n - 1` for small inputs.
- `cohens_kappa`: reject non-square count tables with `StepError`.
- `fba_flux_balance`: require bounds rows to equal the reaction count.
- `pedigree_inbreeding`: detect ancestral cycles and raise `StepError`
  instead of recursing.
- `sc_leiden_cluster`: require a square cell-by-cell adjacency matrix.
- `tree_consensus`: return a valid empty table when no shared split exists.
- `motif_scan_pwm`: keep row labels unique when two sequences share a name.
- `sc_spatial_variable_genes`: require the count matrix column count to equal
  the spatial cell count.
- `structure_md_interface_occupancy`: reject an empty `trajectory_path`.
- `structure_pocket_detect`: require and report the structural column names.

## Reproduce

```
cd /home/gavin/Operon
/home/gavin/bp-numpy21/bin/python scripts/operator_audit/l0_static.py
/home/gavin/bp-numpy21/bin/python scripts/operator_audit/l1_contract.py \
  --out verification/operator-audit-7.0.10/l1_full
/home/gavin/bp-numpy21/bin/python scripts/operator_audit/gen_l1_routes.py \
  /tmp/l1routes verification/operator-audit-7.0.10/l1_full/l1_contract.jsonl
/home/gavin/bp-numpy21/bin/python scripts/operator_audit/run_routes.py
```

The 7.0.10 release assets include this directory and the audit scripts so the
measurements can be reproduced against the released bundle.


## L3 addendum: sequence-input route batch

40 previously uncovered operators (37 with `sequence_codes` inputs and 3
multi-input operators) were exercised
through real `FastaReader` routes (protein FASTA for protein contracts, DNA
FASTA for nucleotide contracts). 27 came from the eleven-route bootstrap batch
and 10 from the single-sequence refinement batch (antibody numbering/CDR
metrics, VHH humanization, hydrophobicity, liability scan, ORF finding).
Fixtures are synthetic test sequences, not biological conclusions.

Coverage after this batch: **620/1063** covered, **443** still without a
passing route. The remaining sequence operators require external databases or
executables (AMRFinderPlus, antiSMASH, QUAST, Flye, HMMER/Pfam, Rfam, ColabFold,
ESMFold), model checkpoints (ESM), longer contigs (Prodigal, GC skew window), or
multi-input combinations. Evidence: `l3_sequence_routes.json` and
`l3_route_coverage.json`.

## L4 addendum: spill, quota and wire probes

A synthetic 24-source route (24 distance matrices, 800 x 800) was run with a
100 MiB managed budget and a 500 MiB disk quota. The memory manager recorded
24 spill events, 59,186,515 spilled bytes and a managed peak of 63,998,644
bytes; the run completed. Three runs (two budgeted, one with
`--no-auto-spill`) all exported the same PCA CSV, md5
`84a92e0063bc840ccc8ce7e81d6f8766`, so spill recomputation is lossless and
deterministic for this route. A 1 MiB disk quota produced
`DiskBudgetError: Spill quota exhausted; original RAM copy retained`,
confirming quota enforcement. An `ExchangeWire` write/read of a 100 x 3 Form
preserved data, dims and labels exactly. Evidence: `l4_advanced.json`.

The full RSS-tail / streamed-wire and source-mutation refusal checks remain
`not_measured`; prepare currently pins operator implementation hashes but not
input-file hashes, so editing a source file between prepare and run is not
refused (recorded as a known limitation earlier in this document).
