# Operon Studio 5.6.1

Released 2026-11-18. Application 5.6.1 requires operator library 1.0.1 or newer.

## Fixed

- **F-32 - operator counts were read from the wrong field.** The runtime panel
  derived the "operators" number of an environment card from the resource
  back-reference (`used_by`), so environments whose operators consume no
  registered resource - `core`, `antismash`, `alphafold2` - showed "none", and
  the visible numbers did not add up to the library total. `/api/environments`
  now groups the installed descriptors by `resources.environment` and returns
  `operator_count` plus a truncated `operators` list; the card, its details and
  the remote listing read that field. The 18 environments now account for all
  1,177 descriptors (`core` 1,093, `proteinmpnn` 26, ...).
- **F-33 - resource units were split finer than the official layout.** AlphaFold-2
  was exposed as nine linkable units (`params`, `uniref90`, ...) although the
  official distribution ships all of them inside a single `afdb` directory.
  Every resource now declares exactly one official unit named after the
  directory or file the upstream project publishes (`afdb`, `ProteinMPNN`,
  `Pfam-A.hmm`, `esm2_t6_8M_UR50D.pt`, ...); completeness is still reported per
  declared file inside that unit, and a resource links as one folder.

## Added

- **Card navigation for environments.** The runtime panel lists one card per
  environment with an "install all" action; opening a card shows exactly two
  cards, one for the environment dependencies and one for its resources.
  Dependency cards list every pinned requirement with a per-requirement
  download action, resource cards list one card per official unit.
- **Per-unit resource download.** `POST /api/resources/{name}/download` accepts
  `unit` and only fetches the files declared by that unit; the UI exposes a
  "download" action per unit card and a group-level "download all" that skips
  units that are already present or linked.
- **Per-dependency installation.** `POST /api/environments/{name}/dependencies/download`
  installs a single declared requirement (`kind` plus `name`) into the isolated
  environment, creating the environment first when needed.
- **Disk space guard.** Preparing an environment or downloading a resource now
  inspects the destination file system first and refuses with a message naming
  the required and available bytes when the target is too small.

## Changed

- The remote connection summary shows the operator and reader counts only; the
  external-tool probe was removed (it reported tools of the agent runtime, not
  of the server, and no longer influenced any operator).
- The runtime panel no longer renders the whole resource grid on the landing
  view; resources are reached through the environment they belong to.
- `operon environment list|install|cancel` and
  `operon resources list|download|link|unlink|cancel|log` accept `--profile` for
  remote execution, matching the HTTP and MCP surfaces.

## Verification

A clean install of `Operon_Setup-5.6.1.exe` takes about 21 s, reports
`5.6.1 (<build>)`, loads library `main-v1.0.1` (7 packages, 1,177 descriptors,
1,069 operators, 108 readers), lists 18 environments whose operator counts sum
to 1,177, and exposes 16 resources with one official unit each. The runtime
panel renders 18 environment cards, an environment opens with the two card
entries, the dependency view lists the pinned requirements with individual
download buttons, and the resource view lists the official unit cards with
download and link actions. Installing or downloading into a location without
enough free space is refused with a message naming the required and available
bytes.

## Operator library 1.0.1

- `resources.json` keeps one `units` entry per resource, named after the
  official folder or file.
- `environment_assignments.json` maps all 1,177 descriptors to 18 environments.
- `library.json` requires application 5.6.1.
