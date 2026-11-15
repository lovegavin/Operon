# Experimental Tauri packaging acceptance (E/F)

This is an experimental Windows host acceptance, not a production release.
The backend stays at the validated 5.3.0 baseline. The operator library, frozen
parameter JSON, memory management and scientific environment isolation are not
changed by this work. A passing build is not an installed-product acceptance.

## Scope and evidence rules

E implements packaging and installation maintenance through DeepSeek Harness.
The integration owner reviews E and owns F. The production checkout, global
runtime configuration, production shortcuts and uninstall registration must stay
unchanged. Tests use new explicitly named experimental directories and synthetic
data. Preserve all prior acceptance evidence.

Do not repeat the unchanged scientific suites. Reuse their recorded 5.3.0
evidence. Recheck native lifecycle only where the installer maintenance hook
changes it. Every result below must identify the actual built executable hash.

| Gate | Required evidence |
|---|---|
| Package | Strict experimental identity, validated input package, exact source/lock hashes, per-component size, Setup SHA256 |
| Boundaries | Foreign root/payload rejected; traversal and reparse paths rejected; unknown files and profiles retained |
| Maintenance | Authentication, bounded framing, request replay, startup exclusion, exact process identity, cancelled/failed drain leaves current version intact |
| Install | Interactive double-click on a second machine; bundled management Python; no preinstalled developer Rust/Node/Python required |
| Update | Stage candidate before exit; actual open workbench saves drafts and exits; new shortcut uses new version and same experimental profile |
| Lifecycle | Shortcut reopen, hide/show, explicit Quit; owned management tree exits; unrelated process survives |
| Desktop | Real selection -> agent read -> batch edit -> single undo; node drag/multi-select; language/theme persist; actual original-result links |
| Export | Existing RunPlan route exports through the Tauri UI; relocated standalone output runs without the source environment |
| Uninstall | Only experimental registration/shortcuts removed; profile and unknown files retained; no force-kill of scientific workers |
| Preservation | Before/after production file hashes and uninstall entries match |

An automated `--smoke-test` opens the real React workbench and exercises its ready,
draft-save and native shutdown handshake. It is not a substitute for double-click,
manual menu, picker, canvas or external viewer evidence. Do not label pending
interactions as passed because an API test passed. Server browsing requires an
available configured server; no paid server is started for this packaging task.

## Local probes

Before installation, run `scripts/acceptance/tauri_preservation.py --baseline
<new-baseline.json>`. After uninstall, use `--compare --baseline <same-file>
--report <comparison.json>`. The probe requires Windows registry access and fails
on inaccessible state; do not substitute an empty baseline.

For each installed native smoke sample, run
`scripts/acceptance/tauri_installed_smoke.py --host <installed-host.exe> --config
<installed-host.json> --evidence <new-directory>`. A timeout is a failure and keeps
the test window available for diagnosis. It never terminates processes by name.

## RC3 status — 2026-11-16

Candidate: `Operon Studio Experimental 0.1.0 RC3`, management payload 5.3.0.
Source: `01ff3be3` on `experimental/tauri-shell` (later commits only update this
acceptance record). Native host code is unchanged from `8b0d3839`; RC3 corrects
the installer-side wait on pending pipe `ValueTask` operations.

Setup SHA256:
`8f6ec6c7bf10e1fca639defd2474960c66d8aa6a8880cb9f3b373c1c85ba619d`.
Test ZIP SHA256:
`9f52299594b4c902c7b1fd26fe12b8528f34fc2d46f3821c1718bc774e792cb7`.
Local delivery directory: `BioPipe/dist/experimental/tauri-0.1.0-rc3/`.
Setup is 387,376,028 bytes; the native executable is 16,251,904 bytes. The package
reuses the validated management payload; it does not include all scientific
execution environments. Detailed components/locks/file identities are supplied.

| Gate | Evidence / result |
|---|---|
| E implementation | DeepSeek Harness CLI implementation/review plus root corrections; only experimental branches |
| Python packaging checks | 5 passed; exact baseline file set/hashes, traversal/reparse and archive contract |
| Native maintenance | 9 focused tests passed, including actual Windows pipe transport with delayed bytewise read and matching/wrong/missing ACK; 2 cross-instance maintenance integration tests passed earlier |
| Installer | Build and SelfTest passed; includes real delayed async pipe read/write, foreign identity, path, rollback snapshot and executable removal barrier checks |
| Installed native window | Initial real WebView ready/save/exit: 8.867 s total; final RC3 reopen: 6.250 s total; exit 0. These are whole smoke durations, not isolated startup benchmarks |
| Running-host upgrade | Actual RC2 -> RC3 Setup: 46.696 s; owned old host exited; new version selected and profile retained |
| Authenticated reinstall | Wrong but well-formed token refused; host/current version preserved. Valid request completed in 57.396 s; host and Setup exit 0; same profile/sentinel retained; unrelated Python survived |
| Installed uninstaller | Exit 0 via installed standalone uninstaller; 340 profile file hashes unchanged; unknown version file retained; experimental shortcut, registration and current pointer removed |
| Production preservation | Before/after global runtime configuration, production shortcuts and uninstall entries match. Production dirty files preserved; no library source changes |
| Independent-machine UI | BLOCKED BEFORE INSTALLATION: remote chat/desktop available, candidate transfer too slow; KMFU/cable not detected on test machine. No double-click, Agent or export pass claimed |

RC1/RC2 are withdrawn diagnostic candidates. The real updater check caught two
issues that source-only tests did not: closing the Rust pipe before its peer
consumed the reply, and synchronously calling `GetResult` on a pending C#
`ValueTask`. RC3 uses a bounded receipt ACK and a Task bridge for pending pipe I/O.

The local uninstaller processed three retained builds in approximately 236 s.
The test parent was stopped before its artificial 240-second deadline could kill
the real uninstaller; that uninstaller continued untouched and wrote success.
It intentionally retained the currently running 71,710,704-byte uninstaller stub,
private profile, generated/unknown files. Automatic self-stub removal remains a
packaging polish item; do not claim a zero-residue uninstall or production readiness.

Evidence: `BioPipe/verification/tauri-packaging-20261116/` contains package/build
logs, `maintenance-ack.log`, `pipe-fix-selftest.json`, `upgrade-rc2-to-rc3*.json`,
`rc3-live/live-update-summary.json`, `installed-rc3-reopen/smoke-result.json`,
`uninstall-rc3-summary.json`, profile hash inventories and `f-preservation-after.json`.
DeepSeek requests/results are in `BioPipe/verification/tauri-dsh-20261116/`.
Credentials/temporary transfer tokens are excluded from the deliverable.

Still pending F: actual second-machine installer/shortcut, Agent six stages,
canvas drag/multi-select/copy/undo, script/route import, settings persistence,
original result links, native export and relocated Python/R/tool execution.
Live server browsing, Linux/macOS, cold/warm performance comparison and online
signed updates remain untested or out of scope. No publication or production
promotion occurred. The ZIP includes the pre-acceptance checklist; this document
is the later evidence record and supersedes its pending status.
