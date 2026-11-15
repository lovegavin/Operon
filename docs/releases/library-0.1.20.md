# Operator library 0.1.20

Release: `operon-library-main-v0.1.20`
Build application: 5.1.17 · Minimum application: 5.1.6 · Bundle format 1

## Contents

| Item | Value |
|---|---|
| Packages | 7 (`operon-core`, `-expression`, `-genetics`, `-hic`, `-microbiome`, `-plots`, `-readers`) |
| Operators | 1069 |
| Readers | 108 |
| Descriptors | 1177 |
| Route templates | 79 |
| Registry errors | 0 |

## Fixes

1. **`proteinmpnn_design` detects CUDA through its interpreter.**
   `device=cuda` used to fail with `device 'cuda' requested but CUDA is not
   available` because the probe imported `torch` in the worker interpreter, which
   is the application runtime and carries no torch. The probe now runs
   `python_executable` (the isolated environment) as a subprocess and asks that
   interpreter whether CUDA is usable, before falling back to a local import.

2. **`proteinmpnn_design` device selection no longer widens GPU exposure.**
   `device=cpu` sets `CUDA_VISIBLE_DEVICES=-1` so `torch.load(map_location=...)`
   cannot pick CUDA device 0 while CUDA is masked; `device=cuda` keeps the device
   list the pool reserved instead of dropping the variable, so a job sees only the
   GPU it was granted.

3. **`proteinmpnn_design` accepts CA-only checkpoints.**
   The CA-only weights (`ca_model_weights/v_48_020.pt`) previously failed with a
   `state_dict` shape mismatch (`features.edge_embedding.weight` 167 vs 416). The
   new `ca_only` parameter (default `false`) passes `--ca_only` to
   `protein_mpnn_run.py`.

4. **`boltz_complex_confidence` resolves the weight cache from the library.**
   An empty `cache_dir` now falls back to the declared `boltz` resource root before
   Boltz falls back to its own cache, so weights downloaded through the library
   resource API are found without an explicit path.

## Evidence

- ProteinMPNN round 1 on the s6 complex binder chain, `device=cuda`, `ca_only=true`:
  job `req-1075029ecd4212dfc2ed62e1`, 11.6 s, 8 designs (score 0.9265–1.0143,
  sequence recovery 0.3295–0.4432), artifact `[8, 3]`.
- Eight Boltz complex predictions ranked in the same session; the best redesign
  reached `iptm 0.3785` with interface pLDDT `75.96`, above the previous best
  structure (`iptm 0.3676`, interface pLDDT `69.98`).
- `operon_library_builder gate`: bundle structure and `SHA256SUMS`, no `operon`
  import in builder sources, descriptors validated against the protocol schema,
  and all seven wheels verified (digest, identity, entry points, archive).

## Assets

| Asset | Bytes | SHA-256 |
|---|---:|---|
| `operon-library-main-v0.1.20.operon-library.zip` | 6,870,166 | `8bddfc5cd18ad4e038b57c5acdf36a185cda4c3e249f6c907d361b91a60e58ba` |
| `operon-routes-main-v0.1.20.zip` | 201,294 | `584316857e06f57ee02530c8ec0ec3f5c476e9f769e0b07acb79eed9e269d631` |

This library release does not hold the repository `latest` pointer; the newest
application release keeps it.
