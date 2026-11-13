# Operon Studio 5.1.6

This patch restores the isolated-environment manifest that 5.1.5 failed to
materialise in an installed application, and exposes environment preparation
progress to the API and the runtime panel.

## Fixed

- Imported libraries now persist `environments.json` beside the installed
  library (`library/environments.json`) and per branch
  (`library/libraries/<label>/environments.json`). The root file is a composed
  union of every installed branch, so `main` and `fork1` can declare different
  environments without losing either set.
- `environments.manifest_path()` treats a missing source tree, `None`, and the
  literal string `"None"` as "no source tree" and falls back to the installed
  library manifest. Previously `str(service.plugins.source_root)` produced
  `"None"`, which resolved to `operon/_no_library/operon/environments.json` and
  made every isolated environment look undeclared.
- Environment preparation jobs started through the application API are now
  returned by `/api/environments` and `operon_environments` as `operations` with
  job id, name, status, error and live progress. A job id returned by
  `operon_environments_prepare` can be polled instead of disappearing.
- Startup backfills per-branch manifests from each branch `archive.zip` and
  recomposes the root manifest for libraries imported by 5.1.5, so no reinstall
  is required. Uninstalling a branch recomposes the root manifest and drops its
  declarations.

## Compatibility

- No protocol, bundle, job, route or provenance changes.
- `bundle_format=1`, `operator_protocol=3`; library bundles 0.0.0/0.1.0 and the
  fork1 bundle remain compatible.
- Existing jobs and run skeletons are unchanged; no repinning is required.
