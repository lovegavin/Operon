# Structure Format Conversion

Converts a structure Form into a coordinate-complete PDB file and returns the
same atoms as a PDB-style Form. It is the in-workflow replacement for ad-hoc
`gemmi`/shell conversion when a route starts from mmCIF (for example 3DI3):
`MmcifReader -> structure_convert_format -> structure_*`.

## Inputs and outputs

* Input: a 2D Form `[atom, field]` from `MmcifReader`, `PdbReader` or any
  structure-producing operator.
* Output: a 2D Form with the canonical `PdbReader` fields (`x`, `y`, `z`,
  `atom_name`, `resname`, `chain`, `residue_number`, `element`, ...), plus a
  native `converted.pdb` artifact.

## Parameters

| Name | Default | Meaning |
| --- | --- | --- |
| `filename` | `converted.pdb` | Native file name (`.pdb` only). |
| `chain` | `A` | Fallback chain when the input has no chain column. |
| `resname` | `UNK` | Fallback residue name. |
| `include_hetatm` | `false` | Write waters/ligands as `HETATM`. |

## Limitations

* Requires numeric `x`/`y`/`z` (or `Cartn_x`/`Cartn_y`/`Cartn_z`) columns.
* Alternate locations are preserved only when an `altloc` column exists.
* Multi-model mmCIF files are flattened to the first model by the reader.
* The operator performs a format conversion, not coordinate repair; use
  PDBFixer for missing atoms.
