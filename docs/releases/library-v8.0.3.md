# Library 8.0.3

8.0.3 is a targeted operator-library correctness release. It fixes the three
library-owned items from the 4.0.5 backend audit (BE-01, BE-02, BE-06) without
changing the application, protocol fields, or the `export_results` public
contract.

## Changes

- **BE-01 — interface energy dependencies.** `interface_alanine_scan`,
  `interface_mmgbsa_delta`, and `structure_interface_residue_energy` now declare
  `openmm>=8.0` and `pdbfixer>=1.9` in `dependencies`, matching their
  `dependency_imports`. Repair no longer skips them as empty-dependency
  operators.
- **BE-02 — Hi-C export is optional.** `export_results` no longer requires
  `hictkpy` for CSV, FASTA, and PDB exports. The `.hic`/`.cool` path imports it
  lazily and raises a clear `StepError` when the optional package is absent.
- **BE-06 — groupable interface statistics.** The five interface operators now
  declare the `statistic` labels in their output contracts:
  - `structure_interface_core`: `delta_sasa`, `isolated_sasa`,
    `buried_fraction`, `is_core`
  - `structure_paratope_predict`: `n_contacts`, `min_distance`, `is_paratope`,
    `cdr_index`
  - `structure_interface_residue_energy`: `coulomb_kj`, `lj_kj`, `total_kj`,
    `n_contacts`
  - `interface_alanine_scan`: `wt_delta_kj`, `mutant_delta_kj`,
    `delta_delta_kj`
  - `interface_mmgbsa_delta`: `complex_kj`, `binder_kj`, `target_kj`,
    `delta_kj`

  `join` and `aggregate(group_col=...)` can now resolve `residue` and
  `cdr_index` from the static interface, not only from runtime labels.

## Compatibility

- Operon Studio: **3.1.9 or newer** (native `operon` namespace).
- 1063 operators, 108 Readers, 7 packages, 79 routes.
- `minimum_application` and `build_application` remain `3.1.9`.

## Testing

Per the release request, only the affected areas were run; the full suite was
not rerun for this patch.

- Ten targeted test files covering the five operators, export paths, contracts,
  and route parameters: **88 passed** (148.62 s).
- New regression tests
  `tests/test_extension257.py::test_output_contract_declares_groupable_statistics`
  and `tests/test_interface_contracts.py` check that all five outputs declare
  their `statistic` labels, that `cdr_index` is accepted by `compatible`, that
  the three interface operators declare their OpenMM dependencies, and that
  `export_results` does not require `hictkpy`.
- The earlier 12 Hi-C test failures were an environment issue: TMPDIR pointed at
  a directory that did not exist. After creating it, all targeted tests passed.
- `operon registry check --json`: operators 1063, readers 108, packages 7,
  routes 79, errors 0.

## Known limits

- The interface operators still return a 2-D `residue × statistic` form.
  `cdr_index` is a statistic column, so aggregate groups by its value; it is not
  a separate third dimension.
- Interface energy values remain model estimates, not experimental energies.
