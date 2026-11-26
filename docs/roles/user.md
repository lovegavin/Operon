# Operon for end users

You want an analysis done, with a record of how it was done. Operon gives you a
canvas of validated operators instead of a pile of scripts: you pick operators,
connect them, fill in parameters, and the engine checks the connections, the
parameters and the environment before anything runs.

## Install

| You are on | Do this |
| --- | --- |
| Windows | Run `Operon_Setup.exe`; the desktop app and its Python runtime are installed together |
| Linux, server or cluster login node | Unpack the Server ZIP and run `install.sh --prefix <directory>` |
| Python 3.11+ only | `python -m pip install . ./library`, then `operon serve` |

The Windows app keeps its profile in `%USERPROFILE%\.operon` and its workspace
under the install directory; the first launch creates both. Details:
[windows_setup.md](../windows_setup.md), [installation.md](../installation.md),
[command_line_installation.md](../command_line_installation.md).

## Your first analysis

1. Start the app. The canvas opens on an empty workspace.
2. Drop a `CsvReader` and point it at a CSV: `sample,feature` columns with
   numbers. It infers the matrix shape and the sample labels.
3. Drop `PCA`, connect it, and set the dimension to `feature` and components to 2.
4. Open the execution panel and let Operon check the environment. If a
   dependency is missing it says so before the run; prepare it once, then rerun.
5. Run. The same panel shows the log, the retained outputs and any figures.
6. Open a result in the viewer configured for that format, or fetch the file
   from run history.

The full walk-through with screenshots-free text is [quickstart.md](../quickstart.md).

## Reading results

Results are files plus a report. The canvas shows the report; the run history
keeps the files, the parameters and the environment receipt. Viewers are chosen
per format under **Settings → Output and viewers** — see
[result_viewers.md](../result_viewers.md). Publication-ready figures and static
plots have their own guides: [PUBLICATION_FIGURES.md](../PUBLICATION_FIGURES.md),
[static_plotting.md](../static_plotting.md).

## Where the work runs

The same workflow runs on your machine or on a configured SSH server. Select the
server in the execution panel; the capability check runs on that host. On Slurm
clusters the node picker shows free CPU and memory per node and places the step
on a ready node. See [REMOTE_EXECUTION.md](../REMOTE_EXECUTION.md) and
[SERVER_HANDSHAKE.md](../SERVER_HANDSHAKE.md).

Reference datasets too large to copy by hand are declared by the library:
[large_resources.md](../large_resources.md) explains download and link.

## When something is blocked

Most blocks are one of four things, and each has a page:

| Symptom | Read |
| --- | --- |
| A step says it is not ready | [readiness.md](../readiness.md) |
| A dependency is missing or stale | [dependency_isolation.md](../dependency_isolation.md) |
| A step is re-running instead of reusing results | [stage_cache.md](../stage_cache.md) |
| An environment install failed on a server | [SERVER_INSTALL_REPAIR.md](../SERVER_INSTALL_REPAIR.md) |

The log drawer shows what the operator printed; the readiness panel shows what
the engine checked.

## Save and share

Save the workflow to reuse it, register it as a route if your group runs it
often ([route_operators.md](../route_operators.md)), or export a package that
runs without Operon ([automatic_portable_export.md](../automatic_portable_export.md)).

## If you work with an agent

An agent connected over MCP can build and run the same workflows. Give it
[roles/agent.md](agent.md) or the prompt block it contains; the rules there keep
it from guessing paths and from reporting a run it did not check.
