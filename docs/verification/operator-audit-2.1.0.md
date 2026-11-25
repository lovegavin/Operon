# Operator audit for library 2.1.0

- Library version: 2.1.0
- Application build target: 5.10.0
- Audit date: 2026-11-25
- Registry: 1074 operators, 110 readers, 79 routes, 0 errors

## What changed since 2.0.0

1. Declared resource roots are exported into environment-bridged steps
   (`_resources_common.apply_environment`, called from `operon/env_worker.py`),
   so `OPERON_ALPHAFOLD_DATA` and the other declared `env` values resolve
   without parameters.
2. New `alphafold2_code` resource (`OPERON_ALPHAFOLD2_HOME`,
   `run_alphafold.py`) lets a machine link its AlphaFold-2 checkout instead of
   passing `runner` on every job.
3. `rfdiffusion_design` and `vina_dock` no longer discard their ported
   structure/receptor inputs (`del inputs` removed); structure-conditioned runs
   now reach `_port_inputs`.
4. `export_results` attributes native results for multi-output producers by
   role instead of refusing to attribute at all.

## L0 static contract

`scripts/operator_audit/l0_static.py` with `PYTHONPATH` pointing at this
checkout (it needs `operon_sdk` for declaration and documentation hashing):

- total 1184, operators 1074, readers 110, failures 0
- `operator:PASS` 1074, `reader:PASS` 110

Evidence: `l0_static.jsonl`, `l0_summary.json`, `l0_stdout.txt`.

## Registry

`registry check --scope packages --scope routes` is clean; the only warnings are
the known "No direct parameter read" notes for TxtReader and ValuesReader.

Evidence: `registry_check.txt`.

## Targeted contract tests

47 passed with 8 classified failures (environment gating and pre-existing
assertions); see `contract_tests.txt` and `acceptance-gap.md`.

## Residual risk

L1/L2/L3 execution layers were not replayed for 2.1.0 in this container; they
are exercised by the 5.10.0 server acceptance run (environment install, node
capacity, AF2 without explicit pointers, and route replays).

## Additional fixes in this line

- Environment-bridged steps now receive , and  falls back to sibling environments, so large-model operators can find their interpreter on managed servers.
-  resolves resource helpers from namespaced provider packages (), so remote resource listing and linking work after a library install.

Both changes were covered by targeted tests (, , ) and do not change any operator contract.

## Additional fixes in this line

- Environment-bridged steps now receive `OPERON_ENVIRONMENTS_ROOT`, and `_envpython.environment_python()` falls back to sibling environments, so large-model operators locate their interpreter on managed servers.
- `src/web/resource_api.py` resolves resource helpers from namespaced provider packages (`operon_library_<provider>.steps`), so remote resource listing and linking work after a library install.

Both changes are covered by targeted tests (`tests/test_envpython.py`, `tests/test_environments.py`, `tests/test_resource_api.py`) and do not change any operator contract.
