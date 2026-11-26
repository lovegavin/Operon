# Operon 5.11.2

## Structure exports keep polymer atoms only

`structure_convert_format` and `structure_extract_chain` used to write every row of
a structure form into the PDB. mmCIF files carry waters, ions and ligands whose
`label_seq_id` is `.`; the writers filled those gaps with `atom index + 1`, so a
crystallographic chain came out with residue numbers such as 510 or 1350 while the
coordinates stayed intact. Interface operators then grouped those rows as residues
and reported empty contacts.

Both steps now drop non-polymer rows by default (`group_pdb` starts with `HETATM`,
with a solvent/ligand residue-name fallback), keep `include_hetatm=True` for the
opt-in path and write those rows as `HETATM` records. Polymer atoms, coordinates and
residue numbers are unchanged; `1CRN`/`1UBQ` round trips stay exact.

## Library 2.1.3

Library metadata follows the application version; no operator signatures changed.

## Known limits

- `export_results` of a produced PDB still needs the producer and the export step in
  the same task; isolated export attribution remains a separate fix.
- Slurm compute-node placement is validated separately through `sacct`.
