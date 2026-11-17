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
| Independent-machine UI | FAIL overall: actual installation, Agent editing, original figures, portable run and uninstall completed; canvas script long-cwd and post-reinstall task reuse failed. Full results below |

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

F was initially pending at package handoff; the second-machine continuation
below supersedes that status and separates passed, failed and unverified checks.
Live server browsing, Linux/macOS, cold/warm performance comparison and online
signed updates remain untested or out of scope. No publication or production
promotion occurred. The ZIP includes the pre-acceptance checklist; this document
is the later evidence record and supersedes its pending status.

## Second-machine F continuation — 2026-11-16

The user transferred the immutable RC3 ZIP to `D:/BioPipeTests/tauri010rc3`.
The test machine verified the ZIP and Setup hashes above, installed through the
actual Setup window into a path containing spaces, and opened the actual Start
Menu shortcut. Installation was observed complete at approximately 49 seconds.
The host's private profile and bundled management interpreter were confirmed.
This is installation evidence only; it does not imply the remaining gates pass.

Two acceptance prerequisites were exposed:

1. The shipped Agent verifier used lexical `Path.is_relative_to` to check the
   backend source. Tauri passes canonical Windows `\\?\` paths, so the verifier
   rejected the correct installed `scripts/desktop_server.py`. A separate verifier
   copy now checks actual filesystem identity with `samefile`, and requires the
   exact expected entry file. Seven focused tests pass, including real Windows
   extended paths, missing files and rejection of another installation. The
   original installed script and package are unchanged. Corrected verifier SHA256:
   `710a6575d2f01bafa790cc892cb904d3235113039b7ced906b1d1c849995efb1`.
2. The validated 5.3.0 input is an application-only payload: neither it nor RC3
   contains a default operator library. A clean profile correctly has no PCA.
   The initial checklist omitted the independent library prerequisite. The F
   continuation uses the existing, unmodified `operon-library-v0.1.0` release in
   the isolated experimental installation and profile only (6,539,983 bytes; SHA256
   `621d7dc0476cb04d4a13cb3d70ca3a7bf6c324fb92d98ff9aecd354ff668eab9`).
   Import through the normal library UI is part of acceptance. Imported library
   files are runtime-generated installation state, outside the RC3 ownership
   manifest; they must be retained/reported during uninstall. No library source
   or production profile is modified, and no all-operator dependency install is
   requested.

Retain the original failures and the corrected verifier result separately. Do
not describe this as the unmodified shipped verifier passing, or a factory PCA
library being present.

The second-machine continuation confirmed the actual library import (1,174
operators/Readers), then passed corrected-verifier `backend`, `open`, `capture`,
`apply` and `undo`. The real PCA selection was clicked in the window; the visible
batch changed the component count from 2 to 3 and added a diagnostic branch;
one undo restored it. Post-reinstall `retry` failed, as detailed below. PNG, PDF
and SVG original links were actually clicked from the results view and rendered
in the browser. The independent script route's export was submitted from the
actual workbench. Its relocated bundle ran successfully in 56.65 seconds (exit 0):
the generator CSV contains 1 through 5, and both scaling branches contain 2, 4,
6, 8, 10. This validates the portable execution sample; it does not establish
canvas/portable parity because the canvas run failed as described below.

Interactive reinstall was observed complete at approximately 48 seconds. The
old experimental host exited with code 0, its management service logged normal
shutdown, and the installation ID was retained. Forty sampled settings, workflow
and result files retained their hashes; English/light settings persisted.
However, post-reinstall Agent `retry` failed because the pinned plugin versions
were unavailable. Successful Setup completion is therefore not successful
functional upgrade acceptance.

Windows Installed Apps uninstalled this experimental instance; removal was
observed complete at approximately 45 seconds. The experimental shortcut and
registration were removed; no owned host or management Python remained. Forty
of forty sampled profile files retained their hashes, and production runtime,
shortcut and uninstall-registration baselines matched. The uninstaller stub,
profile and replaced-version directory (including the imported library) remain.
No additional cleanup, production changes or publication occurred.

The connected route was exported/reimported through the UI and registered.
Selecting all three nodes, copy/paste and single undo preserved the two internal
edges (3/2 -> 6/4 -> 3/2). Node dragging did not yield a confirmed displacement;
two-node Ctrl-selection, raw `.py` drag/drop, live server browsing and R/C/C++
portable execution were not verified in this pass. The portable run used its own
launcher with environment overrides cleared and a restricted PATH; source
environments were not physically removed, so the stronger unavailable-source
environment test is not claimed. Screenshots remain in the test-machine chat.

**Final second-machine F verdict: FAIL.** The two product failures below prevent
promotion. Completed checks are retained; do not rerun them wholesale after a
narrow correction. Test-machine report: `tauri010rc3/acceptance/WINDOWS-TAURI-RC3-F.md`.
Evidence ZIP: `Operon-Tauri-0.1.0-RC3-F-evidence.zip` (74,218 bytes, 32 entries), SHA256
`74024f90b45a66ad5015b3a77b246753dd23c822ba77a47321889e2d290a8c99`.
The evidence ZIP was returned to the root machine, SHA256/CRC verified and
extracted under `BioPipe/verification/tauri-packaging-20261116/remote-f-rc3/`.

### F failure: script child working directory exceeds the Windows limit

The same three-node script route fails in Studio with `NotADirectoryError:
[WinError 267]` inside `operon.script_operators.command` -> `owned_process` ->
`subprocess.Popen` / `CreateProcess`. The attempt's `outputs/scripts/<id>` working
directory has 264 characters. A test-machine read-only child probe reproduces
the error for that existing directory; a short evidence-directory control works.
An independent local probe likewise succeeds at 80 characters but fails at 270
characters, including a 274-character extended-length (`\\?\`) representation
whose `is_dir()` is true. Merely adding the extended path prefix is insufficient.

The installed RC3 and scientific backend have not been patched to conceal this
failure. F cannot be marked fully passed. A future correction must give each
attempt a bounded, owned subprocess working directory (or a safely managed short
alias), retain the script's relative-file semantics and recovery/cleanup identity,
and avoid process-global `chdir` in concurrent execution. Validate the original
long installation/profile layout after that correction; moving the test to a
short root alone is not a fix. Local probe evidence:
`BioPipe/verification/tauri-packaging-20261116/windows-cwd-probe.json`.

### F failure: same-build reinstall disconnects imported library state

The imported library was found under the retained
`.staging-replaced-tauri-0.1.0-rc3-<id>/library` directory after reinstall. The
new process could not resolve the original task's plugin lock, and `retry` failed.
No library reimport or repinning was used to disguise this failure.

The source explains the observed layout: `installation.library_root` selects
`versions/<build>/library`, while `VerifyInstalledVersion` treats files outside
the immutable manifest (except host configuration and bytecode caches) as a
damaged installation. Repair replaces the version directory; cleanup retains
unknown library files in the backup but does not reconnect them. The fix must
separate mutable imported-library state from immutable code ownership and bind
the active version to it transactionally, preserving pinned providers and
rollback. Blind copying of all unknown files or repinning saved tasks is not an
acceptable substitute. Operator implementations themselves need not change.

### Known native limitation observed

Closing the main window keeps the management process alive. A second shortcut
launch reports `activation IPC is not implemented` instead of showing that
window. This was already listed in the C/D remaining gates. It must not be
conflated with the separate native tray Show/Quit interaction. The remote tools
could not access that tray menu, so it remains BLOCKED rather than passed.

## RC4 follow-up (2026-11-16)

Implemented in experimental/tauri-shell only: shared process cwd adapter (including ToolRunner and portable closure), installation-scoped mutable library binding with staged one-time migration, and authenticated existing-instance Show. Root review added final Show-response acknowledgements and a no-content-scan fast path for already-bound libraries. Production and library source are unchanged.

Targeted local evidence: 29 Python tests, 26 Rust tests, 17 installer self-test checks passed; the actual packaged Setup self-test passed too. No full unchanged suite was repeated. Native release build and embedded ZIP/overlay hashes verified.

Candidate: `dist/experimental/tauri-0.1.0-rc4/Operon-Tauri-0.1.0-rc4-test.zip`, SHA256 `345431a909d6c94f2869d3bef031b930b8de16bd18b97149f34b0a02caa8b6d1` (392702041 bytes). Setup SHA256 `c490817bc627896d01de4d3ce3443fa79dde15ec99e5f6c227623a836e213d62` (387463510 bytes).

Remote RC4 F is FAIL. Actual double-click upgrade retained 8/8 route/task files and the library registry/archive hashes, but live catalog was empty because unchecked RC3 bytecode shadowed the source overlay. The long-path Studio worker separately failed because its task TEMP was too long for alias metadata. Actual shortcut activation from hidden/minimized states passed with unchanged host/backend identities; normal exit took about 0.8 seconds with both exit codes zero. Export, cancellation, same-build reinstall and uninstall were deferred. Evidence ZIP on the test machine has SHA256 `a984bfd04c95585f5cf8eb2aebcc0ba226da4c55acae21d7a87f36a49c15f82f`.

After explicit user authorization, RC4 was transferred using a verified byte-copy delta. The receiver reconstructed the exact original ZIP and Setup hashes. All temporary localhost.run tunnels and the HTTP server were closed; closure is recorded in `verification/tauri-rc4-delivery/transfer-receipt.json` under the main project artifact root.

## RC5 targeted follow-up (2026-11-16)

Packaging now removes only bytecode for explicitly overlaid modules and records removed cache hashes. Process alias metadata uses OS-known LocalAppData rather than task TEMP. Native host, installer source, production checkout and library source are unchanged. See `tauri_rc5_bytecode_and_temp.md`.

Changed-path checks: 16 passed, 2 skipped (symlink creation unavailable). An actual RC5 Setup extraction, using its bundled Python, resolved the stable library and successfully ran owned script and external-tool processes with a 307-character physical cwd and the same long TEMP. No unchanged full suite was repeated.

RC5 ZIP: `dist/experimental/tauri-0.1.0-rc5/Operon-Tauri-0.1.0-rc5-test.zip`, 392661768 bytes, SHA256 `5ea84e863d79c640a3a070d42ea4e9908c656a02d5cf6031706da035e660559c`. Setup: 387425275 bytes, SHA256 `20e32dd2b5477722e9b93d2e9ee692df64959e484ca864d27698047ac9d64e3e`. The user copied RC5 directly; no RC5 third-party tunnel is open. No formal release/push.

### RC5 actual desktop outcome

Overall FAIL. Actual double-click upgrade and same-package reinstall passed; live catalog returned 1066 operators and 108 Readers, original task reuse succeeded, and the library archive/registry plus eight saved route/task samples retained their hashes. Reinstall explicitly reused the bound library without content scanning. The 260-character Studio script route and complete exported bundle relocated to a directory with spaces both ran successfully. Both scale branches used factor=2; generator output was 1..5. Successful child TEMP was not separately sampled. Cancellation stopped the worker and script, and both normal shutdowns left no owned host/Python processes; numeric host exit codes were not independently captured.

A fresh calculation of the original pinned CSV/PCA route failed: CsvReader imported `src.core.numeric`, which exists in the installed application but is absent from the generated canvas execution code closure. Task reuse is therefore PASS while fresh execution is FAIL. Separately, cancellation retained a cwd junction and owner journal in `prepared` state after restart; process cleanup passed but metadata recovery is incomplete. No installed code or library was patched to conceal either finding.

Remote evidence ZIP SHA256: `275c25ef24ca986898353e7abfbf295fc1fd56e29de0f55ad028662bc02ec19e`. Root-side summary and diagnostic excerpts are under `BioPipe/verification/tauri-rc5-delivery/remote-acceptance-status.md` and `remote-diagnostics.md`; the complete evidence ZIP remains on the test machine. Unchanged shortcut, Agent, chart, YAML and uninstall suites reused prior evidence. RC5 remains installed and closed; no publication.

## RC6 targeted repairs (2026-11-16)

The provider/application dependency collector now discovers recursive local code
without importing operators, and the discovered closure digest participates in
the canvas RunPlan identity. Canvas and export use the same inventory. Frozen
provider pins and parameter JSON remain unchanged; incomplete older code caches
are not reused by new preparations. See `tauri_rc6_code_closure.md` for supported
static imports and explicit dynamic-resource limits.

Each new Windows attempt also owns durable process-cwd metadata. The outer
executor cleans it only after supervisor containment proof, including forced
worker cancellation. Unknown stop/fence failures preserve metadata and report
recovery_required. Historical unscoped journals are retained. See
`tauri_rc6_process_recovery.md`.

Focused source evidence: 38 unique checks passed, four skipped (three symlink
privilege cases and the opt-in complete canvas environment fixture). The actual
RC6 Setup was extracted and its bundled Python 3.11.15 executed an unchanged
CsvReader from a relocated code closure, an arbitrary recursive helper fixture,
and a forced nested-worker cancellation at a 336-character cwd. Cleanup reported
cleaned with input data preserved. Ten source overlays match the current source
and contain no stale overlaid bytecode. Native host/frontend/installer behavior
and operator-library source were not modified or retested in full.

Evidence lives in `BioPipe/verification/tauri-rc6-delivery/`. The user will copy
the candidate manually. Actual RC6 double-click upgrade, fresh saved CSV/PCA
canvas run plus relocated export, and Studio cancellation remain pending. No
publication or production update is authorized by these local checks alone.

### RC6 actual test-machine outcome

Overall FAIL. Interactive original-root upgrade completed with the original
profile, private RC6 Python, 1174 live catalog entries and matching library plus
eight route/task hashes. The installer was already open when observed, so the
test report does not independently attest the launch gesture.

Fresh saved CSV/PCA execution and portable export both fail during preparation:
`Missing local dependency operon_plots.steps._pdbfixer.pdbfixer imported by operon_plots/steps/_pdbfixer/__init__.py`.
That unused provider subdirectory contains an initializer and bytecode but no
pdbfixer.py. Whole-namespace AST traversal is overbroad: preserve payload files,
but traverse imports from selected reachable entry points. This is a follow-up
diagnosis, not a tested fix. Relocated scientific export remains blocked.

Actual active long-path cancellation PASSED: worker and child exited, scoped
cleanup returned cleaned/tree_exited with no errors, the junction and journal
were removed and CSV values 1..5 retained. Historical RC5 journals were preserved.
Normal shutdown left no owned processes; RC6 remains installed and closed.
Unchanged suites were not rerun. Source/library/production boundaries maintained.

Local inspected summary: `BioPipe/verification/tauri-rc6-delivery/remote-acceptance-status.md`.
Remote 16-entry evidence ZIP SHA256:
`fb92b79ace398d44c27a5d5f97e52b2b7eb3dae65e34b8472c1863cd4581e7c7`.
No publication. Frozen RC6 candidate remains unchanged.

## RC7 selected-dependency follow-up

Only the two code collector modules change relative to RC6. Retained provider
payload and traversal entry points are separate: selected implementation files
plus kernel files seed the traversal, including already-copied imports and their
initializers. Unused resources and optional code remain in the payload without
being treated as dependency roots. Required reachable missing imports still
fail closed; no named-module exceptions. See `tauri_rc7_reachable_dependencies.md`.

Focused checks: 20 passed, two skipped (symlink privilege and the opt-in private
environment full-canvas fixture). Actual extracted RC7 bundled Python 3.11.15
passed relocated CSV reading, selected-provider inventory/execution, unused
resource retention and selected missing-import refusal. Original pins remained
unchanged. Source overlay hashes match and stale overlay bytecode is absent.
RC6-to-RC7 package comparison confirms cancellation cleanup is unchanged; it was
not retested. No full native/installer/Agent suite was repeated.

Actual test-machine fresh saved CSV/PCA run and relocated complete scientific
export remain pending user manual copy of RC7. The user chose manual transfer;
no third-party tunnel is authorized or opened for this candidate. Frozen RC6
failure evidence remains intact. No production/library changes or publication.

### RC7 actual test-machine outcome

Overall FAIL. Actual double-click upgrade, original shortcut startup and baseline
preservation passed. Fresh saved CSV/PCA execution and complete export each fail
before scientific execution with environment_unverified. The old unrelated
provider error no longer appears, but successful new-closure execution remains
unverified. Both staging probes fail to read jsonschema_specifications'
draft201909/vocabularies/applicator from a 261-character unprefixed Windows path.
Both files exist and have identical 1860-byte content. This supports a long-path
resource lookup investigation; no shortened-path causal rerun or candidate patch
was performed. Complete export and relocated numeric comparison are blocked.

Studio and the installer were normally closed; final owned process/window
inventory is empty. Cancellation cleanup and unchanged suites were not rerun.
RC7 remains installed with its profile/evidence intact. Production and library
source are unchanged. No publication. See the inspected local record at
`BioPipe/verification/tauri-rc7-delivery/remote-acceptance-status.md`.
Final remote evidence ZIP SHA256:
`3696336ad9ed1cabe1f916b29337f811c9fad8243f0637d2fe12ca872729220c`.

## RC8 targeted test-machine acceptance — 2026-11-16

PASS for the requested two scientific paths. Candidate ZIP SHA256:
`25cb6bbd5e3eaaf08338a5856003b3d83d19c32d5ed24c9bb5f7208dd12740c9`.
Setup SHA256:
`8183c54c5ddd54189ab410b97d72e7e97f4a18e10f7feac41c664ea2d3c5247b`.

Actual double-click upgrade preserved the experimental profile and library.
The saved route `route_4e4b38d40199` v2 generated a new Studio run
`run-55b6f95062244bed94895958986b5f73`, exit 0. The environment preparation
crossed RC7's failing resource path and the new closure included the application
numeric module. PCA, describe and scatter completed.

Studio built one complete independent export. After moving the whole bundle to
a different directory with spaces, its delivered `run.cmd` completed new run
`run-1305a699a66949b08b37a50ed97859b3`, exit 0, reused=false. PCA and describe JSON
were byte-identical to Studio (zero tolerance); both runs produced nonempty PNG,
PDF and SVG. This used the original synthetic CSV; removal of the source runtime
was not tested. A nonblocking Matplotlib font-cache warning remains in evidence.

Eight original route/task files and the library registry/archive retained their
hashes. Studio and Setup closed normally; the final owned-process list was empty.
RC8 remains installed, with profiles/results/evidence retained. No candidate
patch, manual repin, cache deletion, unrelated dependency installation, or
unchanged cancellation/Agent/full installer regression was used. Production and
library source were not modified; no push/publication occurred.

Local report/index: `BioPipe/verification/tauri-rc8-delivery/`.
The complete 31-entry evidence ZIP remains on the test computer at
`<test-evidence>/tauri010rc8/Operon-Tauri-0.1.0-RC8-evidence.zip`.
Evidence SHA256:
`0860bc62cef2641807c3247d592975b6bf609fcb7999154618d0e6ce99791be3`.

### RC8 supplemental source-unavailable acceptance — 2026-11-17

PASS. The original experimental installation root was temporarily renamed and
its original path verified unavailable. The synthetic CSV was copied outside
that root and its digest verified; only documented input path configuration was
temporarily changed. Child Python/Conda/R injection variables were removed and
PATH retained Windows base tools only. No production installation or library
content was changed.

The existing exported bundle's delivered `run.cmd` ran with new work/output
directories and without `--resume`. Its observed launcher interpreter was inside
the relocated bundle. Run `run-e572dcbf9aaf427f87925fcd16fcc57e` completed with
exit 0 and reused=false. The worker's prepared receipt and on-disk generation
pointed to the new work directory's self-materialized Python; the worker PID was
not separately captured. PCA and describe JSON were byte-identical to the prior
Studio result. PNG/PDF/SVG were nonempty (29357/11034/14522 bytes).

The original installation root and inputs.json were restored in finally.
Installation identity, library registry and library archive hashes matched the
pre-test baseline; final owned-process inventory was empty. Original evidence
was retained. No previously passed unchanged suites were rerun; no publication.

Local supplemental report/index:
`BioPipe/verification/tauri-rc8-delivery/standalone-no-source-report.md` and
`standalone-no-source-result.json`. The new evidence ZIP remains on the test
computer: `<test-evidence>/tauri010rc8/RC8-standalone-no-source-evidence.zip`.
SHA256: `7bd085c281438dbb058d383d8a70a5d7845213baec1a2c17c5350266c2c6b9ff`.
