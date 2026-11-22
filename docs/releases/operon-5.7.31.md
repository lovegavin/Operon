# Operon Studio 5.7.31

5.7.31 ships library 1.1.19. The library release hardens the local MSA path that
5.7.30 introduced and takes the two ColabFold databases out of the environment
dependency gate.

## Library

- **A3M files are written by MMseqs2 itself.** `_msa_common.build_msa()` now
  calls `mmseqs result2msa … --msa-format-mode 6` and reads the file it writes,
  instead of unpacking a profile database and looking for a numeric name. The
  helper also rewrites the file so the terminal NUL byte MMseqs2 leaves behind
  becomes a newline: Boltz parsed that byte as a residue and stopped with
  `KeyError: '\x00'`.
- **The database may live in a subdirectory.** `database_root()` searches the
  resource root and every direct subdirectory, so an archive extracted as
  `<root>/uniref30_2302/…` or `<root>/<archive>/uniref30_2302/…` both resolve.
- **`colabfold_msa` no longer gates environments.** The resource is 205 GiB of
  archives; declaring it under `envs` turned `boltz` and `colabfold` into
  `incomplete` for as long as the download ran. The resource now stands on its
  own: an environment stays ready without it, and only the operators that build
  MSAs locally report the missing database.

## Verification

- `python -m operon registry build --scope routes` keeps 1074 operators,
  108 readers and 79 routes with 0 errors.
- `python -m py_compile` passes for `_msa_common.py`.
- A Ubiquitin query against the Swiss-Prot stand-in database produced a
  269-record A3M through `build_msa()` on the compute host.

## Known limits

- The two databases are 205 GiB compressed in total; the panel shows the planned
  bytes before starting a download.
- An MMseqs2 search against the full UniRef30 database takes minutes on CPU.
- `boltz_predict` still needs a GPU for practical runtimes; the CPU reference
  path is supported but slow.
- `vina` remains an optional binding (`best_effort`) because no cp311 wheel
  exists, and `prodigal` is built from source.
