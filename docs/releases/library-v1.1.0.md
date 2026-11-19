# Operon library 1.1.0

- Adds the AlphaFold2 operator family: `alphafold2_predict`, `alphafold2_batch_predict`,
  `alphafold2_msa_search` and `alphafold2_rank_models`, each with its parameter sidecar and
  documentation page.
- The `alphafold2` environment is now a real environment: `planned` is cleared, it requires
  `alphafold==2.3.2`, and the four new operators are assigned to it (1,177 -> 1,181 assignments).
- Resource expectations are unchanged: the operators read `params/` and the MSA databases from
  the `afdb` root declared by `resources.json`.

Minimum application: 5.7.0.
