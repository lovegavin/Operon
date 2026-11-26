# Operon 5.11.2 test report

- `pytest tests/test_structure_label_decoding.py tests/test_extension113.py tests/test_colabfold_sequence.py -q`
  -> 21 passed, 1 skipped (includes the new hetero-row tests).
- Manual: `3DI3.cif` -> `structure_convert_format` now writes 2402 polymer atoms
  (866 chain A + 1536 chain B) instead of 2500 with water placeholders;
  `structure_extract_chain` A,B preserves coordinates and residue numbers.
- `interface_contact_map` on the extracted pair reports 36 contacting residue pairs
  (2.73-4.49 A) and `interface_bsa` 1407 A^2 buried, so the geometry is intact.
