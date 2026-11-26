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

## Running two minibinder campaigns through MCP

The release was verified by driving two complete campaigns (IL-7Rα / 3DI3 and
GLP-1R / 6X18) through the MCP surface only: read the structure, extract the
target chain, design four backbones with RFdiffusion, redesign each backbone
twice with ProteinMPNN, fold every sequence with ColabFold and export both the
complex models and the FASTA records. Fourteen defects surfaced and are fixed
here.

- **D-20** — `remote_install` compared the build it computed during `provision`
  with the build captured when the client connected, so a first MCP call that
  refreshed the catalog made every install fail with "the local program changed
  after connecting". Provision now recomputes the identity from the uploaded
  archive and retries once when it drifts.
- **D-21** — the RPC daemon counted only its own workers when deciding whether
  it was busy, so a job running inside the shared pool looked idle and the
  daemon exited after five minutes; a long RFdiffusion run then failed with
  "the remote service could not be restarted". `alive()` now also treats a job
  in `queued`, `preparing`, `uploading`, `running` or `waiting_connection` as
  work, the idle default moved to 1800 s and the cold-start window to 150 s.
- **D-22** — `export_results` only copied values that declared
  `info.representation == "exported_files"`, so a normal design form failed
  with "export_results requires a value with …". It now copies any form that
  names a file on disk.
- **D-23** — `operon_workflow_prepare` validated dry-run operators against the
  local catalog, which cannot know the remote plugin lock; validation now runs
  against the submitted route.
- **D-24** — `operon_jobs` and `operon_artifacts` returned multi-megabyte JSON
  that overflowed the model context. Text payloads are capped at 60 KB and
  tables page at 50 rows.
- **D-25** — the prepare view showed the overwritten parent graph instead of
  the graph that was validated.
- **D-26** — MCP text writes, binary writes and relative source paths were
  joined against the host workspace even when the profile was remote, creating
  files in the wrong place. `src/web/remote_api.py` now resolves those writes
  against the remote workspace.
- **D-27** — ColabFold's MSA options were placed in the environment dictionary
  but never exported by the generated `env.sh`, so `msa_databases` and
  `msa_host` were silently ignored. The wrapper now exports
  `OPERON_COLABFOLD_MSA_DATABASES`, `OPERON_COLABFOLD_MSA_DB1`,
  `OPERON_COLABFOLD_MSA_DB2` and `OPERON_COLABFOLD_MSA_HOST`.
- **D-28** — deployed installs dropped PDBFixer's templates, `soft.xml` and
  `LICENSE` because the archive whitelist only kept code and JSON; the
  whitelist now carries every operator data file (see above).
- **D-29** — `proteinmpnn_design` called `resolve_proteinmpnn_path` without
  importing it, so every design step died with `NameError`; a test now checks
  that each step imports the helpers it calls.
- **D-30** — the ColabFold input contract demanded `sequence`/`position`
  dimensions and `info.representation`, which no design step produces, so the
  canonical RFdiffusion → ProteinMPNN → ColabFold edge was rejected before the
  operator ran. The contract now accepts designed sequence lists and the
  resolver raises a clear error when a design carries several sequences.
- **D-31** — `colabfold_batch` has no `--db1/--db2`; passing them aborted with
  "unrecognized arguments". The operator no longer forwards database flags to
  the batch runner and explains that a local search needs `colabfold_search`.
- **D-32** — a design with `num_seq_per_target > 1` could not be folded because
  the operator always took the whole list. `colabfold_predict` gains
  `sequence_index` (default 0) so a route can fold one chosen sequence.
- **D-33** — `sequence_index` was read after it was used, raising
  `UnboundLocalError` at the first fold; it is read once at the top of `run()`.
- **Pool guard** — a crashed job stayed in `running`/`recovery_required` state
  and every later build switch answered "finish tasks before changing its
  application". Only jobs whose worker tree can still be reached now count as
  active.

Both campaigns finished 26/26: four backbones per target, two sequences per
backbone, eight folds and twelve artifacts each. Binder-only folding (the
offline MSA index was not ready) gave mean pLDDT 90.1–97.8 for 3DI3 and
92.8–96.3 for 6X18.

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
