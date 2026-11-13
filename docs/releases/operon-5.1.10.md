# Operon Studio 5.1.10

Released 2026-11-14.

## Fixes

- **Managed server libraries are recognized.** `operon.installation.library_root()`
  now accepts both desktop installs (`versions/<version>/library`) and managed
  remote installs (`code-<id>/library`). Previously the managed layout returned
  `None`, so the environment manifest fell back to
  `operon/_no_library/operon/environments.json` and remote `openmm81` could not
  be prepared.
- **Environment preparation no longer scans the whole library.** When
  `environment_prepare` was asked to repair dependencies, it called
  `dependencies.check()` without ids, checking all 1174 operators one by one and
  holding the plugin lock for tens of minutes. It now checks only the operators
  that declare the environments being prepared. This removes the submit
  timeouts seen on the remote server during a full-library sweep.
- Extended-length (``\\?\``) paths are normalized before launching isolated
  interpreters, so OpenMM imports resolve `OpenMM.libs` correctly.

## Compatibility

- Application 5.1.10.
- Built-in operator library `main` 0.1.1 (1174 descriptors, 7 packages) and route
  collection 0.1.1 (79 routes). Both are unchanged by this release.
- Existing desktop and managed-server installations keep their library and
  workspace; only the application payload is replaced.
