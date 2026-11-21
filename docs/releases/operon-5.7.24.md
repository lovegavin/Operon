# Operon Studio 5.7.24

5.7.24 repairs the route-execution, environment and deployment paths that the
desktop canvas, the CLI and an agent-driven server all use, so a graph prepared
in the UI reaches the remote worker and comes back with results.

## Fixed

- **Canvas plans no longer fail on a frozen `keep`.** The graph contract freezes
  lists into tuples, so `runtime.memory.keep` arrived as `()` and the manifest
  validation rejected it. The parser now accepts any sequence and normalises it
  back to a list before validating the entries.
- **The plan kernel carries what the provider packages import.** The frozen code
  tree only followed the imports of the kernel modules themselves, so a reader
  that imports `src.core.numeric` failed with `ModuleNotFoundError` inside the
  worker. Provider namespaces are now scanned for `src.*` imports before the
  kernel digest is computed.
- **A reader stays a reader when it declares an environment.** The native
  bootstrap wrapped every descriptor with `resources.environment` in the
  environment proxy, including readers, which then had no `read` method. Only
  operators are wrapped; readers keep `read`/`probe`.
- **A portable CPython falls back to the newest patch of the selected minor.**
  The store asked uv for the exact patch the server runs (for example 3.11.18),
  which python-build-standalone does not publish. It now retries with the minor
  and accepts the newest available patch, while a different minor still fails.
- **conda-pack gets the `pkg_resources` provider it imports and exports a
  pip-modified prefix.** The tooling install adds `setuptools<81`, and the pack
  call passes `ignore_missing_files=True` so an Operon environment, which pip
  has written into, can still be exported.
- **pip output keeps moving and a quiet download is not a stall.** pip runs with
  `PYTHONUNBUFFERED=1` and `--progress-bar off`, the resolve grace is one hour,
  and the watchdog treats bytes moving through the child process as liveness.
- **A cached tool miss is re-checked.** Installing an environment that provides
  an external tool now surfaces it without restarting the server.
- **The submit timeout is configurable** through `OPERON_SUBMIT_TIMEOUT`
  (default 900 s) instead of a hard-coded client timeout.
- **A stale page rotates its own session token.** A write request that returns
  401/403 fetches `/api/bootstrap` once, retries with the fresh token and only
  then reports the failure, so a desktop restart no longer makes every
  environment button look dead until the page is reloaded by hand.
- **A ready environment can install its optional bindings.** `prepare` used to
  skip ready environments, so the optional bindings that had failed earlier
  (a reader dependency without a wheel, for example) could never be retried.
  The endpoint accepts `force`, the repair action uses it, and the panel offers
  a separate "补装可选依赖" action for a ready environment with missing
  optional bindings.
- **One optional binding can no longer hide the others.** Optional bindings
  were installed with a single pip command, so a source-only package such as
  `vina` aborted the batch and `pyarrow`, `pysam`, `pyBigWig`, `bed-reader`,
  `bgen-reader` and `pgenlib` were never installed. Each binding is now
  attempted on its own and a failure is reported per item.
- **A single-unit workflow can be scheduled on the frozen pool.** The admission
  reserved the whole frozen capacity for the unit while the pool removed a
  second management reserve from the same number, so a one-slot workflow was
  always infeasible. An admission-driven pool now schedules the whole capacity
  it froze; a pool without admission keeps its reserve.
- **The saved job table is merged instead of replaced.** A desktop window and an
  agent-driven server share `remote/profiles.json`; whoever wrote last used to
  erase the other's job records, which made completed jobs vanish from
  `operon jobs` after a restart. Saving now unions the records on disk with the
  records in memory.
- **A key profile reconnects before the server is reported offline.** Planning
  drops disconnected servers from the candidates, so a graph aimed at a key
  profile failed with "the server profile may be missing or disconnected". Both
  the planner and the remote launcher now reconnect a key/agent profile in
  place; a password profile is still left to the user.

## Library

The bundled library stays at 1.1.14. The environment declarations in
`library/seed/operon/environments.json` changed: `core` declares the modules its
bound operators and readers import (including `coverage` and `libdeflate`, which
`numba` and `pysam` need at import time), `vina` and the binary-reader wheels are
declared as best-effort bindings, and `esm2` declares `biotite` and
`torch_geometric`. A declaration guard in `tests/test_environment_declarations.py`
keeps the declared set in step with what `builtin_packages.json` requires.
