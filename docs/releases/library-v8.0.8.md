# Library 8.0.8

Release date: 2026-11-13

## Compatibility

- **Minimum application: Studio 4.1.0**
- Built and compatibility-tested with Studio 4.0.8 using the forward-minimum path.
- Three-end installation evidence was produced on Studio 4.1.9 (environment installer and PDBFixer probe).
- Linux bundle SHA256: `e4884979192e69c3998d8ad573df1572419c9d668c49f8dcb42c5dbffdcf2d1e`.

## Fixes

### OL-01: alanine scan can select the mutated side

`interface_alanine_scan` now accepts `mutation_side`:

- `target` (default): mutate interface residues on the target chains.
- `binder`: mutate interface residues on the binder chains.
- `both`: mutate both sides.

Each returned row now carries `side` (`binder` or `target`). The old behavior is
preserved by the default. The interface is defined by the existing
`binder_chains`/`target_chains`, `cutoff` and `max_residues` parameters.

### OL-02: single-point energy protocol is explicit

`interface_alanine_scan` and `interface_mmgbsa_delta` now publish a protocol and
quality block in their output metadata:

- `single_point: true`, `entropy_included: false`, `ensemble: false`,
  `calibrated: false`.
- Explicit sign conventions: alanine `delta_delta = mutant - wild_type`;
  MM/GBSA `delta = complex - binder - target`.
- Warnings forbid interpreting the numbers as calibrated affinities or
  experimentally validated hotspots.

When multiple copies of the same side are present, alanine scan compares
per-residue values across copies; `rho < 0.5` or more than 20% sign conflicts
emits a copy-replicate warning. The check is reported as unavailable when there
are fewer than three common residue numbers.

### OL-03: OpenMM environment no longer needs GitHub at install time

PDBFixer 1.9 is vendored in the operator library. The `openmm81` environment now
uses `venv_shared: true`, installs OpenMM 8.1.1, NumPy 1.26.4 and
`setuptools>=68,<81`, and imports the bundled PDBFixer. There is no
`no_build_isolation` GitHub tarball in the environment spec.

Verification on Studio 4.1.9:

- `environment_install.prepare("openmm81")` reached `ready` in 14 s.
- Environment size: 154,686,868 bytes, 3,748 files.
- `openmm` 8.1.1 and `numpy` 1.26.4 probes passed.
- The bundled PDBFixer prepared 1MEL to 8,247 atoms / 587 residues.

## Regression

- 1MEL `structure_interface_core` golden: 46 residues, 28 core / 18 rim,
  A-side ΔSASA 905.8944680690765 Å², target-side 763.2626737356186 Å².
- The 4.0.8 numbers (47 residues, 885.28/797.25 Å²) reflect older input
  preprocessing and are not reproduced by the current algorithm.

## Known limits

These remain single-point, implicit-solvent estimates. They are not calibrated
binding free energies, do not include entropy or ensemble averaging, and must
not be presented as experimentally validated hotspots.
