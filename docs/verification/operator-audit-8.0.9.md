# Operator Library 8.0.9 Verification

## Scope

Library 8.0.9 fixes the 4.2.0 operator-library reports:

- OL-01: alanine scan side selection, magnitude exclusion and copy-replicate flags.
- OL-02: Pearson agreement and per-residue replicate-conflict flags.
- OL-03: MM/GBSA protocol identity, delta terms and cancellation warning.

## Bundle

Linux bundle SHA256:
`202154197303941eb95d382e2ee1418e93fecbe4e8451b94b7c86af2f97b371f`.

Built with Studio 4.2.1 (`minimum_application` 4.2.1, `build_application`
4.2.1). The bundle is 28,394,745 bytes and contains 1,171 descriptors in
7 packages.

## Target-runtime installation

The final Linux bundle was installed into an isolated Studio 4.2.1 profile by
`scripts/verify_library_release.py`. The standard operator probe completed and
`passed: true`; evidence:
`verification/operator-audit-8.0.9/application-4.2.1-compat.json`.

This is an install/probe acceptance. The `openmm81` environment was validated
from the source manifest before the freeze; re-preparing it from the installed
bundle was not repeated for 8.0.9.

## Contract and regression tests

- `tests/test_extension296.py`, `tests/test_extension297.py`,
  `tests/test_extension298.py`, `tests/test_interface_contracts.py`,
  `tests/test_library_release.py`, `tests/test_contract_compositions.py`:
  41 passed, 1 skipped (the skipped test requires `openmm81`).
- Registry: 1,063 operators, 108 readers, 7 packages, 79 routes, 0 errors.
- Documentation check: 0 errors.
- 1MEL golden: 46 residues, 28 core / 18 rim, A/L 螖SASA
  905.8944680690765 / 763.2626737356186 脜虏.

## Environment installation (Studio 4.1.9)

`environment_install.prepare("openmm81")` was executed with the Studio 4.1.9
runtime on a clean Windows host. Evidence:

- status `ready` in 14 s;
- 154,686,868 bytes / 3,748 files;
- imports `openmm` 8.1.1, `numpy` 1.26.4;
- bundled PDBFixer 1.9 prepared `tests/fixtures/vhh_1mel.pdb` to 8,247 atoms / 587 residues.

JSON evidence: `verification/operator-audit-8.0.9/application-4.1.9-openmm81.json`.

The 8.0.8 frozen-artifact L5 gap is documented in
`verification/operator-audit-8.0.8/acceptance-gap.md`; 8.0.9 records the
install/probe acceptance above and does not claim a frozen-artifact environment
preparation.
