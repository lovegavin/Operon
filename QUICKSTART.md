# Operon quick start

From a clean machine to a finished analysis: install Operon Studio 5.11.2 with the
bundled operator library 2.1.3, run one real analysis, then move to the command line
when the same workflow has to be repeatable.

The installer ships the operator library, so there is no separate import step.

## 1. Install

| Target | What to run |
| --- | --- |
| Windows 10/11 x64 | `Operon_Setup.exe`. It carries its own Python runtime; no system Python needed. |
| Linux server | `Operon-<version>-Server.zip`, then `./install.sh --prefix "$HOME/operon" --result` |
| Source checkout | `python -m pip install . ./library`, then `operon serve --port 8765` |

Confirm the build you actually have:

```bash
operon --version
operon capabilities
```

`operon --version` prints `Operon 5.11.2`. `operon capabilities` lists what this
build can do; if a page in the repository disagrees with it, the build is right.

## 2. First analysis on the canvas

You need one CSV whose rows are samples and whose columns are features:

```text
sample,A,B,C
s1,1.0,2.5,3.1
s2,1.4,2.1,2.8
s3,9.2,8.7,9.9
```

1. In Studio, choose a workspace folder and add the CSV to it.
2. Drag **CsvReader** onto the canvas and point it at the file. It reads the header
   as feature names and the first column as sample labels.
3. Drag **PCA** onto the canvas, connect CsvReader's output to it, set
   `dimension` to `feature` and `components` to `2`.
4. Press **Run**. Operon validates the graph, resolves the operator environment,
   executes, and keeps the parameters, environment and logs with the result.
5. Open the result in a viewer. Configure viewers under
   **Settings → Output and viewers**.

Editing and running are separate actions: the canvas can be changed freely, and
nothing executes until you run it.

## 3. The same work from the command line

The CLI talks to the same service as the desktop and the HTTP API:

```bash
operon operators search pca
operon operators describe pca --view schema
operon workflow lint examples/workflows/script_pipeline/workflow.yaml
operon environment check examples/workflows/script_pipeline/workflow.yaml --require-files
operon run examples/workflows/script_pipeline/workflow.yaml --progress --request-id quickstart-001
operon jobs list
```

`environment check` never installs anything. Preparing an environment is a
separate, explicit step (`operon environment prepare`), because it changes the
machine.

## 4. Where to go next

| Goal | Read |
| --- | --- |
| Understand the product | [README.md](README.md) |
| Command reference and everyday use | [docs/roles/user.md](docs/roles/user.md) |
| Drive Operon from an agent | [docs/roles/agent.md](docs/roles/agent.md) |
| Author workflows as YAML | [docs/workflow_yaml_v3.md](docs/workflow_yaml_v3.md) |
| Run on a Linux server | [docs/REMOTE_EXECUTION.md](docs/REMOTE_EXECUTION.md) |
| Ship a result to someone without Operon | [docs/automatic_portable_export.md](docs/automatic_portable_export.md) |
| Full documentation index | [docs/README.md](docs/README.md) |

中文快速开始：[QUICKSTART.zh.md](QUICKSTART.zh.md)
