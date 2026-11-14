# Operon Library 0.1.6

Release date: 2026-11-14

## Scope

Patch release for large-resource downloads. No operator behavior changed.

- `resources.json` now declares direct downloads for:
  - RFdiffusion `Base_ckpt.pt` and `Complex_beta_ckpt.pt`
  - OpenFold `finetuning_2.pt`
  - AntiFold `trained_models/model.pt`
- Added per-operator deployment references under
  `docs/deployment/resource-configs/` (one JSON file per operator; no shared
  global configuration).
- The existing ESM2 / ESM-IF1 / ESMFold / Boltz downloads are unchanged.

## Compatibility

- `minimum_application`: 5.1.6
- `build_application`: 5.1.16
- Operator count: 1069; readers: 108; packages: 7; routes: 79.

## Download limits

`resource_fetch` only downloads manifest-declared HTTPS files. Repository
checkouts, gated resources (ESM3), and the ~220 GB ColabFold databases are not
default downloads; configure them manually.

## Verification

- registry check: 0 errors
- focused resource tests: passed
- bundle/routes builder gate: passed
- installed into a clean 5.1.17 runtime: 16 resources, downloads metadata
  visible for RFdiffusion/OpenFold/AntiFold
