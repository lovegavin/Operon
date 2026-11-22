# Operon Studio 5.7.27 — acceptance report

Scope: the two changes in `operon-5.7.27.md`, verified on the development host and on
the `licai-srv` deployment that runs 5.7.26 before this build.

## Defects

| # | Symptom | Cause | Fix |
|---|---------|-------|-----|
| 1 | A ready environment showed `依赖缺失 1` in the runtime panel (`core`: 67 dependencies, 66 installed) | `RuntimeStatusPanel.readinessOf` compares `dependency_installed < dependency_total`, and both producers counted `best_effort` rows into those two fields | Required and optional rows are counted separately (`_split_dependency_counts`, `environment_api.augment`); `dependency-gap` needs a missing required row |
| 2 | Parallelism could only be changed per graph, and every graph defaulted to 2 on a 56-core host | `settings()` defaulted `max_parallel_tasks` to 2 with no user-level value | `preferences.parallel_tasks` (1–64) feeds `default_parallel_tasks()`, which `settings()` uses as the fallback |

## Evidence

- Before the change, `GET /api/remote/<rid>/environments` returned
  `status: "ready"`, `dependency_total: 67`, `dependency_installed: 66`,
  `missing_dependencies: []`, and one row `{"kind": "best_effort", "name": "vina==1.2.5",
  "optional": true, "installed": false}`. After the change the required counts are 66/66,
  `optional_missing` still lists `vina==1.2.5`, and the panel shows the environment ready.
- `pytest tests/test_environment_optional_counts.py tests/test_environment_dependencies.py
  tests/test_environment_readiness.py -q` → 14 passed.
- `pytest tests/test_execution_plan.py -q` → 58 passed. The fake engine in
  `test_broken_unrelated_host_does_not_block_explicit_target` now carries a no-op
  `_ensure_target`, which the planning path calls before it lists hosts.
- `python -m pytest tests/test_preferences.py tests/test_environment_optional_counts.py -q`
  covers the preference round trip and the counting split.

## Known limitations

- `vina==1.2.5` stays optional: PyPI has no cp311 wheel and the source build fails on the
  deployment host. conda-forge ships `vina 1.2.5 py311hfdbb021_5`; the managed environment
  does not install it today, and the panel now reports it as an optional gap instead of a
  missing dependency.
- `prodigal` remains a build-your-own resource, and the offline-only resources
  (`alphafold2` BFD/params mirrors, `openfold` finetuning weights) are unchanged.
