# Operon Library 0.1.4

## Summary

Patch release for the resource-download interface introduced in 0.1.3.

## Fixes

- `resources.json` accepts both download shapes used by the library:
  - a list of objects (`{path, url, sha256, bytes, ...}`), used by ESM-2,
    ESM-IF1, and ESMFold;
  - a legacy object mapping `filename -> URL`, used by Boltz, with hashes and
    sizes taken from the adjacent `sha256` and `sizes` maps.
- `Resource.from_entry()` normalizes both shapes to the same validated tuple,
  so `resource_preflight`, `/api/resources`, and MCP resource tools can
  enumerate every entry. The 0.1.3 tag failed on Boltz with
  `resource 'boltz' has a non-object download entry`.
- Added a regression test covering the mapping form.

No operator behaviour, environment specification, or application code changed.
