# Coding assignment: experimental Operon Tauri shell

## Read first

1. Repository AGENTS.md, README and current release/installation contracts.
2. `tauri_module_inventory.md` and `tauri_implementation_contract.md` in this folder.
3. Current `desktop/Program.cs`, `ProcessLifetime.cs`, `RuntimeLocator.cs`, Setup
   maintenance code, `scripts/desktop_server.py` and the frontend close handshake.
4. RunPlan/canvas preparation, environment package and artifact contracts.

Implement on `experimental/tauri-shell`, created from the **validated** canvas
integration commit. Preserve dirty worktrees; never reset or clean someone else's
checkout. No library edits, protocol/version bump, push or release in this task.
Do not invent another compiler, scheduler, environment manager, result store or
agent API. Unspecified behavior follows the existing product contract.

## T00 — Freeze the observable baseline

Record source commit, exact runtime/package versions, startup/close handshake,
backend arguments, allowed origins, profile/config locations, process ownership
and current updater/uninstaller expectations. Record cold/warm timings from the
same test machine. Produce `verification/tauri/baseline.json` and a gap list.
Do not run scientific dependency checks merely to open the shell.

## T01 — Introduce a transport-neutral host adapter

Implement `frontend/src/host/types.ts`, browser and current WebView2 adapters.
Move only host-message handling out of App into the adapter. Add targeted tests
for message correlation, listener removal, failed draft save and repeated close.
Include the difference between hiding to tray and explicit full exit. The new
host needs an accessible in-app Quit action and an installation-scoped maintenance
request; a generic window-close message must never be treated as exit evidence.
Current browser/WebView2 behavior must remain unchanged. Do not start Rust work
until this compatibility gate passes.

## T02 — Minimal isolated Tauri window

Create the prescribed Rust files/config/capability document. Pin the verified
stable toolchain and crate resolution. Load a static diagnostic page first.
Use the existing icon/theme tokens. Test experimental app ID/profile/shortcut
separation and that renderer code cannot invoke arbitrary shell or filesystem APIs.

## T03 — Own and authenticate the management backend

Implement installation resolution, isolated child environment, logs and readiness.
Exercise missing/corrupt runtime, occupied port, delayed readiness, backend crash,
second launch and stale instance receipts. Use a small real management service;
do not mock all process tests. No credentials in logs, URLs or renderer storage.

## T04 — Load the existing canvas and bridge

Use the existing Vite output; implement the Tauri `desktopHost` adapter. Verify
editing, double-click inspection, node drag, Ctrl multi-select, copy/paste/undo,
multi-document switch, input browsing and settings persistence. Retain browser
development. No forced Rust rewrites of HTTP operations.

## T05 — Close, upgrade and crash recovery

Implement the specified state machine, bounded draft flush and owned-process
drain. Test normal exit twice, close during preparation, close during a shared-pool
run, service crash, failed draft save and blocked exit. Confirm no unrelated Python,
old Operon installation or server process is terminated. Record process identities
and exit evidence. A timeout is a failed gate, not a successful forced cleanup.

## T06 — Agent and artifact parity

Run the existing Agent six-stage acceptance through the actual installed window.
Verify human selection, agent batch edits, one-step undo and task reuse. Open PNG,
PDF and SVG originals and an installed viewer through opaque committed artifact
IDs. Check missing viewer behavior. Keep untrusted HTML outside privileged views.
CLI/MCP must still operate when no Tauri window exists.

## T07 — Canvas RunPlan and independent export

Run a saved real fixture through automatic canvas preparation. Change a default
after saving: frozen parameters must not change. Verify reuse of sealed runtime
packages without expanded rescans and isolation of conflicting dependencies.
Export without a hand manifest; move the result to a path containing spaces,
disconnect application/library source paths, execute the launcher and compare
scientific outputs. Do not re-run unrelated passed science suites.

## T08 — Experimental packaging

Produce an experimental Windows package using the existing Setup integration
first. Install/reinstall/uninstall alongside production, verify old profile and
global runtime-file hashes, shortcut identity and retained user artifacts.
Report package size split between host, management runtime and optional scientific
payload. Do not claim cross-platform maturity or replace production automatically.

## Deliverables and reporting

- Code only in the host/adapter/build integration scope; no library changes.
- Module/contract docs updated with exact choices and any unavoidable deviations.
- Reproducible commands and evidence under `verification/tauri/`.
- A gate table with separate Implementation / Automated tests / Real interaction
  columns. Skipped or unavailable platforms are not passes.
- Instructions for launching the experiment and returning to the production host.
- No final claim of success without real window lifecycle and moved export proof.

Finish development in coherent groups, then run focused checks. Repeat a test only
after a relevant change/failure. Do not run the entire scientific suite for a host
stylesheet or message adapter change. Stop before production publication.
