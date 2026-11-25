# FileReader

## Purpose

Reference one existing file as a `file_artifact` for operators that declare a
file port, without decoding or copying the payload. Use it for inputs that have
no typed Reader, such as an MD trajectory (`.xtc`, `.dcd`, `.npy`), a docking
pose (`.pdbqt`, `.sdf`), or a model input (`.json`).

## Inputs and outputs

Kind: `reader`. Operator ID: `FileReader`.
This Reader opens files with these extensions: `.npy`, `.xtc`, `.trr`, `.dcd`,
`.nc`, `.mdcrd`, `.crd`, `.edr`, `.gro`, `.psf`, `.top`, `.tpr`, `.prmtop`,
`.parm7`, `.pdbqt`, `.sdf`, `.mol2`, `.mol`, `.json`, `.h5`, `.hdf5`, `.pdb`,
`.ent`.

It declares no input port and one `file_artifact` output. Automatic file
selection prefers a typed Reader for the same extension; ask for `FileReader`
explicitly when the file must reach an operator as a file rather than as a form.

## Parameter guidance

- `format` is recorded as the artifact representation. Leave it empty to infer
  the name from the file suffix; a leading compression suffix is ignored.
- `role` names the file inside the artifact (`data` by default). Operators that
  expect a named role such as `trajectory`, `topology` or `complex` should be
  given that role so they can pick the right file.

## Interpretation

The Reader validates that the file exists and records its size and modification
time. It does not inspect the content, so it cannot confirm that a trajectory is
readable, that a pose is valid, or that the sampling is adequate. Those checks
belong to the consuming operator.

## Runtime environment

Runs in the shared Operon interpreter and needs no optional dependency.

## Limitations

Compressed inputs are passed through as they are: the artifact points at the
compressed file, and the consuming tool must be able to read that compression.
The declared memory modes are full; the payload is never loaded into memory by
this Reader.

## Examples

Connect a `FileReader` source to an operator that declares a file port, for
example `structure_md_pca` (`trajectory` and `topology` roles) or `vina_dock`
(`receptor` and `ligand`). Keep both sources explicit, because automatic
selection returns the typed Reader when one exists for the same suffix.

## Source

Implementation: `src/reader/readers/file_reader.py` (`FileReader`).
