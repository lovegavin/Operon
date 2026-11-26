# Operon Studio 5.11.3 · Operator Library 2.1.4

This release fixes the two defects that surfaced while running a full
minibinder campaign through MCP, and makes ColabFold's MSA handling
explicit instead of implicit.

## Molecular dynamics works again on a deployed install

`structure_openmm_md_stability`, `structure_openmm_md_rmsf`,
`structure_openmm_energy`, `interface_mmgbsa_delta` and
`interface_alanine_scan` ship PDBFixer's residue templates as package
data (`_pdbfixer/templates/*.pdb`, `soft.xml`, `LICENSE`). The deploy
archive and the release packaging only carried `.py`, `.json`, `.md`,
`.sql` and image suffixes, so every installed or remote copy was missing
those files and the operators failed at start-up with
`[Errno 2] No such file or directory: …/_pdbfixer/templates`.

Both `operon/remote/provision.py` and `scripts/package_release.py` now
share one whitelist (`SEED_SUFFIXES` + `SEED_NAMES`) that keeps
`.xml`, `.pdb`, `.txt`, `.cif`, `.mmcif`, `.csv`, `.tsv`, `.yaml`,
`.yml`, `.npy`, `.npz` and `LICENSE`/`NOTICE`/`README`. Because the two
sides share one definition, a packaged tree and a provisioned tree can
no longer disagree about which data files count (the 5.11.2 dangling
`stale_build` class of problem).

## ColabFold can use an MSA server or a local database

`colabfold_predict` gains three parameters:

- `msa_host` — an http(s) MSA server; when set, `--host-url` is passed
  through. Malformed values fail before the predictor starts.
- `msa_databases` — the root that holds `uniref30_2302/` and
  `colabfold_envdb_202108/`; the operator derives `--db1`/`--db2` from
  it and enables the env database only when its MMseqs2 index exists.
- `msa_db1` / `msa_db2` — explicit database prefixes, for layouts that
  do not follow the ColabFold defaults.

The default stays `mmseqs2_uniref_env` against `api.colabfold.com`, so
nothing changes for callers that already had working network access. A
database prefix without `.dbtype`/`.index` now fails with a message that
names the missing index instead of hanging in the predictor.

## ProteinMPNN reads the resource tree the installer writes

Five ProteinMPNN operators searched `<resource>/vanilla_model_weights` and
relied on a hand-made symlink, because the downloaded tree kept the upstream
`ProteinMPNN/` wrapper while the manifest declared one. The resource manifest
now lists the unit files relative to the resource root and links the upstream
tree at that root, so a fresh install and a linked tree resolve the same
files. `_protein_common.proteinmpnn_layout()` accepts both layouts, and every
ProteinMPNN operator falls back to `OPERON_PROTEINMPNN_PATH` and then to the
installed resource when the parameter is empty.

The AlphaFold-2 resource manifest also named probe files that do not exist in
the downloaded tree (`bfd-first_non_consensus_sequences.fasta`,
`mgy_clusters.fa`); it now names the files the bundle really carries.

## Also in this build

- `msa_mode`, `msa_host`, `msa_databases` and the local-database layout
  are documented on the operator page instead of being discoverable only
  by reading the implementation.
- Deployment and release packaging keep every operator data file; only
  the nine route test fixtures (`.gmt`, `.loom`, `.h5ad`, `.vcf`, `.biom`)
  stay out of the archive.

## Compatibility

- Application 5.11.3 requires Operator Library 2.1.4.
- Workflows that pin the library keep working; `msa_host`,
  `msa_databases`, `msa_db1` and `msa_db2` default to empty, which
  preserves the previous command line byte for byte.

## Assets

- `Operon-Studio-v5.11.3-Windows-x64.zip` — desktop payload
- `Operon_Setup-5.11.3.exe` — installer
- `Operon-5.11.3-Server.zip` — Linux server bundle
- `operon_studio-5.11.3-py3-none-any.whl` — application wheel
- `operon-library-main-v2.1.4.operon-library.zip` — operator library
- `operon_builtin_library-2.1.4-py3-none-any.whl` — library wheel
- `Operon-Routes-v2.1.4.zip` — route collection
- `SHA256SUMS-5.11.3.txt`, `SHA256SUMS-library-2.1.4.txt`
