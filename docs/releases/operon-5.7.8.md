# Operon Studio 5.7.8

Runtime dependency installs are queued, every installer step fails fast instead of
hanging, and the same operations are exposed through the HTTP API, MCP and the CLI.

## Fixed

- **F-84 Dependency install blocked the request.** `POST /api/environments/{name}/dependencies/download`
  ran the whole pip or conda command inside the HTTP request, so the panel gave up
  long before pip finished and the button looked dead. The endpoint now queues a
  tracked job, returns immediately, appends the command output to the environment
  log and reports the outcome through the operation list.
- **F-85 Dependency install on an unprepared environment.** The endpoint used to
  create a stub staging tree for an environment that did not exist. It now refuses
  with a readable message: `环境 <name> 还没有准备好（当前：missing）。请先点击「准备」把环境装好，再安装这条依赖。`
  and returns HTTP 409 without touching the disk.
- **F-86 Remote dependency install blocked the bridge.** The remote agent executed
  the install inline, so the desktop waited on a multi-minute call. The agent now
  starts a background worker and answers with a `queued` acknowledgement.
- **F-87 A silent installer step could hang for up to 40 minutes.** Every installer
  command is now supervised: if it produces no output for 60 seconds it is killed
  and the failure reads `<command> produced no output for 60s; aborted instead of
  waiting for the <timeout>s limit`. Slow mirrors surface as a short, readable
  failure instead of an indefinite "installing" card.
- **F-88 CLI parity.** `operon environment dependency <name> <kind> <requirement>`
  queues the same install locally or on a configured server (`--profile`), and
  `operon environment log <name> [--limit N]` reads the same log the panel shows.
- **F-89 MCP gap.** `operon_environment_log` was missing from the MCP surface; the
  tool list now reports 78 tools and the tool reads local or remote logs.

## Changed

- The `environment dependency` install runs through the same serial queue as
  environment preparation, so a dependency install and a preparation never run at
  the same time on one host, and cross-process callers wait for the file lock
  instead of racing a second micromamba.
- The pip step keeps a long total budget (5400 s) but is now bounded by the 60 s
  silence watchdog, which is what a stuck download actually looks like.
- `Interaction audit` in `docs/verification/interaction-audit.md` records the
  dependency card, the log drawer and both of the new CLI actions.
