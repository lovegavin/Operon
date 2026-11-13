# Operating Operon with an agent

Operon exposes one engine through MCP, CLI and HTTP. These operating guides are
for **using** the software; SDK/protocol documentation is for writing extensions.
No model, desktop window or source checkout is required to retrieve a guide.

## Three layers

| Layer | MCP | CLI | Contents |
| --- | --- | --- | --- |
| Entry | Server initialization instructions; `operon_guide()` | `operon help` | Short rules, permissions, task routing |
| Task | `operon_guide(topic="workflow")` | `operon help workflow` | One executable scenario at a time |
| Operator | `operon_operator_search`, then `operon_operator_describe` | `operon operators search`, then `describe` | Installed schemas/contracts and selected Markdown |

`operon help index` lists topics: start, operators, canvas, workflow, jobs,
results and api. `guide` is an alias of `help`. Guides are package resources under
`operon/guides/`, included in wheels. MCP also exposes `operon://guide` and
`operon://guide/{topic}`. Clients that do not display server instructions or
resources can call the guide tool explicitly. A client controls what reaches its
model; Operon cannot force it to inject or obey instructions.

The same English text is available through authenticated GET `/api/v1/guides`
and `/api/v1/guides/{topic}`. Responses include software version and a content
SHA-256. Send `if_sha256` to suppress unchanged text. Unknown topics fail explicitly;
there is no arbitrary-file reading endpoint. Reading CLI help starts no service.

## Small responses by default

- MCP/CLI search defaults to five brief, relevance-ranked matches. Exact IDs rank
  first. Word boundaries avoid matches such as liability/reliability. Declared
  multilingual aliases work; this is lexical search, not automatic translation.
- Search summaries omit implementation hashes and repeated descriptions. Long
  summaries are explicitly marked as truncated. `next_offset` supports paging.
- Describe `view=schema` returns execution schemas/contracts and a section index;
  `view=docs` retrieves only the requested documentation plus identity. `view=full`
  restores complete descriptor metadata. `sections=['*']` explicitly reads all MD.
- MCP job status and CLI `jobs get` default to brief. Use `view=full` / `--view full`
  for runtime internals. `operon_job(wait_seconds=30)` waits inside the tool;
  CLI `jobs wait <id> --timeout 30 --brief` does the same. Timeout never cancels.
- Logs default to 4 KiB of text. Choose base64 for exact byte reconstruction or
  both for compatibility. Offsets remain bytes, with the same reset/done semantics.
- `--compact` removes JSON indentation. `run --brief` omits large job details.
- `workflow prepare ... --require-files --output prepared.json` freezes, validates
  and writes the graph. Use that prepared graph for execution; do not run a second
  identical validation just to follow a checklist.

HTTP search/describe/job/log defaults retain their prior full representations;
new views are explicit query/body options. CLI `operators list` and MCP catalog
remain compatibility operations. Operator v3, saved parameter files, transaction
revisions, run permissions, streaming/spill and SSH scheduling are unchanged.
After upgrading, restart an idle old service/desktop so adapters reach the updated
API; do not stop a service while it has active jobs.

## Task folders and backend writes

Agents often need to create a task directory or drop a report next to results,
but the host shell may not have write permission inside the workspace (Windows
sandboxed shells can run at a lower integrity level than the workspace). Two
backend operations remove that dependency: the service performs the write with
its own permissions, and every path is workspace-relative.

```text
operon_task(base_dir="task1")                     # input, results, reports, figures
operon_task(base_dir="project/task2", folders=["input", "reports"])
operon_write_text(path="task1/reports/summary.md", content="# Summary\n")
```

HTTP equivalents (edit scope): `POST /api/v1/tasks` with
`{"base_dir": "...", "folders": [...]}` and `POST /api/v1/workspace/files`
with `{"path": "...", "content": "...", "overwrite": true}`. Capabilities
`task-scaffolding` and `workspace-files` advertise them.

Rules enforced by the backend: paths must be relative, may not contain `..`,
must resolve inside the workspace, may not be symbolic links, and may not
target internal state such as `.studio`, `.operon` or `.admission`. Existing
files require `overwrite=true`; text writes are UTF-8 and limited to 10 MiB.
Empty parent folders are created automatically. These tools never grant shell
access and never change job execution authority.

## Backend engine diagnostics

The durable backend state is readable without changing execution authority:

```text
operon engine status                       # pool snapshot, epoch, journal counters
operon engine events --after 0 --limit 50  # resumable lifecycle events
GET /api/v1/engine                          # same snapshot (context scope)
GET /api/v1/engine/events?after=0&limit=50  # same cursor (context scope)
```

Event cursors are durable; keep the returned `cursor` and pass it as `after`.
If a cursor has expired, the response sets `snapshot_required` and the caller
must request a snapshot instead of silently skipping events.  The engine journal
is a live index; existing `jobs get`, `jobs logs`, `artifacts` and `events`
APIs remain the user-facing compatibility paths. The default reports `mode: pool`
and a live shared coordinator owner. An explicit `legacy` override keeps the old
allocator authoritative; always inspect the returned status.

### Coordinator mode and environment maintenance

`OPERON_ENGINE_MODE=coordinator` is an explicit opt-in for a **drained**
admission domain.  On startup it refuses to run if a legacy reservation, an
active legacy job, another live launcher, or a legacy worker is present; it
does not silently fall back to shadow.  Once started, one coordinator owns the
pool, the legacy scheduler is not started, and the existing JobService worker
and memory planner remain the scientific implementation.  Use
`operon engine status` to verify `mode`, `epoch`, owner and active attempts
before treating the service as coordinated.

Dependency repair/install and plugin replacement take an exclusive environment
marker.  A repair is rejected while any worker holds an environment lease, and
a new worker is rejected while repair is active.  The gate is keyed by the real
interpreter identity, so workspaces sharing one Python environment are mutually
exclusive; only distinct interpreter/prefix environments can repair
independently.  This is a mutual-exclusion fallback: it does not provide
immutable environment generations or rollback.
If `engine status` reports an environment-gate error, stop starting work and
fix the reported path; do not delete a live gate while workers are running.

### Multi-workspace pool service

Desktop and server applications automatically start/reuse a dedicated shared
pool in their host/account admission domain. No pool configuration is required.
Use `operon pool status` to inspect it without starting anything; `operon pool
stop` retires an idle pool and refuses active tasks. Scientific environment
preparation remains an explicit workflow operation.

For an administrator-managed service instead of automatic discovery:

```bash
python3 -m operon pool serve --config /path/to/pool.json
python3 -m operon pool status --address 127.0.0.1:PORT --token "$OPERON_POOL_TOKEN"
python3 -m operon pool submit --address ... --token ... \
  --workspace /srv/ws-a --principal alice --request-id stable-1 --file graph.json
python3 -m operon pool cancel --address ... --token ... \
  --workspace /srv/ws-a --run-id <run>
python3 -m operon pool stop-workspace --address ... --token ... \
  --workspace /srv/ws-a
```

Each run is bound to its registered workspace root, principal, frozen graph,
parameter JSON and plugin lock.  Closing a client session does not stop the pool
or another workspace's work.  A token is local access control, not a
multi-tenant security boundary; do not use one OS account as an untrusted-user
boundary.  See [multi-workspace resource pool](design/pool_service.md).  Drain
legacy launchers before starting the pool; older binaries that do not honor the
admission ownership record must not be run concurrently.

Ordinary desktop/CLI/MCP/API/SSH entry uses the shared pool without a separate
`pool submit` command. To override automatic discovery with that manually
configured service, start the workspace application with:

```text
OPERON_POOL_ADDRESS=127.0.0.1:PORT
OPERON_POOL_TOKEN=<local token>
OPERON_POOL_PRINCIPAL=<registered principal>
OPERON_ENVIRONMENT_GATE=<pool state>/environment-gate.json
```

The workspace `root`/`data_dir` must be the one registered in the pool service.
In this mode the application has no local HostAdmission, engine coordinator or
scheduler; launch/cancel/details/events are routed to the pool.  A pool failure
returns `engine_unavailable` and never starts a local job.  Two clients may open
independent sessions for one workspace; closing one session leaves the other
client, running jobs and the pool alive.  `workspace.stop` is the separate
explicit "stop accepting new work" action; `PoolService.shutdown` is the
explicit pool-wide action.

### Verified stage cache

Cross-run stage reuse is opt-in and must be declared explicitly in a workflow:

```json
{"runtime": {"execution": {"cache": "verified"}}}
```

The cache identity includes source-file content, frozen parameters, plugin pins
and package generation, the actual environment content fingerprint and execution
semantics.  A hit is accepted only after the recorded output manifest is
re-hashed; changed, missing or added files invalidate it.  The switch alone is
only permission to attempt reuse.  Eligibility additionally requires an
explicit `cache` contract on every operator and reader descriptor:

```json
{"cache": {"deterministic": true, "side_effects": "none",
           "stochastic": false}}
```

A stochastic declaration must name the bound seed parameter(s); a missing seed,
an external side effect, an unknown declaration or an unverified environment
fails closed and records concrete reasons in `cache_decisions`.  There is no
inference that an operator is deterministic merely from its input/output
formats, and no blanket declaration for legacy operators.  The index is local
to the workspace service and is not a substitute for environment generations.

## Recommended operation paths

- Existing canvas: context → selected schemas → one apply transaction → undo if
  requested. Execution is a separate, authorized action.
- Existing saved analysis: retrieve route/version → adjust only required inputs
  and parameters → prepare/save if changed → submit → wait → result index.
- New analysis: bounded search → candidate schemas → relevant examples → prepare
  → submit → wait → result index. Preserve the user's resource/execution settings.
- Failed run: brief status → selected log window → resolve the actual error →
  submit a changed request with a new ID, or retry an identical request with its
  original ID. Never restart merely because an acknowledgement was lost.

Generated operator pages are explicitly labelled; they are not scientifically
validated examples. Operator authors should provide purpose, input assumptions,
parameter choices, a tested example, interpretation and limitations alongside
their code/parameter JSON. See [operator documentation](operator_documentation.md).

See [canvas operations](agent_api.md), [headless execution](headless_api.md), and
[third-party API tutorial](api_quickstart.md). Lower payload size is measurable;
actual monetary cost also depends on the client, model, retries and usage pricing.
