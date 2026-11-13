# Operon Studio 5.1.3

Patch release for managed-server installation and library delivery in the 5.1 line.

## Fixed

- **Managed server install no longer fails with `FileNotFoundError`.** The build
  identity used to read `operon/builtin_packages.json`, which 5.x installations
  no longer ship. It now reads `<install>/library/registry.json` when the legacy
  seed is absent, so provisioning computes an identity for the installed library
  instead of aborting before the server is prepared.
- **Every imported library branch is delivered to a managed server.** The source
  archive now carries `library/libraries/<label>/archive.zip` as
  `library/operon-library-<label>.operon-library.zip`, and the Linux installer
  installs all delivered branches into the application tree's `library/`
  directory rather than only the last archive, and the server reads that
  directory as its version-scoped library.
- **Server identity is computed after the library is installed.** The installer
  compares the installed library digest with the desktop expectation and writes a
  receipt whose library fields describe what the server actually received. The
  server process now receives `library_root` explicitly, so pool and in-process
  execution resolve the delivered operators.
- **`library_release.library_name` is preserved.** Installing a second branch no
  longer rewrites the recorded primary name to `main`.

## Unchanged

- `bundle_format=1`, `operator_protocol=3`, multiple equal-status libraries with
  bundle-derived names, per-run provenance and `runs/<job-id>` skeletons.
- Libraries and routes published for 5.1.2 remain compatible.
