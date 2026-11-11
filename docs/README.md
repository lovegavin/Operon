# Documentation

Operon prepares reproducible analysis results from raw data and hands artifacts
to specialist tools for interactive interpretation and figure refinement. It
supports visual editing, human-agent collaboration and unattended execution.
Operon does not supply an AI model or require a desktop for computation.


## Core value

Operon is a contract-first analysis platform: a large,
maintainable, validated operator and Reader library lets an agent call a verified
analysis instead of writing analysis code. That avoids implementation logic errors
and the token cost of regenerating the same method. The library is the product;
visual workflows, the application API, CLI and MCP are ways to discover, compose and
trace it. See [Why Operon](../README.md#why-operon) for the five supports.

## Use Operon

- **[中文快速开始：10 分钟跑通第一个流程](../QUICKSTART.zh.md)**
- **[English quick start: your first workflow in 10 minutes](../QUICKSTART.en.md)**
- [Detailed quick start: Windows, Linux and your first workflow](quickstart.md)

Current guides describe **Operon Studio 4.0.2** with the **8.0.2** operator library.
Release notes, verification reports and dated design records preserve the versions
they tested; they are historical evidence, not current installation instructions.

- [Shared execution pools](design/pool_service.md)
- [Verified stage reuse and author cache declarations](stage_cache.md)

- [SDK 3.7 mandatory port formats and native Reader bridge](data_formats.md)
- [Static format inspection and explicit legacy migration](format_migration_v37.md)

- [Windows and Linux command-line installation](command_line_installation.md)
- [Linux server and terminal quickstart](server_cli.md)
- [3.0 implementation scope and validation](V3_IMPLEMENTATION.md)
- [Operon 3.0 Setup acceptance](OPERON_3_TEST_ACCEPTANCE.md)
- [Public workflow YAML and templates](workflow_yaml_v3.md)
- [Script operators, parameter extraction and promotion](script_operators_v3.md)
- [Selected-target readiness and explicit preparation](readiness.md)
- [Standalone packages and export boundaries](portable_packages_v3.md)
- [End-to-end quick start](quickstart_full_flow.md)
- [Installation and dependencies](installation.md)
- [Windows Setup and isolated installations](windows_setup.md)
- [Desktop application](desktop.md)
- [Languages, application settings and operator library management](localization.md)
- [Input formats and explicit Readers](input_formats.md)
- [Saved workflow parameters](workflow_parameters.md)
- [Memory, streaming and spill](resource_runtime.md)
- [Repairing the environment and provisioning resources](agent_environment_repair.md)
- [Execution environments and concurrent jobs](EXECUTION_ENVIRONMENTS.md)
- [SSH execution](REMOTE_EXECUTION.md), [server handshake](SERVER_HANDSHAKE.md) and
  [remote recovery incident note](design/remote_recovery_incident.md)
- [Server installation troubleshooting](SERVER_INSTALL_REPAIR.md) and [main/library separation audit](MAIN_LIBRARY_SEPARATION_AUDIT.md)
- [Hi-C workflows](HIC.md) and [16S microbiome](microbiome.md)
- [Publication figures](PUBLICATION_FIGURES.md) and [static plotting adapters](static_plotting.md)
- [Domain exports and desktop-first specialist viewers](result_viewers.md)

## Automate and integrate

- [Bidirectional activity, transaction diffs and conditional undo](canvas_collaboration.md)
- [Three-layer agent operating guide](agent_operations.md)
- [Third-party API tutorial and runnable client](api_quickstart.md)
- [Application API, headless CLI and MCP](headless_api.md)
- [Canvas collaboration and permissions](agent_api.md)
- [Operator documentation and on-demand retrieval](operator_documentation.md)
- [Operator discovery index](../library/seed/operator_index.json)
- [Reader discovery index](../library/seed/reader_index.json)
- [Application and operator-library boundary](application_library_boundary.md)

## Design notes

- [Next server engine: concurrent clients, resource scheduling and backpressure (proposal)](design/server_engine_next.md)
- [Backend engine implementation plan for coding agents](design/server_engine_implementation_plan.md)
- [Backend engine implementation status and handoff](design/server_engine_progress.md)
- [Dedicated multi-workspace pool service](design/pool_service.md)
- [Engine acceptance record and remaining platform gates](design/server_engine_acceptance.md)
- [Real Linux/SSH pool acceptance runner](design/pool_linux_acceptance.md)
- [Control-plane baseline and post-change measurements](design/server_engine_baseline.md)
- [Engine lock and ownership order](design/engine_locking.md)
- [Extension policy and on-demand extension](design/extension_policy.md)
- [Hard-capability status](design/hard_capability_status.md)
- [Minibinder and VHH design route](design/minibinder_vhh_design_route.md)
- [Competitive landscape and moat analysis](design/competitive_landscape.md)
- [Agent working notes](design/agent_working_notes.md)

## Extend and maintain

- [SDK 3.7 logical types, representations and conversion plans](data_formats.md)
- [SDK quickstart](sdk_quickstart.md) and [SDK reference](sdk_reference.md)
- [Operator protocol](operator_protocol.md) and [package protocol](package_protocol.md)
- [Operator library extension forms](library_extensions.md)
- [Reader extensions](reader_extensions.md) and [step extensions](step_extensions.md)
- [Library installation and maintenance](plugins.md)
- [Independent software and operator-library releases](library_releases.md)
- [Importing operator libraries and routes](library_import_compatibility.md)
- [Operator library release standard](library_release_standard.md)
- [Five-layer library test standard](verification/five-layer-test-standard.md)
- [Per-operator trust sheets](operators/README.md)
- [Library 3.x full verification](verification/library-3.0.0-full.md)
- [Operon 4.0.0 release](releases/v4.0.0.md)
- [Biological evidence for 4.0.0](verification/biological-evidence-4.0.0.md)
- [Known biological discrepancies](verification/biological-issues-4.0.0.md)
- [Static registry maintenance](registry_maintenance.md)
- [Backend versioning](backend_versioning.md)
- [Selective frontend integration](FRONTEND_MERGE.md)
- [Unified main and archive](UNIFIED_MAIN.md)
- [Contributing](../CONTRIBUTING.md)

Pages under `releases/`, previous validation reports and `UPSTREAM_REVIEW_*` describe
their named historical versions. Current schemas, source declarations and CLI
help take precedence over historical counts and examples.

- [Application and library ownership, packaging and updates](application_library_boundary.md)
