# Operon quick start

Create a workflow, choose where it runs, and inspect its saved results. You can
use the Windows canvas or run the same workflow from a terminal. An AI account
is optional. The examples below use synthetic data, not biological findings.

For a deliberately short, click-by-click version, use
[中文快速开始](../QUICKSTART.zh.md) or
[English quick start](../QUICKSTART.en.md). The rest of this page explains the
same flow with more detail.

## 1. Choose your installation

Open [GitHub Releases](https://github.com/lovegavin/Operon/releases/latest) and
choose the application release, not a separately versioned library release.

| You want to… | Download / entry point |
| --- | --- |
| Edit and run on Windows | **Operon_Setup.exe** |
| Run on a Linux server without a desktop | **Operon-4.0.2-Server.zip** |
| Develop from source with your own Python | Follow **Source and terminal users** below |

The application and operator library are independently maintained. You do not
need to download every release asset. `SHA256SUMS.txt` lists the published hashes.
Existing published installers are immutable; this guide documents the current
workflow, while each release's verification file describes its exact tested build.

## 2. Windows: install and run a small PCA

1. Run **Operon_Setup.exe**, choose an installation directory, and install.
   Launch **Operon Studio** from its shortcut. Setup supplies a management Python;
   no system Python or Conda configuration is needed to open the application.
2. Save the text below as `matrix.csv` in a writable data folder. In Studio,
   choose **Add input data** and select that file. Use `CsvReader`, dimensions
   `sample, feature`, automatic sample labels and column headers as feature labels.
3. Search the operator library for **PCA**, drag it onto the canvas, and connect
   the input node's output port to PCA's input port. Double-click PCA to inspect
   parameters; set the dimension to `feature` and the component count to `2`.
4. In execution settings, select your local environment and review its memory
   budget. Choose **Check execution environment**. If dependencies are missing,
   use the offered explicit environment/dependency preparation, then check again.
   An initial dependency download needs internet access. Validation does not
   install packages silently.
5. Save the workflow and click **Run**. Open **Run history → View results** when
   the task completes. This example produces PCA data; it does not automatically
   add a scatter plot. To make figures, connect a plotting operator afterwards.
6. Open the task's logs and retained outputs. For plotting routes, PNG, PDF and
   SVG entries open the actual saved files. Configure third-party viewers under
   **Settings → Output and viewers** when you want to inspect native outputs.

```csv
gene_a,gene_b,gene_c
1,2,3
2,3,4
4,1,2
3,4,1
5,2,6
6,5,3
```

Expected result: one input node connected to PCA and a completed task containing
two principal components for six rows. This tiny dataset checks installation
and connectivity; it is not an analysis benchmark.

Language and theme are under **Settings**. The library's **+** opens **Add
operators** for ordinary packages and saved workflow operators. Installing an
operator registers its declaration; scientific dependencies belong to the
execution environment selected for the workflow.

## 3. Linux: install and run without a desktop

Download and extract the server ZIP. For the current `4.0.2` release:

```sh
unzip Operon-4.0.2-Server.zip
cd Operon-4.0.2-Server
bash install.sh --prefix "$HOME/apps/operon" --result "$PWD/server-install.json"
```

Use a writable installation directory. On Linux x86_64, the installer can
bootstrap private Python when Python 3.11+ is absent; this needs networking,
`curl` or `wget`, `tar` and `sha256sum`, but no `sudo`. Other architectures need
a compatible supplied Python. See [installation options](command_line_installation.md#linux-server).

The result JSON prints the actual `install_dir`, `workspace`, `command` and log
path. If the chosen directory was already occupied, use those returned paths
in place of the examples below. With an initially empty prefix:

```sh
OPERON="$HOME/apps/operon/bin/operon"
"$OPERON" --version
cp -R examples/workflows/script_pipeline "$HOME/apps/operon/workspace/quickstart"
"$OPERON" workflow lint "$HOME/apps/operon/workspace/quickstart/workflow.yaml"
"$OPERON" environment check "$HOME/apps/operon/workspace/quickstart/workflow.yaml" --require-files
"$OPERON" run "$HOME/apps/operon/workspace/quickstart/workflow.yaml" --progress --brief --request-id quickstart-001
"$OPERON" jobs list
```

The included example generates synthetic numeric data and scales it in two
branches. It uses standard-library Python scripts and needs no optional analysis
packages. A completed task and two branch outputs confirm the execution path.
Use the returned task ID in these commands:

```sh
"$OPERON" jobs logs JOB_ID
"$OPERON" artifacts list JOB_ID
"$OPERON" pool status
```

Repeat the same unchanged submission with `--request-id quickstart-001` to reuse
its original task record. After changing inputs or parameters, use a new request
ID. Keep `workflow.yaml`, its scripts, `parameters.json` and `execution.json`
together. Parameter values are frozen with the workflow, independent of later
operator defaults.

## 4. Source and terminal users: generate a CSV/PCA project

Use Python 3.11+ in a dedicated virtual environment. From an application source
checkout on `main`:

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install . ./library
operon workflow init my-first-workflow
cd my-first-workflow
operon --workspace . workflow lint workflow.yaml
operon --workspace . environment check workflow.yaml --require-files
# If the check reports missing scientific dependencies, install them explicitly:
operon --workspace . environment prepare workflow.yaml
operon --workspace . run workflow.yaml --progress --brief --request-id pca-001
operon --workspace . jobs list
```

On Windows, use `python -m venv .venv` and `.venv\Scripts\Activate.ps1` instead
of the first two commands. `workflow init` creates the synthetic CSV, YAML,
independent parameter/execution JSON and lock files. A frontend build is not
required for terminal execution. `python -m operon` is equivalent to `operon`.

## 5. Edit locally, execute on a server

In **Settings → Servers**, add the SSH host, port and login method. Select the
existing server installation returned by the Linux installer, or use the explicit
**Install / upgrade server** action for a new one. Then choose that server in the
workflow's execution settings, select server-resident inputs or local inputs to
upload, validate and run. Local uploads support progress, resumption and reuse.
You can reconnect to inspect server jobs and logs.

Both hosts must be upgraded to use their current scheduling behavior. Since
3.1.1, each host/account automatically starts or reconnects to its shared resource
pool. No pool address or manual service command is needed. Accepted pool workers
survive client disconnects; stages not yet submitted by a closed workflow
orchestrator resume on reopening/retry. See [server CLI and lifecycle](server_cli.md).

## 6. Connect your own agent (optional)

Use the desktop's **Agent** panel to copy the connection configuration into your
MCP client. Grant read, edit and run permissions according to the work you want
it to perform. For a headless terminal project, the equivalent entry point is:

```sh
operon --workspace /absolute/path/to/project mcp --allow-run
```

Editing is enabled by default; `--read-only` restricts the connection to reads,
and omitting `--allow-run` prevents task submission. The selected environment
needs the application's `agent` extra for MCP. Start
with `operon help` or the MCP `operon_guide` tool, then retrieve only relevant
operators and documentation. Tool IDs keep the `operon_` compatibility prefix.
In the desktop, selected nodes provide context; an agent can submit a batch of
canvas edits that the user can undo together. Running a task is a separate action.
See [agent guide](agent_operations.md) and [third-party HTTP API tutorial](api_quickstart.md).

## If something stops the first run

| Symptom | Next action |
| --- | --- |
| Environment check reports missing dependencies | Prepare dependencies for the selected local/server environment, then validate again. |
| An operator requires Linux | Select a compatible Linux execution host. Installing a Windows package does not supply Linux tools. |
| Input file not found | Check the input path on the selected host; terminal relative input paths use the selected workspace. |
| No new operator after editing source | Use library management to refresh its registry; ordinary reads use the cached manifest. |
| A different Operon version owns the pool | Finish its tasks and close its clients before switching versions. |
| Task fails | Open **Run logs**, or use `jobs logs JOB_ID`; retain the task ID and log when reporting the problem. |

Report reproducible problems through [GitHub Issues](https://github.com/lovegavin/Operon/issues),
including the application version, execution OS and relevant logs. Do not attach
credentials or private research data. Operon is licensed under
[Apache-2.0](../LICENSE); bundled/external third-party components keep their own licenses.
