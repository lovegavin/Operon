# Operon Studio 5.7.34

The pool no longer refuses work that arrives while another task runs, and the
last dependency that only existed as a source build becomes a resource.

## Added

- `library`: `vina` ships as a downloadable resource
  (`vina_1.2.5_linux_x86_64`, 4,089,576 bytes) and `vina_dock` /
  `vina_dock_batch` resolve it through `_vina_common.resolve_binary`, so
  docking works on a machine that cannot build the Python binding (PyPI has no
  cp311 wheel and the source build fails on CentOS 7).
- `application`: the shared pool reports a busy version gate as
  `503 pool_busy` with `details.retryable = true` instead of the generic
  `engine_unavailable`, so a client knows to retry rather than treat it as an
  operator failure.

## Fixed

- `pool`: a registration that does not name a library keeps the binding the
  workspace already runs with. Re-deriving it from the application directory
  made the catalog policy look changed on every submit, and the pool answered
  `Finish tasks before changing its application, interpreter or catalog policy`
  whenever another task was active — which is what turned most of the sweep's
  concurrent submissions into failures.
- `environments`: `core` no longer lists `vina==1.2.5` among its optional
  bindings, so an environment that cannot install it is still ready.

## Notes

- Library version `1.1.22`, minimum application `5.7.20`.
