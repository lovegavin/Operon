# Operon Studio 5.10.0 test report

## Scope

Node discovery and capacity-aware automatic placement; resource environment
injection; `alphafold2_code` resource; library 2.1.0.

## Automated checks

| Check | Command | Result |
| --- | --- | --- |
| Node inventory and scoring | `pytest tests/test_nodes.py -q` | passed |
| Placement and parity | `pytest tests/test_execution_plan.py tests/test_nodes.py tests/test_mcp_parity.py -q` | 71 passed |
| Resource environment injection | `pytest tests/test_resource_environment.py tests/test_resource_api.py tests/test_resource_link.py -q` | 75 passed, 1 skipped, 1 known pre-existing failure |
| AlphaFold-2 operators | `pytest tests/test_resource_environment.py tests/test_alphafold2_operators.py -q` | 15 passed, 1 known pre-existing failure |
| Registry | `python -m operon registry check --scope packages` / `--scope routes` | clean (warnings only) |
| Frontend typecheck/build | `npm run build` (Windows mirror) | tsc clean, vite built in 4.12 s |
| Frontend unit tests | `vitest run` (Windows mirror) | 44 files / 287 tests passed |

The two failures noted above (`test_environment_metadata_lists_the_alphafold2_family`,
`test_expected_files_follow_the_released_unit_layout`) reproduce on the parent
commit with `git stash`, so they are pre-existing environment-gated failures.

## Manual acceptance

- `GET /api/nodes` on the desktop lists the local host and `licai-srv` with
  measured capacity; MCP `operon_nodes` returns the same document.
- In automatic mode the plan assigns a node to the host with the higher score;
  switching to manual keeps the explicitly selected host.
- The execution settings capacity panel loads only after pressing
  `查看节点容量`.
- On `licai-srv`, linking `alphafold2_code` to a real checkout and running
  `alphafold2_predict` without `data_dir`/`runner` starts the AlphaFold-2 run
  (the pointers come from the linked resources).
