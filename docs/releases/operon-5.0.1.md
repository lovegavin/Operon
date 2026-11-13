# Operon Studio 5.0.1

Patch release for the 5.0.0 library/application split. No operator, route or
contract change.

## Fixed

- **Import entry points follow the two-ZIP design.** The operator-library
  importer accepts `operon-library-v0.0.x.zip`, the route-library importer
  accepts the collection `.zip`, and the single route importer accepts only
  `.operon.zip`.
- **Library state is version-scoped.** The imported library, its wheels and isolated environments live under <install>/versions/<version>/library, not in the workspace; the workspace holds only task data.
- **The canvas is no longer pin-bound.** Saved graphs resolve the unique operator/Reader id against the installed library at run time; stale pins are ignored and removed when a graph is prepared.
- **No stale 8.x library after an in-place upgrade.** A workspace created by a
  4.x installation kept its old `registry.json`, so the panel displayed
  `library 8.0.10` even though those wheels live in a deleted application
  version. On the first read, 5.0.1 clears that catalog and asks the user to
  import an `operon-library-v0.0.x` bundle.
- Version identifiers are 5.0.1 across the application, wheel and frontend.

## Compatibility

- Library bundles: `bundle_format = 1`, `operator_protocol = 3`, built for
  Operon 5.0.0 or newer. The released `operon-library-v0.0.0` and
  `operon-library-v0.1.0` are unchanged.
- Old 8.x libraries are still rejected with the documented migration message.
