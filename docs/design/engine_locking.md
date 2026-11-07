# Engine lock and ownership order

**Scope:** local Studio/headless services, coordinator takeover and the SSH
server adapters.  This document is normative for future edits.

## 1. Ownership boundaries

| Component | Owns | Must not do |
| --- | --- | --- |
| `StateStore` | one writer transaction, run/attempt/lease/event/outbox persistence | spawn a process or send on a socket while the transaction is open |
| `Coordinator` | pool queue, leases, epoch, launch outbox | grant resources from an executor or a worker |
| `Executor`/`Supervisor` | process launch/stop receipts and confirmed termination | change a committed lease |
| `JobService` | job directory, worker process map, compatibility receipts, coordinator-mode executor target | be a second allocator beside an active coordinator |
| `EnvironmentGuard` | exclusion between dependency mutation and live attempts (fallback until generations exist) | provide two simultaneous environments or rollback |
| `ControlLoop` | connection admission, request deadlines, response framing | own scientific job lifetime |
| `EngineJournal` | adapter request claims and job lifecycle event index | replace the scientific job record |

## 2. Lock order

Acquire in this order; never take an earlier lock while holding a later one.

1. `PoolResources`/coordinator state writer (`StateStore.lock` + SQLite
   `BEGIN IMMEDIATE`).
2. `JobService._dispatch_lock` (serializes legacy admission/spawn cycles).
3. `JobService.lock` (`FileLock`, reentrant per thread) — job state, process
   maps, compatibility receipts.
4. `RouteLibrary`/catalog lock (`JobService._catalog_lock`).
5. `EnvironmentGuard` file lock — attempt leases and exclusive repair marker.
6. Adapter-specific locks (`RemoteService._lease_guard`, transfer store
   mutexes, handshake lock).
7. Per-artifact/run file locks — leaf locks only.

The admission ledger is a leaf owned by `HostAdmission`.  `JobService._dispatch`
may hold the job lock while reserving a legacy entry (job → admission), but no
path holds the admission lock while taking a job lock.  `PoolService` claims the
admission ownership before starting its workspace services and coordinator; a
workspace `launch` releases the admission lock before taking its job lock.
The environment gate is likewise acquired after the job-state snapshot and is
not taken by repair while a job lock is held.

The important changed paths this round:

- **Handshake inversion removed.** `ManifestHandshake.response` reads
  `service.history()` and `service.resources()` *before* acquiring
  `handshake.lock` and `dependencies.lock`.  The previous code held those two
  locks while taking the job-state lock.  There is now no
  handshake/dependency → job-state edge.
- **Job → environment gate only.** `JobService._start` releases the job lock
  before it acquires the attempt lease.  `_refresh_jobs` may hold the job lock
  while it calls `EnvironmentGuard.ensure_job`; the reverse path does not
  exist: repair/plugin-install takes the gate and then works on dependencies,
  plugins or the filesystem, never on job state.
- **Coordinator → executor → job, never state → job.** The coordinator closes
  its SQLite transaction before `executor.launch/cancel`; the executor takes the
  `JobService` lock.  No path takes the job lock and then requests an engine state
  transaction that is held by a coordinator callback.
- **Pool ownership is an admission leaf.** `HostAdmission.claim_coordinator`
  performs inventory and ownership in one ledger lock.  Legacy paths check that
  record before `launch`, dispatch and reserve.  The dedicated pool service
  claims before creating workspace services and before the coordinator starts;
  workspace job records never become a second allocator.
- **Cancel/start extraction.** `JobService.cancel`/`_cancel_local` mutate state
  under `self.lock`, release it, stop the owned tree, and reacquire it only to
  publish the terminal transition.  A worker tree that is not confirmed stopped
  leaves `recovery_required` and retains the lease/reservation.
- **Start extraction.** `_start` publishes reservation/`starting` state under
  the lock, releases it, acquires the environment lease, spawns, then binds the
  process identity.  `JobServiceExecutor`/the pool executor call this only from
  the coordinator launch outbox after the lease transaction committed.

Proof obligation: a new edge is acceptable only if a directed acyclic graph
exists over these components.  "The critical section is short" is not a
proof.  In particular, do not call `service.details`, `service.launch`,
`executor.*` or a socket operation while holding `StateStore.lock` or the
environment gate.

## 3. Fork/exec and socket rules

- No `subprocess.Popen`, `wait`, `communicate`, `socket.sendall` or remote RPC
  while a `StateStore` transaction is open.
- No process launch while `JobService.lock` is held.
- Socket handlers may dispatch concurrently; a slow client must not hold the
  state lock.
- A response is always framed even after an exception (`ControlLoop` maps
  errors to stable codes).

## 4. Shutdown and epoch rules

- Only one live coordinator owns a pool.  Claiming an occupied fresh pool
  raises `busy`; a stale owner is adopted only after its identity/heartbeat
  proves it is gone.
- Coordinator mode refuses to start over a legacy reservation, a legacy active
  job, another live launcher in the admission domain, or a live legacy worker.
  The dedicated pool service uses the same ownership record.  This is the
  drain/inventory gate; it is not a silent shadow downgrade.
- Environment leases record the real interpreter identity (executable, version,
  prefix), so workspaces/install roots sharing that interpreter share the
  exclusion domain.  A repair for one identity does not block a distinct
  environment, and a live orphan worker keeps its own lease.
- Epoch advances on takeover.  Old fences cannot acknowledge a resize, publish
  an artifact or stop a lease as if they were current.
- `close_session`/client disconnect detaches observation only; it never calls
  `shutdown_pool`.  Closing one workspace session in the pool service does not
  cancel that workspace's running work or another workspace's work.
- Resource release requires proven process-tree termination or a verified
  supervisor handoff.  An unconfirmed stop leaves `recovery_required` and keeps
  the lease charged.

## 5. Remaining known constraints

- `JobService.resources()` holds `self.lock` while reading the engine status
  snapshot (job-state → engine-state).  It must not call a coordinator command
  or block on a worker.
- `JobService._launcher_event` appends to the engine journal while a caller may
  hold `self.lock` (job-state → engine-state).  It is best effort and must not
  acquire the environment gate, catalog lock or a process.
- The existing `ExecutionService` keeps its own coordinator lock and file
  locks; it is not driven by the engine pool directly.  The pool coordinator
  drives workspace `JobService` workers; `ExecutionService` stage cache and
  same-run resume remain at the application layer.  Do not introduce a second
  resource reservation there.
- Environment leasing is mutual exclusion, not generation isolation: a task
  that already started continues under its old interpreter state; a repair
  cannot start until all leases for that interpreter identity end.  There is no
  rollback of a completed environment mutation.
- The dedicated pool's token and configured principal are local access control,
  not isolation between untrusted OS users.
