# Experimental Operon desktop host

Windows x64 developer build, on `experimental/tauri-shell`. This is not a
replacement installer. It reuses the current React UI and Python management
service; science workers, RunPlan, scheduling, environment isolation, parameter
JSON and the operator library remain unchanged.

## Build

Prerequisites: Microsoft C++ Build Tools (MSVC and Windows SDK), WebView2,
Node/npm, and Rust via rustup. `rust-toolchain.toml` pins Rust 1.100.0;
`Cargo.lock` pins the dependency resolution. Tauri is 2.12.5.

From the repository root, prepare an explicit management interpreter if needed:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-studio.txt
cd frontend
npm ci
npm run build
cd ../desktop-tauri
cargo build --locked
Copy-Item host.example.json host.local.json
```

Edit `host.local.json` to select the interpreter and experimental profile.
Paths are resolved relative to that JSON file. The example is suitable for the
repository-local `.venv`; an already prepared management interpreter also works.
There is no PATH search, global runtime fallback, production-profile migration,
or automatic analysis dependency installation.

```powershell
.\target\debug\operon-desktop-experimental.exe --config .\host.local.json
```

With a custom `CARGO_TARGET_DIR`, use its `debug` executable instead. Keep the
repository, frontend build and Python interpreter present: this developer binary
is not yet a portable distribution. Build tools are not end-user dependencies.

## Behavior

- A profile marker binds the profile to this experimental installation. Foreign
  or nonempty unmarked profiles fail closed. A second host for the same profile
  is rejected; activation IPC is deferred.
- The selected Python starts suspended, is assigned to an owned Windows Job,
  then resumes. Readiness must identify that process or a member of its exact
  job (including Windows venv redirectors), followed by an instance-secret
  challenge and bootstrap validation.
- Closing a ready window hides it. **Quit Operon** in the native menu or tray
  requests draft saving, then stops the owned management tree. It does not
  cancel remote/shared-pool jobs or kill unrelated Python processes.
- A draft timeout restores the window. A drain timeout retains ownership and
  offers retry. Nonzero exits remain failures, including on retry; an explicitly
  closed failed tree ends the host with exit code 1.
- New RunPlan results open through opaque IDs, authenticated metadata, verified
  streaming downloads and an owned cache, then the OS file association. No raw
  renderer path or command line is accepted. Older figure links have a narrow
  same-origin OS-browser handoff; arbitrary popups are denied.
- Native path pickers and installation-namespaced credential helpers are
  available. Existing SSH credentials remain managed by Python, not migrated to
  Rust. Credential values never cross the renderer IPC.
- Logs and private runtime configuration stay in the experimental profile.

## Targeted verification

```powershell
cd desktop-tauri
$env:OPERON_TEST_PYTHON = (Resolve-Path ../.venv/Scripts/python.exe).Path
$env:OPERON_RUN_KEYRING_TEST = '1'
cargo test --locked
cargo fmt --check
.\target\debug\operon-desktop-experimental.exe --config .\host.local.json --smoke-test
```

The Python and keyring flags deliberately enable real-process and temporary
Windows Credential Manager tests. Without them those test bodies return early;
do not report such a run as process/keyring acceptance. The keyring test creates
and deletes a unique test-only entry. Smoke mode uses the actual frontend's
ready event and draft ACK, never an injected success, and writes
`profile/logs/native-smoke.json`.

See [native acceptance](../docs/design/tauri_native_acceptance.md) for observed
results and remaining gates. Installer/update integration, cross-platform hosts,
cross-machine acceptance and production promotion are separate work.
