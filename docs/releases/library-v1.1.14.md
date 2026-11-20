# Operon Operator Library v1.1.14

Base application: **5.7.20** (minimum and build application). The library keeps
its own version; installing it does not require a new Studio build.

## Resource declarations

- **git sources** for `ligandmpnn`, `colabfold`, `rfdiffusion`, `prodigal` and
  `openfold`; the downloader clones them shallowly, keeps the checkout free of
  `.git` metadata and marks the copied files writable.
- **https mirrors** for `proteinmpnn`: `cdn.jsdelivr.net` first, then
  `ghproxy.net`, then `raw.githubusercontent.com` (the last one is unreachable
  from some hosts).
- **antismash** and **amrfinder** now declare direct https files instead of
  relying on a manual copy.
- **AlphaFold DB** (`afdb`) is declared in its released, unpacked layout (18
  files across bfd, pdb70, pdb_seqres, params, pdb_mmcif, uniref90, uniref30,
  mgnify and uniprot); `pdb_mmcif` stays on `rsync://rsync.wwpdb.org:33444`.
  Archive downloads without a `member` now unpack the whole tree.
- **Rfam** moves to `15.1/Rfam.cm.gz`; `cmpress` indexes remain generated on the
  host.
- **ColabFold** `roots` start with the writable
  `~/.local/share/operon/resources/colabfold`; `/usr/local/bin` is a read-only
  fallback.
- **Prodigal** `roots` follow the same order so a binary built with `make` can
  be linked.
- **Hugging Face** downloads prefer `hf-mirror.com` and fall back to
  `huggingface.co`.

## Environments

- `genomics` installs `flye=2.9.5=py311*`; bioconda ships a cp311 build for it,
  while 2.9.3 only had py310.
- `core` pins `econml==0.16.0` and `lightgbm==3.3.5`. `econml` 0.17 requires
  `lightgbm>=4.5.0`, whose x86_64 wheels need glibc 2.28; on a glibc 2.17 host
  the sdist cannot be compiled, so the pin keeps the environment installable
  with wheels only.
- `openmm81` keeps `setuptools<81`, `openmm==8.1.1` and the bundled PDBFixer.

## Dependency accounting

- A virtual environment created with `--system-site-packages` now counts the
  packages it inherits from its base interpreter, so `wheel` and `setuptools`
  are no longer reported missing.
- A project declared in both `requirements` and `pip_wheels` is counted once.

## Limits

- `Rfam.cm.i1*` and the `prodigal` binary have no upstream download; they are
  produced on the host (`cmpress`, `make`) and then linked.
- `uniref30` has no reachable mirror besides the primary host, which rate-limits
  large downloads.
- Conda-only environments stay unavailable on Windows and macOS.
