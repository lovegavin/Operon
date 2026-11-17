# Operator library main-v0.1.29

Released 2026-11-18. Requires Operon Studio 5.5.0 or newer.

This bundle restores the isolated environments that `main-v0.1.28` shipped, adds
the resource fetch and link helpers, and refreshes the resource manifest.

- Seven isolated environments: `antifold`, `boltz`, `colabfold`, `esm3`,
  `esmfold`, `openfold`, `openmm81`.
- New operators: `ResourceFetch` (`resource_fetch.ResourceFetchStep`) downloads the
  declared files of one resource into a target root.
- New helpers used by the application: `resource_link.link` / `resource_link.unlink`
  create and remove junctions, symlinks and hardlinks for a resource root, and
  `_resources_common` gains `link_roots`, `expected_files`, `receipt_path`,
  `read_receipt`, `write_receipt` and `link_state`.
- Resource manifest: sixteen resources, seven of them with declared `downloads`,
  `expected_files` for every resource, and shared plus per-resource `link_roots`.
- Restored operators that the 5.5.0 application tree had dropped:
  `structure_convert_format` and `structure_extract_chain`.
- Refreshed resource-facing operators from the library branch
  (`antibody_developability`, `antifold_score`, `boltz_complex_confidence`,
  `colabfold_predict`, `esmfold_predict`, `openfold_predict`,
  `proteinmpnn_design`, `rfdiffusion_design`, `structure_openmm_energy`,
  `structure_openmm_md_rmsf`, `structure_openmm_md_stability`, plus
  `_openmm_platforms`).

Contents: 7 packages, 1069 operators, 108 Readers, 1177 descriptors.
