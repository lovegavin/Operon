# Experimental Tauri C/D acceptance — 2026-11-16

Integration branch: `experimental/tauri-shell`. Production remains at Operon
5.3.0, commit `0600b2bba146240495882b0a5275297b942c5b80`. No release, installer,
operator-library change or backend-engine change is included.

## Delegation and review

DeepSeek Harness CLI 0.2.2-rc.3 was used through the existing DeepSeek account,
with `deepseek-flash`. C and D worked in separate experimental Git worktrees.
Their completion reports were inputs to review, not test evidence.

- C: backend ownership, readiness authentication, lifecycle state machine,
  single-profile lock, bounded/redacted logs and real-process fixtures.
- D: native dialogs, artifact verification/cache/opening, navigation policy and
  installation-namespaced Windows credential storage.
- Integration: shared native scaffold, IPC capability scope, existing frontend
  adapter, native menu/tray and real ready/draft-flush/drain wiring.

Root review and real tests corrected the following before acceptance:

1. Preserve nonzero exit status across retries; verify the whole owned job is
   empty, rather than equating parent exit with tree drain.
2. Create Python suspended, assign its Windows Job, then resume. Authenticate
   venv redirector children using exact Job membership and real process IDs.
3. Preserve Windows account-name variables in the otherwise explicit environment
   so Python `getpass` does not fall through to the unavailable `pwd` module.
4. Use `x-studio-token` for native artifact requests. Agent bearer tokens have
   different semantics in the existing backend.
5. Fix the frontend unlisten callback type and native result routing. Unsupported
   associations can still save via HTTP; integrity/transport failures cannot
   silently bypass verification.
6. Use an embedded diagnostic page, not an unsupported `data:` URL. Make profile
   marker creation exclusive. Keep one deadline across signal/tree/log draining.

The composition contractor was stopped after writing its files while it was
continuing repetitive source inspection. Root completed compilation, review,
repairs and verification; no unfinished contractor is left running.

## Toolchain and checks

Rust 1.100.0, Tauri 2.12.5, tauri-build 2.7.4; MSVC C++ Build Tools and Windows
SDK installed and proven by a real link. Rustfmt and Clippy are available.
Rust/Cargo homes are project-local; no permanent PATH change was made. Microsoft
Build Tools also installs normal shared Windows components. `Cargo.lock` is
committed; the product and frontend dependency versions are unchanged.

| Check | Result | Scope |
|---|---|---|
| Rust unit tests | 81 passed | Contracts, locks, lifecycle, bounds, navigation, cache and credentials |
| Real HTTP artifact test | 1 passed | Studio header, metadata/body, hash verification and cache reuse |
| Real Python process tests | 12 passed | Explicit configured venv; crash, PID/identity/version mismatch, timeout, retry, breakaway and unrelated-process protection |
| Windows credential round trip | Passed within the 81 tests | Explicit opt-in; unique test entry written/read/deleted |
| Frontend targeted tests | 73 passed / 11 files | Browser/WebView2/Tauri adapter, Agent transport, plans and artifact routing |
| TypeScript/Vite build | Passed | Existing large-chunk advisory remains |
| Cargo locked native build / format | Passed | Windows x64 development executable, not Setup |

No full science suite was repeated. Process and keyring test opt-ins were set;
these were not their early-return paths. No claim is made that every scientific
operator ran under the experimental host.

## Actual native launches

The final executable loaded the existing React workbench through the owned Python
service in a fresh experimental profile, then reopened the same profile. Both
performed the real frontend ready and draft-save ACK flow and exited with code 0.
The host did not synthesize the ACK or inject successful frontend state.

| Launch | Whole automated launch/save/exit | Draft-save ACK to confirmed tree exit |
|---|---:|---:|
| Fresh experimental profile | 15.22 s | 0.321 s |
| Reopen same profile | 9.58 s | 0.412 s |

These are two smoke samples, not a statistical performance comparison or pure
startup measurements. The Python management service still starts; this port does
not claim to remove its initialization cost.

A normal non-smoke launch also exposed the real workbench accessibility tree,
including the saved demo graph and operator catalog. However, a foreground
fullscreen application covered the screenshot and Windows refused activation.
No clicks were sent to that unrelated application. The diagnostic normal launch
was subsequently terminated by its verified test-only process identity; that is
not counted as a graceful-close sample.

Both previously existing global runtime configuration checks remained unchanged.
Production HEAD and its existing dirty-file list were preserved. The integration
diff contains no `library/`, SDK, Python product, legacy desktop-host or frontend
lockfile changes. Final test-owned host processes have exited.

## Remaining gates

- Manual native menu/tray hide/show/Quit and picker selection/cancellation.
- Actual OS viewer launching from a committed result, OS association failures,
  and the legacy figure-browser handoff; the native cache/HTTP boundaries are
  tested, but those user interactions are not claimed passed.
- Native-host Agent six-stage interaction, full canvas/RunPlan/export parity,
  performance comparison, installation/update/uninstall and a second machine.
- Same-profile second launch is rejected safely, not forwarded to activate the
  existing window. Linux/macOS native hosts are unsupported in this phase.

Thus C/D's implemented modules and targeted automated/native smoke checks pass;
T05–T08 and full product promotion remain incomplete. Continue E/F on the
experimental branch, not the production branch.

Portable summary: `verification/tauri/native-acceptance.json`. Detailed local
logs/receipts: project `verification/tauri-native-20261116/`. Harness prompts and
CLI receipts remain in `verification/tauri-dsh-20261116/`; account configuration
and raw local logs must not be included in a product package.
