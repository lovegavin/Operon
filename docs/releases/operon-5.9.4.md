# Operon 5.9.4

This release fixes managed server deployments that reported the desktop build
identity while installing no operator library at all. Such a server advertised
1184 descriptors, yet every `/api/remote/{key}/environments` response was empty
because the environment manifest was never delivered.

## Fixed

- **The managed source archive now carries the library.** `source_archive()`
  (`operon/remote/provision.py`) ships `library/pyproject.toml`,
  `library/release.json`, `library/README.md` and the `library/seed` tree
  (excluding `__pycache__` and `.pyc` files). The managed installer therefore
  takes its `install_source` branch, builds the 7-package library on the
  server, writes the workspace registry and composes `environments.json`, and
  computes the same seed-derived identity as the desktop. Previously the
  archive omitted the library entirely, so the installer skipped the library
  branch and merely recorded the desktop-supplied identity
  (`receipt_build(identity, expected)`), which is why a server could advertise
  `library 2.0.0 / 1184 descriptors` with nothing installed.
- **Build handshake mismatches are logged.** When
  `provision()` detects that the local program changed between connect and
  install, it now writes both build ids to the setup log before raising
  `本地程序在准备期间发生变化，请重试。` (`code=build_changed`), and states that
  no file was uploaded and the server keeps its previous version.

## Compatibility

No protocol, descriptor or workflow change. The library stays 2.0.0. The
source archive grows by about 3.9 MB compressed so a managed install can build
the library itself; the installer path was already present and is now
exercised by every managed deployment.

## Verification

- `tests/test_remote_provision.py`: 15 passed, including the new
  `test_archive_carries_the_library_seed_for_managed_installs`.
- Identity parity probe on the repository tree: the archive is 3,869,690 bytes
  and `library_identity()` of the extracted deployment equals the desktop
  identity (`bundle_sha256 96eef2ac…`, 7 packages, 1184 descriptors).
- End-to-end UI force upgrade is recorded in the 5.9.4 test report once the
  installed build completes it.
