# Operon Studio 5.1.9

This patch fixes isolated-environment installation on Windows and supersedes the
unpublished 5.1.7 build.

## Fixed

- Readiness and dependency probes no longer run with the environment directory
  as their current directory. A probe that kept the directory open made the
  final atomic rename fail with `WinError 5` after the working environment had
  already been renamed away, leaving the environment unusable.
- Environment probes now receive the same DLL search directories as the real
  worker (`Scripts`, the environment root, `Library/bin`, `bin`), so an
  installed OpenMM 8.1.1 environment is probed under the same loader
  conditions as execution.
- The installer commits an environment with retries and rolls back to the
  previous directory if the rename still fails, raising an actionable error
  instead of deleting the working environment.
- An environment being installed reports `installing` while a create/install/
  probe/commit phase is active, so readiness does not probe a directory that is
  being swapped.
- Dependency and environment probes decode child output explicitly as UTF-8
  with replacement and run children with `-X utf8`. `-I` implies `-E`, so
  without that flag a Chinese Windows host emitted GBK and produced
  `UnicodeDecodeError` or mojibake in readiness diagnostics.
- The probe error path no longer slices a missing `stderr` and reports the
  captured stdout or a neutral message instead.

## Compatibility

- No protocol, bundle, job, route, library or provenance changes.
- `bundle_format=1`, `operator_protocol=3`; all 5.1.x libraries remain valid.

## Extended-length paths

`installation.library_root()`, `environments.root()/resolve()`, the readiness
probe and the environment installer now strip Windows' `\\?\` prefix before
starting a child interpreter.  An install opened through a junction could
otherwise launch `Scripts\python.exe` with an extended path; Python then
reported `sys.prefix` in that form and OpenMM's `_openmm` extension failed to
locate `OpenMM.dll` even though a direct import worked.


## Library 0.1.1

- Bundles the vendored PDBFixer runtime files (`pdbfixer.py`, `soft.xml`, templates) and the resource manifest (`resources.json`) that the library builder previously omitted.
- Rebuilt library and routes with matching pins; the base library installed with Studio is `main-v0.1.1`.
