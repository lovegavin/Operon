# Experimental Tauri host: implementation contract

## Fixed decisions

1. Branch: `experimental/tauri-shell`. Production remains on the validated release
   train. No default branch change, release upload or library modification.
2. Rust/Tauri 2 replaces only the C# window host. Reuse React/TypeScript/Vite.
3. Python Application, HTTP/CLI/MCP, RunPlan, pool, supervision and export remain
   authoritative. No Rust scheduler, alternate graph compiler or dependency solver.
4. Use the OS WebView: WebView2 on Windows, WKWebView on macOS, WebKitGTK on Linux.
   Windows x64 is the first supported experiment. Other platforms are not accepted
   merely because Tauri compiles there.
5. Start the existing lightweight management service. Scientific environments are
   prepared explicitly for a selected execution host, not at application startup.

## Technology stack and repository layout

Implementation references: [Tauri capabilities](https://v2.tauri.app/security/capabilities/),
[sidecar packaging](https://tauri.app/develop/sidecar/) and
[shell plugin scope](https://v2.tauri.app/reference/javascript/shell/).
These define available mechanisms, not permission to expose arbitrary process
execution to the renderer. Keep the narrow Rust-owned lifecycle contract below.

| Layer | Choice |
|---|---|
| Host | Tauri 2, Rust edition 2021, stable toolchain pinned in `rust-toolchain.toml` at first verified build |
| Async process/lifecycle | Tokio supplied by the Tauri runtime; bounded channels, explicit deadlines |
| Typed bridge | `serde` / `serde_json`; tagged request and error enums; no arbitrary command RPC |
| Logging | `tracing` + rolling file appender; credentials filtered before formatting |
| Secrets | OS credential store via a reviewed Rust keyring adapter; server secrets remain in the existing Python credential service initially |
| Web UI | Existing React/TS/Vite/XYFlow lockfile, no framework change |
| Backend | Existing CPython >=3.11, FastAPI/Uvicorn and Application services |
| Development tests | Rust unit tests, Vitest, existing Python contract tests; real Windows interaction for lifecycle gates |
| Packaging | Existing Setup first; experimental bundle identifier and install root; Tauri NSIS evaluation later |

All Rust crates use a committed `Cargo.lock`; CI and release builds run `--locked`.
At gate T00 record the exact Rust version and resolved Tauri/plugin versions in a
runtime manifest. No unpinned nightly toolchain, Git dependency, wildcard runtime
download or package-manager side effect on launch.

```text
desktop-tauri/
  Cargo.toml, Cargo.lock, rust-toolchain.toml, tauri.conf.json
  capabilities/main.json
  src/main.rs              # compose host; no business rules
  src/config.rs            # typed installation/profile selection
  src/backend.rs           # owned management process + authenticated readiness
  src/lifecycle.rs         # explicit close/update state machine
  src/bridge.rs            # minimal allowlisted UI commands
  src/windows.rs           # Windows Job Object / owned process handling
  src/diagnostics.rs       # startup log, redaction, bounded error report
  src/open.rs              # authorized file/viewer opening
frontend/src/host/
  types.ts, browser.ts, webview2.ts, tauri.ts, index.ts
```

## Bridge contract

Frontend accesses only `desktopHost`, with Promise-returning methods:

```typescript
interface DesktopHost {
  kind: 'browser' | 'webview2' | 'tauri';
  ready(): Promise<void>;
  acknowledgeDraftFlush(requestId: string, saved: boolean): Promise<void>;
  showDiagnostics(): Promise<void>;
  openCommittedArtifact(runId: string, artifactId: string, fileId: string): Promise<void>;
  onPrepareClose(handler: (requestId: string) => void): () => void;
}
```

No `exec(command)`, `readFile(path)`, `writeFile(path)`, arbitrary URL opening or
renderer-selected executable API. File and viewer requests resolve opaque artifact
IDs through the authenticated backend, then enforce its authorized result. Keep
the existing original-file HTTP links as a browser-compatible alternative.

Stable errors: `{code, message, request_id, retryable, next_actions}`. Use existing
backend errors where possible. Never convert an unknown submission outcome into
an automatic new run. UI edits retain their existing batch/undo semantics.

## Local service bootstrap

1. Read installation metadata and choose the experimental profile explicitly.
2. Acquire an experimental instance lock. Verify existing instance identity before
   activation; a matching PID alone is insufficient.
3. Resolve the owned management runtime. Do not use a system `python` from PATH.
4. Spawn the existing desktop service with an isolated environment and the current
   installation/profile arguments. Keep stdout/stderr in an owned rotating log.
5. Negotiate a randomly selected loopback port and session credentials through the
   existing bootstrap channel. Never use a hardcoded port or put credentials in
   a public URL, query parameter, localStorage or diagnostic report.
6. Verify authenticated health, installation identity and supported API version.
7. Load the existing UI. Report ready only after the canvas bootstrap has completed.
8. A backend crash shows a useful recovery screen and log location; restart requires
   confirmation when a submission outcome is unknown. Do not relaunch a workflow.

The experimental profile location comes from installation/configuration APIs.
Never embed a developer drive, account name, interpreter path or server address.

## Capabilities and navigation

Tauri 2 capabilities must grant only the commands used by the main window. No
shell/fs wildcard permissions. Do not grant privileged capabilities to an arbitrary
remote origin. If the app retains the loopback-origin UI, allow only the actual
owned local service and keep privileged commands behind host-side origin/session
verification. A static bundled UI with typed backend transport is a later gate,
not an excuse to broaden CORS or copy auth tokens into the renderer.

Block top-level navigation away from the owned UI. Open external documentation in
the system browser with an http/https allowlist. Do not render untrusted HTML results
with host capabilities; use sandboxed previews or external viewers.

See the official [capability model](https://v2.tauri.app/learn/security/capabilities-for-windows-and-platforms/)
and [configuration reference](https://v2.tauri.app/reference/config/).

## Ownership and shutdown state machine

```text
starting -> ready -> close_requested -> flushing_draft
  -> draining_owned_management -> closed
flushing_draft -> ready (save failed/user cancels close)
draining_owned_management -> recovery_prompt (timeout/unconfirmed exit)
starting/ready -> backend_failed (diagnostics; no job replay)
```

Use correlation IDs for close messages. The current draft-save timeout is a
starting compatibility value; record it, do not silently discard a failed save.
Close the management session according to existing policy; do not cancel shared
pool tasks or shut down a remote server just because a client window closes.

Windows process control must target only the exact owned process group with PID
and creation identity. Give graceful shutdown a bounded deadline; report unresolved
ownership rather than kill all python.exe. An installer upgrade obtains the same
maintenance/ownership proof as the current Setup. Preserve outstanding jobs and
submission receipts through restarts.

## Runtime distribution

Use a release-provided management runtime as a Tauri sidecar/deployment resource,
with an architecture-qualified path and verified release receipt. It is not the
full scientific dependency environment. Rust starts it with fixed arguments.
Tauri's [sidecar documentation](https://v2.tauri.app/develop/sidecar/) describes the
target-triple naming; frontend shell execution is not required.

Retain content-addressed runtime/dependency packages and environment conflict
isolation. A portable export remains an independent Python/R/native package and
does not require Tauri. Do not replace it with a shortcut back to the application.

## Installation and updates

Experimental product name `Operon Studio Experimental`, separate bundle ID,
shortcut and uninstall key. Never migrate or delete a production profile during
the experiment. Importing a workflow copy is allowed; it must not mutate its source.
Do not enable automatic updates until signatures, interrupted updates, rollback,
active-job protection and uninstall ownership have separate evidence. Production
Setup remains supported until the experimental replacement passes those gates.

## Promotion criteria

All T00–T08 gates in the coding instructions must pass with attached evidence.
Windows installation/reinstallation/uninstall, original canvas interactions,
Agent six-stage behavior, RunPlan execution/export, original result opening and
normal repeated exit are mandatory. Single-host Linux server functionality remains
headless and independent. Multi-host/Slurm support keeps its experimental label.
Promotion requires an explicit release decision; passing `cargo build` is not it.
