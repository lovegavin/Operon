# Operon

**Contract-first bioinformatics workflows — visual, scriptable and agent-operable.**

Operon Studio 5.11.2 · Operator Library 2.1.3 · Apache-2.0

[中文快速开始](QUICKSTART.zh.md) · [Quick start (EN)](QUICKSTART.en.md) · [Documentation](docs/README.md) · [Releases](https://github.com/lovegavin/Operon/releases) · [License](LICENSE)

---

## Why Operon exists

Most bioinformatics analyses are assembled from shell scripts, notebooks and one-off
Python. That works until someone has to re-run the pipeline a year later, hand it to a
collaborator, or explain to a reviewer exactly which tool version produced a figure.

Operon treats an analysis as **data, not code**. A workflow is a graph of typed steps
with explicit inputs, outputs, parameters and runtime requirements. Each step comes
from a validated operator whose contract is declared once and checked when the library
is built.

That gives three properties that ad-hoc scripts do not have:

- **Nothing generated to trust.** You compose declared operators; you do not review
  model-written code before it touches your data.
- **Reproducible by construction.** Parameter values, library generation, environment
  receipts and artifact hashes are snapshotted with every run.
- **One engine, several surfaces.** The desktop canvas, the CLI, the HTTP API and the
  MCP server all drive the same workflow store, scheduler, memory admission and
  execution environment — not four reimplementations.

The operator library is the product. The interface is how you reach it.

## What you get

| Area | What it does |
| --- | --- |
| **Visual canvas** | Compose workflows by connecting operator cards; edit parameters, inspect schemas, save revisions and undo as one transaction. |
| **Operator library** | 1,000+ validated operators and 100+ Readers covering statistics, machine learning, sequences and omics, structures, genomes and epigenomes, quality control, phylogenetics, proteomics, metabolomics, single cell, Hi-C, microbiome, docking, causal inference and visualization. |
| **Workflow routes** | 79 ready-made route templates (alignment QC, ATAC/ChIP pipelines, assembly QC, codon design and usage, annotation, ML baselines, and more) that you can open, adapt and save. |
| **Execution** | Local environment, explicit dependency preparation, memory admission, disk/stream resource protocols, resumable transfers, SSH servers and Slurm clusters with capacity-aware node placement. |
| **Results** | Run history, retained output tables, native result viewers, publication figures and static plots. |
| **Portable export** | Freeze a run plan into a standalone package that runs on a machine without Operon installed. |
| **Automation** | Versioned HTTP API, scriptable CLI and MCP tools with progressive documentation, workspace files and job reporting. |

## Four surfaces, one service

| Surface | Reach it with | Best for |
| --- | --- | --- |
| Desktop Studio | Windows installer or `operon serve` in a browser | Building, inspecting and debugging analyses |
| CLI | `python -m operon …` | Batch jobs, servers, reproducible commands |
| HTTP API | `operon serve`, `/api/v1/openapi.json` | Web front ends, LIMS and pipeline integration |
| MCP | `operon mcp` | Agents that compose and run workflows |

MCP is a protocol bridge, not an AI provider: Operon never calls a model. Connect any
MCP-capable client, grant `--allow-run` only when execution is intended, and use
`--read-only` for inspection-only sessions.

## Install

| Target | How |
| --- | --- |
| Windows desktop | Run `Operon_Setup.exe`. It ships its own relocatable CPython runtime, isolates the app profile and uses a signature-verified WebView2 bootstrapper. |
| Linux / headless server | Unpack `Operon-<version>-Server.zip` and run `install.sh --prefix <dir>` (see [command_line_installation.md](docs/command_line_installation.md#linux-server)), or `pip install . ./library`. |
| Source checkout | `python -m pip install '.[agent]'` (Python 3.11+) — add the `agent` extra for MCP. |
| Agent client | Start `operon mcp` from your MCP client configuration; see [agent_operations.md](docs/agent_operations.md). |

Verify any installation:

```text
operon --version        # Operon 5.11.2
operon capabilities     # API version, protocol version and capability list
operon registry check   # operator, Reader, package and route counts for this library
```

Windows installs keep the workspace under the install directory and the shared
profile in `%USERPROFILE%\.operon`; Linux and macOS use `~/.operon`. Large model
weights, databases, external tools and dedicated environments are prepared on demand
and are never implied by an installer.

## First run: desktop (5 minutes)

1. Launch Operon and open the canvas.
2. Drag in a Reader and point it at a table — for example `CsvReader` with
   `matrix.csv`, dimensions `sample,feature`, sample labels `auto` and column labels
   from the header row.
3. Add an operator such as `PCA`, connect the Reader output to it, set the dimension
   to `feature` and the component count to `2`.
4. Open the execution settings, check the environment and prepare any missing
   dependencies.
5. Run. Follow the task in the task manager; an environment preparation step is
   explicit, never implicit.
6. Open the result viewer, then inspect the run history for parameters, logs and
   retained outputs.

Viewers are configured under **Settings → Output and viewers**. Sub-graphs can be
collapsed, single operators bypassed, and the whole canvas edited as one undoable
transaction; starting a job is always a separate action.

## First run: headless

```text
python -m pip install . ./library
operon --version
operon serve --port 8765     # then open http://127.0.0.1:8765
```

Or drive the same service from the CLI without a browser:

```text
operon operators search "differential expression"
operon operators describe pca --view schema
operon workflow lint examples/workflows/script_pipeline/workflow.yaml
operon environment check examples/workflows/script_pipeline/workflow.yaml --require-files
operon run examples/workflows/script_pipeline/workflow.yaml --progress --request-id demo-001
operon jobs list
```

`environment check` validates declarations and input files; `environment prepare`
explicitly authorizes installation. Preparation and validation never install.

## How a run is composed

1. **Graph** — steps, ports and tags define the computation; saved workflows carry
   their own frozen parameter values.
2. **Readiness** — contracts, parameters and input files are validated before
   submission; a missing kernel or file fails early with a diagnostic.
3. **Environment** — the declared environment is checked and prepared explicitly,
   then recorded as a receipt with the run.
4. **Execution** — the scheduler runs steps locally, over SSH or on a Slurm node,
   enforcing memory admission, resource modes and spill limits.
5. **Artifacts** — outputs are indexed with representation, size and SHA-256, then
   displayed through result viewers or exported.
6. **Export** — the frozen plan can be packaged with its verified environment to run
   without Operon on the destination.

## Operator library

The bundled library is versioned separately from the application. This source tree
declares application **5.11.2** and library **2.1.3** (minimum application 5.11.2).

Operators and Readers use **SDK protocol v3**: a literal class declaration, a separate
parameter schema, adjacent Markdown documentation, declared ports and a content-hashed
implementation. The registry rejects a declaration that does not compile, that reads
parameters it never declared, or whose route references a missing operator.

Inspect what you have instead of trusting a number in a README:

```text
operon registry check
operon operators list --kind reader
operon operators describe <id> --view docs
```

Third-party operators live in packages. Build one with `operon plugin init/check/test/build`,
hot-load a single module through **Library Management → Refresh library**, or install a
signed library with `operon library install`. See
[library_extensions.md](docs/library_extensions.md) and
[application_library_boundary.md](docs/application_library_boundary.md) for the
application / library split.

## Repository layout

| Path | Contents |
| --- | --- |
| `operon/` | Application: service, CLI, HTTP API, MCP server, execution engine, environments, remote coordinator, storage and pool. |
| `operon_sdk/` | Public SDK for protocol v3 Steps and Readers. |
| `src/` | Implementation package the bundled library imports from: `src/task/step/steps/`, `src/reader/readers/`, shared contracts in `src/core/`, server helpers in `src/web/`. |
| `library/seed/` | Generated library: registry indexes, documentation, route templates and package manifest. |
| `frontend/` | React 19 + Vite canvas UI. |
| `desktop/`, `installer/` | Windows desktop host and installer. |
| `docs/` | Documentation; start at [docs/README.md](docs/README.md). |
| `examples/` | Protocol v3 examples and an example workflow. |
| `tests/`, `scripts/`, `verification/` | Test suite, build and release tooling, acceptance evidence. |

## Documentation

| I want to… | Read |
| --- | --- |
| Get running | [quickstart.md](docs/quickstart.md), [installation.md](docs/installation.md), [windows_setup.md](docs/windows_setup.md), [desktop.md](docs/desktop.md), [command_line_installation.md](docs/command_line_installation.md) |
| Author workflows | [workflow_yaml_v3.md](docs/workflow_yaml_v3.md), [workflow_parameters.md](docs/workflow_parameters.md), [data_formats.md](docs/data_formats.md), [readiness.md](docs/readiness.md) |
| Control execution | [EXECUTION_ENVIRONMENTS.md](docs/EXECUTION_ENVIRONMENTS.md), [resource_runtime.md](docs/resource_runtime.md), [server_cli.md](docs/server_cli.md) |
| Run remotely | [REMOTE_EXECUTION.md](docs/REMOTE_EXECUTION.md), [SERVER_HANDSHAKE.md](docs/SERVER_HANDSHAKE.md), [SERVER_INSTALL_REPAIR.md](docs/SERVER_INSTALL_REPAIR.md) |
| Ship a result | [result_viewers.md](docs/result_viewers.md), [PUBLICATION_FIGURES.md](docs/PUBLICATION_FIGURES.md), [automatic_portable_export.md](docs/automatic_portable_export.md), [portable_packages_v3.md](docs/portable_packages_v3.md) |
| Integrate or automate | [headless_api.md](docs/headless_api.md), [api_quickstart.md](docs/api_quickstart.md), [agent_operations.md](docs/agent_operations.md), [canvas_collaboration.md](docs/canvas_collaboration.md) |
| Extend the library | [operator_protocol.md](docs/operator_protocol.md), [sdk_quickstart.md](docs/sdk_quickstart.md), [sdk_reference.md](docs/sdk_reference.md), [plugins.md](docs/plugins.md), [library_release_standard.md](docs/library_release_standard.md) |
| Follow changes | [docs/releases/](docs/releases/), [updates-since-3.1.6.md](docs/updates-since-3.1.6.md) |
| Understand the design | [docs/design/](docs/design/), [five-layer-test-standard.md](docs/verification/five-layer-test-standard.md) |

Full index: [docs/README.md](docs/README.md).

## Development

```text
python -m pip install -e '.[dev]'
python -m pytest -q                          # full suite
python -m pytest tests/test_contracts.py -q  # focused
cd frontend && npm ci && npm run build       # canvas bundle
python -m operon registry check              # library consistency
```

Rebuild the static registry and operator documentation whenever authoring metadata
changes ([registry_maintenance.md](docs/registry_maintenance.md)):

```text
python -m operon registry build
python scripts/build_operator_docs.py
```

Documentation-only changes must not change execution identity or force users to
re-pin workflows. Keep product paths portable and technical documentation in English.

## Release model

`main` integrates the application and the bundled library. They release on separate
semantic versions and tags:

- application releases use `v<major>.<minor>.<patch>`;
- library releases use `library-v<major>.<minor>.<patch>`.

Each application release records the exact library sources it was built with, and each
library declares the minimum application that can load it. Published tags and installers
are immutable. Rebuilding the library is a deliberate, versioned operation — a
documentation or packaging fix in the application does not silently rewrite the seed.

## Status

Operon releases with acceptance evidence rather than claims here. The evidence
standards live in [five-layer-test-standard.md](docs/verification/five-layer-test-standard.md)
and the per-release audit reports in [docs/verification/](docs/verification/). Counts,
platform support and coverage vary by release and by the library you have installed;
`operon registry check` and `operon capabilities` report the truth for your tree.

## Open source

Operon is released under the [Apache License 2.0](LICENSE), Copyright 2026 Haojian Li.
Keep `LICENSE` and `NOTICE` with any distribution and review
[THIRD_PARTY_NOTICES](THIRD_PARTY_NOTICES) for bundled components. Contributions are
welcome; see [CONTRIBUTING.md](CONTRIBUTING.md).
