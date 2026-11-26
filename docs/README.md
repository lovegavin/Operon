# Operon documentation

Start with the page for the reader you are. Each role page is written for one
level of depth and links only what that reader needs; the reference list below
is the complete set of hand-written pages, grouped by task.

The installed build is the authority: `operon help`, `operon_guide` and
`operon capabilities` describe what you actually have. These pages describe
`main`.

## Choose your role

| You are | Start here | Depth |
| --- | --- | --- |
| An AI agent connected over MCP | [roles/agent.md](roles/agent.md) | Rules, first calls, a paste-ready prompt |
| An end user running analyses | [roles/user.md](roles/user.md) | Install, first analysis, results |
| A power user composing workflows | [roles/power-user.md](roles/power-user.md) | Authoring, freezing, hosts, export |
| A contributor to operators or the engine | [roles/contributor.md](roles/contributor.md) | Contracts, seed layout, validation |
| A maintainer cutting releases | [roles/maintainer.md](roles/maintainer.md) | Versioning, checklists, known debts |

## Reference

Install and run — [quickstart.md](quickstart.md),
[installation.md](installation.md), [windows_setup.md](windows_setup.md),
[desktop.md](desktop.md), [command_line_installation.md](command_line_installation.md),
[server_cli.md](server_cli.md).

Execution environments — [EXECUTION_ENVIRONMENTS.md](EXECUTION_ENVIRONMENTS.md),
[readiness.md](readiness.md), [dependency_isolation.md](dependency_isolation.md),
[stage_cache.md](stage_cache.md), [resource_runtime.md](resource_runtime.md),
[large_resources.md](large_resources.md), [workflow_parameters.md](workflow_parameters.md).

Remote and servers — [REMOTE_EXECUTION.md](REMOTE_EXECUTION.md),
[SERVER_HANDSHAKE.md](SERVER_HANDSHAKE.md),
[SERVER_INSTALL_REPAIR.md](SERVER_INSTALL_REPAIR.md).

Data, results and export — [input_formats.md](input_formats.md),
[data_formats.md](data_formats.md), [data_contracts.md](data_contracts.md),
[result_viewers.md](result_viewers.md), [PUBLICATION_FIGURES.md](PUBLICATION_FIGURES.md),
[static_plotting.md](static_plotting.md),
[automatic_portable_export.md](automatic_portable_export.md),
[portable_packages_v3.md](portable_packages_v3.md).

Authoring workflows — [workflow_yaml_v3.md](workflow_yaml_v3.md),
[route_operators.md](route_operators.md), [workflow_parameters.md](workflow_parameters.md),
[script_operators_v3.md](script_operators_v3.md).

Authoring operators and Readers — [operator_protocol.md](operator_protocol.md),
[sdk_quickstart.md](sdk_quickstart.md), [sdk_reference.md](sdk_reference.md),
[operator_documentation.md](operator_documentation.md),
[reader_extensions.md](reader_extensions.md), [step_extensions.md](step_extensions.md),
[library_extensions.md](library_extensions.md), [package_protocol.md](package_protocol.md),
[plugins.md](plugins.md).

Automation and agents — [headless_api.md](headless_api.md),
[api_quickstart.md](api_quickstart.md), [agent_operations.md](agent_operations.md),
[agent_api.md](agent_api.md), [agent_environment_repair.md](agent_environment_repair.md),
[canvas_collaboration.md](canvas_collaboration.md).

Library and releases — [application_library_boundary.md](application_library_boundary.md),
[registry_maintenance.md](registry_maintenance.md),
[library_releases.md](library_releases.md),
[library_release_standard.md](library_release_standard.md),
[library_import_compatibility.md](library_import_compatibility.md),
[backend_versioning.md](backend_versioning.md), [localization.md](localization.md).

Migration — [migration_v2.md](migration_v2.md),
[format_migration_v37.md](format_migration_v37.md).

Domain notes — [HIC.md](HIC.md), [microbiome.md](microbiome.md).

Candidate acceptance — [OPERON_3_TEST_ACCEPTANCE.md](OPERON_3_TEST_ACCEPTANCE.md),
[OPERON_3_TEST_INSTRUCTIONS_ZH.md](OPERON_3_TEST_INSTRUCTIONS_ZH.md) (packaging
inputs, not history).

## Directories

| Directory | What it is |
| --- | --- |
| [roles/](roles/) | The five reader-specific entry pages |
| [design/](design/README.md) | Architecture notes and design ledgers |
| [releases/](releases/README.md) | Release notes for the current line |
| [verification/](verification/README.md) | Surviving evidence and its standard |
| [operators/](operators/README.md) | Generated per-operator documentation |

## Conventions

- Links are relative and never point into `library/seed/`.
- A page describes `main`; the installed build wins when they disagree.
- Counts are point-in-time. Re-run `operon registry check` for today's numbers.
- Historical notes are frozen. Older release notes live in the git history, not
  in this tree.
