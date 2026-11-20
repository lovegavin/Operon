# Operon Studio 5.7.18

Released 2026-11-20. Library `1.1.12` ships in the same release.

## Added

- Physical-machine isolation in the runtime panel. When a remote target is
  selected, every runtime field on the environment, dependency and resource
  cards comes from that machine's snapshot; local metadata is only used for
  static catalogue fields (`title`, `notes`, `planned`, `operator_count`,
  `operators`, `expected_bytes`) and never for state, interpreter, location,
  progress, size or dependency flags.
- Three-state dependency badges (`installed`, `not installed`, `unknown`) so a
  row without a flag is no longer rendered as missing.
- `POST /api/resources/{name}/download` accepts a unit name and downloads only
  the files of that unit that are still missing.

## Changed

- `ArtifactService.list()` tolerates legacy report entries without an
  `artifact_id`; a single malformed descriptor no longer fails the whole job
  artifact index with a 500.
- A unit whose declared files match resource downloads by path now reports
  them as downloadable even when the unit/resource keys differ, so AlphaFold2
  shows its eight sources instead of "no download source".

## Fixed

- F-120 Remote dependency rows were taken from the desktop, producing
  "ready + numpy not installed" on a remote card.
- F-121 Dependency badges rendered a missing flag as "not installed".
- F-122 AlphaFold2 unit rendered as having no download source.
- F-123 `/api/v1/jobs/{id}/artifacts` returned 500 for jobs whose report
  carried descriptors without `artifact_id`.
- F-124 `pairwise_alignment` rejected the documented two-port single-form
  wiring and reported a self-contradictory row count.
- F-125 `variant_consequence` raised a bare `KeyError('chr1')` instead of
  naming the missing FASTA sequence.
- F-126 `prodigal_genes` treated a data file as an executable and ignored the
  binary installed in its declared environment.

## Verification

Clean install on Windows: 20.4 s, version `5.7.18 (e70aedfc)`, library
`main-v1.1.12` (1,074 operators / 1,182 descriptors / 7 packages / 108
readers), 18 environments, 141 MCP tools, 22/22 interface checks passing and
the six installer actions (prepare, cancel, retry, dependency install, resource
download, log) answering 200. See `operon-5.7.18-test-report.md`.
