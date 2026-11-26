# Operon for power users

You already know the analysis. You need the workflow to be explicit, repeatable
and movable. This page is about the decisions Operon makes at that level.

## Compose, don't script

A workflow is a graph of operators with parameters attached to nodes, not values
baked into code. You can build it on the canvas or author it as YAML:

- [workflow_yaml_v3.md](../workflow_yaml_v3.md) — `format: operon.workflow`,
  `schema_version: 1`, ports `in0/out`, sidecars `parameters.json` and
  `execution.json`, and `operon workflow init/lint/format/prepare/validate`.
- [workflow_parameters.md](../workflow_parameters.md) — how values are declared,
  defaulted and frozen.
- [route_operators.md](../route_operators.md) — route templates and collections.
- [script_operators_v3.md](../script_operators_v3.md) — when a step genuinely
  needs literal code, and the contract it must satisfy.

A canvas run, a CLI run and a plan export all compile to the same frozen RunPlan.
That is the reason a figure can be reproduced from a receipt months later.

## Freeze and re-run

Before execution Operon resolves readiness: contracts, files, environments,
resources. The output of that step is what gets snapshotted into the job's
parameter and environment receipts.

- [readiness.md](../readiness.md) — what is checked, and what blocks a run.
- [dependency_isolation.md](../dependency_isolation.md) — one environment per
  operator family, prepared explicitly, with a receipt.
- [stage_cache.md](../stage_cache.md) — when a step is reused rather than re-run.
- [resource_runtime.md](../resource_runtime.md) — memory admission, spill and
  worker limits.
- [large_resources.md](../large_resources.md) — weights and reference data.

## Choose the host

Execution is a property of the workflow, not of your terminal. Local, SSH server
or a Slurm node inside that server:

- [REMOTE_EXECUTION.md](../REMOTE_EXECUTION.md) — profiles, capability checks,
  what runs where.
- [SERVER_HANDSHAKE.md](../SERVER_HANDSHAKE.md) — version and protocol agreement.
- [SERVER_INSTALL_REPAIR.md](../SERVER_INSTALL_REPAIR.md) — a server that no longer
  matches its client.
- [design/node_discovery.md](../design/node_discovery.md) — how a node is scored
  and chosen (free memory, free CPU, GPU, readiness).
- [server_cli.md](../server_cli.md) — `operon serve`, `operon service`.

## Automate

Every surface talks to the same service; pick the one your pipeline already
speaks.

- [headless_api.md](../headless_api.md) — the service model and permissions.
- [api_quickstart.md](../api_quickstart.md) — first request, first job.
- [design/backend_cli_quickstart.md](../design/backend_cli_quickstart.md) — the
  `operon plan compile|submit|details|artifacts|logs` pipeline with `binding.json`.
- [agent_operations.md](../agent_operations.md) — the MCP equivalents.

## Move it

- [automatic_portable_export.md](../automatic_portable_export.md) — a package that
  runs without Operon: controller, environments, inputs, `run.sh`/`run.cmd`.
- [portable_packages_v3.md](../portable_packages_v3.md) — the legacy export path.
- [EXECUTION_ENVIRONMENTS.md](../EXECUTION_ENVIRONMENTS.md) — what an environment
  is expected to carry.
- [format_migration_v37.md](../format_migration_v37.md) — upgrading stored data
  and workflow formats.

## Contracts

Operators are typed, so the graph can be checked before it runs:
[operator_protocol.md](../operator_protocol.md), [data_formats.md](../data_formats.md),
[data_contracts.md](../data_contracts.md), [input_formats.md](../input_formats.md).
When a connection is refused, the error names the contract, the axis or the
format that did not match.
