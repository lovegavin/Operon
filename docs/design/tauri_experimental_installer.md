# Experimental Windows installer and maintenance channel

Status: implementation contract for Session E. This is an experimental
replacement beside production, not a release-promotion plan.

## Product and layout

| Item | Value |
|---|---|
| Product | `Operon Studio Experimental` |
| Identifier | `org.operon.studio.experimental` |
| Host | `operon-desktop-experimental.exe` |
| Default root | `%LOCALAPPDATA%\Programs\Operon Studio Experimental` |
| Profile | `<install-root>\profiles\<installation-id>` |
| Versions | `<install-root>\versions\<build-id>` |
| Uninstaller | `<install-root>\bin\Operon_Experimental_Uninstall.exe` |
| Shortcut | `Operon Studio Experimental (<id-prefix>).lnk` |
| Uninstall key | `HKCU\...\Uninstall\OperonStudioExperimental-<installation-id>` |

The installation ID is generated once on a clean install and retained by
updates. The profile is outside every version directory and is never removed by
update or uninstall. No production shortcut, key, profile, or runtime hint is
written.

A selected directory is used directly when it is empty, contains this
installation, or contains only empty/transient directories. A nonempty unowned
directory gets an `Operon Studio Experimental` child; an existing nonempty
foreign child is refused. Existing installation state is validated before any
write.

## Candidate and manifest

The setup embeds a canonical `experimental-manifest.json` and a payload ZIP with
the existing `Operon Studio/` root and `OPERON-SETUP-V1` footer. The manifest
contains:

- product, channel, build ID, host version `0.1.0`, management release `5.3.0`;
- source commit and dirty flag;
- Cargo, frontend, base-manifest, and optional runtime-receipt hashes;
- component byte totals;
- every payload file's relative path, byte count, and SHA-256;
- a `payload_id` derived from the identity fields and sorted file list.

The setup validates the product/channel/version pair, payload ID, every path,
and the exact extracted file set before it requests host exit. Production
payloads are rejected at the manifest boundary. The installed manifest is the
ownership list for later cleanup.

## Maintenance protocol

The host publishes a local named pipe and a private profile receipt at
`<profile>\.operon-maintenance-host.json`:

```json
{
  "schema": 1,
  "installation_id": "...",
  "pid": 1234,
  "created_filetime": "133...",
  "exe": "C:\\...\\operon-desktop-experimental.exe",
  "pipe_name": "\\\\.\\pipe\\OperonExperimentalMaintenance-...",
  "token": "<uuid-v4><uuid-v4>"
}
```

The pipe rejects remote clients and starts with one first instance. A request is
one newline-terminated JSON frame, maximum 4096 bytes, read with a 3-second
deadline:

```json
{
  "schema": 1,
  "installation_id": "...",
  "token": "<two UUID-v4 values>",
  "action": "quit",
  "request_id": "<uuid-v4>"
}
```

The host verifies exact installation ID, bearer token, action, and request ID;
unknown fields and caller paths/commands are rejected. On acceptance it replies

```json
{"schema":1,"request_id":"...","status":"accepted"}
```

and only then invokes the existing `bridge::request_exit`. Repeated identical
request IDs are acknowledged without a second exit request; a bounded recent-ID
list allows a new request ID after a timeout. The host never performs file
operations or process control from this channel.

Before sending, the setup verifies the pipe server PID with
`GetNamedPipeServerProcessId`, the exact process image path under the current
version, the process creation FILETIME, and the receipt installation identity.
A live instance lock without a valid receipt refuses maintenance. A stale
receipt is ignored only when the process is dead or its creation identity does
not match; live unknown processes are never signaled or killed.

## Atomic startup exclusion

The host and installer use:

- `Local\OperonExperimentalMaintenance-<sha256(installation_id)>` as a named
  mutex;
- `<same-name>-active` as a manual-reset event.

The host takes the mutex before the profile instance lock or backend spawn,
checks that the event is not signaled, publishes the pipe and receipt, and only
then releases the mutex. The installer takes the same mutex and sets the event
for the whole drain/commit or uninstall transaction. The RAII guard clears the
event and releases the mutex on every outcome. A host starting during
maintenance fails before backend spawn.

## Install, update, and rollback

1. Validate the selected root and existing installation state.
2. Extract and verify the candidate under a staging directory.
3. Acquire the maintenance lease.
4. If an exact owned host is live, request graceful quit and wait for exit code
   zero. Timeout, cancellation, nonzero exit, or an old host without the channel
   aborts with the current pointer, shortcut, registration, profile, and old
   version intact.
5. Promote the staged directory to `versions/<build-id>`. Old versions are
   retained.
6. Write the new host config with the same installation ID/profile, install the
   small uninstaller stub, update the shortcut and HKCU uninstall entry, then
   atomically commit state and the current pointer.
7. On any commit failure, restore the previous shortcut bytes, registry values,
   state, pointer, host config, and uninstaller stub. A newly promoted failed
   version is removed only through its verified manifest.

Cancellation before host exit leaves files unchanged. Cancellation while
waiting for exit aborts the update; a host that already accepted the request may
still exit, but the old pointer remains launchable.

## Uninstall

Uninstall requires the experimental state and current pointer. It acquires the
maintenance lease, requests an owned host quit, and refuses while any confirmed
process image remains under the installation's `versions` directory, including
scientific workers. It never kills a process.

Only files listed in each verified installed manifest are deleted, and only when
their current SHA-256 still matches. Reparse points, foreign files, modified
files, and the profile are preserved. The installed uninstaller stub may remain
while it is the running process and is reported. Shortcuts and the experimental
uninstall key are removed only after payload cleanup succeeds.

## CLI

```text
Operon_Experimental_Setup.exe --silent --install-dir <path> [--result <path>]
Operon_Experimental_Setup.exe --silent --install-dir <path> --uninstall [--result <path>]
Operon_Experimental_Setup.exe --self-test [--result <path>]
```

Exit codes: `0` success, `2` usage, `3` validation/payload, `4` maintenance or
owned-process refusal, `5` install/commit failure, `6` uninstall failure, `8`
cancelled, `9` self-test failure. The interactive form keeps the directory field
editable after errors and displays progress while active.

## Packaging

The packaging input is explicit; no user Python or scientific dependency
installation is performed:

```text
python scripts/package_tauri_experimental.py \
  --base-payload <5.3.0 payload directory> \
  --host <experimental release exe> \
  --frontend <experimental frontend dist> \
  --output <new output directory> \
  --build-id <tauri-0.1.0-rc1>
```

The base `package-manifest.json` is verified as an exact file set and hash list.
The script copies the reusable management runtime/back end read-only, replaces
the production host and frontend, removes production desktop wrappers, preserves
bundled library resources byte-for-byte, writes `EXPERIMENTAL_README.txt` and the
experimental manifest, and appends the payload to the setup. It builds the
uninstaller stub separately so the installed uninstaller does not duplicate the
payload.

No network update, Tauri updater, production signing credential, publication,
or release tag is part of this experiment.

## Verification

Focused automated checks:

```text
cargo test --locked --test maintenance_ipc
cargo test --locked maintenance
python -m pytest tests/tauri/test_experimental_package.py
dotnet build desktop-tauri/installer/OperonExperimentalInstaller.csproj -c Release
dotnet run --project desktop-tauri/installer/OperonExperimentalInstaller.csproj -- --self-test --result <path>
```

Root still needs a real built candidate, a clean install/update/uninstall on
Windows, double-click shortcut verification, a running owned backend update,
unrelated-process preservation, profile retention, and production-baseline hash
comparison. Source tests alone are not installed-product acceptance.
