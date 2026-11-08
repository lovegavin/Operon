# Operon Operator Library v6.0.1

**Release date:** 2026-11-08

Patch release for Operon Studio 3.1.2. The operator and route catalogs are
unchanged from v6.0.0; this release raises the supported application floor to
the current Studio maintenance line and rebuilds the release artifacts.

## What changed

- `minimum_application` and `build_application` are now 3.1.2. Studio 3.1.2
  only changed the shared-pool defaults, the Linux acceptance fixtures, the
  licence text and the optional interpreter passed to `PluginManager`; no
  protocol, descriptor or bundle-layout change is involved.
- Release checksums are now assembled from the artifacts that are actually
  published, removing the duplicate Quickstart entry and the unpublished
  BioPipe mirror names that appeared in the v6.0.0 manifest.
- No operator or route content changed: 1017 operators, 108 Readers,
  7 packages and 78 route templates remain.

## Compatibility

| Item | Value |
| --- | --- |
| Operon Studio | 3.1.2 |
| Operon SDK | 3.7.0 |
| Operator protocol | integer 3, `protocol_revision` 3.7 |
| `minimum_application` / `build_application` | 3.1.2 / 3.1.2 |

Studio 3.1.0 remains able to install the v6.0.0 bundle; v6.0.1 intentionally
requires 3.1.2 so that one release train is supported at a time.

## Verification

- Bundle installation on Studio 3.1.2: passed, 1017 operators, 108 Readers,
  existing pins and parameters preserved, idempotent reinstall.
- Registry: 1017 operators, 108 Readers, 7 packages, 78 routes, 0 errors.
- Full pytest on the NumPy 2.1.3 environment: 3659 passed, 223 skipped,
  0 failed.
- srv route parity from the 6.0.0 tree is retained in
  `docs/verification/routes-5.x.md`; the same operators and routes are shipped
  in this patch release.

## Assets

The tag `library-v6.0.1` produces the standard set: Linux and Windows
`.operon-library.zip` bundles, `Operon-Routes-v6.0.1.zip`,
`Operon-Quickstart-v6.0.1.zip`, the `operon_builtin_library-6.0.1` wheel,
bilingual quick starts, the three dependency installers, `SHA256SUMS.txt` and
the two verification JSON files.
