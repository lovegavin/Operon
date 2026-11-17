# Operon Studio 5.5.0

Released 2026-11-18.

This release links existing copies of large resources and model weights instead of
copying them, rebuilds the runtime status panel, makes environment preparation
cancellable, and fixes the resource endpoints that failed on every 5.4.x install.
It ships operator library `main-v0.1.29`, which restores three isolated
environments the previous library bundle had dropped and adds the resource
fetch/link helpers the application needs.

## Added

- **Link a local copy of a large resource.** `POST /api/v1/large-resources/{name}/link`
  (and `DELETE` on the same path) point a resource root at an existing directory
  or file with a junction, symlink or hardlink, so weights that already live on the
  machine are not duplicated. Linking is idempotent (`already_linked`), refuses to
  overwrite an unmanaged directory with `409`, requires the source to sit under a
  declared `link_roots` entry, rejects relative paths and `..`, probes the link
  through a read of the first expected file, and records a receipt under
  `<resources>/.receipts/receipt-<id>.json`. MCP exposes the same operation as
  `operon_resource_link` / `operon_resource_unlink`.
- **`resources.json` describes downloads and link sources.** Each resource may
  declare `downloads` (URL, relative path, size, checksum), `expected_files`
  (checked after linking) and `link_roots`; the manifest may declare shared
  `link_roots`. `GET /api/resources` now reports `linked`, `source`, `mode`,
  `size_bytes`, `expected_files` and a real `used_by` list derived from the
  operators that read the resource.
- **`ResourceFetch` operator** in the library: downloads the declared files of one
  resource into a target root and reports what was written.
- **Runtime status panel rebuilt.** One card per isolated environment with title,
  notes, installed size, Python version, last update, the number of operators that
  depend on it, in-flight operations with phase and byte counters, an inline log
  drawer, and a cancel action. The panel adapts to narrow windows and follows the
  light/dark theme.
- **`POST /api/environments/{name}/cancel`** stops a preparation cooperatively and
  records it as `cancelled` rather than as a failure.
- **Installer notice for a substituted directory.** When the chosen directory
  already holds other content the installer still installs into `Operon` below it,
  but now says so in the log (and on the console) instead of nesting silently.

## Changed

- Operator library `main-v0.1.29`: 7 packages, 1069 operators, 108 Readers and
  1177 descriptors, plus seven isolated environments (`antifold`, `boltz`,
  `colabfold`, `esm3`, `esmfold`, `openfold`, `openmm81`).
- `operon_operator_search` retries with a coverage-ranked match when an all-term
  match finds nothing, so a query like `describe table summary` no longer returns
  zero results.
- The MCP server reports the product version in `initialize` instead of the SDK
  version.
- `GET /api/environments` adds `title`, `notes`, `size_bytes`, `python_version`,
  `updated_at` and `used_by_count`; operations carry `cancelable`, `phase`,
  `detail`, `bytes`, `files` and `updated_at`.

## Fixed

- **Large resources were unusable on every 5.4.x install.** The application
  imported `operon_core.steps.resource_fetch`, which the shipped library did not
  contain, so `GET /api/resources` and `GET /api/v1/large-resources` answered 500.
  The library now ships the module, and a library that predates linking is reported
  as `link_unsupported` (501) instead of failing the listing.
- **Windows junctions were invisible.** Python 3.11 has no `Path.is_junction`, so a
  linked root was reported as "not a link": relinking the same source failed with
  `source must not be the resource root or contain it` and unlinking failed with
  `target is not a link; refusing to delete it`. Detection now uses the reparse
  tag, unlinking returns `unlinked`, and relinking is idempotent.
- `POST /api/v1/large-resources/{name}/download` returned 500 for an invalid root;
  it now returns `409 resource_rejected`.
- `operon_job` swallowed every exception, could report another endpoint's error,
  and turned an unknown id into a generic internal-failure message. Unknown ids now
  return `unknown_job` with status 404, and `operon_result_files` agrees.
- `POST /api/environments/prepare` answered `500 RuntimeError: no running event
  loop` because it scheduled work with `asyncio.create_task` from a thread-pool
  handler.
- **Cancel did not cancel.** The operation was marked `cancelled` while the install
  kept running, replaced a working environment, and later completed as `ready`; a
  cancelled `micromamba` run was persisted as `... exited with 15`. Cancellation is
  now cooperative: the child process is killed, the staging directory is removed
  with retries, `finished_at` is stamped, and no error file is written.
- `{"names": ["openmm81", "nope"]}` answered 404 but still started `openmm81`;
  unknown names now reject the whole request.
- Operations synthesised from progress files reported `finished_at: null` after
  they stopped; the last progress timestamp is now used.

## Verification

A clean install from the release installer produced a flat managed layout
(`bin`, `current`, `versions`), reported `5.5.0` from `GET /api/version`, loaded
library `main-v0.1.29` with 7 packages, 1069 operators, 108 Readers and 1177
descriptors, declared all seven isolated environments, and listed all sixteen
large resources with their download and link metadata. The link round trip
(`linked` → `already_linked` → `unlinked` → relink) passed on Windows, joining a
real directory with a junction and leaving the source untouched. Cancelling a
preparation left no staging directory, no error file and a `cancelled` operation
with a finish stamp. See `docs/releases/operon-5.5.0-test-report.md` for the full
evidence, including the backend suite, the MCP analysis paths and the defects that
remain open.
