# Operon Studio 5.1.2

Release date: 2026-11-13

## Operator library identity

An imported library now carries its own primary name and version in the bundle
manifest. The installer records the label `<library_name>-v<library_version>`
and never asks the user to invent a name.

- The bundle's `library_name` is authoritative; bundles without it default to
  `main`.
- The import dialog no longer shows name or version fields.
- The library manager lists the primary name and the version for every
  installed library.
- A second library with the same primary name is rejected; operator, package
  and module ids must not overlap either. Coexisting examples are
  `main-v0.1.0` and `fork1-v0.0.0`.

Backend, HTTP API (`POST /api/libraries/install`), CLI and MCP derive the same
identity from the bundle; the old `name`/`version` request arguments are
ignored.

## Compatibility

- Bundle format 1, operator protocol 3, 8.x libraries still rejected.
- Libraries, routes, job provenance and `runs/<job-id>` skeletons are
  unchanged.
- `main-v0.0.0`, `main-v0.1.0` and `fork1-v0.0.0` are the bundles paired with
  this release.
