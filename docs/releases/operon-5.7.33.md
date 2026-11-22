# Operon Studio 5.7.33

Two defects the operator sweep exposed, both fixed inside the library bundle.

## Added

- `library`: the ProteinMPNN interface operators (`proteinmpnn_hotspot_masked_design`,
  `proteinmpnn_interface_scan`, `proteinmpnn_interface_temperature_scan`,
  `proteinmpnn_masked_interface_design`, `proteinmpnn_masked_interface_score`)
  re-emit the wired atom form into a temporary PDB when no `structure_path` is
  passed, so a route that already carries the coordinates no longer asks for the
  same file twice.
- `library`: `esm_if_*` and `esm_*` operators fall back to the checkpoint their
  resource declares instead of demanding an explicit `model_path`.

## Fixed

- `environments`: every environment declares `pydantic` (the plugin registry
  imports `operon_sdk.protocol`, so an environment without it fails before the
  operator starts; the sweep showed 18 operators hit this).
- `environments`: `hmmer` declares `numpy`, which `hmmer_domains` imports.
- `environments`: `antismash` pins `ncbi-amrfinderplus=4.2.5`, because the
  current AMRFinderPlus database refuses any binary older than 4.2.0.

## Notes

- Library version `1.1.21`, minimum application `5.7.20`.
