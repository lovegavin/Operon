# Operon Library v0.0.0

First release of the independently versioned operator library line. Operon
Library v0.0.0 replaces the former bundled `library-v8.x` release train.

## Compatibility

- Application: Operon Studio **5.0.0** or newer.
- Bundle format: **1** (`bundle_format: 1`).
- Operator protocol: version **3**, revision **3.7**.

The application rejects every legacy `library-v8.x` bundle with an explicit
migration message; there is no silent pin repair or legacy read path.

## Contents

- 1,063 operators, 108 Readers, 7 packages, 79 built-in route templates.
- Canonical per-package identity (`code_sha`) generated once by
  `operon-library-builder` 1.0.0 and copied into the library manifest, every
  provider wheel and every route pin.
- A single universal `operon-library-v0.0.0.zip` (no per-platform variants) and
  a matching `operon-routes-v0.0.0.zip`.
- Environment declarations travel with the library in `environments.json`.

## Install

1. Download `operon-library-v0.0.0.zip` and `operon-routes-v0.0.0.zip`.
2. In Operon Studio 5.0.0 import the library bundle, then import the route
   collection.
3. The application installs the provider wheels, registers descriptors and
   prepares environments on demand.

## Notes

- Identity values are computed from the packaged wheel sources, never from the
  installed copy. Applications must treat `code_sha` as canonical data.
- Route bundles pin exactly `{package, version, code_sha}`. A route collection
  built for another library version is rejected instead of being guessed.
