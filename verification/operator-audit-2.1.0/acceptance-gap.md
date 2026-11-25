# Acceptance gap for library 2.1.0

This cycle re-ran the layers that can gate a library-only release on this
machine; deeper layers need a live server and are scheduled with the 5.10.0
acceptance run.

| Layer | Status | Evidence |
| --- | --- | --- |
| L0 static contract (all operators and readers) | PASS, 1184/1184 | `l0_static.jsonl`, `l0_summary.json` |
| Registry build and check | PASS, 1074 operators / 110 readers / 79 routes, 0 errors | `registry_check.txt` |
| Targeted contract tests for changed steps | 47 passed, 8 classified failures | `contract_tests.txt` |
| L1 single-operator execution | not repeated for 2.1.0 | covered by the 5.10.0 server acceptance run |
| L2 multi-operator routes | not repeated for 2.1.0 | route replays from the 2.0.0 audit remain the last full L2 evidence |
| L3 literature-style route analysis | not repeated for 2.1.0 | unchanged since the 2.0.0 audit |

Classified failures in `contract_tests.txt`:

- `tests/test_export_results.py::test_managed_branch_continues_and_existing_viewer_opens_files`
  requires the `core` isolated environment, which is not installed in this
  test container (`export_results: isolated environment 'core' is not installed`).
- `tests/test_alphafold2_operators.py::test_environment_metadata_lists_the_alphafold2_family`
  fails identically at HEAD (pre-existing metadata assertion).
- six `tests/test_library_release.py::test_optional_dependencies_are_not_imported_during_registration[...]`
  cases spawn a bare `python -c` without the repository on `PYTHONPATH`
  (`ModuleNotFoundError: No module named 'src'`), i.e. an environment gap of the
  test harness, not a library regression.

The changed steps in 2.1.0 are `rfdiffusion_design`, `vina_dock`,
`export_results`, `_resources_common` and `operon/env_worker.py`; each has a
dedicated regression test in `tests/test_ported_structure_inputs.py`,
`tests/test_export_results.py` and `tests/test_resource_environment.py`.
