# Operon Studio 5.1.4

## Base operator library

A packaged Studio now includes the base `main` operator library under
`library/base/`. It is installed automatically on the first start, so a new
installation shows `main-v0.1.0` in 算子库管理 instead of an empty list.

- If libraries are already registered, startup never overwrites them.
- Deleting every library keeps a marker and does not resurrect the base library.
- A failed base install only logs a warning; startup still succeeds.
- A failed library import no longer leaves an orphan archive directory.

## Route library import

Importing a route collection now registers its routes immediately. The
redundant checkbox list and “添加到算子库” button are removed; the panel shows
the imported routes as read-only status.

## Compatibility

`bundle_format=1`, `operator_protocol=3`, multi-library branches and per-run
provenance/run skeletons are unchanged. Operator libraries built for 5.1.x
remain usable.
