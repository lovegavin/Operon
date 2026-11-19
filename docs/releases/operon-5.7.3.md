# Operon Studio 5.7.3

Released 2026-11-19. This release gives every bundled resource a declared
download source and makes preparation progress honest.

## Added

- Every resource in the bundled library now declares downloadable files:
  model weights, databases and source checkouts. The two large AlphaFold-2
  mirrors that are only distributed over rsync (`pdb_mmcif/mmcif_files`) stay
  link-only and are reported as such.
- Unit cards show how many declared files can be downloaded
  (`下载可用文件（1/9）`) and how many have no HTTP source
  (`无下载源`), with a note listing the link-only files.
- Preparation progress shows the elapsed time next to the phase label and
  keeps moving while dependency installation continues after the download.

## Changed

- `POST /api/environments/prepare` accepts `names` and the `environments`
  alias, and rejects unknown fields with 422 instead of silently preparing
  every environment.
- Unit downloads only fetch the missing and not-yet-linked files; existing
  files are reported as `existing` unless `overwrite` is requested.

## Fixed

- F-58: the progress bar was capped at 99% for environments whose install
  continues after the download finished; the indicator is now indeterminate
  with a running elapsed time.
- F-59: a unit that only declared a project page URL used to save the HTML
  page as the resource file; such units are now rejected with an actionable
  message.
- F-60: unit-level coverage was computed against the link unit name instead of
  the manifest unit name, so downloadable files never showed up.

## Notes

- `operon environment status <name>` still resolves against a workflow
  directory.
- The AlphaFold-2 environment is a shell environment; point `runner` and
  `python_executable` at a local checkout, or export `OPERON_ALPHAFOLD2_HOME`.
