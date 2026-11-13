# Operon Studio 5.1.2

Release date: 2026-11-13

## Operator library names

An imported library is now identified by a primary name and a version instead
of one free-form label. The label is always ``<name>-v<version>``.

- The primary name defaults to ``main``.
- The version field is optional; when blank the bundle's own ``library_version``
  is used. A version that does not match the bundle is rejected.
- Examples: ``main-v0.0.0``, ``main-v0.1.0``, ``fork1-v0.0.0``.

The import dialog therefore shows two fields: library name and version. The
backend, HTTP API (``POST /api/libraries/install``), CLI
(``operon library install --name --version``) and MCP tool
(``operon_library_install(path, name, version)``) accept both.

## Compatibility

- Bundle format 1, operator protocol 3, 8.x libraries still rejected.
- Libraries, routes, job provenance and ``runs/<job-id>`` skeletons are
  unchanged.
- Existing branches keep their recorded labels; new imports use the pair.
