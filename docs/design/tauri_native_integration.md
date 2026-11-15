# Experimental Tauri native integration

Status: experimental native integration, compiled and exercised on Windows.
See `tauri_native_acceptance.md` for evidence and remaining manual/package gates.
The composition layer originally owned:

- `desktop-tauri/src/main.rs`
- `desktop-tauri/src/bridge.rs`
- `desktop-tauri/src/lib.rs`
- `desktop-tauri/ui/index.html`
- `docs/design/tauri_native_integration.md`

## Entry point and startup

`main` accepts exactly:

```text
operon-desktop-experimental --config <path> [--smoke-test]
```

There is no implicit global configuration, production profile, or managed
runtime lookup. The config path is loaded through `HostConfig::load`, which
canonicalizes and validates every configured path. After a successful load:

1. `HostConfig::ensure_experimental_profile()` claims or verifies the
   experimental profile marker.
2. `InstanceGuard::acquire()` takes the OS-backed profile lock.
3. The `InstanceGuard` is moved into managed `HostState` and retained until the
   process actually exits.

No log directory or instance lock is created before the profile marker step.
Configuration, profile and second-instance failures use a safe native message
dialog and a non-zero exit; they do not panic and they do not start a backend.

The Tauri builder manages `HostState`, registers the six commands, and creates
the native shell in `setup`:

- app-wide native menu: Show Operon, Open Logs, Documentation, Quit Operon;
- tray menu: Show Operon, Quit Operon;
- static local diagnostics window (`WebviewUrl::App("index.html")`).

The diagnostics window gets no runtime capability. It cannot invoke host
commands. Its close button requests the same full-exit flow as the menus.

## Owned backend and owned origin

After the native shell is created, `Backend::start(config)` runs on the Tauri
async runtime, not on the main UI thread. On success the host:

1. stores the authenticated loopback `Url` in `HostState.expected_origin`;
2. installs one runtime capability:

```rust
CapabilityBuilder::new("owned-ui")
    .local(false)
    .window("main")
    .webview("main")
    .remote(origin.to_string())
    .permission("host")
    .permission("core:event:allow-listen")
    .permission("core:event:allow-unlisten")
```

No wildcard origin, wildcard port, shell permission, or filesystem permission is
added.

3. creates the main window with:
   - `WebviewUrl::External(origin)`;
   - `data_directory(profile/webview)`;
   - top-level navigation restricted by
     `navigation::allow_owned_navigation(url, origin)`;
   - `NewWindowResponse::Deny` for all `window.open` requests.

External documentation is opened only through
`navigation::open_default_documentation()`, from the native menu. No renderer
command opens an arbitrary URL.

If capability installation or main-window creation fails, the owned backend is
retained and the diagnostics window explains the failure. The backend is not
restarted, and an explicit Quit Operon drains it through the same shutdown path.

## Command contract

Rust argument names serialize with Tauri's default camelCase mapping. The JS
side uses:

- `ready` — no arguments;
- `acknowledge_draft_flush` — `{ requestId, saved }`;
- `show_diagnostics` — no arguments;
- `request_full_exit` — no arguments;
- `open_committed_artifact` — `{ runId, artifactId, fileId }`;
- `select_path` — `{ kind }`, where `kind` is `open_file`, `save_file`, or
  `folder`.

Every command first re-checks the caller's window label and exact current URL.
Renderer arguments never carry authority. The accepted URL policy is the
`http://127.0.0.1:<explicit-port>/` origin already stored from the authenticated
backend; userinfo, HTTPS, `localhost`, IPv6, a different port, a path, a query,
or a fragment are rejected. Pure policy unit-test functions are authored for
wrong label, wrong port, API/result URLs, userinfo, query/fragment, non-loopback
and HTTPS URLs. They were not executed in this integration.

`ready` additionally requires a retained backend. It marks the lifecycle ready
and destroys the diagnostics window. Duplicate `ready` calls are harmless only
in the ready states; the lifecycle rejects stale states.

`show_diagnostics` creates and opens only `config.logs_dir()` through the OS
file-association opener. It accepts no path from the renderer.

`open_committed_artifact` copies the owned origin and studio token transiently,
releases the backend mutex, then delegates the opaque IDs to the D artifacts
module. The token is never logged or written to the smoke receipt.

`select_path` delegates only the enum picker kind to the D dialogs module.
Cancellation returns `null`.

## Full-exit flow

The native app menu, the tray menu, and the `request_full_exit` command all call
the same `request_exit` path.

When the lifecycle is ready, the host first queries the existing `GET /api/jobs`
endpoint with the owned `x-studio-token`. It counts queued/running local and remote
jobs without cancelling them. If any are pending, or if the query cannot be
verified, a warning `rfd::AsyncMessageDialog` asks for confirmation. Cancelling
the dialog leaves the app running.

After confirmation:

1. `Lifecycle::begin_close()` mints one request ID.
2. `app.emit_to("main", "operon://prepare-close", { request_id })` is emitted
   exactly once for that request.
3. A five-second task checks that the same request ID is still flushing. If it
   is, `draft_flush_timed_out` restores the visible ready state, shows the main
   window, and displays a diagnostics message.
4. A renderer ACK with `saved: false` restores the visible ready state and does
   not exit.
5. An ACK with `saved: true` moves the lifecycle to `Draining`; the host then
   calls the retained `Backend::shutdown(8s)` without creating a new process.
6. Only a confirmed child stop calls `Lifecycle::backend_stopped()`. The host
   records the optional smoke `exit` transition and calls `app.exit(0)`.
7. A drain timeout enters `Recovery`, keeps the app alive, shows diagnostics,
   and allows an explicit retry through the same retained backend.

No `std::sync::Mutex` guard is held across an await. Duplicate close requests
coalesce onto the in-flight request ID.

Starting is handled separately because the lifecycle source rejects
`begin_close` from `Starting` and `BackendFailed`. Explicit quit during startup
sets a retained cancellation flag. The startup task is not aborted or dropped;
when the backend later becomes ready it drains the newly created owned child. If
startup fails, no child exists and exit is allowed. A backend failure is a
separate diagnostics state and is never auto-restarted.

The window close button hides the main window only in a ready state. Closing it
during startup, flushing, draining, recovery, or backend failure requests the
shared exit/retry flow. Closing the diagnostics window also requests an exit.

## Backend monitor

A once-per-second monitor calls `Backend::try_exited()` outside Draining and
Recovery. An unexpected exit moves the lifecycle to `BackendFailed`, shows a
diagnostics window, and never replays jobs. There is no automatic restart.

## ExitRequested gate

`RunEvent::ExitRequested` is prevented unless one of these is true:

- the lifecycle reached `Closed` after a confirmed owned-child stop;
- startup finished and there is genuinely no owned child;
- the native shell failed before startup, so no child was ever spawned.

An unknown OS session end is not claimed as graceful. The owned instance guard
is retained in managed state until the process exits.

## Smoke mode

`--smoke-test` does not fake an acknowledgement. After the real main frontend
calls `ready`, the host triggers the normal full-exit path once. The real React
listener receives `operon://prepare-close` and performs its real draft flush.

When smoke mode is enabled, actual transitions are appended to
`profile/logs/native-smoke.json`:

- `ready` after the lifecycle actually becomes ready;
- `draft_saved` or `draft_cancelled` after a valid ACK;
- `exit` only after confirmed `backend_stopped()`.

The receipt contains no token and is not written for a normal launch.

## Actual limitations

- Native build and real frontend/backend smoke results are recorded in
  `tauri_native_acceptance.md`; installed-package acceptance remains pending.
- `tauri.conf.json` declares no static capabilities and no static windows. The
  runtime capability is created only after authenticated readiness.
- On Windows the app-wide menu is attached to native windows; when the main
  window is hidden, the tray menu is the always-available native Quit path. The
  code installs both, but no accessibility claim is made for a hidden window's
  menu bar.
- No activation IPC is implemented. A second instance for the same profile is
  rejected cleanly with the typed `use_tray_menu_exit` action and a safe native
  dialog.
- No installer or updater channel exists in this phase; E remains pending.
- Review fixes touch C/D modules, manifests and the frontend host/result adapter.
  The scientific backend, SDK, operator library and production worktree remain
  unchanged. A parent exit is not tree-drain proof: all owned job members must
  stop. Explicit quit after a confirmed nonzero tree exit returns code 1.

## Reviewed additions

- Windows creation is suspended until Job Object assignment, so a venv
  redirector cannot launch an unowned server before attachment. Its announced
  PID must identify an exact member of this job; `GetProcessId` checks that
  Windows did not normalize an invalid low-bit PID.
- `/api/v1` artifact reads use the studio authentication header, not an agent
  bearer token. The two credential kinds are not interchangeable.
- Only the owned main root receives native IPC. New windows are denied. A narrow
  legacy figure route may instead open in the OS browser; results never receive
  native IPC. RunPlan result buttons pass opaque IDs to the native artifact
  opener. Executables, arbitrary paths and arbitrary URL popups are rejected.
- The single drain deadline includes stdin signaling and bounded log draining;
  retries do not relaunch the backend.
