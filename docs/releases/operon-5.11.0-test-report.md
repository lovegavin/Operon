# Operon 5.11.0 test report

## Automated

- `PYTHONPATH=. python3 -m pytest tests/test_nodes.py tests/test_execution_plan.py -q`
  -> 74 passed.
- `python3 -m pytest tests/test_nodes.py` covers capacity from idle CPUs/free
  memory, readiness bands, ready-small above unready-big, all-unready order and
  the `%C|%m|%e|%G` parser.
- `python3 -m pytest tests/test_execution_plan.py` covers keeping/rejecting
  `runtime.execution.node`.
- Frontend (Windows mirror): `npx tsc -b && npx vitest run` -> 289 passed across
  44 files, including the new compute-node picker tests.

## Manual acceptance

- The node inventory on `licai-srv` reports `master`, `node78`, `node79` and
  `node80` with idle CPUs, free memory and scores; `node79` is idle and ranks
  first when every node is ready.
- Selecting `node79` in the execution settings and running a small CSV -> PCA
  graph is verified by observing the job under `squeue -u lihj` on the compute
  node and by the job's `execution_node` field.

## Notes

- Library 2.1.1 is unchanged.
- Jobs without a selected node follow the previous login-host path.
