# Operator library 0.1.23

Fix for a deadlock in the complex-prediction operator on Linux GPUs, found while re-running one of the
retained designs on a remote RTX 3090.

## What was wrong

`boltz_complex_confidence` hard-coded `--num_workers 1` when it built the Boltz command line. On Linux,
Boltz initialises CUDA and then forks its data-loader worker; the forked child inherits an initialised CUDA
context and the two processes deadlock. The symptom is a job that holds its lease and a GPU that stays at
0 % utilisation, with the main thread parked in `futex_wait_queue_me` and no Boltz output in the log.
Running the same `complex.yaml` by hand with `--num_workers 0` finished in 190.6 s.

## What changed

- `boltz_complex_confidence` takes a `num_workers` parameter (integer, default 0, range 0-8) and passes it
  to Boltz instead of the hard-coded value. The parameter is documented in the operator's sidecar with
  `x-ui-group: 模型`, so it appears in the canvas inspector.
- `library/release.json` now reports `0.1.23` (it had been left at `0.1.11`).
- No environment declaration changed: `environments.json` is byte-identical to 0.1.22, so existing
  environments stay `ready` and are not rebuilt.

## Evidence

Remote re-execution of the s6 complex under this library, `boltz1`, CUDA, 20 sampling steps:

| Host | Job | iPTM | Interface residues | Interface pLDDT |
|---|---|---:|---:|---:|
| remote, 0.1.23 | `...-req-5d6972ab0a0df2fb5f2229c2` | 0.0605 | 63 | 67.74 |
| remote, 0.1.23 | `...-req-d2913e71d087bcef7ff1264a` | 0.4412 | 61 | 69.44 |
| local, 0.1.23 | `req-6411a07a52e65e7ab256f182` | 0.3287 | 60 | 68.92 |

The job completes in 103 s on the remote host with `--num_workers 0`. The spread across draws is sampling
noise, not a host difference; see `docs/releases/design-loop.md` for the full four-draw table.

## Assets

- `operon-library-main-v0.1.23.operon-library.zip` — 6,870,732 B, sha256
  `dc70235224d0c891314a77262d9dc3e79879cd8cd71af2dc353e6b2ca8328ad0`
- `operon-routes-main-v0.1.23.zip` — 201,383 B, sha256
  `47b7ee8caf79ae6997359682e4e0da151496f774cdb00548e035ab28e9c123ba`
- `SHA256SUMS.txt`

Registry: 1069 operators, 108 Readers, 7 packages, 1177 descriptors, 79 routes, 0 errors.

## Upgrading

Remove the installed library, then install this bundle; in-place replacement is not supported because the
label carries the version. The application version does not change, and saved graphs do not need repinning.
