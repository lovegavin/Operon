# RC5 packaging and task-TEMP repair

Scope: experimental/tauri-shell only. Production and operator-library sources remain unchanged. RC4 is retained as failed acceptance evidence.

## Evidence and cause

The RC4 test machine confirmed that installation.py, processes.py and tool_runner.py had unchecked-hash bytecode from RC3 despite updated source. Source hashes alone did not establish executed code identity. Library files and pins survived migration but the management process still used the old location. The real long-path task independently failed because the task-scoped TEMP was itself long.

## Changes

- Packaging invalidates only bytecode corresponding to the five explicit Python overlays: adjacent legacy .pyc and matching __pycache__ tags/optimization variants. It records removed paths and hashes. It does not invalidate the rest of Python, dependencies, or the library.
- Candidate containment and reparse checks precede cache removal and source replacement. Source inputs are read-only.
- ProcessDirectory obtains the current user's LocalAppData through Windows SHGetKnownFolderPath, independent of worker TEMP and LOCALAPPDATA environment overrides. Only unique junction/journal metadata is placed in Operon/ProcessCwd. Task temporary files, data, results and memory-spill locations are unchanged.
- Existing per-process ownership, pinned junction verification, confirmed-stop cleanup and recovery_required retention remain in force. No administrator requirement, global environment mutation, drive-letter assignment or data copy is introduced.
- A redirected/non-local or extraordinarily long Windows user metadata directory still fails explicitly rather than using an unsafe arbitrary location. This does not remove external programs' independent filename restrictions.

API references: [Known folders](https://learn.microsoft.com/en-us/windows/win32/shell/known-folders), [SHGetKnownFolderPath](https://learn.microsoft.com/en-us/windows/win32/api/shlobj_core/nf-shlobj_core-shgetknownfolderpath). COM initialization is balanced and the returned buffer is freed with CoTaskMemFree.

## Focused validation

- Two new real Windows checks passed: deeply redirected task TEMP still runs with relative I/O; changing LOCALAPPDATA in the environment cannot redirect the OS-known metadata directory.
- Packaging and affected path regression: 14 passed, 2 skipped. Skips are symlink creation unavailable on this Windows account, not claimed passes.
- The bytecode regression first proves a fresh isolated interpreter executes the OLD unchecked cache after a source-only overlay, then proves the rebuilt overlay executes the NEW value with normal and optimized imports. Unrelated cache/library/source bytes remain unchanged.
- DeepSeek Harness implemented the bounded packaging fix in two files. Its own test invocation was blocked by its sandbox ACL setup; root independently reviewed and ran the tests under native Windows permissions. No filesystem ACL repair was performed.

## Remote evidence carried forward

RC4 actual shortcut hide/minimize and double-click activation passed with the same host/backend PID and creation identity. Normal exit was about 0.8 seconds, both exit codes zero. Native host and installer source are unchanged in RC5, so these gates are reused. RC4 upgrade retained 8/8 route/task files and the library archive/registry hashes. Library loading/task reuse failed; long task TEMP execution failed. Export, cancellation and same-build reinstall were intentionally deferred.

RC5 must complete actual installed library loading and pinned task reuse, long task-TEMP execution and relocated export, then same-build reinstall with stable library reuse. Do not repair the installed candidate by manually removing caches or reimporting the library during acceptance.
