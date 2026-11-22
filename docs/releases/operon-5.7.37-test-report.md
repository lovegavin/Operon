# Operon Studio 5.7.37 acceptance report

## Scope

The release carries two runtime fixes found while running every operator in library 1.1.23
against the licai-srv server. No library content, operator code or environment declaration
changed, so the 19 prepared environments and the 1.1.23 operator catalog still apply.

## What was verified

- **Source-less graphs reach the target server.** A graph whose only node is an operator
  that takes its inputs as parameters (`runtime.execution` = ssh target, no file source)
  used to be classified as a local graph, handed to the shared pool and rejected with
  `503 engine_unavailable`; the new classification keeps the explicit target. Unit tests
  in `tests/test_execution_applies.py` cover the four cases (explicit remote with no
  source, explicit local with no source, source-located graph, child execution).
- **Job listing stays cheap.** `ExecutionService.history()` now builds each entry from the
  job record instead of composing a full detail view (64 KiB console tail plus a lock and
  result read per child unit). On the acceptance instance with ~900 recorded jobs a
  `GET /api/v1/jobs` call returned 22.8 MB and blocked the server for seconds; the summary
  path keeps `/api/bootstrap` and the environment snapshot responsive during sweeps.
- **Environment and library unchanged.** 19 of 19 environments ready, library 1.1.23 with
  1074 operators / 108 readers / 79 routes.

## Known gaps

- `amrfinder_plus` needs the AMRFinderPlus 4.2.5 database matching its binary; the hosted
  update endpoint is not reachable from this server, so the operator is exercised only with
  the database already on disk.
- `align_reads.reference_fasta` still requires a real reference FASTA that this offline
  environment does not ship.
- The protein language-model operators (`nucleotide_transformer_*`,
  `ligandmpnn_side_chain_packing`) have no offline weights in this environment and are
  documented as such rather than reported as operator defects.
