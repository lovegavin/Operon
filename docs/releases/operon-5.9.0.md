# Operon Studio 5.9.0

Released 2026-11-25. Library: main-v2.0.0.

5.9.0 makes ports the only transport for run data. A step now receives its
inputs from declared ports and offers its product on a declared output port; a
parameter can configure a step, but it can no longer be the way data enters or
leaves. The rule is enforced by the registry, so a future operator cannot quietly
reintroduce a path-only interface.

## Changed

- **54 operators declare the port they were missing.** The structure, design,
  folding and molecular-dynamics operators used to read `structure_path`,
  `fasta_path`, `trajectory_path`, `topology_path`, `complex_path`, `ligand_path`,
  `pose_path`, `receptor_path`, `query_path`, `target_path` or
  `affinity_path` with no input port. They now declare a `form` port (structure,
  FASTA) or a `file_artifact` port (trajectory, topology, pose, receptor,
  affinity) and resolve the value through
  `library/seed/src/task/step/steps/_port_inputs.py`. The old parameter remains
  as an optional, empty-default override for direct API calls; a graph that
  supplies the port is not reported as missing data.
- **A generic `FileReader`.** Molecular-dynamics trajectories, docking poses and
  model inputs had no Reader that could hand them to an operator. `FileReader`
  publishes a `file_artifact` for an explicit list of suffixes, records the
  representation from the extension (compression suffixes stripped, `fa`/`faa`/
  `fna`/`fas` -> `fasta`, `mmcif` -> `cif`) and never parses the payload. Reader
  count: 109 -> 110.
- **`result_report` is a terminal step.** It registered its report as a native
  result and also declared an `output` port, which made a report look like a
  data producer. It now declares no output port and no output parameter, like
  `histogram` and the other report steps.
- **`msa_trim` emits a form.** The trimmed alignment is a numeric
  sequence-by-position form (gap positions are `NaN`, the residue map is in
  `info`), so `export_results` can render FASTA from it. This is the one emitter
  whose product a Form represents without loss.
- **The registry enforces the policy.** `operon/port_rules.py` is applied by
  `operon registry build` and `registry check`: a `file_artifact` output is
  allowed only for the sixteen operators whose product cannot be a lossless
  form, each with a recorded reason; a converted emitter may not emit a file
  again; every `*_path` must be classified as tool, weights, resource or output;
  a run-data path requires an input port; a Reader declares no inputs.

## Migration

- A saved workflow that passed a structure or FASTA through a path parameter
  keeps working through the optional override, but the portable form is
  `PdbReader`/`FastaReader` -> operator, or `FileReader` -> operator for
  trajectories, poses and other file-shaped inputs.
- `result_report` no longer has an `output` parameter. Remove the property from
  saved parameter JSON if a workflow still sets it.
- The library version is 2.0.0: the port declarations are a breaking interface
  change for anything that read an operator's parameters to build a graph.

## Verification

- Registry: 1074 operators, 110 readers, 79 routes, 0 errors; package index
  regenerated and `registry check --scope packages` reports no change.
- Unit tests: `tests/test_port_rules.py` (10), `tests/test_port_inputs.py` (9),
  `tests/test_file_reader.py` (6), `tests/test_result_report.py` (3),
  `tests/test_extension380.py` (9) pass; the 62 test modules that touch the
  converted operators show no new failure against the HEAD baseline (97
  environment-gated failures remain because isolated environments are not
  installed on this build host).
- The exported-FASTA path is covered end to end:
  `tests/test_export_contract.py::test_export_results_fasta_from_trimmed_alignment`
  runs `msa_trim` -> `export_results` and checks three `>` records.

## Notes

- This release was verified on the build host only; no remote server was
  upgraded.
- `align_reads`, `build_contacts`, the eight VCF producers, `consensus_sequence`,
  `liftover_intervals`, the AlphaFold-2 PDB/A3M/batch products and
  `alphafold2_msa_search` keep a `file_artifact` output; the reasons are listed in
  `operon/port_rules.py` and in `docs/design/port_contract_inventory.md`.
