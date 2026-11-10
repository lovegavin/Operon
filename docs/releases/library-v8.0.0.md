# Library 8.0.0

First native Operon library release. It requires **Operon Studio 3.1.9 or
newer** and no longer ships the legacy `biopipe` source tree.

## Compatibility

- `minimum_application`: **3.1.9**
- `build_application`: **3.1.9**
- Bundle format: `operon.library`
- Providers: `operon_core`, `operon_expression`, `operon_genetics`,
  `operon_hic`, `operon_microbiome`, `operon_plots`, `operon_readers`
- Catalog: **1063 operators**, **108 Readers**, 1171 descriptors, 7 packages

## Changes

- Removed `library/seed/biopipe/`; the bundle now contains native
  `sources/operon/**`, `sources/src/**`, `packages/*.whl` and `library.json`,
  with no legacy `sources/biopipe/**` tree.
- Rewrote the remaining library imports from `biopipe_sdk` /
  `biopipe.bytecode` to `operon_sdk` / `operon.bytecode` (12 files).
- Rebuilt with the 3.1.9 `build_bundle`; `unpack_bundle` accepts the archive and
  a temporary 3.1.9 profile installs all seven providers.
- No operator definition, protocol field, route contract, or export contract
  changed.

## Verification

- Clean 3.1.9 wheel install: 1171 descriptors, 1063 operators, 108 Readers.
- Archive inspection: no `sources/biopipe/`, `library.json` format
  `operon.library`, seven provider wheels.
- The 7.0.15 operator-audit evidence is carried forward for reference. Its
  operator and route set is unchanged, but the evidence was collected on
  Studio 3.1.6 and has not been re-executed on 3.1.9. Full pytest and a fresh
  route-coverage run are pending.
