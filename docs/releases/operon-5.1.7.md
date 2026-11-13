# Operon Studio 5.1.7

This patch fixes readiness probes on hosts whose system locale is not UTF-8.

## Fixed

- Dependency and environment probes now decode child output explicitly as
  UTF-8 with replacement instead of using the operating system locale. On a
  Chinese Windows host the default codec is GBK, so a child that wrote UTF-8
  paths in an import traceback raised `UnicodeDecodeError` and turned every
  node of a prepared workflow into `failed`.
- The probe error path no longer slices `stderr` unconditionally: a failed
  probe with no captured error stream reports the captured stdout or a neutral
  "import failed" instead of raising `TypeError`.
- The same explicit UTF-8 decoding is applied to interpreter identity checks,
  portable-runtime probes, remote pip installs and `pip check`, and git
  metadata lookups, so non-ASCII paths cannot crash those paths either.
- Child probes are also started with `-X utf8`. They run under `-I`, which
  implies `-E` and makes Python ignore `PYTHONIOENCODING`/`PYTHONUTF8`, so
  without the flag the child still emitted GBK on a Chinese host and the
  parent's UTF-8 decode produced mojibake in the readiness message.

## Compatibility

- No protocol, bundle, job, route, library or provenance changes.
- `bundle_format=1`, `operator_protocol=3`; all 5.1.x libraries remain valid.
