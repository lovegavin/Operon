# Operon Library 0.1.5

## Added

- `structure_extract_chain`: select one or more chains from a structure Form and
  write a native PDB plus a filtered PDB Form. This makes multi-chain mmCIF
  inputs usable with operators that expect a single chain (for example the
  3DI3 A/B interface workflow).
- `colabfold` isolated environment (Python 3.11, `colabfold[alphafold]==1.5.5`,
  MMseqs2/Kalign/HMMER, CPU torch). `colabfold_predict` now declares it.

## Fixed

- `colabfold_predict` no longer depends on a host `colabfold_batch`; the
  declared environment supplies the binary. Sequence databases remain external
  and must be mounted or downloaded separately.
- Structure readers label-encode chain/atom strings; `structure_extract_chain`
  decodes them before filtering, so chain names such as `A` match.

## Compatibility

- `minimum_application`: 5.1.6
- `build_application`: 5.1.17
- 1069 operators, 108 Readers, 79 routes, 0 registry errors.

## Known limitations

- RFdiffusion and OpenFold are external checkouts plus weights; the library
  reports their absence but does not clone repositories or download
  multi-gigabyte weight files automatically.
- ColabFold databases (UniRef/MMseqs2) are not bundled.
- Boltz still needs the application-side `LD_LIBRARY_PATH` environment fix;
  the library provides `libstdcxx-ng` but cannot change process loading.

## Verification

- `tests/test_structure_extract_chain.py tests/test_library_012.py tests/test_resource_fetch.py`
  → 11 passed.
- Registry rebuilt with `operon registry build --scope packages`.
