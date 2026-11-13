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

The current source integrates **Operon Studio 4.2.3** with the independently
versioned **8.0.9 operator library**: **1,063 operators, 108 Readers (1,171
descriptors), seven provider packages and 79 route templates**. Operators and
Readers use protocol v3 / SDK 3.7 with separate parameter JSON and adjacent
Markdown documentation. Studio 4.2.3 requires library **8.0.9 or newer** and ships
it as the built-in library.

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
| Run a Linux server without a desktop | Download **Operon-4.2.3-Server.zip**, then follow the [server guide](docs/command_line_installation.md#linux-server) |
| Develop from source | `python -m pip install . ./library` with Python 3.11+ |
| Connect an AI agent | Use the desktop **Agent** panel or `operon mcp`; see [agent operations](docs/agent_operations.md) |

Windows Setup includes a private management Python and creates an isolated
profile. Scientific packages are installed only for the workflow and execution
host you choose; they are not all bundled. If WebView2 is missing, Setup asks
Microsoft's installer for it, which needs internet access.

A new 4.2.3 installation puts the working workspace under the installation root
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

## What is new in 4.2.3

- Route archives now separate provable pin migrations from unprovable ones. `POST
  /api/routes/import-archive` rewrites a pin only when the installed library proves the
  source-to-wheel identity, reports it in `pin_migrations`, and rejects anything else with an
  explicit error instead of guessing.

- **Task folders, including scaffolds written by the backend.**
  `operon_task(base_dir="task1")` creates `input`, `results`, `reports` and
  `figures`, and `operon_write_text(path=..., content=...)` writes a file inside
  the workspace even when the host shell cannot. Paths are workspace-relative;
  `..`, absolute paths, symbolic links and internal state (`.studio`, `.operon`,
  `.admission`) are rejected. Writes are UTF-8 and limited to 10 MiB.
- **Exported files download as files.** `GET /api/v1/jobs/<job>/artifacts/<id>/file`
  now returns the exported CSV/TSV when no `role` is given; the explicit
  `?role=<name>` form is unchanged.
- **Longer job waits.** `operon_job(wait_seconds=...)` accepts up to 120 seconds
  and returns `wait_timed_out: true` instead of an error when the window closes.
- **Clearer remote errors.** A missing SSH input environment now says the server
  profile may be missing or disconnected, and points at `operon remote-status`
  and `operon remote-ensure`.
- **Operator library 8.0.9.** `interface_alanine_scan` flags Gly→Ala mutations
  with `flag: "gly_to_ala"`, `excluded_reason` and `excluded_from_ranking`, and
  reports `quality.gly_to_ala_excluded`. Both alanine-scan and MM/GBSA documents
  gained a scientific-limitations section (single-point estimates, no entropy or
  ensemble, manual Gly→Ala review, copy-reproducibility warnings).

## What is new in 4.1.9

- **Exported tables are readable over MCP.** `operon_artifacts(preview=true)` and
  `operon_artifact_table` now return CSV/TSV rows, not only file metadata, and
  honor `offset`/`limit` on every kind of job.
- **Stale canvas pins repair themselves.** Opening a canvas saved against an
  older bundled library refreshes pins whose implementation is no longer
  installed, records `runtime.pin_migrations`, and no longer fails with
  `pinned implementation is unavailable`.
- **`operon_job(wait_seconds=...)` is capped at 120 seconds.** A closed wait
  window returns `status: running` with `wait_timed_out` instead of an MCP timeout.
- **Isolated environments always bootstrap `setuptools>=68,<81`**, even when they
  share the host interpreter, so `pkg_resources` is present for PDBFixer. The
  environment repair guide and paths now use `<install root>/environments`.
- 4.1.8 remains available in [its release notes](docs/releases/v4.1.8.md); full
  replacement updates, pool control tools and the 8.0.7 library are unchanged.

## What is new in 4.1.0

- Shipped **Operon Operator Library 8.0.6** at release time. Current builds
  require 8.0.9 or newer; earlier libraries use an environment model this
  application does not load.
- The library bundle now carries `operon/environments.json`. Imported libraries
  can materialize their declared environments instead of reading only the
  application seed.
- The structure operators use the `openmm81` environment: OpenMM 8.1.1 and
  PDBFixer 1.9 are installed together in an isolated Python 3.11 environment,
  without downgrading the shared NumPy 2 runtime. The previous dependency range
  could resolve PDBFixer 1.12 against an unavailable OpenMM 8.2 wheel.
- All 4.0.10 installer, remote-pin and shared-pool fixes are included.

## What is new in 4.0.10

- Windows Setup uses the exact folder selected, never appends `-2`, asks for
  **强制重装** when an older installation is found, and records the root for the
  uninstaller. Uninstall cleans that root except `workspace`.
- Remote submissions discard plugin pins from an older canvas before preparing the
  graph, then resolve implementations against the selected server. This corrects
  the 4.0.9 attempt, which removed the re-overwrite but left the stale pin in place.
- A forced server upgrade closes every remote workspace client before the new
  application registers, and re-registration prunes sessions left by a process
  that has already exited. A normal upgrade still stops without touching active
  tasks or live clients.
- operon_remote_status returns a compact build/library summary instead of the
  full multi-megabyte remote catalog.

## What is new in 4.0.8

- Windows Setup now accepts a non-empty folder that is not an Operon installation; it preserves unrelated files and removes only Operon-managed versions on uninstall.
- Uninstall disconnects every connected MCP client across local profiles before stopping processes, even when the frontend already exited.
- Setup offers **强制重装** after a failed attempt and keeps the checkbox hidden after success.
- FE-03: local files can be uploaded from the Inspector, staged to the selected remote workspace, and the UI explains the local data directory vs. remote path.
- Library 8.0.3, protocol v3 and SDK 3.7 are unchanged.

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

Application 4.1.9 and library 8.0.7 do not change the wire protocol (v3) or SDK
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

The 8.0.4 evidence is recorded in
[the operator audit](docs/verification/operator-audit-8.0.4.md):

- L1 static contracts: **1,063 PASS, 0 FAIL, 0 SKIP**.
- L2 unit/oracle evidence: **11 oracle, 8 smoke, 1,044 referenced unit tests;
  0 SKIP**.
- L3 execution/routing: **223 local executions, 47 server executions, 789
  compiled routes; 4 documented SKIP**.
- L4 memory/determinism: **37 measured, 1,026 resource estimates; 0 SKIP**.
- Focused 8.0.4 regression: **37 passed, 0 failed** (composition matrix,
  interface contracts, release, and route parameters); this metadata-and-test
  patch did not rerun the full 3,722-test suite from 8.0.3.
- The 1,063 operator and 108 Reader counts are the shipped library totals.

Historical release notes, validation reports and design records keep the versions
they tested; they are not current installation instructions. Current schemas,
source declarations and CLI help take precedence.

## License

Copyright (c) 2026 Haojian Li and Operon contributors.

Licensed under the [Apache License, Version 2.0](LICENSE). See [NOTICE](NOTICE)
for attribution and [THIRD_PARTY_NOTICES](THIRD_PARTY_NOTICES) for bundled
third-party terms.
