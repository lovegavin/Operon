# Operon Operator Library v7.0.1

**Release date:** 2026-11-08

Patch release for Operon Studio 3.1.4. Operator content, route templates and
the wire protocol are unchanged from 7.0.0; this release fixes packaging of
the legacy application seed so the v7 bundle verifies and installs cleanly on
the released 3.1.2 application.

## What changed

- `library/seed/biopipe/builtin_packages.json` is rebuilt from the canonical
  `library/seed/operon/builtin_packages.json` manifest. The 7.0.0 bundle shipped
  the legacy manifest from the 6.0.0 snapshot, so its documentation hashes for
  `bayesian_linear_regression`, `graph_pseudotime`, `image_gaussian_blur` and the
  restored `iv_2sls` were stale. On the released 3.1.2 application (a legacy
  `biopipe` installation) `PluginManager.state()` therefore raised
  `Documentation for this exact implementation is unavailable` during
  `verify_library_release.py`, which failed the Linux and Windows verification
  jobs and skipped publishing.
- No operator code, parameter JSON, Markdown documentation, route template or
  protocol declaration differs from 7.0.0. The 1063 operators, 108 Readers,
  7 packages and 78 routes are identical.

## Compatibility

| Item | Value |
| --- | --- |
| Operon Studio | 3.1.4 |
| Operon SDK | 3.7.0 |
| Operator protocol | integer 3, `protocol_revision` 3.7 |
| `minimum_application` / `build_application` | 3.1.4 / 3.1.4 |

## Verification

- Clean Python 3.11 environment with the released-shape 3.1.2 wheel:
  `scripts/release_library.py --tag library-v7.0.1` followed by
  `scripts/verify_library_release.py` reports `passed: true` (1063 operators,
  108 Readers, application unchanged, old pin preserved, idempotent install,
  disabled provider, worker streaming).
- Registry: 1063 operators, 0 errors, 78 routes.
- Full test suite and route evidence for the 46 new operators are unchanged
  from 7.0.0; see `docs/verification/routes-5.x.md`.

## Assets

The tag `library-v7.0.1` produces Linux and Windows `.operon-library.zip`
bundles, `Operon-Routes-v7.0.1.zip`, `Operon-Quickstart-v7.0.1.zip`, the
`operon_builtin_library-7.0.1` wheel, bilingual quick starts, the three
dependency installers, `SHA256SUMS.txt` and the two verification JSON files.
