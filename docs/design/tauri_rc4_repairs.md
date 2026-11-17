# RC4 focused repairs (experimental desktop)

Scope: `experimental/tauri-shell`. No production checkout or operator-library implementation changes. RC3 is immutable evidence and is not replaced.

## Process working directories

Windows CreateProcess can reject an existing current directory at MAX_PATH even with the extended `\\?\` spelling. File I/O spelling, executable spelling, and process cwd are different boundaries. `operon.process_paths.ProcessDirectory` now supplies a verified short junction to the exact original cwd for long Windows paths. `owned_process` uses it for nested script/tool/dependency processes, while the RunPlan supervisor retains its existing attempt-scoped alias. No global chdir, data copying, drive-letter reservation, administrator privilege, or 8.3-name dependency is introduced.

Each launch owns a separate temporary alias and journal. The reparse entry is held against replacement while active. Confirmed tree exit removes only the junction and journal, never target data. Uncertain exit retains metadata with `recovery_required`; it is not reaped by an unsafe PID-only timer. A too-long/unusable OS TEMP root produces an actionable error. Portable collection follows the new module's imports automatically. Third-party runtimes with their own filename restrictions still require their existing explicit validation; this is not a claim that all external programs accept every Windows path.

## Stable library binding

Immutable program versions and mutable imported library state must have different lifetimes. New experimental versions bind `<installation>/library` through an explicit generated `experimental-library-binding.json`. Backend validation binds its installation identity to `install-state.json` and `host.json`; production and source-checkout layouts remain unchanged.

Setup drains the owned host before staging the first migration from the current version's library. It copies and verifies metadata/archives/environments without rewriting their pins or parameter JSON, then promotes the complete directory. The original is retained for rollback. An already bound stable library is authoritative. Conflicting unbound libraries must not be silently merged. Uninstall retains the stable library and profiles. Historical RC3 backups are evidence, not an automatically guessed source.

## Existing-instance activation

A second shortcut invocation must exit without constructing a second backend. The existing installation-scoped named pipe gains a bounded authenticated Show action. Client validates executable/PID/creation identity and the actual pipe-server PID before sending credentials. A matching accepted/ack exchange plus final `shown` response is required. Show executes on the UI thread only in a ready lifecycle state; maintenance/draining/recovery reject it. The Quit protocol remains compatible with the installer.

## Packaging and verification

The validated production 5.3.0 payload remains unchanged. The experimental builder applies a fixed five-file backend overlay and writes old/new hashes in `experimental-backend-overlay.json`; the final experimental manifest hashes the resulting payload. Runtime dependencies and frontend assets are reused.

Focused Python evidence: six real Windows long-cwd/relative-I/O/cancellation/cleanup/export-closure tests; binding identity tests; a real synthetic wheel-library import/copy/pin-resolution test; two unchanged-layout compatibility checks; packaging overlay and existing verifier tests. Sandbox-denied junction/temp checks were rerun under native Windows permissions, not counted as product failures. Rust activation and C# migration evidence and candidate hashes are recorded in the RC4 delivery status after review.

Reuse RC3 evidence for unchanged Agent edit/undo, chart viewing, YAML round-trip and scientific numerics. Remote RC4 gates are the repaired long-path Studio route, library preservation through reinstall/upgrade, shortcut wake-up/no duplicate Python, and normal shutdown of the changed host. No full suite or production release is requested.
