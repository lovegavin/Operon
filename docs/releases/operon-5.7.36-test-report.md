# Operon Studio 5.7.36 — acceptance report

## What this build contains

| Change | Commit | Evidence |
|---|---|---|
| Unbounded parallelism (`parallel_tasks: 0`) + `operon_submit_many` / `operon_jobs_many` | `ec5a8bf5b` | 67 tests across the preference, MCP, admission and execution suites |
| BED interval roles accept `chromStart`/`chromEnd` | `ffff91052` | annotation/peak routes read a BED form without a column error |
| A shared resource no longer downgrades a ready environment | `130bd34ec` | 17 tests in `test_environment_api`, `test_environment_resources`, `test_remote_environment_snapshot`, `test_environment_optional_counts` |
| `psutil>=5.9` declared by 17 environments | `ec5a8bf5b` | bridge steps start in `genomics`, `rna`, `dssp`, `hmmer` and the design environments |

## Environment and resource state (licai-srv)

- 19 environments installed and ready; 20 resource directories present.
- `vina` now ships as a downloaded binary resource (4,089,576 B) instead of a pip
  dependency that has no cp311 wheel.
- Real data used by the census lives under `/public/home/lihj/Operon/workspace/rt/data`
  and `/public/home/lihj/Operon/workspace/p6/{fixtures,fmt,gen}`; the MSA databases
  download from `https://opendata.mmseqs.org/colabfold/` (uniref30_2302 95.8 GiB,
  colabfold_envdb_202108 109.9 GiB).

## Operator census

- Catalog: **1074 operators**, 108 readers, 79 routes; `registry build --scope routes`
  reports 0 errors.
- Coverage counted from every recorded run (`<workdir>\p6\runs\*.csv`, 966 distinct
  cases, 950 attempted): **592 operators have completed at least once (55.1 %)**.
- Families closed tonight with real fixtures: distance/group operators (46/46),
  2×2 table families (19/19), sequence families including codon, peptide, assembly,
  MSA, phylogeny, HMMER, foldseek and GO (29/29 → 25 operators).
- Remaining non-completions are classified in `<workdir>\p6\DEFECTS.md` and
  `<workdir>\p6\CLASSIFY.md`: fixture semantics first, then environment/tool gaps,
  then a small number of product findings.

## Known gaps (recorded, not silently dropped)

- `nucleotide_transformer_embedding` / `nucleotide_transformer_variant_effect`
  need checkpoint files that are not downloadable offline.
- `ligandmpnn_side_chain_packing` needs `sc_checkpoint` weights that are absent.
- `align_reads.reference_fasta` in the generated case is a placeholder value.
- Six skipped cases need three-dimensional pose collections, Hi-C pairs or real
  embeddings and cannot be built from the available open data.
- `hmmer_domains` requires a pressed Pfam database; the operator reports the
  parameter instead of guessing.
