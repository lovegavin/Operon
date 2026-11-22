# Operon Studio 5.7.26

5.7.26 makes the environment panel tell the truth about a dependency that was
installed from a wheel URL. Everything else is 5.7.25.

## Fixed

- **A wheel declared by URL reports its project name.** PyG publishes
  `torch_scatter` only on `data.pyg.org`, so `esm2` declares the wheel as a URL.
  The installer pip-installed it and `import torch_scatter` worked, but the
  readiness table asked for a project name and got the whole URL back, never
  matched `torch_scatter-2.1.2.dist-info`, and left the environment at
  `incomplete` with one dependency that could never turn true. Both dependency
  tables (the engine one used by a remote host and the one used for a local
  environment) now read the project out of the wheel filename, which also covers
  a local `.whl` path. `tests/test_wheel_requirement_name.py`.

## Environment repair that this unblocks

`esm2` installs `pydantic==2.14.3` and the PyG `torch_scatter` wheel because
`esm/inverse_folding/gvp_modules.py` imports `torch_scatter` and the ESM-IF
family needs pydantic. With this build the panel reaches `ready` instead of
`incomplete`, which is what the seven `esm_if_*` operators wait for.

## Verification

- `pytest tests/test_wheel_requirement_name.py` — 3 passed.
- `esm2` reinstalled on licai-srv: `import biotite, esm, torch, torch_geometric,
  pydantic, torch_scatter` all succeed in the staging interpreter, and the
  panel reports the environment `ready` after the rebuild.
- `esm_if_masked_region_scan` on 1CRN (seed 5) completes in 106.8 s with the
  `<EOS>` token fix from `08f3e4a54`.

## Library

Unchanged at `main-v1.1.16` (7 packages, 1182 descriptors, 1074 operators,
79 routes).
