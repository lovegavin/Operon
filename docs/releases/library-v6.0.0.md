# Operon Operator Library v6.0.0

**Release date:** 2026-11-08

Feature release for Studio 3.1.0. The library grows from 867 to 1017 operators
and from 72 to 78 route templates while keeping wire protocol 3 and SDK 3.7
declarations.

## What changed

- 150 new operators across chemistry, protein/structure, epigenomics,
  population genetics, metagenomics, single-cell, proteomics, phylogenetics,
  metabolomics, transcriptomics, immunology, epidemiology and comparative
  genomics. See `docs/releases` history and the v2 gap matrix.
- Six post-1001 route bundles: radius of gyration plus metagenomic transforms,
  iBAQ/CAI/PTM occupancy, JC69 likelihood and outgroup rooting, methylation
  conversion and ASM/RF, population selection scan, noncoding RNA editing.
- Runner and descriptor compatibility with Studio 3.1.0; `minimum_application`
  and `build_application` are now 3.1.0.

## Compatibility

| Item | Value |
| --- | --- |
| Operon Studio | 3.1.0 |
| Operon SDK | 3.7.0 |
| Operator protocol | integer 3, `protocol_revision` 3.7 |
| `minimum_application` / `build_application` | 3.1.0 / 3.1.0 |

## Verification

- Registry: 1017 operators, 108 Readers, 7 packages, 78 routes, 0 errors.
- Full pytest on the NumPy 2.1.3 environment: 3659 passed, 223 skipped, 0 failed.
- Three-host route verification (WSL, Windows, srv) with byte-identical exports;
  biological oracle evidence is retained in `docs/verification/routes-5.x.md`
  (43 chapters, 1547 lines) and `docs/verification/competitor-gap-matrix-v2.md`.

## Assets

| Asset | Purpose |
| --- | --- |
| `Operon-Library-v6.0.0-Linux.operon-library.zip` | Operator library, Linux |
| `Operon-Library-v6.0.0-Windows.operon-library.zip` | Operator library, Windows |
| `Operon-Routes-v6.0.0.zip` | All 78 builtin routes, one bundle per route inside |
| `Operon-Quickstart-v6.0.0.zip` | QUICKSTART pair and smoke example |
| `operon_builtin_library-6.0.0-py3-none-any.whl` | Factory seed wheel |
