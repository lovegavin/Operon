# Tauri implementation: coordinated coding sessions

Status: implementation assignments, not a completed Tauri port. Start from the
validated canvas/portable-export integration commit, on an experimental branch.
Do not promote it to the production branch merely because it builds.

## Shared decisions (all sessions)

Read `tauri_module_inventory.md`, `tauri_implementation_contract.md` and
`tauri_coding_instructions.md` first. Their T00–T08 acceptance gates apply here.

Keep React/TypeScript/Vite and the existing graph UI, Python Application services,
RunPlan compiler, resource-pool scheduler, immutable environment store, independent
parameters, exports, CLI, MCP and HTTP APIs. Rust owns the desktop lifecycle and
OS integration only. No second scheduler/compiler/environment installer. No
library edits, silent protocol migrations, production version changes or release.

Use Tauri 2, Rust 2021, Tokio, serde, tracing and keyring. Session A pins verified
versions, the Rust toolchain and Cargo.lock. Other sessions may request dependency
changes from A; they must not independently upgrade shared dependencies. Preserve
the existing frontend lockfile and UI dependency versions during the host port.

Each session gets its own Git worktree/branch from the SAME committed baseline.
Do not share a dirty working directory. Worktree locations belong under the
project's `worktrees/` directory. Do not touch unrelated current worktrees.

## Ownership and handoff order

| Session | Branch suffix | Owns | Depends on |
|---|---|---|---|
| A: integration/contracts | `integration` | contract docs, shared types, build manifests, integration branch | T00 baseline |
| B: frontend host adapter | `frontend-host` | `frontend/src/host/`, narrow App bridge wiring, host tests | A contract v1 |
| C: Rust lifecycle | `lifecycle` | `desktop-tauri/src/{backend,lifecycle,instance,logging}.rs` | A crate skeleton/contracts |
| D: OS integration | `os-services` | `desktop-tauri/src/{dialogs,artifacts,credentials,navigation}.rs` | A command DTOs |
| E: packaging/update | `packaging` | experimental packaging scripts, capability/config proposals, installer integration tests | C lifecycle baseline, D integration |
| F: acceptance | `acceptance` | `scripts/acceptance/tauri_*`, `tests/tauri/`, evidence checklist | B–E integrated candidate |

Use branch prefix `experimental/tauri-`. A alone owns Cargo.toml/Cargo.lock,
tauri.conf.json, capabilities, the top-level Rust module declarations, shared
TypeScript DTOs, package scripts, and final merge decisions. D/E propose changes
to those files in their handoff instead of racing to edit them. B alone changes
App.tsx; other sessions request a small typed hook through A.

Stage 1: A establishes the baseline, shared contract and minimal crate skeleton.
Stage 2: B/C/D can work concurrently; F writes acceptance fixtures and negative
tests without pretending UI tests have run. Stage 3: A integrates B/C/D; E builds
the experimental installer. Stage 4: F performs real installed-window acceptance;
owners fix only reported failures. A repeats only affected integration gates.

## Session A — integration and protocol owner

Goal: establish a single host contract and keep parallel changes compatible.

Deliver a committed baseline receipt with source hash, exact versions, startup
arguments, profile/config resolution, authentication, process ownership and
shutdown handshake. Define the transport-neutral `DesktopHost` types and error
codes, request IDs, readiness response, artifact/viewer requests and close events.
Use the existing implementation contract's API rather than designing another one.

Create the minimal Tauri skeleton, dependency lockfile and capability document.
Publish the contract commit hash to B–F before their implementation. Review all
requests to change a shared API; breaking changes require an explicit contract
revision and updates to both adapters/tests. Integrate in order, never by copying
whole modified trees. Maintain an implementation/automated/interaction gate table.

Acceptance: all public messages are typed; renderer privileges are minimal;
production C# host/browser still work; no backend/library/protocol drift. Provide
the exact experimental launch/install/uninstall commands and rollback procedure.

## Session B — existing frontend and host abstraction

Goal: run the same UI in browser, WebView2 and Tauri.

Implement browser, current WebView2 and Tauri adapters behind `DesktopHost`.
Remove direct host-global access from App only where covered by the adapter.
Preserve normal HTTP APIs, selection, batch edit/undo, clipboard behavior,
multi-document state, settings/config, local and remote file browsing and result
links. React must not spawn interpreters, resolve environments or inspect process
trees. Do not redesign the graph UI or move scientific code into JavaScript.

Acceptance: correlated concurrent requests, listener cleanup, repeated close,
failed draft save and cancelled file dialog have targeted tests. Existing browser
and WebView2 builds pass. Submit a narrow diff and screenshots only for changed
interaction; report Tauri interactions not yet tested as pending.

## Session C — backend process and window lifecycle

Goal: own the lightweight management service safely, not scientific workers.

Implement the prescribed lifecycle state machine, per-install instance ownership,
isolated backend environment, readiness/authentication, bounded startup diagnostics
and graceful drain. A window's death must not terminate a shared server or other
installation. Use process identity/creation-time and installation ownership, never
process name alone. Handle occupied ports, stale receipts and startup failure.
Respect existing pool task survival and maintenance/upgrade semantics.
Keep hide-to-tray distinct from full exit. Provide an accessible in-app Quit
command as well as the tray action; the installer cannot treat `WM_CLOSE` as a
proof of exit. Session E consumes C's installation-scoped maintenance handshake.

Acceptance: real child-process tests for normal/repeated exit, delayed readiness,
backend crash, close during preparation, shared-pool work continuing after UI
disconnect and an unrelated Python process surviving. Failed shutdown stays a
failed gate. No broad process kill or global runtime/profile write.

## Session D — native dialogs, artifacts and credentials

Goal: expose the smallest safe OS bridge the existing product needs.

Implement open/save/folder dialogs, approved external-viewer invocation, opening
committed artifacts, OS credential storage and external URL navigation. Use
opaque artifact IDs resolved by the service, not arbitrary renderer paths. Keep
viewer preference config in the existing profile. Credentials stay outside
frontend storage, URLs and logs. No generic shell command or unrestricted file
read/write IPC. Untrusted results must not load inside the privileged main view.

Acceptance: cancelled dialogs, absent viewers, unsupported file formats, invalid
artifact IDs, path traversal and untrusted navigation are tested. PNG/PDF/SVG and
one installed external viewer are tested in the installed candidate by F.

## Session E — experimental installer and updates

Goal: package a reproducible alternative shell beside production.

Reuse the validated lightweight management runtime and current package contracts.
Do not bundle all scientific environments into the app or inspect dependencies on
startup. Keep runtime/library packages independently reusable. Preserve old profile
data, global runtime config, production shortcut and uninstall registration.
Use a distinct experimental app identifier, install directory and profile by
default. Integrate with existing Setup ownership/drain rules before considering
Tauri's updater as a separate future change.

Acceptance: clean install, reinstall, shortcut reopen, update with running owned
backend, unrelated process preservation and Windows uninstall. Produce checksums,
component size breakdown and exact source/lockfile identities. Do not sign or
publish with production credentials. A approves all shared config changes.

## Session F — independent end-to-end acceptance

Goal: test the installed product, not substitute dev-server scripts for UI proof.

Prepare synthetic, non-private fixtures. Actually double-click the experimental
installer and shortcut. Cover graph node drag, multi-select, copy/paste/undo,
script import, route registration, language/theme settings, server-file browsing,
Agent six stages and original PNG/PDF/SVG links. Run the SAME canvas through
RunPlan, export without a manual manifest, move it to a path with spaces and run
using packaged Python/R/tools with source environments unavailable. Compare
scientific outputs, frozen parameters, memory limits and isolation evidence.

Do not repeat unchanged backend scientific suites. Record untested platforms and
viewers explicitly. Keep installation, startup, exit and process-ownership logs;
hash the preserved baseline before/after. Restore configuration and retain reports.
Return failures to the owning session with minimal reproducible steps. Do not
silently patch product code from the acceptance branch or publish a release.

## Standard prompt and output for each coding session

Assign a session using this template, filling only the bracketed fields:

```text
Implement session [A/B/C/D/E/F] in docs/design/tauri_session_assignments.md.
Baseline commit: [validated commit]. Shared contract commit: [A's commit].
Create branch experimental/tauri-[suffix] in an isolated project worktree.
Read AGENTS.md and the three linked Tauri design documents first.
Goal and owned files are exactly the session assignment. Preserve existing
backend, library, memory management, frozen parameters and environment isolation.
Do not edit another session's files or shared manifests without A's approval.
Implement the coherent scope, then run focused checks once; repeat only changed
or failing checks. Do not publish or change the production version.
Return commit IDs, changed paths, contract assumptions, implementation vs actual
test evidence, commands, failures and the next dependent handoff.
```

A must substitute real hashes before distributing prompts. A plan without a
contract commit is not authorization for each model to invent its own backend.
