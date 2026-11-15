# Operator Library 0.1.21

`proteinmpnn_design` can now keep a set of residues fixed, which the interface
maturation loop needs. The 0.1.20 `fixed_positions` implementation wrote the
ProteinMPNN JSONL keyed by the absolute PDB path, while ProteinMPNN looks the
entry up by the PDB basename stem (`b['name']`). Every fixed-position run failed
with:

```
KeyError: 'complex_d3'
  protein_mpnn_utils.py:308 tied_featurize
    fixed_pos_list = fixed_position_dict[b['name']][letter]
```

0.1.21 keys the JSONL by `structure_path.stem`, so `fixed_positions` and
`design_ranges` both work.

## What changed

- `library/seed/src/task/step/steps/proteinmpnn_design.py`: the
  `fixed_positions.jsonl` payload is keyed by the PDB stem instead of the full
  path; a comment records why.
- Library version 0.1.21 (no application change, no protocol change).

## Evidence

Round-2 interface maturation on the best round-1 design (`complex_d3.pdb`, 88 aa
binder chain A, 193 aa target chain B):

- interface positions fixed: 1, 2, 3, 27-34, 49-51, 53, 77-82 (21 residues,
  taken from an `interface_hotspots` run with 48 contact rows);
- job `req-6cfc03945b2799c6b1c193f3`, GPU (RTX 3090), 11.7 s, 8 designs;
- all 8 designs keep the 21 fixed positions identical to the input structure and
  mutate 26-37 of the remaining 67 positions.

## Assets

- `operon-library-main-v0.1.21.operon-library.zip` (6,870,205 bytes)
- `operon-routes-main-v0.1.21.zip` (201,489 bytes, 79 routes)

This library release does not hold the repository `latest` pointer; the newest
application release keeps it.
