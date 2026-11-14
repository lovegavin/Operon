# Operon Library 0.1.2

Released 2026-11-14. Library-only release; the application remains Operon
Studio 5.1.16.

## Environment declarations

- `boltz` now installs conda `libstdcxx-ng`, so its NumPy no longer binds to
  the host `libstdc++` and no longer fails with `CXXABI_1.3.9 not found`.
- New `esmfold` environment (Python 3.11, torch 2.3.1, NumPy 1.26.4,
  Biopython 1.83, SciPy 1.13.1, `fair-esm==2.0.0`, plus the OpenFold runtime
  dependencies). `esmfold_predict` declares this environment and loads the
  ESMFold checkpoint from the existing `esmfold` resource entry; the 2.5 GB
  checkpoint remains a user-supplied resource.
- `esm3`, `antifold`, `openmm81` keep their existing declarations.

## New operator

`structure_convert_format` converts any structure Form into a coordinate
complete PDB artifact and returns the canonical `PdbReader` fields. It replaces
out-of-workflow `gemmi`/shell conversion when a route starts from mmCIF (for
example 3DI3). It has no external dependency beyond NumPy.

## Other changes

- `library/release.json` and `library/pyproject.toml` are `0.1.2`;
  `minimum_application` is 5.1.6 and `build_application` is 5.1.16.
- The pin-free route regression now asserts an empty `plugin_lock` and reads the
  historical implementation pin from the job's `plugins.lock.json`.

## Verification

- Registry: 1067 operators / 108 Readers / 7 packages / 79 routes, 0 errors.
- Focused tests: 24 passed (`test_library_012`, `test_library_release`,
  `test_route_parameters`).
- `operon_library_builder gate` passed; two builds byte-identical.
- Bundle `operon-library-main-v0.1.2.operon-library.zip` 6,851,444 B,
  sha256 `7972b84f59f3a477a528911599cb3f7af5dac6388721c99f32f899ce004fcb6e`,
  1,175 descriptors.
- Routes `operon-routes-main-v0.1.2.zip` 201,208 B,
  sha256 `88caa9392d7d7625c7a4f39cbea1cd6030a1d7bdfe60f163801b2aefb9098e20`,
  79 bundles, 0 route/library pin mismatches.
- Clean-profile install reported `main-v0.1.2`, 7 packages, 1,175 descriptors.
- Real 3DI3 mmCIF conversion: 2,500 atoms x 21 mmCIF fields to 2,500 atoms x 12
  canonical PDB fields; native PDB 197,528 B; the 1MEL fixture round-trips.
- The frontend and application were not modified.

## Known limitations

- The ESMFold checkpoint, OpenFold weights and RFdiffusion checkpoints are not
  distributed in this bundle; operators report the missing resource path.
- `esmfold` and `boltz` environments were not installed during local packaging;
  preparation is verified by manifest/plan and must still be exercised on the
  target server.
