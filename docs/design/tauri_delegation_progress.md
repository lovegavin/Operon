# Tauri delegation progress

Updated 2026-11-16. Experimental source only; no push, release, installer or
native Tauri window is claimed. Integration branch: `experimental/tauri-shell`.
Base: Operon 5.3.0, `0600b2bba146240495882b0a5275297b942c5b80`.

## Delegation and ownership

Codex owns architecture, bounded assignments, review and acceptance. DeepSeek
Harness CLI 0.2.2-rc.3 implements the assigned files using the configured
`deepseek-account` / `deepseek-flash` route. The smoke request returned the exact
JSON challenge in 2.67 seconds with exit code 0; continued sessions also returned
structured final results. CLI prompts are supplied through stdin to preserve
quotes. An invocation-only headless overlay enables the existing account and
credential services; it does not modify the desktop account configuration.

Each implementation session has its own experimental worktree. No production
source, operator library, SDK, dependency lockfile or version change was made.
The CLI file tools worked. Its shell tool encountered a Windows ACL error;
Codex ran all verification independently without changing ACLs.

| Session | Scope | Implementation | Review | Automated acceptance | Native/installed interaction |
|---|---|---|---|---|---|
| A | T01 shared contract and source baseline | Completed for T01; native crate deferred | Accepted with close-ownership corrections | Contract tests included in 44 passing tests | Not a native implementation |
| B | Browser/WebView2 adapters and App close wiring | Completed for T01; Tauri adapter deferred | Accepted after one focused correction | Host and Agent tests: 44 passed; TypeScript/Vite build passed | Existing real C# WebView2 host smoke passed |
| C | Rust backend process and window lifecycle | Pending | Pending | Not run | Not run |
| D | Native OS integration | Pending | Pending | Not run | Not run |
| E | Experimental packaging/update | Pending | Pending | Not run | Not run |
| F | Installed-window acceptance | Pending | Pending | Not run | Not run |

## Reviewed commits

- A source: `c9a1b14567f315c77f3df500f5efbe47950caafd`; integration: `04c55a45`.
- B source: `41b8419c`; integration: `d4942849`.
- Shared six-method contract: `frontend/src/host/types.ts`.
- The old C# transport has one uncorrelated close waiter. The WebView2 adapter
  coalesces repeated prepare-close requests, invalidates stale acknowledgements
  and isolates subscription closures even if removing a listener fails.
- Browser and unsupported legacy host operations reject with typed errors;
  unavailable full-exit/diagnostics/artifact IPC is not reported as success.
- The existing HTTP artifact path and tray exit are unchanged. No Quit UI was
  added in this compatibility stage.

## Verification

From the integration worktree:

```text
npm --prefix frontend test -- src/host src/agentBridge.test.ts src/agentTransport.test.ts
7 files / 44 tests passed
npm --prefix frontend run build
TypeScript and Vite passed; large-chunk advisory remains
```

The existing validated C# host executable was copied into an isolated test
folder, pointed at the new frontend and existing backend, and launched with
`--smoke-test` using a private profile/runtime configuration. Evidence confirms
frontend ready, draft flushed, backend exit=0 and host stopped. Total automated
smoke duration: 12.08 seconds (not a startup or shutdown performance benchmark).
Both pre-existing global runtime configuration hashes were unchanged.

Local evidence is under `BioPipe/verification/tauri-dsh-20261116/`: CLI receipts,
prompts and NDJSON, `frontend-tests.log`, `frontend-build.log`, `host-smoke.json`
and `host-smoke.log`. The compact portable result is
`verification/tauri/t01-acceptance.json`. Do not publish local account/config/log
files as part of a product package.

## Gates and remaining work

T01 adapter compatibility gate passes targeted automated tests, production build
and the real legacy host smoke. This is not installed Tauri acceptance and does
not replace F. No manual browser/desktop interaction is claimed in this pass.

T00 source observations remain in `verification/tauri/baseline.json`; that file is
the initial A receipt, not the current acceptance state. Node v24.14.1 and npm
11.11.0 were independently verified; frontend dependencies were installed from
the unchanged lockfile in the review worktree. Cold/warm performance baselines
remain unmeasured. Rust was not found and MSVC is unverified; no Cargo build or
native dependency lock is claimed.

Before C/D: complete native toolchain verification and baseline measurements,
then have A pin the minimal Tauri 2 crate, Cargo.lock and capabilities. C owns
process lifecycle, D owns OS integration, E owns packaging, F independently
accepts the integrated candidate. Preserve the existing scientific backend,
operator library and production branch throughout.

## Native C/D implementation and review — 2026-11-16

The earlier "Before C/D" toolchain gap is now resolved: Rust 1.100.0, MSVC and
Windows SDK produced the actual Windows Tauri binary. C and D were delegated
through DeepSeek Harness in isolated worktrees, reviewed and merged only into
experimental/tauri-shell. Root fixed the real-process and HTTP integration
issues recorded in tauri_native_acceptance.md.

Current evidence: 94 Rust tests (including real process/HTTP and opt-in Windows
keyring checks), 73 frontend tests, locked native build, frontend build, and two
final real native ready/draft-save/drain smokes all passed. Runtime configuration
hashes and the production/library boundaries were preserved. Detailed status and
remaining manual, packaging and cross-machine gates are in
`tauri_native_acceptance.md`; T05-T08 are not marked complete. This supersedes the
earlier missing-Rust/MSVC observation, not the earlier T01 compatibility evidence.
