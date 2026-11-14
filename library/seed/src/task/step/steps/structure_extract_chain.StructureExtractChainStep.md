# Structure Chain Extraction

Select one or more chains from a structure Form and materialise a native PDB
file plus a PDB-style Form.

## Purpose

Complex structures often carry several chains. Downstream interface, epitope or
per-chain quality operators expect one chain (or a defined pair), so a
deterministic extraction step is needed before them. `MmcifReader` also emits
mmCIF-style field names; this operator reuses the canonical field mapping from
`structure_convert_format` and therefore accepts both canonical (`x`, `y`, `z`)
and mmCIF (`Cartn_x`, `label_asym_id`) inputs.

## Parameters

| Name | Type | Default | Meaning |
| --- | --- | --- | --- |
| `chains` | string | `A` | Comma-separated chain identifiers, e.g. `A` or `A,B`. |
| `filename` | string | `chain.pdb` | Plain `.pdb` output name. |
| `atom_dim` / `field_dim` | string | `atom` / `field` | Input Form dimensions. |
| `output` | string | `output` | Output port name. |
| `include_hetatm` | boolean | `false` | Mark common solvent/ligand residues as HETATM. |

## Behaviour and limits

- Atoms are written in input order; `TER` separates chains; serial numbers are
  renumbered from 1.
- Only `ATOM`/`HETATM` rows from the selected chains are retained. Water and
  ligands are retained only when `include_hetatm=true`.
- Coordinates must be finite; a missing `x`/`Cartn_x` column is rejected with a
  `StepError` before any file is written.
- The output Form is reread through `PdbReader`, so it carries canonical
  `x/y/z`, `atom_name`, `chain`, `residue_number`, `resname`, `element`.
- This operator does not repair missing atoms, altlocs or models; it is a
  selector, not a structure preparation step.
