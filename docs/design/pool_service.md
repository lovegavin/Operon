# Multi-workspace resource pool service

The shared pool is the default execution authority for desktop, headless CLI,
HTTP/MCP and SSH servers. One pool per host/account serves all workspaces in
the same admission domain. No address, token or manual pool command is needed.

## Automatic startup and discovery

The application starts a detached control process on first resource access and
registers its workspace. Concurrent clients reuse the same owner. The host RAM
ceiling is scanned once (90% of available memory); CPU capacity respects affinity
and visible container quotas. Recovery with active attempts preserves the durable
ceiling rather than treating currently free memory as a new pool budget.

The account-local state is under `<admission directory>/managed-pool`; the
existing admission directory remains compatible with earlier ownership checks.
`BIOPIPE_ADMISSION_DIR` is an administrator override, not a way to obtain extra
capacity. Keep one admission domain for clients sharing physical resources.
The daemon persists workspace bindings and retains each workspace's selected
scientific interpreter and allowed input directories. It does not install or
repair scientific dependencies at startup; workflow readiness remains explicit.

Closing a client removes its subscription only. Dead client processes are
reconciled by PID and creation time. The pool exits after the last subscription
and active task/lease disappear. A replacement daemon adopts surviving workers
without launching them again. Local idle observation does not start a pool:

```bash
operon pool status
operon pool stop  # retire an idle pool; rejects active work, never cancels it
```

Different application code versions cannot share a live managed daemon. Finish
tasks and close clients before switching installations. A live legacy allocator
also blocks takeover; no failure silently launches a second allocator. An
explicit `BIOPIPE_ENGINE_MODE=legacy` remains available for diagnosis on a drained
domain. `Settings(testing=True)` retains the isolated in-process test default;
production-default lifecycle tests deliberately use ordinary settings.

`BIOPIPE_POOL_ADDRESS` and `BIOPIPE_POOL_TOKEN` select an administrator-managed
pool instead of automatic discovery. The manual service/configuration below is
for this optional deployment mode.

## Authority model

- One `PoolService` process acquires the existing `HostAdmission` ownership
  record atomically (`claim_coordinator`).  A legacy launcher using the same
  installation checks that record before `launch`, before dispatch and before
  `reserve`; it cannot silently become a second allocator after the inventory
  scan.  Older binaries that do not know the record must be upgraded first;
  mixed-version operation is an explicit deployment prohibition, not a guessed
  safety property.
- The pool coordinator is the sole RAM/CPU lease authority.  Workspace
  `JobService` instances are execution adapters only: they create their own job
  directory, frozen `parameters.json`, `task.yaml`, plugin lock and worker, but
  never reserve host memory through `HostAdmission`.
- Every run stores its own `workspace_id`, principal/project and frozen graph.
  No shared mutable working directory is used.  The worker's `cwd` and task
  directory are the registered workspace.
- A client connection is not an entitlement.  The fairness identity is the
  configured workspace principal; multiple connections under one principal
  share one aggregate share.
- Closing a client session, or closing one workspace's client surface, does not
  stop the pool or cancel another workspace's runs.  Only `PoolService.shutdown`
  explicitly stops the coordinator and owned workers.

## Workspaces and task binding

Each `JobService` in the pool has:

- its own workspace root and `.studio/jobs/<run>` directory;
- the same shared engine database and pool ceiling, but a workspace-specific
  `EngineRuntime` facade for event/journal scope;
- the same shared `EnvironmentGuard` path, keyed by the real interpreter
  identity (executable + version + prefix), not by workspace or installation
  directory;
- the existing scientific worker, memory planner, emergency spill, frozen
  argument JSON and artifact layout.

A job submitted to workspace A cannot read or cancel workspace B's record even
when both use the same OS account.  The implementation does **not** claim
security isolation between untrusted OS users sharing one account or one
Python environment; use separate OS accounts/hosts for that boundary.

## Control API

`operon pool serve --config pool.json` starts a loopback-only framed control
server.  The token is read from `--token`, `BIOPIPE_POOL_TOKEN` or the config;
if omitted it is generated into `<root>/pool-token` with restrictive file mode.

Methods (through `biopipe.pool_service.PoolClient`):

| Method | Purpose |
| --- | --- |
| `pool.status` | pool ceiling, coordinator/epoch, leases, workspaces, gate |
| `workspace.list` | registered workspace ids, roots and principals |
| `session.open` / `session.close` | per-client subscription lifetime; close never stops the workspace/pool |
| `workspace.stop` | explicit stop accepting work for one workspace; running work continues |
| `run.submit` | submit a graph to a named workspace with a stable request id |
| `run.details` | job + run + attempt + lease + lifecycle state |
| `run.cancel` | cancel one run; other workspaces unaffected |
| `events.page` | durable events scoped to that workspace/principal |

### Ordinary application/API/CLI/MCP/SSH entry

The existing `Application`/`TaskService` boundary routes to the automatic pool
by default. To select a separately managed pool, set:

```text
BIOPIPE_POOL_ADDRESS=127.0.0.1:57891
BIOPIPE_POOL_TOKEN=<local token>
BIOPIPE_POOL_PRINCIPAL=alice
```

The workspace's `root` and `data_dir` must be the same directory registered in
the pool service, and for local desktop/CLI/MCP viewing the pool service must
share the filesystem so job records/reports remain readable.  A remote pool
whose workspace is not mounted locally is not supported by this adapter; use a
pool service co-located with the workspace or add an explicit artifact/report
proxy (not implemented).  In this mode `JobService` has **no local
`HostAdmission`, no engine coordinator, and no local scheduler**: `launch`,
`cancel`, `details` and `events` go to the same pool authority.  A pool/session
failure raises `engine_unavailable`; it never starts a local fallback job.  The
SSH server uses the same environment on the server host, so an SSH `run` is also
a pool submission rather than a second allocator. Environment maintenance uses
the gate path returned by the pool, not a client-local gate. ExecutionService
continues to orchestrate placements, uploads and stages; each stage carries a
stable pool request key. Transfer buffers consume the same pool RAM ledger and
are released after use or confirmed owner death, never solely on a timeout.

A session is per client connection, not per workspace.  Two clients can open
independent sessions for the same workspace; closing one removes only that
session and leaves the other session, running jobs and the pool untouched.
After a pool restart, the client reopens its subscription before retrying the
same durable run key.
`workspace.stop` is the separate explicit "stop accepting new work" operation;
`PoolService.shutdown` is the explicit pool-wide operation.

CLI client commands:

```bash
operon pool status --address 127.0.0.1:PORT --token ...
operon pool submit --address ... --token ... \
  --workspace /srv/ws-a --principal alice --request-id stable-1 --file graph.json
operon pool cancel --address ... --token ... --workspace /srv/ws-a --run-id ...
operon pool stop-workspace --address ... --token ... --workspace /srv/ws-a
```

The config shape is:

```json
{
  "root": "/srv/operon-pool",
  "admission_dir": "/srv/operon-pool/admission",
  "workspaces": [
    {"root": "/srv/ws-a", "principal": "alice"},
    {"root": "/srv/ws-b", "principal": "bob"}
  ],
  "code_root": "/opt/operon",
  "capacity_bytes": 8589934592,
  "cpu_threads": 8,
  "token": "replace-with-a-local-secret",
  "port": 57891
}
```

## Lifecycle states

`run.details` exposes all four independently:

- `compute_complete`: the worker produced a complete run summary and exited 0;
- `artifact_committed`: the output manifest was verified/published;
- `tree_exited`: the root and every observed descendant are gone;
- `resources_released`: the coordinator lease (or legacy reservation) is
  released.  `lease_state` is also returned.

A failed artifact publication does not become a scientific success.  A live
descendant prevents terminal acknowledgement and keeps the lease charged.

## Recovery

The coordinator outbox and attempts are durable.  On restart a new pool process
re-registers the same workspace roots, adopts live workers by process identity
and reconciles attempts.  If a run references a workspace that is no longer
registered, reconcile fails closed and keeps the lease rather than launching in
a guessed directory.

## Current limitations

- The pool is a local loopback control service; it does not implement
  cross-OS-user authentication.  A token is local access control, not a
  multi-tenant security boundary.
- The pool coordinator's fairness identity is the workspace principal configured
  by the trusted operator; it does not authenticate that principal.
- No automatic migration from a live legacy binary: drain first.
- A session is a subscription record, not a durable task owner.  Closing it does
  not cancel work; `workspace.stop` stops new submissions for one workspace and
  `PoolService.shutdown` stops the pool explicitly.
- See [release acceptance](server_engine_acceptance.md) for platform evidence;
  production Reader streaming and immutable environment generations remain
  separate roadmap items. Verified caching is optional: see [stage reuse](../stage_cache.md).
