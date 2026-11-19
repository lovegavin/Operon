# Operon Studio 5.7.7

## Added

- Resource downloads accept a list of mirrors. The download step tries each
  URL in order, discards partial files between attempts, and reports every
  failure when no mirror works (`download failed for <path>: <url>: <reason>`).
  Existing single-URL entries keep working unchanged.
- `openfold` and `boltz` now declare two mirrors each (the HF mirror first,
  `huggingface.co` second) and carry notes describing the ModelScope and
  Kaggle alternatives when both are unreachable.

## Fixed

- **F-79** Downloads aborted on the first unreachable mirror even when a
  second one would have worked. `resource_fetch` and the control API now walk
  the full candidate list and only fail after the last attempt.
- **F-80** AlphaFold 2 database names now follow the official 2.3.x flag
  defaults: `mgnify/mgy_clusters_2022_05.fa` and
  `pdb_seqres/pdb_seqres_2022_09_28.fasta`. Previously the manifest stored
  `mgy_clusters.fa` / `pdb_seqres.txt`, so `run_alphafold.py` could not find
  the files with its default `--mgnify_database_path` and
  `--pdb_seqres_database_path` values. The `uniref30` unit keeps the 2023-02
  release (`uniref30_2302.db.tar.gz`) instead of the 2021-03 snapshot named by
  the upstream script, and the manifest notes explain the difference.
- **F-81** The `alphafold2` unit file list still referenced the old file names;
  it now matches `expected_files`, so the missing-file report and the link
  check agree with what the operator actually reads.
- **F-82** Downloading `pdb_mmcif` produced a confusing error. The manifest now
  records that RCSB publishes this database over rsync only
  (`rsync.ebi.ac.uk::pub/databases/pdb/data/structures/divided/mmCIF/`) and the
  UI tells the user to link an existing copy instead of offering a download.

## Changed

- Resource manifest entries may now be either `"url": "https://…"` or
  `"url": ["https://…", "https://…"]`; the parser validates every candidate and
  keeps a single string when only one URL is declared.

## Library

- Library version 1.1.5 records the corrected database names and the mirror
  lists. No operator code changed in this release.
