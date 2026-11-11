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

The current source integrates **Operon Studio 4.0.7** with the independently
versioned **8.0.3 operator library**: **1,063 operators, 108 Readers (1,171
descriptors), seven provider packages and 79 route templates**. Operators and
Readers use protocol v3 / SDK 3.7 with separate parameter JSON and adjacent
Markdown documentation. Library 8.0.3 declares minimum application 3.1.9 and is
the built-in library shipped with 4.0.7.

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
| Run a Linux server without a desktop | Download **Operon-4.0.7-Server.zip**, then follow the [server guide](docs/command_line_installation.md#linux-server) |
| Develop from source | `python -m pip install . ./library` with Python 3.11+ |
| Connect an AI agent | Use the desktop **Agent** panel or `operon mcp`; see [agent operations](docs/agent_operations.md) |

Windows Setup includes a private management Python and creates an isolated
profile. Scientific packages are installed only for the workflow and execution
host you choose; they are not all bundled. If WebView2 is missing, Setup asks
Microsoft's installer for it, which needs internet access.

A new 4.0.7 installation puts the working workspace under the installation root
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

## What is new in 4.0.7

- Jobs that fail remote admission now show **failed** with the admission reason and error instead of remaining queued. A resource-infeasible job explains how to lower the request or raise the server limit.
- Readiness is tied to the graph digest. If the canvas changes after a readiness check, the run is rejected as stale and you are prompted to check again.
- Turning memory management off no longer reserves the entire host pool; it disables the per-run memory ceiling while keeping CPU exclusivity.
- Remote prepare now verifies that the saved server connection is still usable before launch, while offline bundle export and validation continue to work.
- The remote status response no longer resends full job history, so polling stays small as history grows.
- Library 8.0.2, protocol v3 and SDK 3.7 are unchanged.

## What is new in 4.0.6

- Artifact previews keep their row and column labels aligned with the displayed
  values, including when a preview is truncated.
- The canvas warns when a readiness check is older than the current graph, so a
  stale "ready" result cannot silently lead to a failed run.
- A run stops before submission if two nodes use the same output name, with the
  conflicting nodes highlighted for correction.
- Turning memory management off now shows that the run will reserve the whole
  pool and may wait or fail when the pool is shared.
- Library 8.0.2, protocol v3 and SDK 3.7 are unchanged.

## What is new in 4.0.5

- Setup hides **强制重装** after an installation completes. The option remains available while a reinstall is still being decided, or after a failed attempt leaves the old installation in place.
- Route-package import errors now tell you to import the matching operator-library version before retrying.
- This is a small installer/frontend patch. Library 8.0.3, protocol v3 and SDK 3.7 are unchanged from 4.0.4.

## What is new in 4.0.4

- Setup no longer crashes when you browse to or type a non-empty folder that is not an existing Operon installation. This is an installer-only fix; the application is unchanged from 4.0.3.
- Windows Setup keeps the working workspace under the installation root
  (`<install root>/workspace`), while profile metadata and logs stay in the user
  profile. Uninstall preserves the workspace and analysis results.
- Installing or upgrading a Linux server is one full action. Operators are not
  uploaded package by package.
- Reinstalling Windows detects the existing installation and asks first. A
  normal reinstall refuses while old tasks are active; **强制重装** stops the old
  processes and removes the old version while keeping the workspace and
  analysis results.
- **Force server upgrade** cancels every running Operon task on that server,
  closes all sessions, then replaces the server build. The desktop asks for
  confirmation first.
- Uninstall now disconnects connected MCP clients automatically; the old
  "disconnect DSH/MCP first" warning is gone.
- Dependency readiness is reported as **install on demand**, not as a
  startup-wide failure count.

Existing 4.0.x installations keep their old profile workspace when upgraded.
The old data remains under `%USERPROFILE%\.operon\profiles\<old-id>\workspace`;
copy it into the new `<install root>/workspace` if you need it in the new
installation.

Application 4.0.7 and library 8.0.3 do not change the wire protocol (v3) or SDK
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
- [What changed since 3.1.6](docs/updates-since-3.1.6.md)
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

The 8.0.3 evidence is recorded in
[the operator audit](docs/verification/operator-audit-8.0.3.md):

- L1 static contracts: **1,063 PASS, 0 FAIL, 0 SKIP**.
- L2 unit/oracle evidence: **11 oracle, 8 smoke, 1,044 referenced unit tests;
  0 SKIP**.
- L3 execution/routing: **223 local executions, 47 server executions, 789
  compiled routes; 4 documented SKIP**.
- L4 memory/determinism: **37 measured, 1,026 resource estimates; 0 SKIP**.
- Focused 8.0.3 regression: **88 passed, 0 failed** (interface contracts,
  exports, route parameters, and affected extension tests); this contract-only
  patch did not rerun the full 3,722-test suite from 8.0.2.
- The 1,063 operator and 108 Reader counts are the shipped library totals.

Historical release notes, validation reports and design records keep the versions
they tested; they are not current installation instructions. Current schemas,
source declarations and CLI help take precedence.

## License

Copyright (c) 2026 Haojian Li and Operon contributors.

Licensed under the [Apache License, Version 2.0](LICENSE). See [NOTICE](NOTICE)
for attribution and [THIRD_PARTY_NOTICES](THIRD_PARTY_NOTICES) for bundled
third-party terms.
