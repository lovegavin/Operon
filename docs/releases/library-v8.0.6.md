# Library 8.0.6

Library 8.0.6 is the first release built for **Operon Studio 4.1.0 and newer**.
Studio 4.1.0 is released after this library; its runtime acceptance remains the
first post-release gate. The bundle was built with the available 4.0.8
application code line plus the 8.0.6 runtime changes in this commit.

## Changes

- The `.operon-library.zip` now carries `sources/operon/environments.json`, so
  the isolated `openmm81` environment definition travels with the library.
- `minimum_application` is read from `library/release.json`; it is no longer
  hard-coded in the bundle builder. This release declares `4.1.0`.
- A runtime that loads a pinned library reads the manifest from that library's
  active source root, not only from the application seed or wheel.
- Operators that declare `resources.environment` always execute through the
  environment worker. A missing environment raises a clear readiness error; it
  never silently falls back to the shared interpreter.
- Bundle validation now accepts exactly the environment manifest in addition to
  the operator, Reader, package and `builtin_packages.json` files. Path
  traversal and unexpected files remain rejected.

## Compatibility evidence

- 1063 operators, 108 Readers, 7 packages, 79 built-in routes.
- Registry: 0 errors.
- Bundle: `0cf2c2a648e5d1fb0d82c859e2de80d435ea3fa5be70fa71e9043e9764a05ea2`.
- 4.0.8 code line + 8.0.6 runtime changes: install, frozen routes, worker
  streaming and environment manifest import PASS. The verification copy changes
  only `minimum_application`; the bundle bytes are otherwise exact.
- Stock Studio 4.0.8 predates environment-manifest import and is **not** a
  supported host for this bundle.
- Studio 4.1.0 runtime acceptance: **pending** until the Studio 4.1.0 release is
  available. This is an explicit release gate, not a claim of tested support.

## Environment

The `openmm81` environment pins Python 3.11, OpenMM 8.1.1, NumPy 1.26.4 and
PDBFixer 1.9. It is provisioned by the application environment manager from the
manifest in this bundle. The shared application interpreter remains on its
normal NumPy 2 runtime.
