# Operon Studio 5.9.3 test report

## Scope

The only behaviour change is the remote provider-library install path; the
application library is unchanged at 2.0.0.

## Automated tests

- `python3 -m pytest tests/test_remote_library.py -q` -> 15 passed.
- The new regression test builds a wheel with `OPERON_PLUGIN = {'name':
  'remote-bare-provider'}` and a step named `remote_bare_op`, uploads it through
  the transfer store, runs `install_selected`, and asserts the descriptor is
  registered. Before the fix the same call fails with
  `Plugin IDs must be namespaced`.

## Manual verification

- `verify593.py` is the packaged-artifact check for this release (payload,
  library bundle, server zip and installed import).
- End-to-end: install the provider library on `licai-srv` from the desktop UI
  (设置 -> 服务器 -> 强制同步算子库) and confirm the catalog returns 1184
  descriptors and the environment list is repopulated. This step requires the
  server to be reachable; it is recorded in the hand-over notes rather than
  claimed here before it is run.
