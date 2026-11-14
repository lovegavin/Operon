# Operon Library 0.1.9

## Changes

- `boltz_predict` now always passes an explicit `--cache` directory to Boltz.
  The directory is the first declared resource root
  (`~/.local/share/operon/resources/boltz` by default), created on first use.
  A fresh deployment therefore downloads weights into the location that
  `operon_resources` and every later run resolve, instead of Boltz's private
  default cache.
- Cache precedence remains explicit `cache_dir`, `OPERON_BOLTZ_CACHE`, the
  resource root, then the canonical fallback. All paths are expanded and
  created before the command is built; an unwritable path raises `StepError`.
- Added `tests/test_boltz_cache.py` covering missing-root creation, explicit
  override, environment override, canonical fallback and unwritable paths.

## Compatibility

`minimum_application` stays 5.1.6; the change is library-only.
