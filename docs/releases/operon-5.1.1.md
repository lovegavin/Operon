# Operon Studio 5.1.1

Released 2026-11-13. Patch release for the 5.1.0 multi-library release.

## Fixed

- The operator-library import UI no longer prints version-specific bundle names
  such as `operon-library-v0.0.x.operon-library.zip`. It shows only the accepted
  extensions: `.operon-library.zip` for an operator library and `.zip` for a
  route-library collection.
- The route-library error and empty-state copy no longer names a particular
  bundle version.
- The "route search" box on the import surface was removed. Saved routes are
  listed directly and imported through the existing file pickers.
- The library-name hint no longer suggests a specific example version.
- The legacy 8.x rejection message is version-neutral; it asks for a current
  operator library bundle built for this Operon Studio release.

## Unchanged

`bundle_format=1`, `operator_protocol=3`, the multi-library directory layout,
per-operator metadata, per-job provenance, and `runs/<job-id>` skeletons are
unchanged from 5.1.0. Operator libraries and Routes collections are compatible
with both 5.1.0 and 5.1.1.
