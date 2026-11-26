# Operon 5.11.2

## Design tasks run end to end

- `rfdiffusion_design` can return a single design or all of them, and `design_index`
  selects one model for the next step (`0` keeps the stacked `[design, atom, field]`
  form). `proteinmpnn_design` accepts that stacked form and slices the requested
  design; its structure port no longer declares a 2-D payload, so a design form can
  be wired directly.
- A step that runs in an isolated environment now receives the task output root and
  the parent export registry, and an export step resolves a producer port from the
  recorded export entry when the bridge loaded only that one step. `export_results`
  can therefore copy the PDB that `colabfold_predict` wrote in the previous step
  instead of failing with “no matching original pdb file”.

## Structures and PDB files

- The PDB writers keep blank `altLoc` and insertion-code markers instead of writing
  `_`, so readers such as ProteinMPNN parse chain IDs and residue numbers again.
- A stacked design table keeps the reader label encoders, so a chip writes real atom
  names, residue names and chain IDs instead of their numeric codes.
- `structure_convert_format` and `structure_extract_chain` keep polymer atoms only:
  waters, ions and ligands whose `label_seq_id` is `.` no longer inflate residue
  numbers, and `include_hetatm=True` still writes them as `HETATM` records.

## Deployment

- Deploy source digests hash the canonical tar instead of the gzip container, so a
  tree archived on Windows and a checkout on Linux produce the same identity and a
  managed server no longer reports `stale_build` after an upgrade.
- The deploy archive now packs exactly the files the release does, so operator
  library seeds match between a checkout and an installed tree.
- A path parameter that is wired in the canvas no longer requires a non-empty
  default, and a pin failure names the missing packages and the install command.

## Agent-facing contracts

- `operon_sessions` and the workflow list return bounded `{items, total}` envelopes;
  the saved-workflow brief projection drops the full interface contract and reports
  `node_count` instead of every node.
- An empty or unmatched operator search answers with guidance (counts, categories and
  example queries) instead of a page of unrelated operators.
- Canvas context exposes `session_name`, `document_name` and `documents[]` while
  `name` keeps the document title; the guide states that `revision` is for edits and
  `ui_revision` tracks selection only.

## Library 2.1.3

Library metadata follows the application version. RFdiffusion and ProteinMPNN gained
the `design_index` parameter, the ProteinMPNN structure port accepts a design form,
and a producer port recorded by an isolated step resolves again.

## Known limits

- Slurm compute-node placement is validated separately through `sacct`.
- `colabfold_predict` expects its weights to be present with the model's completion
  marker; offline clusters cannot download them on first use.
