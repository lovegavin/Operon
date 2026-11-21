# Operon Studio 5.7.25

5.7.25 fixes the two ESM-IF defects that the format-faithful sweep found and
ships the declarations that make the inverse-folding family installable from a
clean environment.

## Fixed

- **A sampled ESM-IF design is read as residues, not as characters.**
  `GVPTransformerModel.sample` joins raw dictionary tokens, so a sample that
  picks `<EOS>` or `<unk>` returns a longer string than the chain: 1CRN chain A
  is 46 residues and a masked window at position 34 samples
  `TTCCPSIVARSNFNVCRLPGTPEAICATYTGCII<EOS>GKKKKPGDYAN`, 50 characters. The five
  `esm_if_*` operators compared that string against the residue count and failed
  the job with "the sampled design has length 50, expected 46". A shared
  `design_letters()` helper now splits the sampled string into tokens, turns a
  special token into `X` so recovery counts it as a mismatch, and only then
  checks the residue count.

## Library

The bundled library moves to **1.1.16**:

- `esm2` declares the modules that `esm.inverse_folding` imports at load time:
  `pydantic` (imported by the model wrapper) and `torch_scatter`, installed from
  the PyG wheel that matches the environment's `torch 2.3.1+cu121`. Without
  them the seven `esm_if_*` operators failed with
  `No module named 'pydantic'` and, once that was installed,
  `No module named 'torch_scatter'`.
- The ESM-IF design fix above is part of the library payload, so a fresh server
  install carries it.

## Verification

The fix was reproduced and confirmed on the deployment at
`code-9ce292db890c14acab61` (library `main-v1.1.16`):

- `esm_if_masked_region_scan` on 1CRN chain A, window 6, seed 5: **complete in
  106.8 s** (`exec-d205eb0d8927403889d84e3353cfde62`); the same graph with the
  previous build failed in 97.1 s with the length error.
- `esm_if_design` 58.4 s, `esm_if_position_entropy` 42.8 s and
  `esm_if_redesign` 51.3 s complete on the same input with the checkpoint
  `esm_if1_gvp4_t16_142M_UR50.pt`.
- The four `fba_*` operators complete against the BiGG `e_coli_core` model
  (37.2 s, 37.3 s, 36.9 s and 30.7 s).
- `interval_annotate` completes in 36.6 s on a two-BED route, which exercises
  the `strict_classes` parameter that 1.1.15 started declaring.

The full 5.7.24 acceptance matrix (route inventory, reader coverage, test
suites) still applies; this release only changes the library payload and the
version string.
