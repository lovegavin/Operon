# RC4 shortcut activation handoff

Scope: `experimental/tauri-shell` only. Production `desktop/`, `library/` and the
installer are unchanged.

## Behavior

A second shortcut launch for the same owned installation/profile now proves the
live host and sends authenticated `show` requests over the existing maintenance
pipe. A new request id is used for each bounded `not_ready` retry. Success exits
`0` before `HostState`/Tauri construction, so no second Python/backend is
spawned. Failure exits `2`; there is no fallback that starts a host.

`main.rs` keeps the gate-first first-launch path. If `StartupGuard::acquire`
fails, it checks the installation-scoped active event and the profile instance
lock. A maintenance event, an unverifiable gate, or a free lock fails closed. A
busy gate with a held instance lock is the startup race; activation may proceed
without taking the mutex, and the running host rechecks maintenance before it
shows. If the guard is held and `InstanceGuard::acquire` returns only the typed
`UseTrayMenuExit` contention, activation runs while the gate stays held. The
guard is not dropped before the spawning path takes ownership of it.

`activation.rs` reads `.operon-maintenance-host.json` with a 16 KiB limit and
`deny_unknown_fields`. It validates schema `1`, installation id, token shape,
pipe prefix/hash/UUID, stale/missing receipt, canonical executable path, PID,
process creation FILETIME, liveness, and the pipe server PID. The token is not
written until `GetNamedPipeServerProcessId` matches the receipt PID. The whole
exchange is bounded to five seconds.

Show wire exchange:

1. `show` request with a fresh UUID.
2. Host precheck: maintenance active -> `rejected`; lifecycle `Starting` ->
   `not_ready`; shutdown/failure -> `rejected`; ready -> `accepted`.
3. Client sends the same `ack` frame as quit.
4. Host rechecks maintenance and lifecycle on the Tauri UI thread, then
   `show`/`unminimize`/best-effort `set_focus`.
5. Host returns `shown` or `rejected`. Only `shown` is success. `not_ready` is
   retried by the client within the five-second deadline; all other statuses are
   terminal.

Quit is unchanged: `accepted`, matching `ack`, then the existing close flow. It
has no post-ack frame. The quit tests remain in place.

## Files

- `desktop-tauri/src/activation.rs` (new client and tests)
- `desktop-tauri/src/main.rs` (second-launch branch)
- `desktop-tauri/src/instance.rs` (read-only lock probe)
- `desktop-tauri/src/maintenance.rs` (`Action`, `is_active`, show handling)
- `desktop-tauri/src/bridge.rs` (activation verdict and UI-thread show)
- `desktop-tauri/src/lib.rs`, `desktop-tauri/Cargo.toml`
  (`Win32_System_Pipes`)

## Focused verification

Toolchain is project-local:

```powershell
$env:RUSTUP_HOME='D:\sysu\dinglab\BioPipe\.toolchains\tauri\rustup'
$env:CARGO_HOME='D:\sysu\dinglab\BioPipe\.toolchains\tauri\cargo'
$env:PATH="$env:CARGO_HOME\bin;$env:PATH"
cmd /c '"D:\sysu\dinglab\BioPipe\.toolchains\tauri\BuildTools\VC\Auxiliary\Build\vcvars64.bat" >nul && cargo test --locked --lib activation::'
cmd /c '"D:\sysu\dinglab\BioPipe\.toolchains\tauri\BuildTools\VC\Auxiliary\Build\vcvars64.bat" >nul && cargo test --locked --lib instance::'
cmd /c '"D:\sysu\dinglab\BioPipe\.toolchains\tauri\BuildTools\VC\Auxiliary\Build\vcvars64.bat" >nul && cargo test --locked --lib maintenance::'
cmd /c '"D:\sysu\dinglab\BioPipe\.toolchains\tauri\BuildTools\VC\Auxiliary\Build\vcvars64.bat" >nul && cargo test --locked --lib bridge::tests::activation'
```

Observed in this session (project-local toolchain, `--locked`):

- `activation::`: 8 passed, 0 failed (not-ready retry, required `shown`, terminal
  rejected/maintenance, wrong installation, bounded missing/stale receipt,
  pipe/token binding, server PID match).
- `instance::`: 5 passed, 0 failed (including the read-only lock probe).
- `maintenance::`: 12 passed, 0 failed (existing quit accepted/ack test unchanged;
  show ack/shown, not-ready/rejected, active-event check).
- `bridge::tests::activation`: 1 passed, 0 failed.
- `cargo check --locked --bin operon-desktop-experimental`: passed.
- `cargo fmt --check`: passed.

Limits: these are focused unit/IPC tests only. No full `cargo test`, no installer
run, no OS app launch, no screenshot, and no real double-click acceptance. The
final process-level shortcut acceptance remains for root.
