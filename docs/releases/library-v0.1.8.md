# Operon Library 0.1.8

Release date: 2026-11-15

## Changes

- Resource roots now list the canonical Operon directory first for `esmfold`,
  `colabfold` and `prodigal`: `~/.local/share/operon/resources/<id>`. Existing
  tool-managed directories remain valid fallbacks.
- MCP resource downloads share the library downloader target resolution, so a
  download always lands in the canonical directory (or an explicit/env
  override) and is visible to another MCP query and to operator
  `resolve_root` calls.
- Fixed duplicate byte accounting in the resource API job, which reported twice
  the transferred size.

## Compatibility

- Operator protocol 3, bundle format 1.
- Minimum application: 5.1.6.
- Built and tested against Operon Studio 5.1.17.

## Assets

- `operon-library-main-v0.1.8.operon-library.zip`
- `operon-routes-main-v0.1.8.zip`
- `library-0.1.8-SHA256SUMS.txt`
