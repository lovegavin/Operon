# Library 7.0.15

Packaging-only patch for Operon Studio 3.1.6. The operator library, routes,
protocol and export contracts are identical to 7.0.14; the full audit evidence
therefore carries over unchanged (794 / 1063 routed, 269 documented SKIP).

## Fix

The 7.0.14 Quickstart archive mistakenly bundled `examples/quickstart`
(including two data files), although the release contract says the Quickstart
asset contains only `QUICKSTART.md` and `QUICKSTART.zh.md`; examples are
distributed separately. `scripts/release_library.py` now packages exactly those
two documents. The 7.0.14 tag and assets remain published and immutable.

## Verification

`verify_library_release.py` passes on Studio 3.1.6 with 1063 operators and 108
Readers; the Quickstart archive contains exactly the two bilingual documents.

## Assets

Linux/Windows library bundles, routes collection, Quickstart, wheel, audit
archive, dependency installers and `SHA256SUMS.txt`, built by the tagged
release workflow.
