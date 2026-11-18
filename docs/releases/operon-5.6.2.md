# Operon Studio 5.6.2

This release makes the runtime view work the way the runtime model actually is:
one card per environment, dependencies described inside the environment, and
large resources split into the official units that upstream projects ship.

## Added

- The runtime window offers an *execution location* selector: local machine or
  any connected server. Switching the location reloads that machine's own
  environment list from its operator library.
- The link dialog for a resource unit can open a file-manager style picker. On
  Windows it lists drive letters and directories; on a remote host it browses
  the remote file system through the agent. Selecting an entry fills the path
  field, so a link no longer has to be typed from memory.
- `POST /api/browse` exposes the local directory listing used by that picker
  (`roots`, `parent`, `entries`); the remote counterpart already existed as
  `POST /api/remote/{key}/browse`.
- `POST /api/environments/{name}/dependencies/download` installs a single
  declared dependency, and `POST /api/resources/{name}/download` accepts a
  `unit`, so one official unit can be fetched on its own.

## Changed

- Environment cards, dependency cards and resource-unit cards share the same
  card layout, so the three levels look alike instead of mixing tables and
  lists.
- Only *install all* remains, at the top right of the runtime window and of the
  detail page; the duplicate *download all* action and the stray *cancel*
  button were removed.
- Environment titles are short Chinese labels (基础运行时, ProteinMPNN 蛋白设计,
  HMMER 序列比对, ...) instead of the long English descriptions.
- `resources.json` keeps exactly one official unit per resource; the previous
  split of `alphafold2` into nine sub-units was wrong because `afdb` is itself
  the unit upstream publishes.

## Fixed

- F-34: the environment card showed the number of operators *using the
  environment's resources* instead of operators *assigned to the environment*,
  so most cards read zero. `operator_count`/`operators` now come from the
  descriptor assignment map.
- F-35: the library packager never stamped `resources.environment` into the
  packaged `descriptors.json`; only `operon registry build` did. A library built
  by `operon_library_builder` therefore shipped 1,157 descriptors without an
  environment. The packager now reads `environment_assignments.json`, validates
  the names against `environments.json`, stamps the environment and recomputes
  the declaration hash.
- F-36: the runtime window had no way to switch machines after the environment
  cards replaced the resource section.
- F-37: a link path could only be typed; there was no way to inspect the target
  machine's directories.

## Library

Operon Studio 5.6.2 ships operator library `main-v1.0.2`, which assigns all
1,177 descriptors to exactly one of 18 environments and records one official
unit per resource.

## Verification

- Clean install to a fresh directory: 21 s, version `5.6.2 (a5901d99)`,
  library `main-v1.0.2`.
- `/api/environments`: 18 environments whose `operator_count` sums to 1,177.
- `/api/v1/large-resources`: 16 resources, 16 components, one per resource.
- `/api/browse` returns the local drive roots and 29 entries at a drive root.
- Runtime window: 18 cards with Chinese titles, one *install all* button, an
  execution-location selector, two entry cards per environment, dependency
  cards and unit cards, and a working browse picker.
