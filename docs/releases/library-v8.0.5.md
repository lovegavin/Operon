# Library 8.0.5

8.0.5 is a dependency-correctness release over 8.0.4. It keeps the protocol,
the operator count, and the `export_results` public contract unchanged.

## Findings addressed

- **OL-01 (P0)**: the OpenMM/PDBFixer operators declared
  `pdbfixer>=1.9`. PyPI only publishes PDBFixer 1.12.0, which requires
  OpenMM 8.2 or newer, while the supported Python 3.11 image carries the
  OpenMM 8.1.1 wheel. Installation failed with
  `ResolutionImpossible: Cannot install openmm>=8.0 and pdbfixer==1.12.0`.
  OpenMM 8.1.1 also uses the NumPy 1 C ABI, so pinning it into the shared
  NumPy 2 runtime produced `numpy.core.multiarray failed to import`.
- **OL-02 (P2)**: the `structure_interface_core` and
  `structure_paratope_predict` composition path needed a fresh acceptance run
  on Studio 4.0.8.
- **OL-03 (P2)**: `export_results` no longer requires `hictkpy`; all CSV
  exports in the second online run succeeded.

## Fix

The operators now run in a dedicated Python 3.11 environment instead of
downgrading the shared NumPy 2 runtime:

- `library/seed/operon/environments.json` declares `openmm81` with
  `openmm==8.1.1`, `numpy==1.26.4`, `setuptools`, and `wheel`.
  PDBFixer 1.9.0 is installed from a pinned upstream commit with
  `--no-build-isolation`.
- Five operators declare `resources.environment: "openmm81"` and
  `dependencies: ["openmm==8.1.1", "numpy==1.26.4"]`:
  `interface_mmgbsa_delta`, `structure_interface_residue_energy`,
  `structure_openmm_energy`, `structure_openmm_md_rmsf`, and
  `structure_openmm_md_stability`.
- `interface_alanine_scan` only needs `openmm.app.PDBFile`; it declares
  `openmm==8.1.1` and no PDBFixer dependency.
- The library no longer vendors PDBFixer and no longer changes the shared
  NumPy or pandas runtime. The backend resolves and provisions the dedicated
  interpreter; the frontend only requests preparation and reports its state.
- Removed `removeHeterogens`-related vendoring changes; the five operators use
  the normal `pdbfixer` import inside `openmm81`.

## Verification

- Focused contract, composition, release, and route tests: **40 passed** in
  111.16 s.
- `tests/test_interface_contracts.py`: 9 passed; the output contracts declare
  `residue`/`statistic` dimensions and the paratope `cdr_index` statistic label.
- `openmm81` probe: `resolve()` returned the isolated interpreter and
  `probe()` reported `True` for `openmm`, `pdbfixer`, and `numpy`.
- MMGBSA route on `tests/fixtures/vhh_1mel.pdb` (binder A, target L):
  `Task finished` in 2.488 s.
- `vhh_cdr_quantification` on Studio 4.0.8: 22 interface residues, 17 paratope
  residues, join `(19, 8)`, aggregate by `cdr_index` produced 4 groups x 7
  features, and export succeeded.
- Official bundle verification on Studio 4.0.7: **95 passed, 2 skipped,
  7 deselected**, application 4.0.7, library 8.0.5, 1063 operators,
  108 Readers, `passed: true`.
- Registry: 1063 operators, 108 Readers, 7 packages, 79 routes, 0 errors.

## Compatibility

- Operon Studio: **4.0.7 or newer**. 3.x is no longer supported.
- 1063 operators, 108 Readers, 7 packages, 79 routes.
- Protocol v3 and SDK 3.7 are unchanged.

## Known limits

- Environment provisioning is backend-managed. The frontend does not install
  or select a Python build; it triggers preparation and displays the result.
  Provisioning evidence for this release is Linux. A host without micromamba
  can still use `OPERON_ENV_OPENMM81` to point at a prepared interpreter.
- The `structure_openmm_energy` route was stopped after nine minutes in the
  local acceptance run and is not used as release evidence; the preparation
  path is covered by the MMGBSA route.
- Energy values are model estimates, not experimental measurements.
- `NOL-01` through `NOL-06` from the same report are application, scheduler,
  MCP, or staging issues documented in
  `docs/verification/backend-issues-non-library-4.0.5.md`; this library release
  does not change them.
