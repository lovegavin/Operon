# Operon Studio 5.1.5

Patch release.

## Fixed

- The route-library file picker accepts the new collection name
  `operon-routes-<library>-v<version>.zip` as well as the legacy
  `operon-routes-v<version>.zip`. Previously a collection built for a named
  library was rejected before it reached the importer.
- The route-library rejection message no longer embeds a version-specific
  example filename; it asks for a `.zip` collection containing
  `routes/*.operon.zip`.
