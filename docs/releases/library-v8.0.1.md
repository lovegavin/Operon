# Operon Library 8.0.1

Native Operon library bundle for Operon Studio **3.1.9 and later**. The operator
and Reader catalogs are unchanged from 8.0.0: **1063 operators, 108 Readers,
7 packages, 79 built-in routes**.

## Fixes in 8.0.1

- **Implementation hashes.** `library/seed/operon/builtin_packages.json` is now
  regenerated from the source tree. Descriptors use the source `code_sha`
  instead of the provider-wheel digest, so Studio 4.0.0 no longer raises
  `Implementation code hash mismatch` for operators or Readers.
- **Built-in route readers.** `gwas`, `survival`, and `proteomics_de` declare
  explicit Readers (`VcfReader`, `TsvReader`, and `CsvReader`) instead of
  relying on extension-based inference. This removes the
  `TsvFileReader`/`TxtReader` ambiguity for the `.txt` inputs.
- **Genotype metadata.** `missing` now declares that it preserves
  `info.missing_code` and, when present, `ploidy`/`representation`, so the
  downstream `maf`/`hwe` contracts can be checked statically.
- **Survival contracts.** `kaplan_meier`, `logrank_test`, and `cox_regression`
  no longer require specific field labels in their static input contracts.
  Runtime still validates the requested time/event/group/covariate columns.
  This lets registration compile routes without reading source data, while a
  missing clinical column still fails at execution time.

Registration of all **79/79** built-in route definitions was checked against
the Studio 4.0.0 `RouteLibrary.register` code path using virtual source paths
and the shipped descriptors.

## Compatibility

- Minimum and build application: **3.1.9**.
- Bundle format: native `operon.library` (no `sources/biopipe`).
- 8.0.0 native bundles remain the previous release; 8.0.1 is a compatibility
  and registration fix, not an operator expansion.

## Testing status

Per the release instruction, compatibility and runtime test suites were not
run for this build. The 8.0.0 operator audit (L0-L5) is carried forward as
historical evidence for the unchanged catalog; the route-registration result
above is the only new check in this release. Full regression testing is
deferred to a later patch.
