# Operon Library 0.1.3

Released 2026-11-14.

## Highlights

- New zero-input operator `resource_fetch`: downloads files declared by
  `resources.json` (`downloads`) into a resource root. HTTPS only, streaming
  `.part` writes, optional size/sha256 verification, atomic replace, and a
  per-resource receipt.
- `resources.json` now declares verified direct downloads for ESM2, ESM-IF1 and
  ESMFold. Resources without a reliable direct URL remain check-only; see
  `docs/design/resource-download-interface.md`.
- Resource download is available through the normal engine/MCP path
  (`operon_submit` with a zero-input `resource_fetch` node) without an
  application release.
- No application code or app version was changed. Torch remains the CUDA build;
  the Boltz `CXXABI_1.3.9` issue remains an application-side `LD_LIBRARY_PATH`
  fix.

## Verification

- `tests/test_resource_fetch.py` 6 passed.
- Focused library contract tests: 16 passed.
- Registry: 1068 operators, 108 Readers, 7 packages, 79 routes, errors 0.

## Compatibility

- `minimum_application`: 5.1.6
- `build_application`: 5.1.16
- Bundle: `operon-library-v0.1.3.operon-library.zip`
