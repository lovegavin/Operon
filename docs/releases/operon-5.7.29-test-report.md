# Operon Studio 5.7.29 test report

Build: `source_commit` recorded in `release98`. Library `main-v1.1.17`
(7 packages, 1182 descriptors, 1074 operators, 79 routes).

## What changed and how it was verified

| Surface | Change | Evidence |
| --- | --- | --- |
| MCP upload | `operon_upload_file` streams any size instead of a 50 MiB base64 body | `tests/test_workspace_upload.py` writes 3 chunks of 4 KiB, compares sha256, then posts a 6 MiB body through `/api/v1/workspace/files/raw` and compares the stored bytes |
| MCP upload safety | absolute paths, `..`, drive letters and `.studio` are rejected | same file, four cases, all `422 invalid_path` |
| MCP figure | `operon_job_figure` downloads the rendered step figure | route already served by `control_api.figure`; the tool reuses `_download_target` with `format`/`figure_id` |
| Parity guard | `api.ts` methods are all classified again | `test_mcp_parity.py` passes with 109 pinned methods, `preferences` and the two resource cancels mapped |
| Boltz environment | `pydantic>=2.7` declared | `library/seed/operon/environments.json`; `import pydantic` false before, true after a fresh prepare |

## Suites

- `pytest tests/test_workspace_upload.py tests/test_task_files.py -q` → 32 passed.
- `pytest tests/test_mcp_parity.py tests/test_parity_control_plane.py tests/test_workspace_upload.py -q` → 73 passed.
- `pytest tests/test_environment_optional_counts.py tests/test_remote_environment_snapshot.py tests/test_execution_plan.py -q` → 62 passed.
- Frontend: `npm test` (44 files, 287 tests) runs inside the packager before the
  Vite bundle is produced.

## Operator sweep (server side, MCP only)

The sweep submits every generated case through `operon_submit` against the
licensed server (`licai-srv`), with `runtime.execution.max_parallel_tasks`
raised so a batch is not serialized. Cases use real open data: 1CRN/1UBQ/1L2Y
structures, GTEx and PBMC matrices, ClinVar chr21 VCF, chr21 GFF3/BED,
E. coli reads, BiGG `e_coli_core` SBML, plus derived Newick/MatrixMarket/BIOM
fixtures.

Results are recorded per case in `runs/fmt_*.csv` with the data path, status,
error text and wall time, and summarised in `FMT-SWEEP.md`. Failures are
classified as fixture precondition, environment or external tool, product
defect, or offline-unavailable source.

## Known limitations

- `vina==1.2.5` has no cp311 wheel and does not build from source on CentOS 7
  (glibc 2.17, g++ 4.8.5). It stays an optional binding; conda-forge carries
  `vina 1.2.5 py311` but installing it drags five downgrades, so it is left to
  the operator.
- `prodigal/prodigal` is built by `make`; the resource panel reports it as not
  downloadable instead of pretending it is a file.
- Several operators need offline databases (Pfam, antiSMASH clusters, AMRFinder
  database). Those runs are classified as offline-unavailable rather than
  failed.
