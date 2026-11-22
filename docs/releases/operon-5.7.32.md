# Operon Studio 5.7.32

Library **1.1.20**. This release closes three defects that a whole-population
sweep of the operator catalogue exposed: FASTA inputs the reader rejected,
isolated workers that could not start outside the `core` environment, and an
ESM-2 checkpoint that fair-esm could not load without a second file.

## Fixed

- The FASTA reader accepts `builtin` as a position label rule. Records carry no
  per-residue names, so `builtin` and `auto` mean the same thing (index the
  residues from `0`); the reader used to raise
  `unsupported label rule for 'position': 'builtin'` even though the reader's
  own default and the form editor both offered it. Every assembly, codon,
  antibody and AMR operator that reads a FASTA file was blocked by that refusal.
- Every environment declares `pydantic>=2.7`. An isolated step worker imports
  `operon.plugins` to rebuild the reader table, and that module's import chain
  reaches `operon_sdk.protocol`, which is a pydantic model module. Environments
  that did not list pydantic therefore failed during startup with
  `No module named 'pydantic'` before the operator ran; 18 operators across
  `core`, `hmmer`, `esm2`, `boltz`, `proteinmpnn` and `genomics` were affected.
- The `esm2` resource ships `esm2_t6_8M_UR50D-contact-regression.pt`. fair-esm
  loads that head unconditionally for every `esm2_*` checkpoint when it loads a
  local file, so a resource with only the model weights failed with
  `FileNotFoundError: ... -contact-regression.pt`. The file is 1,511 bytes and
  comes from the same `fair-esm/regression` directory the official hub loader
  uses.
- A broken server channel no longer waits forever. The call path reconnects a
  key profile once — and once more after a stale channel reports the break —
  and the `waiting_connection` loop now fails after
  `OPERON_DISCONNECT_SECONDS` (default 900 s) with an actionable message instead
  of holding its worker slot indefinitely. The same path serves the environment
  panel, so a stale connection no longer reports `connected: true` while every
  request answers `服务器未连接`.
