# Operon Studio 5.9.3

Library: 2.0.0 (unchanged)

## Fixes

- Installing the provider library on a managed server now uses library
  semantics. `operon/remote/library.py` called the package installer without
  `library=True`, so the target builder treated the library's bare operator IDs
  (for example `pca`) as plugin IDs and every remote library install failed with
  `Plugin IDs must be namespaced`. The archive path already passed the flag.
- Regression test: `tests/test_remote_library.py::test_selected_bare_ids_install_with_library_semantics`
  installs a wheel with a non-namespaced ID through `install_selected`.
