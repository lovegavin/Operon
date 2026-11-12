# Operon Library v8.0.7

Released 2026-11-12. This is a patch release for Studio 4.1.x installations.

## Compatibility

- Minimum application: **4.1.0**
- Build/verification application: **4.0.8** (forward-minimum compatibility build)
- Library version: **8.0.7**

Studio 4.1.0 is the first application line that can consume the environment manifest shipped inside an imported `.operon-library.zip`. The 4.0.8 build is used only to exercise the forward-minimum packaging path; the release declares 4.1.0 as its supported minimum.

## Fixes

### openmm81 environment installation

The previous manifest used micromamba to create a Python 3.11 environment. On Windows this failed while fetching conda-forge metadata (`CRYPT_E_REVOCATION_OFFLINE`), and the PDBFixer build could still fail on `pkg_resources`.

- `openmm81` now uses `venv_shared: true`: an isolated virtual environment created from the host Studio Python (3.12 on the 4.1.x runtime), shares the host interpreter's site-packages; the pinned packages are installed into the venv and take precedence.
- `setuptools<81` and `wheel` are installed before PDBFixer, so `pkg_resources` remains available.
- PDBFixer 1.9 is installed from the pinned upstream commit without build isolation.
- OpenMM 8.1.1 and NumPy 1.26.4 are pinned inside the environment; the shared NumPy 2 runtime is not downgraded.

Verified installation on Studio 4.1.7 (Windows, Python 3.12):

- environment `openmm81`: **ready**
- interpreter: `Scripts/python.exe`
- 157,355,136 bytes, 3,823 files
- probes: `openmm`, `pdbfixer`, `numpy`, `pkg_resources`
- PDBFixer on `vhh_1mel.pdb`: **8,148 atoms / 554 residues**

### Interface contract regression fixture

Added a 1MEL golden test for `structure_interface_core`: 46 interface residues, 28 core / 18 rim, 22 binder / 24 target rows, and ΔSASA values
`905.8944680690765` (A) / `763.2626737356186` (L).

### OL-03 numerical difference

The 4.0.8 report values (47 residues, A 885.28 Å², B 797.25 Å²) are not reproduced by the current source. `structure_interface_core` has had no algorithm change since 8.0.2; only output schema metadata changed. The 4.1.6 reference values are reproduced by the new golden fixture. The 4.0.8 numbers therefore reflect an older input/preprocessing path and are not a byte-for-byte compatibility baseline.

## Distribution

The `.operon-library.zip` contains `sources/operon/environments.json`, so an application import carries the `openmm81` definition. Environment creation is still performed by the application after import; the library does not install interpreters or packages during import.

## Known application-side items

Remote environment provisioning, job progress/ETA, partial-graph execution and reinstall history are application responsibilities. They are documented in the accompanying 4.1.6 issue reports and are not changed by this library release.