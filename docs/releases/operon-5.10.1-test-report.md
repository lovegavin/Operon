# Operon 5.10.1 test report

## Focused tests

- `pytest tests/test_environment_install.py -q` -> `43 passed`
  (three new tests: patch append is idempotent and scoped, write mode replaces
  the file, and path/mode validation rejects escapes or unknown modes).

## Manual acceptance

1. Rebuild the library bundle and wheel for 2.1.1, rebuild the app chain.
2. Install 5.10.1 locally, force-upgrade `licai-srv` from the UI.
3. Restore the hand-edited `simtk/openmm/app/__init__.py` from its `.bak`
   backup, run the environment repair path from the UI (or the repair API),
   then confirm `import simtk.openmm.app.internal.pdbstructure` succeeds.
4. Submit `alphafold2_predict` with no `data_dir`/`runner`; it should pass the
   imports and reach the MSA stage, then be cancelled after the output directory
   with `query/msas/` appears.
