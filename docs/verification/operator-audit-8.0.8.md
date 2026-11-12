# Operator Library 8.0.8 Verification

## Scope

Library 8.0.8 fixes the 4.1.8 operator-library reports:

- OL-01: alanine scan side selection.
- OL-02: single-point energy protocol and copy-replicate warning.
- OL-03: OpenMM/PDBFixer environment installation.

## Environment installation (Studio 4.1.9)

`environment_install.prepare("openmm81")` was executed with the Studio 4.1.9
runtime on a clean Windows host. Evidence:

- status `ready` in 14 s;
- 154,686,868 bytes / 3,748 files;
- imports `openmm` 8.1.1, `numpy` 1.26.4;
- bundled PDBFixer 1.9 prepared `tests/fixtures/vhh_1mel.pdb` to
  8,247 atoms / 587 residues.

JSON evidence: `verification/operator-audit-8.0.8/application-4.1.9-openmm81.json`.

L5 status under the revised standard: **verification incomplete**. This probe
used a source-tree manifest, not the manifest inside the frozen bundle. See
[`acceptance-gap.md`](../../verification/operator-audit-8.0.8/acceptance-gap.md).


## Bundle

Linux bundle SHA256: `e4884979192e69c3998d8ad573df1572419c9d668c49f8dcb42c5dbffdcf2d1e`.

The 4.0.8 forward-minimum verification report is installed as
`verification/operator-audit-8.0.8/application-4.0.8-compat.json`; it reports
`passed: true`, 1,063 operators, 108 readers and
`forward_minimum_compatibility: true`.

## Contract and regression tests

- `tests/test_extension297.py`, `tests/test_environments.py`,
  `tests/test_extension249.py`: 15 passed.
- Registry: 1,063 operators, 108 readers, 7 packages, 79 routes, 0 errors.
- 1MEL golden: 46 residues, 28 core / 18 rim, A/L ΔSASA
  905.8944680690765 / 763.2626737356186 Å².

## Compatibility build

The Linux bundle was built against Studio 4.0.8 with
`OPERON_FORWARD_MINIMUM=1` because `minimum_application` is 4.1.0. The
forward-minimum compatibility report is recorded in
`verification/operator-audit-8.0.8/application-4.0.8-compat.json`.
