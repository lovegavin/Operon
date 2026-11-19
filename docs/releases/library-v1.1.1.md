# Operator library 1.1.1

Released 2026-11-19 with Operon Studio 5.7.1.

## Changed

- `resources.json`: the `alphafold2` resource declares a per-file download for
  `params/params_model_1_ptm.npz` (the AlphaFold-2 parameter tarball on the
  public Google Cloud bucket), so the unit can be completed file by file
  instead of downloading a project page.
- `environments.json`: `alphafold2` requires `numpy`, which the environment
  bridge needs to move inputs and outputs between the service and the
  environment process.

No operator signatures changed; existing workflows stay valid.
