# Operon Studio 5.7.38 — acceptance report

Release 5.7.38 bundles library 1.1.24 and closes the last gaps the operator
campaign found in the runtime itself. Every item below was reproduced on the
deployment at `licai-srv` before it was changed.

## What is verified

| Item | Result |
| --- | --- |
| Operator catalogue | 1074 operators, 109 readers, 79 routes, 0 registry errors |
| Environments on `licai-srv` | 19/19 ready, `core` optional extras satisfied |
| Resources | 18 declared resources, every file present, no undownloadable unit except `prodigal/prodigal` (a `make` product) |
| Operators with a recorded successful run | 1006 of 1074 |
| Routes exercised per run | reader → operator wiring with real, format-faithful fixtures |
| Four clients | UI, MCP (146 tools), HTTP `/api/v1/jobs`, CLI `operon run` all reach the same engine |

## Fixes in this release

1. **`ValuesReader`** — the catalogue declared exactly two operators with a
   one-dimensional numeric input (`diversity_simpson`, `numeric_gini_coefficient`)
   and no reader produced such a form, so the pair was unreachable. The new
   reader turns a single column of numbers into a one-dimensional form with
   per-position labels, and both operators now complete.
2. **`/api/v1/jobs` honours `limit`** — the endpoint ignored it and serialised
   every historical job; a 900-job workspace answered in 7.7 s with 11 MB.
3. **VCF site labels stay distinct** — duplicated `CHROM:POS` sites collided in
   `vcf_hardy_weinberg` and `vcf_site_missingness`, which rejected the form with
   `dim 'site' has unlabeled positions`.
4. **The probe exports the environment libraries** — `torch` loaded the host
   `libstdc++` first, `numpy` then failed with `CXXABI_1.3.9 not found`, and
   every environment that needs torch stayed blocked. The probe now exports
   `<env>/lib` and `<env>/lib64` like the worker already did, so
   `mlp_classifier`, `mlp_regressor` and `autoencoder_anomaly` run.
5. **`_protein_common` imports `Path`** and the hotspot operator takes its form
   before it asks for a structure file; five ProteinMPNN interface operators no
   longer fail with `NameError`.
6. **Dependency declarations** — `core` gains `python-igraph` and `hdbscan`,
   `hic` gains `cooltools` and `python-igraph`, `ligandmpnn` gains `prody`,
   `rfdiffusion` gains `opt_einsum`. `sc_leiden_cluster`, `hdbscan_cluster`,
   `ligandmpnn_design` and `rfdiffusion_design` depend on them.

## Coverage method

Every operator was driven through a real reader: PDB, FASTA, FASTQ, VCF, GFF3,
BED, BIOM, SBML, Newick, MatrixMarket and CSV fixtures that follow the format
the reader documents, with the parameter names each `*.parameters.json` accepts.
A run counts as covered only when the job reaches `complete`; failures are
classified as fixture semantics, missing environment or tool, product defect, or
impossible offline. The ledgers live in `DEFECTS.md`, `CLASSIFY.md` and the
per-family reports.

## Known limits

- `nucleotide_transformer_embedding` and `nucleotide_transformer_variant_effect`
  need model weights that are not part of any downloadable resource; they are
  reported as offline-only.
- `amrfinder_plus` ships binary 4.2.5 while its database reports 4.2.0 and the
  database update endpoint is blocked by the host trust store.
- `diversity_simpson` and `numeric_gini_coefficient` need the new reader, hence
  the library bump to 1.1.24.

## Reproducing

```
operon --workspace <ws> --data-dir <ws>/.studio run graph.json --brief --wait
```

The same graph is accepted by `POST /api/v1/jobs` (raw graph, `x-studio-token`)
and by the `operon_submit` MCP tool.
