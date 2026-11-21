# Operon Studio 5.7.24

5.7.24 repairs the route-execution paths that the desktop canvas uses, so a graph
prepared in the UI reaches the remote worker and comes back with results.

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

## Library

The bundled library stays at 1.1.14; no operator declarations changed in this
release.
