# Operon Studio 5.6.6

Released 2026-11-19. Application 5.6.6 ships with operator library 1.0.5.

## Fixed

- **F-53 — ProteinMPNN-family operators failed on Windows with `WinError 193`.**
  The ProteinMPNN, AntiFold, LigandMPNN and OpenFold steps defaulted
  `python_executable` to an empty string, so they launched the operator script
  with the engine host interpreter instead of the interpreter of the isolated
  environment they belong to. A new helper `_envpython.environment_python(name)`
  resolves `OPERON_ENV_<NAME>` first and then the registered environment, and
  nineteen steps now use
  `python_executable or environment_python("<environment>") or sys.executable`.
- **F-49 — operators whose required inputs are not in the catalog parameter
  schema.** The sweep harness now reads `contracts.inputs[i].dims[j].default`
  to learn the axis names an operator expects, so generic clients can wire
  tabular inputs without guessing column names.
- **F-51 — shared pool rejects new work after an environment is modified out of
  band.** Documented in the operations notes: stop the application processes of
  that installation, restart the service, and the pool accepts submissions
  again.

## Changed

- Operator library 1.0.5: dependency metadata for the ProteinMPNN family now
  records the environment interpreter requirement explicitly.

## Verification on this build

- Clean install to a fresh directory, service start in 24 s, `/api/version`
  reports `5.6.6` with build `fc9f00e3`.
- Library `main-v1.0.5`: 18 environments, 1,177 operator assignments,
  16 resources with 16 official units.
- Interface parity: `/api/v1` retry and cancel return 200, unit downloads
  start, unknown environment returns 404.
- Operator coverage probe: 491 of 1,069 operators attempted, 112 completed end
  to end; the remainder are classified in the test report.

## Known limitations

- Databases and weights larger than 20 GB are never downloaded automatically;
  link an existing copy instead.
- `hmmer`, `infernal`, `prodigal` and `amrfinder` ship only Linux and macOS
  builds, so the matching environments cannot be prepared on Windows.
- Large structure operators (molecular dynamics) exceed the default client
  timeout of 90 s; they still run on the service.
