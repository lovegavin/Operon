# Operon Library 8.0.10

This release fixes the 8.0.9 release-artifact pin mismatch.

## Fix

The 8.0.9 library bundle was built while `builtin_packages.json` still carried
the previous descriptor `code_sha` (`a49cb693…`), while the 8.0.9 Routes archive
was built from a different catalog snapshot (`9d8dd391…`). As a result, after
installing 8.0.9 the registered source pins no longer matched the pins stored in
the route bundles.

8.0.10 rebuilds the package index and the route archive from the same catalog.
Every route `plugin_lock` entry in `Operon-Routes-v8.0.10.zip` uses
`a49cb69340e957e8eac12f288d3c2c31735dfaca2cd6b8f3ffca97f573cc174f`, the same
value carried by the library packages and the installed registry.

`scripts/package_routes.py` now builds its route catalog from
`library/seed/operon/builtin_packages.json` instead of the operator library
shipped with the installed Studio build, preventing the two artifacts from
diverging again.

## Requirements

- Operon Studio 4.2.2 or newer.
- The application-side `import_route_archive` pin-migration gap is not masked by
  this release; this release makes the published pins internally consistent.

## Assets

- `Operon-Library-v8.0.10-Linux.operon-library.zip`
  - sha256 `685fb5cadc13a4cf0c02129b148ee2b12bb89527a23d000efb014202df5b9041`
- `Operon-Library-v8.0.10-Windows.operon-library.zip`
  - sha256 `8ef11d81789f11ea40d7b5c42397d313090e0fcf82e276b674f98a022cc05d81`
- `Operon-Routes-v8.0.10.zip`
  - sha256 `8cccf623db17596e4654c9d9e02f280cf9e23bc99d740f16a31fdabf9846d65e`
- `Operon-Operator-Audit-v8.0.10.zip`
  - sha256 `99376902cb671de2638b26161d0eebcb245586a726ba66a6ef27dc251796712d`
- `Operon-Quickstart-v8.0.10.zip`
  - sha256 `9aedecc0c3864506901eb2baa89feff84336b28a6c009f15c9dc0b284fc898fc`
- `operon_builtin_library-8.0.10-py3-none-any.whl`
  - sha256 `88ddfe051ce1e932cf18b9ee71e1366cf91a3709ae3af8ae14b7d74901c93914`
- `QUICKSTART.md`, `QUICKSTART.zh.md`
- `install_dependencies.py`, `install-dependencies.sh`, `install-dependencies.ps1`
- `SHA256SUMS.txt`
