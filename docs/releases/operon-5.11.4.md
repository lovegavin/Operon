# Operon 5.11.4

Released 2026-11-27. Application 5.11.4, bundled operator library 2.1.5.

5.11.4 fixes the defects that made the first real binder campaigns produce useless
designs, and adds a direct path from a native (jackhmmer) alignment into ColabFold.
It ships the same operator surface as 5.11.3 plus the fixes below.

## Defects fixed

### Library

- **D-35, chain extraction dropped coordinates.** `structure_convert_format` and
  `structure_extract_chain` resolved coordinate columns by exact name only. mmCIF
  tables name them `Cartn_x/Cartn_y/Cartn_z`, so the lookup fell through, the last
  column (occupancy, constant 1.0) was taken for x, y and z, and every extracted
  atom landed on `1.000 1.000 1.000`. The collapsed target made RFdiffusion build
  binders tens of angstroms away from the target, ProteinMPNN then designed
  poly-alanine/poly-glutamate homopolymers on the all-glycine placeholder backbone,
  and single-chain ColabFold reported pLDDT above 90 for them. `column_index()` now
  matches case-insensitively through an alias table (mmCIF and PDB names both work)
  and raises when a required column is missing instead of silently using the last
  one. `tests/test_structure_columns.py` pins the real coordinates.
- **D-31, local ColabFold databases were refused.** `colabfold_predict` refuses to
  pass `--db1/--db2` to `colabfold_batch` (it does not accept them) and now runs
  `colabfold_search` first, with the documented positional arguments, `--use-env 0`
  when no environmental database is given, and an explicit error when the database
  is missing `_h/_seq/_aln` components.
- **D-32/D-33, one design, several sequences.** `colabfold_predict` gained
  `sequence_index` so a ProteinMPNN design with `num_seq_per_target > 1` can be
  folded one sequence at a time; the index is read before the sequence is resolved.
- **New `msa_a3m`.** An alignment produced elsewhere — for example by the native
  `alphafold2_msa_search` (jackhmmer against the existing AF2 databases) — can be
  handed straight to `colabfold_batch`, skipping ColabFold's own search. This is
  the recommended route on hosts that already carry the AlphaFold2 reference
  databases: no MMseqs2 index has to be built.

### Remote execution

- **D-36, long jobs were declared failed.** The remote client used a 100 s response
  timeout for every RPC, so a four-design RFdiffusion run (about eleven minutes
  without progress frames) failed client-side while the worker kept running. The
  `run` method now waits up to 1800 s.
- **D-21, the RPC daemon exited mid-job.** The daemon counted only in-process work
  as activity, so a job running in the managed pool left it idle for 300 s and it
  exited; the next poll had to cold-start it inside a 60 s window. Active jobs now
  count as work, the idle window is 1800 s and daemon start-up may take 150 s.
- **D-20, stale build identity after connect.** `provision` recomputes the digest
  and identity from the uploaded archive before comparing it with the expected one,
  and retries once, instead of failing forever with "the local program changed after
  connecting".
- **Pool guard.** Crashed jobs no longer block a new build: a `running` job counts
  as active only while its execution identity is alive, and `recovery_required`
  no longer blocks.

### CLI, HTTP and MCP

- **D-37, `operon_jobs` returned full graphs.** The MCP tool now projects job rows
  (id, name, status, progress, timestamps, error) instead of embedding every graph
  and provenance record; `operon_job` remains the way to inspect one job.
- **D-22, exported files were rejected.** `export_results` copies Form-backed files
  natively and no longer requires `info.representation == "exported_files"`.
- **D-26, MCP reads and writes used host paths.** Text/binary writes and relative
  source paths resolve against the remote workspace when the profile is remote.
- **D-23, dry runs were judged with the local catalog.** Preflight now asks the
  remote service, so a remote-only operator is not reported as missing a dry run.
- **D-24, oversized MCP payloads.** Job and artifact listings are bounded.

### Deployment

- **D-8/D-10, deploy digests.** The source archive excludes test fixtures the same
  way the release packager does, members are sorted, and the digest is computed on
  the canonical tar so a tree has the same identity on Windows and Linux.
- **D-9/D-34, path parameters.** `proteinmpnn_design` accepts a wired
  `structure_path`, and `mmseqs_path` is classified as a tool path.
- **Data files.** PDBFixer templates (`templates/*.pdb`, `soft.xml`, licences) are
  shipped; without them the MD steps fail before running.

## Notes

- `alphafold2_msa_search` needs the `alphafold2` isolated environment (conda:
  `hmmer`, `hhsuite`, `kalign2`, `openmm`, `pdbfixer`). Prepare it once with
  `operon_environments_prepare(names=["alphafold2"])`; the reference databases are
  read from `data_dir` (default `OPERON_ALPHAFOLD2_DATA`).
- The ColabFold MMseqs2 index for UniRef30 is roughly a terabyte on disk and is
  *not* required for the native MSA route.
- Two binder campaigns (IL-7Rα and GLP-1R) completed end to end through MCP on
  5.11.3. Their designs predate D-35 and are kept only as regression evidence.
