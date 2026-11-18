# Operon Studio 5.6.4

This release fixes the resource and environment defects that surfaced while exercising
Operon Studio 5.6.3 end to end, and completes the card runtime that 5.6.3 introduced.

## Added

- Downloading a single official unit now works for weight and database resources. When a
  resource declares only `units[].url`, the download job resolves that unit URL into a
  transfer and records the usual progress, cancel and log surfaces.
- Remote downloads exist as first-class API: `POST /api/remote/{key}/resources/{name}/download`
  forwards to the remote agent, and the MCP `operon_resource_download` tool accepts
  `profile_id`.
- `/api/v1` aliases for environment retry, cancel, log and dependency download so MCP and
  CLI clients reach the same handlers as the desktop routes.
- `operon_job` and `operon_result_files` accept the `id` alias in addition to `job_id`.
- CLI `environment install|cancel|status <name>` accept bare environment names; previously
  the first positional argument was always parsed as a workflow file.
- CLI mutating commands request the `plugins` capability, so `resources link|unlink|download`
  and `environment install|cancel` no longer fail with a capability error.
- Workflow JSON files written by PowerShell (UTF-8 with BOM) load correctly.
- Conda packages resolve against the channel that publishes them: HMMER, Infernal, Prodigal,
  AMR FinderPlus and antiSMASH install from `bioconda` in addition to `conda-forge`.

## Changed

- Environment detail is a card hierarchy: two entry cards (dependencies, resources), then one
  card per dependency or official unit. Each level carries its own download action in the
  top-right corner, and no table is used anywhere.
- The environment entry card reports the number of official units, not the number of
  resource ids.
- Modal dialogs scroll when their content is taller than the viewport.
- Resource headers place refresh and download actions on the right.

## Fixed

- F-39 A resource with only unit URLs reported `resource has no downloadable files` for every
  unit download.
- F-40 Remote unit downloads returned 404 because the remote router had no download route and
  the agent had no `resources_download` dispatch.
- F-41 The environment resource entry card counted resource ids, so a three-unit resource read
  as one.
- F-42 `.runtime-resources-header` had no layout rule, which left the group actions on the
  left instead of the top-right.
- F-43 A detail modal taller than the viewport could not scroll.
- F-44 Unit cards still printed the download URL, which the card layout no longer needs.
- F-45 `environment install|cancel|status <name>` failed with `No such file or directory`.
- F-46 CLI resource and environment mutations failed with a plugin capability error.
- F-47 `workflow validate` rejected UTF-8 BOM files.
- F-48 HMMER-family environments were unsolvable because the installer pinned `conda-forge`
  with `--override-channels` while those packages live on `bioconda`.

## Verification

- Clean install of the packaged setup on Windows 11, headless server on a fresh data
  directory: `/api/version` reports `5.6.4`, `/api/libraries` reports `main-v1.0.3`
  with 7 packages, 1,177 descriptors, 1,069 operators and 108 readers.
- `/api/environments` lists 18 environments covering 1,177 assigned operators; `/api/resources`
  lists 16 resources with 16 official units.
- `POST /api/v1/environments/{name}/retry` and `.../cancel` answer `200`; an unknown
  environment still answers `404` and an unknown resource `422 unknown_resource`.
- Unit download of `antifold` starts a job (`200`, `phase=starting`), and cancel restores the
  environment to `missing`.
- MCP `operon_environments_cancel`, `operon_job {"id": ...}` and `operon_result_files {"id": ...}`
  answer with their documented semantics instead of 405 or a quoting error.
- CLI `environment status hmmer`, `environment cancel hmmer` and `environment install hmmer`
  reach the service; a workflow file with a BOM validates.
- Browser sweep of the runtime panel: 18 environment cards, two entry cards per environment,
  8 dependency cards for `antismash`, 3 unit cards for its resources, the file picker opens at
  the system drive root with 29 entries, and the console reports no errors.

## Known limitations

- `operon environment status <name>` still reports host status; per-environment inspection is
  available through `/api/environments`.
- `/api/jobs/{id}` returns `500` for an unknown job id while `/api/v1/jobs/{id}` returns `404
  unknown_job`.
- `plan submit` still requires a hand-authored execution binding.
- `GET /api/bootstrap` is unauthenticated by design for local desktop startup, so a local
  process can obtain the session token.

## Verification on this build

- 112 backend tests passed, 1 skipped on this tree (resource, environment, remote, MCP guard, control plane groups).
- Frontend suite: 43 files / 265 tests passed; `npm run build` produced the bundle shipped in the payload.
- 18 environment cards were prepared one by one (never with "prepare all"): `core`, `openmm81` and `proteinmpnn` installed to readiness; `hmmer`, `hic`, `rna`, `openfold`, `rfdiffusion` stopped with a clear win-64 availability message; the remaining large environments were started and cancelled, returning to `missing`.
- UI smoke on a clean install drives 18 environment cards, both entry cards per environment, dependency cards, unit cards, the link dialog and the local file picker; console reported no errors.
- 4 of 6 `openmm81` operators run end-to-end through MCP; the MD operators exceed the 90 s client timeout and one scan needs a different structure. `proteinmpnn` operators need the dedicated torch environment, which this host did not install.
