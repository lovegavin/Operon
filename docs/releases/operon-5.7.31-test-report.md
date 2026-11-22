# Operon 5.7.31 test report

Version 5.7.31 carries library 1.1.19. The changes close the two failures the
5.7.30 local-MSA path hit on the compute host: MMseqs2 writing its alignment to
a different file than the helper expected, and the terminal NUL byte that made
Boltz abort while parsing the alignment.

## Defects fixed in this build

| # | Symptom | Root cause | Fix |
|---|---------|-----------|-----|
| 1 | `mmseqs result2msa failed: No datafile could be found for …_db_h!` | `result2msa` reads the header database, and a database assembled by hand (or extracted under a subdirectory) does not always ship the `_db_h` triple next to `_db` | `database_root()` accepts the database in the resource root or one level below; `mmseqs search` and `result2msa` receive the same resolved prefix |
| 2 | `build_msa()` reported `MSA search produced no alignment` although MMseqs2 succeeded | the helper unpacked a profile database and looked for `<name>.a3m`, while `result2msa` writes the alignment directly | `build_msa()` runs `result2msa <qdb> <db> <res> <out> --msa-format-mode 6` and returns that file |
| 3 | `boltz_predict` failed with `KeyError: '\x00'` inside `boltz/data/parse/a3m.py` | `--msa-format-mode 6` terminates the last record with a NUL byte, which Boltz read as a residue | the helper replaces `\x00` with `\n` before returning the alignment |
| 4 | `boltz` and `colabfold` stayed `incomplete` for hours with `资源未备齐 1/3（uniref30_2302、colabfold_envdb_202108）` | the 205 GiB `colabfold_msa` resource was declared under `envs`, so a long download blocked two environments | the resource no longer gates an environment; the operators that need it report the missing database themselves |

## Evidence

- Manual MMseqs2 run on the compute host against a Swiss-Prot stand-in for
  UniRef30: `createdb`, `search -s 8 --max-accept 5000` and
  `result2msa --msa-format-mode 6` produced a 269-record A3M for Ubiquitin
  (`MQIFVKTLTGKTITLEVEPSDTIENVKAKIQDKEGIPPDQQRLIFAGKQLEDGRTLSDYNIQKESTLHLVLRLRGG`).
  The file ends with one NUL byte, which the helper now replaces.
- `python -m py_compile` for `_msa_common.py`; catalog: 1074 operators,
  108 readers, 79 routes, 0 errors.
- The `colabfold_msa` units record both archives with their exact byte sizes
  (102,918,187,842 B and 117,965,643,010 B) and the download host
  `https://opendata.mmseqs.org/colabfold/`; the previous host served 38 KB/s,
  the current one 2.9–9.4 MB/s.

## Sweep state at release time

The remote job store held 1,050 jobs (605 failed, 441 complete) and the format
sweep continues to add rows. Two product defects the sweep reported are fixed in
this build or the previous one: the ESM-IF `<EOS>` token parsing (`08f3e4a54`)
and the wheel-URL dependency name (`2e73c6b7d`). The failures that remain are
dominated by fixture prerequisites: `FastaReader` accepts `position: auto` or an
explicit map but not `builtin`, so every single-sequence FASTA case has to drop
that rule; CDS DNA and real SBML models are still missing from the fixture set.

## Known limits

- The two ColabFold databases need 205 GiB compressed; the download is a
  long-running resource operation.
- MSA search runs on CPU through MMseqs2 (`-s 8`), which takes minutes for a
  full UniRef30 database.
- `vina` has no cp311 wheel and remains an optional binding; `prodigal` is
  built from source.
