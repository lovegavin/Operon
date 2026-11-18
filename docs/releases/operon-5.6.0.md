# Operon Studio 5.6.0

Operon Studio 5.6.0 ships operator library **main-v1.0.0** and turns the runtime
panel into an environment-first view. A library now states, for every operator,
which environment it runs in, and every environment states the dependencies and
the large resources it needs.

## Added

- **Environment-first runtime panel.** The panel lists environment cards only.
  Opening a card shows its dependencies (with install, cancel and repair) and
  its resources, grouped by the environment that owns them.
- **Official resource units.** Each resource declares the units the upstream
  project publishes, for example `afdb`, `params`, `Pfam-A.hmm` or
  `esm2_t6_8M_UR50D.pt`. A unit card reports presence, size and whether the
  path is a link, and offers `Download`, `Link` and `Unlink` for that unit.
- **Library model 1.0.0.** Every operator belongs to exactly one environment.
  `environment_assignments.json` records the mapping, the registry build stamps
  it into `resources.environment`, and unknown environment names fail the build.
  Environments declare `requirements`, `conda_packages`, `binaries` and
  `resources`, and resources declare `envs` and `units`.
- **Environment inventory API.** `/api/environments` now returns `resources`,
  `dependencies`, `shared` and `managed` for every environment, and
  `/api/v1/large-resources` returns `components`, `environments` and
  `official_root` for every resource.
- **Dependency install and cancel.** `operon environment install NAME...`,
  `operon environment cancel NAME` and `operon_environments_cancel` reuse the
  same serialized preparation queue as the desktop panel, so the HTTP API, MCP
  and CLI expose the same operations.
- **Resource operations across every surface.** `operon resources
  list|download|link|unlink|cancel|log` and the MCP resource tools accept a unit
  name, so a unit can be linked or removed without touching its siblings.
- **Disk space preflight.** Environment preparation and resource downloads call
  `shutil.disk_usage` before writing and refuse to start when the destination is
  short of space, reporting the required and available byte counts.
- **Remote tool inventory.** The server panel lists which external command line
  tools are missing instead of only showing a count.

## Changed

- Large resources moved out of the settings dialog into the runtime panel.
- `check_resource` reports an entry for every declared file, including files
  whose parent directory is absent, so a missing tree no longer hides its
  contents.
- External command line tools are environment dependencies now: `genomics`,
  `hic` and `rna` were added, `hmmer` gained `infernal` and `antismash` gained
  `prodigal` and `ncbi-amrfinderplus`.

## Fixed

- **F-28** `check_resource` iterated the legacy `files` list, so a resource with
  nine declared files reported one entry and the panel rendered the rest as
  present. It now iterates `expected_files`.
- **F-29** The runtime panel counted operators with a `count` placeholder that
  the translation template did not use, which rendered a literal `{n}`.
- **F-30** Linking a resource unit always validated against `expected_files`,
  so a declared unit such as `params` could not be linked. Link now resolves a
  declared unit to its own path first.

## Verification

- Focused backend suites: `test_resource_link.py`, `test_environment_install.py`
  and `test_environment_api.py` pass; frontend unit tests pass with 266 tests.
- Clean installation reports library `main-v1.0.0`, 18 environments, 16
  resources and 26 official units.
- Resource units resolve on a fresh profile: every `alphafold2` unit reports
  missing with no false positives, and a manual junction on a unit is reported
  as linked.

## Compatibility

Library `main-v1.0.0` requires application 5.6.0 or newer because the resource
snapshot gained `components`, `environments` and `official_root`. Older
applications keep working with library `main-v0.1.30`.
