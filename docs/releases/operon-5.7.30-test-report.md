# Operon 5.7.30 test report

Version 5.7.30 carries library 1.1.18. The changes in this build were driven by
the structure sweep: the Boltz operators could not produce a structure on the
compute host because they either downloaded weights on every run or needed an
MSA from the ColabFold web API, which the host cannot reach.

## Defects fixed in this build

| # | Symptom | Root cause | Fix |
|---|---------|-----------|-----|
| 1 | `boltz_predict` failed with `urllib.error.URLError: <urlopen error [Errno 104] Connection reset by peer>` | `cache_dir` defaulted to empty, so Boltz downloaded its checkpoints | `_default_cache()` resolves the `boltz` resource root and passes `--cache` (`023104f29`) |
| 2 | `boltz_predict` exited 0 but produced `no predicted structure` | no MSA: the default `msa_mode` is `server`, and `msa_mode: empty` gives Boltz nothing to align | new `msa_mode: local` builds an A3M with MMseqs2 from the `colabfold_msa` resource and writes `msa: <path>` into the YAML |
| 3 | local search could not start: `mmseqs` missing | the `colabfold` environment did not declare an MMseqs2 binary | `colabfold.conda_packages` now lists `mmseqs2` |

## Evidence

- Manual MMseqs2 run on the compute host against a Swiss-Prot database built
  from `uniprot_sprot.fasta` produced `msa` (A3M, 20 records) for
  `TTCCPSIVARSNFNVCRLPGTPEAICATYTGCIIIPGATCPGDYAN` (1CRN).
- Resource download speeds measured on the compute host (2026-11-22):
  `opendata.mmseqs.org` 2.9 MB/s (UniRef30) and 9.4 MB/s (environmental
  database); `wwwuser.gwdg.de/~compbiol/colabfold/` 38 KB/s. The manifest
  records this in the resource notes.
- `python -m py_compile` for `_msa_common.py`, `boltz_predict.py`.
- Catalog: 1074 operators, 108 readers, 79 routes, 0 errors.

## Sweep state at release time

The remote job store held 900+ jobs; `opcov_remote.py` counted 457 attempted
operators (42.6%) and 241 with at least one successful run (22.4%). The fields
that remain red are dominated by fixture prerequisites (single-sequence FASTA,
CDS DNA, real SBML models) and by operators that need offline databases
(antiSMASH `nrps_pks`, ColabFold API). Two product defects found by this sweep
are already fixed and shipped: the ESM-IF `<EOS>` token parsing (`08f3e4a54`)
and the wheel-URL dependency name (`2e73c6b7d`).

## Known limits

- The two ColabFold databases need 205 GiB compressed; the download is a
  long-running resource operation.
- MSA search runs on CPU through MMseqs2 (`-s 8`), which takes minutes for a
  full UniRef30 database.
- `vina` has no cp311 wheel and remains an optional binding; `prodigal` is
  built from source.
