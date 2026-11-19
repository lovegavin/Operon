# Operon Studio 5.7.9

Released 2026-11-20. Library: `1.1.5` (unchanged).

## Added

- Environment cards now report six readiness states instead of a single installed flag:
  `未创建` (no interpreter yet), `未就绪` (interpreter exists but dependencies or
  resources are incomplete), `安装失败`, `已就绪`, `准备安装` and `正在安装`. The state is
  recomputed on every refresh from `interpreter`, the stored error, the dependency
  counters and the resource gap of that environment, so a card can no longer claim
  readiness while weights or databases are missing.
- Environment logs are persisted to
  `<environment root>/.operon-environment-logs/<name>.log` with UTC timestamps.
  Preparation, dependency installs and every pip/conda/micromamba command append
  their output there, and `operon environment log`, the REST endpoint and the MCP
  tool `operon_environment_log` read the same file, so the log drawer is no longer
  empty for environments that were installed earlier.
- `operon_environment_retry` for MCP and `POST /api/remote/{key}/environments/{name}/retry`
  for remote agents. The desktop repair button now follows the selected execution
  location instead of always retrying on the local machine.
- Installation slots are keyed by environment root, so a local install and a remote
  agent install no longer wait for each other.

## Fixed

- F-90: the "修复" action always called the local retry endpoint, even when the
  execution location was a remote server.
- F-91: `operon environment log <name>` parsed the name into the positional `file`
  argument and then printed the usage text.
- F-92: the CLI sent `POST` (because it passed an empty payload) to a read-only log
  endpoint, so the request failed with `Method Not Allowed`.
- F-93: environment logs lived only in the in-memory progress record; a restarted
  service lost them and older environments had no log at all.
- F-94: the process-wide installation semaphore serialised every environment root,
  including the remote agent's root inside the same process.

## Verification

Clean install of 5.7.9, 18 environments, resource manifest 16 entries, HTTP, MCP and
CLI parity checked on port 5815. See `operon-5.7.9-test-report.md`.
