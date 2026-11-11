# Operon

**Open-source, contract-first bioinformatics workflows — visual, scriptable and agent-ready.**

[中文快速开始](QUICKSTART.zh.md) · [English quick start](QUICKSTART.en.md) ·
[Documentation](docs/README.md) · [Releases](https://github.com/lovegavin/Operon/releases) ·
[Apache-2.0](LICENSE)

Operon turns raw omics data into reproducible results. Build a workflow on the
canvas or in YAML, run it locally or on an SSH server, and inspect every saved
parameter, log and artifact. The same engine is available through the desktop,
CLI, HTTP API and MCP, so an agent can call validated tools instead of writing
analysis code from scratch.

The current source integrates **Operon Studio 4.0.2** with the independently
versioned **8.0.2 operator library**: **1,063 operators, 108 Readers (1,171
descriptors), seven provider packages and 79 route templates**. Operators and
Readers use protocol v3 / SDK 3.7 with separate parameter JSON and adjacent
Markdown documentation. Library 8.0.2 declares minimum application 3.1.9 and is
the built-in library shipped with 4.0.2.

Operon does not bundle or require an AI model. Agent access is optional.

## Why Operon

- **Call a validated method, not generated code.** Every operator has a typed
  input/output contract, a parameter schema and scientific documentation.
- **Reproducible by construction.** Workflow values are frozen independently of
  later defaults; task records, logs and output artifacts stay inspectable.
- **One engine, several surfaces.** Canvas, CLI, HTTP API and MCP share workflow
  preparation, validation, execution and artifacts.
- **Local or remote, same workflow.** Run on Windows, a Linux workstation or an
  SSH server; move computation to the data when that is cheaper.
- **Open and extensible.** Add an operator, Reader, provider package or route
  without changing the engine. The full source and third-party notices ship with
  the project.

## Install

| I want to… | Start here |
| --- | --- |
| Use the Windows desktop | Download **Operon_Setup.exe** from [Releases](https://github.com/lovegavin/Operon/releases/latest) |
| Run a Linux server without a desktop | Download **Operon-4.0.2-Server.zip**, then follow the [server guide](docs/command_line_installation.md#linux-server) |
| Develop from source | `python -m pip install . ./library` with Python 3.11+ |
| Connect an AI agent | Use the desktop **Agent** panel or `operon mcp`; see [agent operations](docs/agent_operations.md) |

Windows Setup includes a private management Python and creates an isolated
profile. Scientific packages are installed only for the workflow and execution
host you choose; they are not all bundled. If WebView2 is missing, Setup asks
Microsoft's installer for it, which needs internet access.

A new 4.0.2 installation puts the working workspace under the installation root
(for example, `workspace` under the installation root). Profile metadata, logs and browser
state remain under `%USERPROFILE%\.operon`. Earlier installations keep their
existing workspace. Uninstall removes the program but preserves the workspace
and analysis results.

## First run

The two quick starts are deliberately short and use only synthetic data:

- [中文：10 分钟跑通第一个流程](QUICKSTART.zh.md)
- [English: run your first workflow in 10 minutes](QUICKSTART.en.md)

In short: install, open **Operon Studio**, add a CSV, connect it to **PCA**, check
the local environment, and press **Run**. Results appear under **Run history →
View results**. The first dependency check may need internet access; Operon never
installs scientific packages silently during a run.

## What is new in 4.0.2

- Setup-created installations use `<install root>/workspace` for workflows, jobs
  and `.studio` data, reducing growth on the system drive.
- Profile metadata and logs stay in the user profile and are not mixed into the
  analysis workspace.
- Upgrades preserve the existing workspace; uninstall keeps it for later use.
- Server maintenance uses one full **Install / upgrade server** action. It
  replaces the server library and build identity as a unit instead of asking you
  to synchronize operators package by package.
- Dependency readiness is reported as **install on demand** rather than as a
  startup-wide failure count.

Application 4.0.2 and library 8.0.2 do not change the wire protocol (v3) or SDK
(3.7). Published tags and release assets are immutable.

## Open source

Operon is licensed under the **Apache License, Version 2.0**. You may use, copy,
modify and redistribute it, including commercially, under that license; no
separate commercial permission is required. Retain [LICENSE](LICENSE) and
[NOTICE](NOTICE), and identify modifications when redistributing.

Third-party libraries, external tools, model weights and datasets keep their own
licenses. Their notices are collected in [THIRD_PARTY_NOTICES](THIRD_PARTY_NOTICES)
and in the installed package. The Apache-2.0 grant does not replace those terms.
Contributions are welcome under the same license; see [CONTRIBUTING.md](CONTRIBUTING.md).

## Repository layout

| Path | Contents |
| --- | --- |
| `operon/`, `operon_sdk/` | Application package, CLI, MCP and SDK schemas |
| `src/core/`, `src/task/`, `src/web/` | Engine, task runtime and HTTP service |
| `library/seed/` | Reference operators, Readers, parameter JSON, routes and indexes |
| `frontend/` | React canvas and desktop UI |
| `desktop/`, `installer/` | Windows host and Setup/uninstaller |
| `docs/` | Guides, design notes, release notes and verification evidence |
| `tests/` | Python, frontend and integration tests |

`main` is the integrated source branch for the current application and library.
The application and the operator library remain **independently versioned
products**: application releases use `vX.Y.Z`, library releases use
`library-v<version>`, and an operator-only change does not require a new installer.
See [application/library boundary](docs/application_library_boundary.md) and
[independent library releases](docs/library_releases.md).

## Documentation

- [Documentation index](docs/README.md)
- [Windows Setup and isolated installations](docs/windows_setup.md)
- [Command-line and Linux server installation](docs/command_line_installation.md)
- [Linux server and terminal guide](docs/server_cli.md)
- [SSH remote execution](docs/REMOTE_EXECUTION.md) and [server handshake](docs/SERVER_HANDSHAKE.md)
- [Public workflow YAML](docs/workflow_yaml_v3.md)
- [SDK 3.7 data formats](docs/data_formats.md) and [format migration](docs/format_migration_v37.md)
- [Operator documentation and retrieval](docs/operator_documentation.md)
- [HTTP API, CLI and MCP](docs/headless_api.md)
- [Application API tutorial](docs/api_quickstart.md)
- [Library extensions](docs/library_extensions.md)
- [Release notes](docs/releases/)
- [Contributing](CONTRIBUTING.md)

## Verification and status

The 8.0.2 evidence is recorded in
[the operator audit](docs/verification/operator-audit-8.0.2.md):

- L1 static contracts: **1,063 PASS, 0 FAIL, 0 SKIP**.
- L2 unit/oracle evidence: **11 oracle, 8 smoke, 1,044 referenced unit tests;
  0 SKIP**.
- L3 execution/routing: **223 local executions, 47 server executions, 789
  compiled routes; 4 documented SKIP**.
- L4 memory/determinism: **37 measured, 1,026 resource estimates; 0 SKIP**.
- Full test suite: **3,722 passed, 209 skipped, 0 failed**; the skipped cases
  and their reasons are listed in the 8.0.2 audit.
- The 1,063 operator and 108 Reader counts are the shipped library totals.

Historical release notes, validation reports and design records keep the versions
they tested; they are not current installation instructions. Current schemas,
source declarations and CLI help take precedence.

## License

Copyright (c) 2026 Haojian Li and Operon contributors.

Licensed under the [Apache License, Version 2.0](LICENSE). See [NOTICE](NOTICE)
for attribution and [THIRD_PARTY_NOTICES](THIRD_PARTY_NOTICES) for bundled
third-party terms.
