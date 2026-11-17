# Tauri delegation progress

Updated 2026-11-16. Experimental source and RC3 test installer; no push or release.
Integration branch: `experimental/tauri-shell`. The sections below preserve the
earlier T01 observations; the current gate table and RC3 record supersede them.
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
| C | Rust backend process and window lifecycle | Integrated | Accepted for Windows experiment | 94 native tests in C/D baseline | Native ready/save/exit passed |
| D | Native OS integration | Integrated | Accepted for Windows experiment | C/D baseline and 73 frontend tests | Manual OS/canvas gates remain in F |
| E | Experimental packaging/update | Integrated via Harness, root reviewed/fixed | RC3 local lifecycle passed | 5 packaging, 9 maintenance, 2 cross-instance tests and installer SelfTest | Real installed update/reinstall/uninstall passed; self-stub retained |
| F | Installed-window acceptance | Probes/instructions implemented | Local preservation passed | Installed native smoke + profile/production hash checks | Second-machine transfer blocked before install; manual gates pending |

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

## E/F packaging review — 2026-11-16

Harness implemented E on `experimental/tauri-packaging` (`af6f3237`), integrated
as `368627a6`. Root added focused F probes and reviewed actual Setup behavior.
Harness subsequently implemented the bounded receipt-ACK correction; root found
and fixed pending C# `ValueTask` handling with a real delayed-pipe regression.
The final candidate source is `01ff3be3`. No operator library, backend, production
branch or production version was changed. No network updater/signing was enabled.

See `tauri_packaging_acceptance.md` for exact RC3 hashes, local lifecycle results,
withdrawn candidates and the retained uninstaller stub. Second-machine F now ran
through actual installation, Agent editing, portable export, reinstall and
Windows uninstall. F is **FAIL**: a long script subprocess working directory
causes WinError 267, and same-build reinstall strands imported library state in
the retained version backup, preventing Agent task reuse. The shipped acceptance
helper also needed an external physical-path identity correction; seven focused
helper tests pass. No scientific/backend/library code or production checkout was
changed to hide these failures. Do not turn native smoke or partial UI passes
into full product acceptance. Preserve completed evidence for narrow retesting.

RC4 follow-up: DSH implemented scoped installer and native activation changes; root reviewed and completed cwd/tool-runner/portable overlay integration, stable-library no-scan reuse, and final-response pipe ACK. Local checks passed, but actual remote F was FAIL: unchecked RC3 bytecode shadowed updated modules and the task TEMP was too long for alias metadata. Shortcut activation and normal exit passed. See tauri_rc5_bytecode_and_temp.md. DSH implemented bounded packaging invalidation; root reviewed it, fixed task-TEMP metadata placement and verified the actual RC5 bundled runtime. RC5 is ready for user-copy and remaining targeted acceptance; retain both RC3/RC4 failure evidence.

RC6 follow-up: RC5 actual acceptance found incomplete provider-to-application
code collection and retained cancellation cwd metadata. Root implemented both
repairs after two DSH attempts stalled without code edits; they are not credited
as contractor implementation. Generic code collection, cache identity, durable
attempt cleanup, and actual packaged-Python probes are documented in the RC6
design notes and packaging acceptance. Source-focused checks passed; actual RC6
test-machine acceptance is pending manual copy. Production and library source
remain unchanged, with no push or release.

RC7: root completed the narrowly scoped follow-up using the RC6 live evidence.
Payload preservation and reachable dependency traversal are now separate; two
collector modules changed. Focused source and actual packaged-Python checks
passed. No contractor output is claimed for this change. Manual transfer and
the original saved scientific route/export acceptance are pending; validated
RC6 cancellation cleanup is unchanged and will not be rerun.

RC8: RC7 installation succeeded, but the original route and complete export
failed in environment preparation before worker launch. The failure was a real
261-character dependency resource path, not a missing resource. Read-only probes
using each original failed staging interpreter reproduced failure with ordinary
paths and success with extended paths. Root implemented a shared stdlib-only
Python import/resource bootstrap, including cached filesystem loader metadata,
probe identity and independent export entry points. No package-specific patch
or operator edit was used. Eight subprocess boundary checks, 51 related checks,
and two real isolation/streaming checks passed; two symlink checks skipped for
Windows privileges. See `tauri_rc8_python_resource_paths.md` and the RC8 delivery
proofs. Actual RC8 test-machine acceptance subsequently passed: the original
saved route completed a new scientific run, and its complete exported bundle ran
after relocation using the delivered launcher. Both exited 0; PCA and describe
JSON were byte-identical and both runs produced PNG/PDF/SVG. The original eight
route/task file hashes and library registry/archive matched. Source environment
absence was not tested. A nonblocking Matplotlib font-cache warning was retained.
RC8 remains installed and closed with no owned test processes. Unchanged RC6
cancellation and native/installer suites were not repeated. No push or release.

RC8 supplemental acceptance (2026-11-17) also passed with the original source
installation path temporarily unavailable, host environment injection removed,
and a copied/hash-checked input outside that source root. The delivered launcher
used bundle Python, and a new non-resumed run produced byte-identical numeric
results and nonempty figures. Source root/config were restored and baseline
hashes matched. See the supplemental section in packaging acceptance for exact
scope, interpreter observation limits, run ID and evidence. No source/runtime
changes or previously passed suite reruns were required; no push/publication.
