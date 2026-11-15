# Goal C handoff: native backend lifecycle

Scope: this worktree contains only the Goal C implementation files. Root still
owns `lib.rs`, `main.rs`, manifests, `bridge.rs`, commands/ACLs and integration.
No command, ACL, dependency or Python product file was changed here.

## Files delivered

| File | Purpose |
|---|---|
| `desktop-tauri/src/backend.rs` | Fixed-argument owned process, Job Object attach, bounded stdout/stderr drain, readiness/receipt/identity/bootstrap proof, shutdown ownership |
| `desktop-tauri/src/windows.rs` | Windows Job Object with exactly `KILL_ON_JOB_CLOSE | BREAKAWAY_OK`; no process-name cleanup |
| `desktop-tauri/src/instance.rs` | `fs2` exclusive profile lock, retained handle, no lock-path deletion |
| `desktop-tauri/src/lifecycle.rs` | Pure close/update state machine, no I/O and no waits |
| `desktop-tauri/src/logging.rs` | Bounded rotating file diagnostics below `profile/logs`, secret redaction |
| `desktop-tauri/tests/lifecycle_process.rs` | Real Python fixture tests; skipped clearly without `OPERON_TEST_PYTHON` |
| `desktop-tauri/tests/fixtures/fake_studio.py` | Handshake/readiness/receipt/auth fixture; no science |
| `desktop-tauri/tests/fixtures/unrelated_server.py` | Unrelated/breakaway loopback process fixture |

Root must add these module declarations to `lib.rs` (root-owned):

```rust
pub mod backend;
pub mod instance;
pub mod lifecycle;
pub mod logging;
pub mod windows;
```

`Cargo.toml` already contains every crate used: Tokio `process/io-util/time/
rt-multi-thread/sync`, `reqwest` without redirects/proxy, `url`, `uuid`, `fs2`,
`serde`/`serde_json`, `windows-sys` features and `tempfile` (dev). No dependency
change is requested.

## `Backend` API

```rust
pub const EXPECTED_STUDIO_VERSION: &str = "5.3.0";
pub const STARTUP_TIMEOUT: Duration = Duration::from_secs(30);
pub const MAX_STDOUT_LINE_BYTES: usize = 64 * 1024;

impl Backend {
    pub async fn start(config: &HostConfig) -> Result<Self, HostError>;
    pub fn pid(&self) -> u32;
    pub fn origin(&self) -> &url::Url;
    pub fn studio_token(&self) -> &str;
    pub fn try_exited(&mut self) -> Result<bool, HostError>;
    pub async fn shutdown(&mut self, timeout: Duration) -> Result<(), HostError>;
}
```

`Backend` intentionally has no `Debug` implementation. The token is never put in
a URL, a `HostError` message, or a log line. `start` returns only the four safe
`HostError` shapes; child/HTTP text is never copied into the error message.

### Startup sequence

1. Require absolute configured paths: configured Python file, backend
   `scripts/desktop_server.py`, frontend `index.html`. No PATH lookup.
2. Re-verify `HostConfig::ensure_experimental_profile()` so the profile marker is
   validated before any spawn.
3. Open `profile/logs/native-host.log`.
4. Create one Windows Job Object with `KILL_ON_JOB_CLOSE | BREAKAWAY_OK`.
5. Spawn exactly one Tokio child:
   `python -I -X utf8 -B -u <backend>/scripts/desktop_server.py
   --profile-dir <profile> --frontend <frontend> --port 0 --wait-for-host`, cwd
   `backend_root`, stdin/stdout/stderr piped, `kill_on_drop(false)`.
6. Attach that exact child handle to the Job Object. **Only after the attach
   succeeds is `start\n` written.**
7. Start bounded stdout/stderr drain tasks before the handshake. Every line is
   capped at 64 KiB; oversized lines are consumed and discarded.
8. Wait for `OPERON_READY <json>` within the 30 s deadline. The URL must be
   exactly `http://127.0.0.1:<nonzero>/` with no credentials, query, fragment or
   additional path; `pid` must equal the retained child PID.
9. Poll the owned receipt directory
   `profile/workspace/.studio/agent/servers/*.json` for a receipt with the exact
   child PID, the expected origin and `api_version == 1` (receipt publication
   races readiness).
10. `GET /api/agent/identity` with `x-operon-bridge: <receipt secret>` and require
    the returned `instance_id` to equal the receipt.
11. `GET /ready` and require `status == "ok"` plus `studio == "5.3.0"`.
12. `GET /api/bootstrap` and require canonical `storage.profile_dir`,
    `storage.workspace` and `storage.data_dir` to match this configured profile.
    Only then is the token retained.
13. Any failure in steps 5–12 terminates only this child/this Job Object, then
    returns `HostError::bridge_unavailable()` (or a retryable capability error on
    deadline expiry).

HTTP uses a client with redirects disabled, proxies disabled, a 2 s default
timeout and bounded response bodies. Identity/ready bodies are 64 KiB; bootstrap
is capped at 32 MiB. The receipt secret and studio token are registered with the
redacting diagnostics sink.

### Environment

`env_clear`, then only:

- Windows necessities: `SystemRoot`, `WINDIR`, `TEMP`, `TMP`, `USERPROFILE`,
  `APPDATA`, `LOCALAPPDATA`, `PROGRAMDATA`, `PROGRAMFILES`, `PROGRAMFILES(X86)`,
  `COMMONPROGRAMFILES`, `NUMBER_OF_PROCESSORS`, `PROCESSOR_ARCHITECTURE`, `OS`.
- `PATH` built from configured interpreter directory, backend root and Windows
  system directories (`System32`, `System32/Wbem`, `SystemRoot`).
- Optional proxy variables only (`HTTP_PROXY`, `HTTPS_PROXY`, `NO_PROXY`,
  `ALL_PROXY` and lowercase variants) when already present.
- `OPERON_RUNTIME_CONFIG=<profile>/runtime.json`,
  `OPERON_STUDIO_HOME=<profile>`, `PYTHONIOENCODING=utf-8`.

`PYTHONPATH`, `PYTHONHOME`, production `OPERON_*`/`BIOPIPE_*` runtime/profile
overrides and every other inherited variable are absent. Nothing global is
written.

### Shutdown and failure ownership

- `shutdown` writes `shutdown\n`, closes stdin, and polls the retained child
  until the caller's deadline.
- On timeout it returns
  `HostError::capability_unavailable(HostNextAction::Retry, None)` and **does
  not** kill, terminate the job, mark closed, or report success. Ownership stays
  in `Backend` for a UI retry or a later `try_exited`.
- Unexpected child exit is returned as a safe bridge error by `start` or
  `try_exited`; there is no automatic restart or job replay.
- Successful shutdown keeps the Job Object until `Backend` drops. Dropping
  `Backend` closes the job handle, which is the fail-safe only for actual host
  death. Breakaway children are no longer in the job and survive.

## `InstanceGuard` API

```rust
pub const INSTANCE_LOCK_FILE: &str = ".operon-instance.lock";

impl InstanceGuard {
    pub fn acquire(profile: &Path, installation_id: &str) -> Result<Self, HostError>;
    pub fn profile(&self) -> &Path;
}
```

- Creates/canonicalizes the profile, opens
  `<canonical profile>/.operon-instance.lock`, and retains an exclusive `fs2`
  lock handle for the guard lifetime.
- Same-profile second acquisition returns
  `HostError::capability_unavailable(HostNextAction::UseTrayMenuExit, None)`.
  Activation IPC does not exist yet, so a second launch is a typed
  already-running action, not a claimed success.
- The file is persistent evidence, not liveness proof: after a crash the lock is
  released and the stale file is re-locked safely. The file is intentionally not
  removed on drop, preventing lock-path splitting.
- Different profiles have independent lock files.
- Foreign-install/profile-marker policy remains in `HostConfig`, not here.

**Required composition order:** `HostConfig::ensure_experimental_profile()` →
`InstanceGuard::acquire()` → `Backend::start()`. The marker must exist before the
lock file is created; otherwise the next `ensure_experimental_profile()` sees a
non-empty profile without a marker and rejects it as foreign. `Backend::start`
re-verifies the marker, which is harmless when the lock file already exists.

## `Lifecycle` API

```rust
pub enum LifecycleState {
    Starting, ReadyVisible, ReadyHidden,
    Flushing { request_id: String },
    Draining, Recovery, BackendFailed, Closed,
}
pub struct CloseRequest { pub request_id: String, pub coalesced: bool }
pub enum FlushOutcome { Visible, Draining }
pub enum CloseFailure { DraftTimeout, DrainTimeout }

impl Lifecycle {
    pub fn new() -> Self;
    pub fn state(&self) -> &LifecycleState;
    pub fn request_id(&self) -> Option<&str>;
    pub fn failure(&self) -> Option<CloseFailure>;
    pub fn mark_ready(&mut self) -> Result<(), HostError>;
    pub fn hide(&mut self) -> Result<(), HostError>;
    pub fn show(&mut self) -> Result<(), HostError>;
    pub fn begin_close(&mut self) -> Result<CloseRequest, HostError>;
    pub fn acknowledge_draft_flush(&mut self, request_id: &str, saved: bool)
        -> Result<FlushOutcome, HostError>;
    pub fn draft_flush_timed_out(&mut self, request_id: &str) -> Result<(), HostError>;
    pub fn drain_timed_out(&mut self) -> Result<(), HostError>;
    pub fn backend_failed(&mut self) -> Result<(), HostError>;
    pub fn backend_stopped(&mut self) -> Result<(), HostError>;
}
```

Transitions:

| From | Event | To |
|---|---|---|
| `Starting` | `mark_ready` | `ReadyVisible` |
| `ReadyVisible` | `hide` | `ReadyHidden` |
| `ReadyHidden` | `show` | `ReadyVisible` |
| `ReadyVisible`/`ReadyHidden` | `begin_close` (new UUID) | `Flushing{id}` |
| `Flushing{id}` | `begin_close` again | same ID, `coalesced: true` |
| `Flushing{id}` | matching ACK `saved=false` | `ReadyVisible` |
| `Flushing{id}` | matching ACK `saved=true` | `Draining` |
| `Flushing{id}` | matching draft timeout | `ReadyVisible` + `DraftTimeout` |
| `Draining` | `drain_timed_out` | `Recovery` + `DrainTimeout` |
| `Draining`/`Recovery` | `backend_stopped` | `Closed` |
| `Starting`/visible/hidden/flushing | `backend_failed` | `BackendFailed` |
| `Recovery` | `begin_close` | retryable capability error; no new ID |
| `Recovery` | `backend_failed` | stale error; use `backend_stopped` |

A wrong/stale ACK, timeout ID, or transition leaves state unchanged and returns
`request_stale`. Hiding never starts an exit. `Recovery` cannot reach `Closed`
through a timeout; only confirmed `backend_stopped` (or a confirmed failure path
already in `BackendFailed`) can.

## Diagnostics

`logging.rs` writes only `<profile>/logs/native-host.log`, rotates at 4 MiB to
`native-host.1.log`, caps each persisted line at 8 KiB, strips control characters,
replaces registered secret values, and drops credential-looking lines
(`token`/`secret`/`password`/`authorization`/bridge headers/`Bearer`). It does not
configure global `tracing` output.

## Tests

`tests/lifecycle_process.rs` covers:

- delayed readiness, authenticated origin/token, normal stop;
- crash before ready → typed safe failure;
- missing configured runtime → typed failure without spawning;
- an occupied unrelated port is not reused;
- an unrelated Python process survives backend shutdown;
- a fixture child that uses `CREATE_BREAKAWAY_FROM_JOB` survives backend
  shutdown (proves `BREAKAWAY_OK` semantics);
- shutdown timeout → retryable failure, not success, ownership retained;
- receipt/identity mismatch, readiness PID mismatch and studio version mismatch
  all fail startup.

Run only when explicitly configured, for example:

```powershell
$env:OPERON_TEST_PYTHON = 'C:\path\to\python.exe'
cargo test --test lifecycle_process
```

Without `OPERON_TEST_PYTHON` each real-process test prints a clear SKIP and
returns. The lifecycle unit tests and receipt/origin unit tests do not need
Python. No test result is claimed by this handoff.

## Deviations / decisions

1. **Already-running action:** there is no dedicated `already_running` action in
   the shared `HostNextAction`; `UseTrayMenuExit` is used for the typed
   second-instance result. Activation IPC is not invented.
2. **Startup timeout:** the fixed 30 s deadline is internal. There is no public
   shortened-deadline test hook; slow-timeout tests would take 30 s and are not
   included.
3. **Logging:** implemented as a small profile-owned rotating writer instead of
   configuring the global `tracing` subscriber, keeping file output confined to
   the profile and avoiding side effects in the Tauri process.
4. **Storage proof:** all three bootstrap storage paths (`profile_dir`,
   `workspace`, `data_dir`) must canonicalize to the configured profile; a null
   `profile_dir` is rejected.
5. **Non-Windows:** `windows.rs` provides a no-op guard so the crate shape can
   compile, but process-tree ownership is only claimed for Windows x64.

## Unresolved gates for root

- Add the five `pub mod` declarations and compose the state machine with
  `Backend`/`InstanceGuard` in root-owned `bridge.rs`.
- Call order must be `ensure_experimental_profile` → `InstanceGuard::acquire` →
  `Backend::start` (see above).
- Compile the integrated crate and run `cargo test`; this worktree has no
  `Cargo.toml`/`lib.rs` and cannot be compiled in isolation.
- Run the real backend smoke separately with an actual CPython and the real
  `scripts/desktop_server.py`; the fixtures here are not science evidence.
- Verify the Job Object attach on the target Windows environment (including any
  parent job/sandbox restriction) and verify real pool/viewer breakaway.
- Wire close UX: hide vs full exit, draft-flush request IDs, shutdown retry from
  `Recovery`, and diagnostics open action.
- The real `/api/bootstrap` catalog can be large; the 32 MiB cap is deliberate.
  If the product catalog grows past it, only that cap needs review.
