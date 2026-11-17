# RC4 installer library handoff

Status: installer-only repair for the experimental Windows setup. The imported
library is copied to an installation-owned mutable tree before an immutable
version is promoted or replaced, so a same-build reinstall or an upgrade no
longer disconnects existing pins.

Scope implemented in this task:

- `desktop-tauri/installer/InstallerEngine.cs`
- `desktop-tauri/installer/SelfTest.cs`
- this handoff document

No backend, protocol, operator-library, production-source, Rust-host, version or
release change is included. The Rust host work and the backend
resolver/packagebuilder are separate workstreams. This installer writes the
binding marker that the backend reader validates; the reader itself is not
modified here.

## Layout

| Path | Ownership |
|---|---|
| `<install>/library` | Stable mutable imported library. Outside every version. Retained by update and uninstall. Created empty on a fresh bound install. |
| `<install>/versions/<build>/library` | Version-local legacy/bundled library tree. Never moved or deleted by migration. |
| `<install>/versions/<build>/experimental-library-binding.json` | Installer-generated version-owned binding to `../../library`. |
| `<install>/profiles/<installation-id>` | Profile, retained as before. |
| `<install>/.library-migration-<uuid>` | Temporary staged copy. Only renamed to `<install>/library` after verification. |

The stable library is the only location a bound version resolves at runtime. The
version-local source remains byte-for-byte for rollback and historical pins.

## Installer transaction order

1. Verify and extract the candidate payload under `.staging-<build>-<uuid>`
   (unchanged).
2. Read `install-state.json` and `current.json`; validate product/channel,
   installation ID, profile and current version path (unchanged).
3. Acquire the maintenance lease, find an exact owned host, request graceful
   quit and wait for it to drain.
4. Validate the target version directory identity before any library write. A
   wrong/non-current build identifier still fails with "No files were changed".
5. Run the library migration (below).
6. Promote the staged version, or reuse the existing exact payload, or replace
   the damaged current version.
7. In the existing snapshot-protected commit block, write `host.json` and
   `experimental-library-binding.json`, install the uninstaller stub, create the
   shortcut, write registration/state/current pointer. A failure restores the
   binding and pointer with the other generated files.
8. Remove the replaced version copy through its verified immutable manifest. The
   unknown legacy `library` tree in that backup is retained.

The migration runs exactly between step 3 and step 6, never before the owned host
is drained and never after a version directory is replaced or promoted.

## Migration rules

- **Stable absent, current version library nonempty.** Enumerate the source
  recursively, reject any reparse point in a directory or file, copy every file
  and relative directory (including `packages/`, `snapshots/`, `environments/`
  and empty directories) into `.library-migration-<uuid>`, then verify the
  copied file set, sizes, SHA-256 values and directory set against the source
  snapshot. Rename the verified staging tree to `<install>/library`.
- **Source retained.** The original `<version>/library` is read only. It is
  never moved, renamed or deleted by migration. Absolute audit archive paths
  stored inside copied JSON files are untouched because files are copied as
  bytes; no package, descriptor or parameter JSON is parsed or rewritten.
- **Stable nonempty.** The stable library is authoritative. A current version
  with a valid binding is reused even when its version-local tree differs. A
  current version with no valid binding must have the same file set and bytes as
  the stable library; otherwise the installer refuses before copying. The
  message names both exact paths and a recovery action. No automatic merge is
  performed.
- **Stable nonempty, source absent/empty.** The stable library is authoritative
  and is reused.
- **Stable and source absent/empty.** The installer creates an empty ordinary
  `<install>/library` directory. The bound backend then has a real import
  target and does not fall back to the version-local tree. No backup is guessed.
- **Recovery boundary.** If the current version library is gone and a retained
  `.staging-replaced-*` or `.library-migration-*` tree exists, the installer
  reports those exact candidate paths but never uses them automatically. It
  still installs the empty stable directory and reports the boundary in the
  result message.
- **Idempotence.** If a previous failed transaction already created the stable
  library and the source still has the identical file set/bytes, the migration
  is a reuse: no staging tree, no second copy, and no change to the stable tree.
  The stable tree may remain after a failed install; the old pointer and binding
  remain in effect until the commit block succeeds.
- **Reparse rejection.** Links, junctions and other reparse points fail the
  migration with the exact path. They are never traversed or copied.

## Version-owned binding marker

Every installed version gets `experimental-library-binding.json` next to
`host.json`:

```json
{
  "schema": 1,
  "installation_id": "<the installation UUID>",
  "location": "../../library"
}
```

From `versions/<build>/`, `../../library` resolves to `<install>/library`.
`VerifyInstalledVersion` treats this generated mutable config like `host.json`
and allows it during integrity checks. It is also included in `FileSnapshot`
rollback and removed from an old replaced-version backup. A valid marker must
have exactly schema `1`, the same installation ID, and location
`../../library`; any other schema, ID, location, unreadable file or reparse
point is invalid.

## Backend resolver contract (separate workstream)

The backend resolver/packagebuilder is owned outside this installer patch. Its
reader validates the following before resolving the mutable library:

1. `install-state.json` exists, has `schema: 1`,
   `product: "operon-studio-experimental"`, `channel: "experimental"` and a
   nonempty `installation_id`.
2. The current version's `host.json` exists and its `installation_id` equals the
   state ID.
3. The current version's `experimental-library-binding.json` has schema `1`,
   the same installation ID and location `../../library`.
4. The resolved `<install>/library` path is inside the validated installation
   root, is an ordinary directory (not a symlink/reparse point), and contains no
   reparse point that would escape it.

No protocol or library-source change is required. An absent/invalid marker is a
legacy version; the backend must not silently bind it to an arbitrary path. The
backend treats a missing stable library directory as unavailable rather than
reconstructing it from version backups, which is why the installer creates the
empty directory on a fresh bound install.

## Uninstall and reinstall

- Uninstall still deletes only manifest-owned files whose SHA-256 matches, then
  removes the shortcut and uninstall registration. It never traverses or deletes
  `<install>/library`.
- The result message explicitly reports the retained stable library and the
  retained profile.
- After uninstall, `install-state.json` and `current.json` are gone. The
  installer recognizes a retained layout when `<install>/library` exists and a
  retained profile marker validates (`schema_version: 1`, installation ID equal
  to the profile directory name). This prevents a reinstall from nesting a new
  installation under the old root. The new installation creates a new state and
  reuses the stable library.

## Focused tests

Build with project-local output:

```text
dotnet build desktop-tauri/installer/OperonExperimentalInstaller.csproj -c Release -o desktop-tauri/installer/.selftest-out
```

Run the self-test (the executable is a WinExe, so use `Start-Process -Wait`):

```text
Start-Process -FilePath desktop-tauri/installer/.selftest-out/Operon_Experimental_Installer.exe `
  -ArgumentList @('--self-test','--result', <result.json>) -Wait -PassThru -NoNewWindow
```

Result: exit `0`, `"message": "Self-test passed."`.

New focused checks:

- `library-migration-exact-copy`: packages/snapshots/environments bytes,
  absolute audit archive string and empty relative directories are copied
  exactly; the version-local source, binding and current pointer are unchanged.
- `library-migration-idempotent`: a second migration reuses the identical stable
  tree, leaves the source in place and retains no staging directory.
- `library-empty-stable`: a fresh bound version gets an empty ordinary stable
  library directory, so the backend resolver has a real import target.
- `library-migration-divergent`: two different nonempty libraries are refused
  with both exact paths; a valid binding makes the stable tree authoritative
  without merging.
- `library-migration-reparse`: a directory junction inside the source is
  rejected and no stable library is created.
- `library-binding-rollback`: snapshots restore the old binding bytes, remove a
  promoted binding, and restore the old current pointer.
- `library-binding-integrity`: the generated marker is accepted, another
  installation ID or foreign location is rejected, and the binding plus a
  legacy `library` tree passes integrity checks while a foreign file or corrupt
  manifest-owned file fails.
- `retained-library-root`: a retained library plus valid profile marker is
  reused as the installation root, including when it is the product child.

No full test suite was run, and no app was installed or uninstalled by this
task.

## Limitations / recovery boundary

- The backend resolver and packagebuilder are not changed in this task.
- Once the stable library exists it is authoritative. A newer payload's bundled
  library seed is not merged automatically into it; that would require an
  explicit, reviewed migration.
- Divergent nonempty libraries are refused, not merged. Recovery requires a
  backup and an explicit choice; the installer never edits pins or saved tasks.
- Retained `.staging-replaced-*` and `.library-migration-*` trees are reported
  but never used automatically. If both the current version library and the
  stable library are gone, that is the recovery boundary.
- Uninstall retains the stable library and profiles. It does not attempt to
  prune unused historical pins or merge profiles.
- Reparse coverage requires a Windows junction or symlink; the self-test creates
  a junction when symbolic-link creation is not permitted.
