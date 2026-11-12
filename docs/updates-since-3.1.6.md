# What changed since Operon Studio 3.1.6

This page is for people upgrading from **3.1.6**. It summarizes the changes that
affect day-to-day use. Detailed release notes are in `docs/releases/`.

## The short version

- The product is now called **Operon Studio** everywhere. The old Biopipe name
  is not kept as a compatibility alias.
- The bundled operator library is **8.0.6**: 1,063 operators, 108 Readers,
  1,171 descriptors and 79 built-in routes. Studio 4.1.0 supports 8.0.6+ only.
- Installing or upgrading a Linux server is one action in the desktop app.
  There is no per-package incremental upload.
- New Windows installations keep their workspace under the installation root.
- 4.0.3 adds a force-upgrade option for a remote server and removes the old
  "disconnect MCP first" uninstall warning.
- 4.0.4 is an installer hotfix: Setup no longer crashes when you browse to or
  type a non-empty folder that is not an existing Operon installation.
- 4.0.5 hides the **强制重装** option once installation completes and adds a same-version operator-library hint to route-import errors; it remains
  available only for a reinstall decision or after a failed attempt.
- 4.0.6 aligns artifact-preview labels with their values, warns when readiness
  was checked before the canvas changed, blocks duplicate output names before a
  run, and warns when memory management is disabled.
- 4.0.7 fixes remote admission failures that stayed queued, binds readiness to
  the graph digest, stops unmanaged memory from reserving the whole pool, and
  trims the remote status payload.
- 4.0.8 accepts foreign non-empty install folders, deletes only Operon-managed
  files, disconnects all MCP clients before uninstall, offers force reinstall
  after failure, and uploads local inputs to the selected remote workspace.
- 4.1.0 ships library 8.0.6, which can carry its environment manifest in the
  bundle and declares the OpenMM 8.1.1 / PDBFixer 1.9 environment for the
  structure operators. It requires Studio 4.1.0 or newer.
- 4.0.10 clears old remote plugin pins before preparation and closes sessions on a forced server upgrade; 4.0.9 did not remove the stale pin.
- 4.0.9 closes all remote workspace sessions on a forced server upgrade and
  prunes sessions left by an exited process before re-registering the library.
- Remote runs refresh stale plugin pins against the selected server; MCP remote
  status returns a compact summary instead of the full catalog.

## Upgrade path

| Version | What it means for you |
| --- | --- |
| 3.1.7 | Remote builds are checked for identity, the built-in library can be replaced as a whole, the Windows host has a tray and a real **完全退出**, and the uninstaller removes the installation cleanly. |
| 3.1.8 | The Biopipe to Operon rename. Workflows or plugins that still use `biopipe-*` provider IDs must be updated. |
| 3.1.9 | Desktop startup parsing is fixed, the installer path picker works in both modes, and a route collection can be imported as one ZIP file. |
| 4.0.0 | The 8.x operator library ships in the app: 1,063 operators, 108 Readers, 79 routes. Protocol 3 / SDK 3.7 are unchanged. |
| 4.0.1 | One-click server install records the desktop build, compares library identity instead of per-operator hashes, and defers dependency checks until execution. |
| 4.0.2 | Setup-created installations use `<install root>/workspace`; profile metadata and logs still live under `%USERPROFILE%\.operon`. |
| 4.0.3 | Force server upgrade cancels active remote tasks and closes all sessions. Uninstall disconnects connected MCP clients instead of asking you to do it. |
| 4.0.4 | Setup no longer crashes when checking a non-empty folder that is not an existing Operon installation. If Setup asks to reinstall, normal reinstall still checks for running tasks; 强制重装 preserves the workspace. |
| 4.0.5 | Hides 强制重装 after a successful install and tells you to import the matching operator-library version when route import fails. Library and protocol are unchanged. |
| 4.0.6 | Fixes preview label order, stale readiness warnings, duplicate output names, and the memory-management warning. Library and protocol are unchanged. |
| 4.0.7 | Fixes remote admission terminal-state display, stale readiness after canvas edits, unmanaged-memory whole-pool reservation, and oversized remote status. Library and protocol are unchanged. |
| 4.0.8 | Installer accepts foreign folders and removes only Operon files; uninstall disconnects all MCP clients; Setup offers force reinstall after failure. Local files can be uploaded/staged for remote runs. Library 8.0.3 and protocol are unchanged. |
| 4.0.9 | A forced server upgrade closes every remote workspace client before the new application registers, stale sessions from an exited process are pruned, remote runs refresh old plugin pins, and MCP remote status is compact. Normal upgrades still abort on active work. Library 8.0.3 and protocol are unchanged. |
| 4.0.10 | Exact-root install and uninstall, remote stale-pin refresh, forced-pool session close. Library 8.0.3 and protocol are unchanged. |
| 4.1.0 | Requires library 8.0.6+. The library bundle carries environment manifests; the structure operators use the isolated OpenMM 8.1.1 / PDBFixer 1.9 environment. Protocol 3 / SDK 3.7 are unchanged. |

## Reinstall or upgrade a Windows installation

If the selected directory already contains Operon Studio, Setup asks before
replacing it.

- **Normal reinstall** closes the old window and checks its local and remote
  jobs first. If any task is still running, Setup refuses the reinstall and
  leaves the old installation untouched.
- **强制重装** is the quick override. It terminates the old Operon/Python
  processes, removes the old version files, and then installs the new version.
  It never deletes the profile, workspace, routes, results, or job records.
- A new installation keeps its working workspace under the installation root
  (`<install root>/workspace`). An existing 4.0.x profile workspace is not moved
  automatically; it remains under
  `%USERPROFILE%\.operon\profiles\<old-id>\workspace`. Copy any files you need
  into the new workspace.
- Start the new installation and confirm that **服务端维护** shows the expected
  build before running production work.

## If Setup asks to reinstall

This is the 4.0.4 directory-probe fix in practice. You can select an existing
Operon installation directory, or any non-empty folder. A foreign folder is
reported as not being an Operon installation instead of crashing Setup. An
actual existing installation still offers the normal reinstall and force
reinstall choices described above.

## Upgrade a remote server

Use **服务端维护 → 安装 / 升级服务端** on the connection. A normal upgrade waits
for idle tasks. If the old server has active tasks or an old shared pool, the
upgrade stops without changing the server files.

Use **强制升级服务端** only when you accept that every Operon task on that
server will be stopped and every session closed. The desktop will ask for
confirmation. The old server processes and their shared pools are then retired
before the new build is installed.

## 4.1.0: isolated operator environments

- Importing a library bundle now also provisions its declared isolated
  environments in the background. Status is visible in **算子库管理**, with
  prepare, retry and log actions; a missing environment no longer appears only
  as an execution failure.
- The library bundle carries `sources/operon/environments.json`; 4.1.0 rejects
  operator libraries older than **8.0.6** so an environment model mismatch
  cannot be hidden.
- Operator and Reader dependency discovery uses only the operator-library
  archive and the route archive. The optional `install-dependencies` helpers
  published next to the library are not required.

## What did not change

- Wire protocol 3 and SDK 3.7.
- Saved workflow JSON and operator parameters remain valid.
- Operator and Reader APIs remain compatible; 4.1.0 requires library 8.0.6+.
- Linux x86_64 is still the supported automatic server target.

## Known limitations

- The 4.0.2 workspace move is not an automatic data migration for existing
  4.0.x profiles.
- The 4.0.3 server archive was not deployed during release acceptance; the
  one-click server path was verified with the 4.0.1 build and the same install
  code.
- Historical design and verification pages keep their original version numbers
  and machine paths. They are records, not current setup instructions.

## 4.1.1: upgrade-path fixes

- Library import no longer fails on 4.0.x source trees that lack
  `operon/environments.json`; the manifest joins the fingerprint only when the
  imported library declares it.
- Bundle verification compares per-entry wheel contents, so Windows-built and
  Linux-built libraries validate on either platform.
- A library without an environment manifest is reported explicitly instead of
  silently using the application seed.
- Isolated environments are installed only when the user installs dependencies
  from the pre-run check, or explicitly through the environment API/MCP tools.
- Minimizing the desktop window keeps its taskbar button; closing hides it to
  the tray.

## 4.1.2: cross-platform library verification

Provider wheels rebuilt on Windows and Linux now compare equal even though their
`RECORD` rows are ordered differently. Libraries packaged on one platform import
on the other without `Library source does not match wheel`.

## 4.1.4: runtime ships the matching application package

The Windows runtime now carries the same `operon` package version as the
application. Before this release the runtime kept an old 3.1.8 copy in
`site-packages`, so an MCP client that started `python -m operon` outside the
version directory loaded stale code and failed the handshake. Packaging now
rejects a runtime whose package version or distribution metadata does not
match.

## 4.1.3: installation prompts and unified environment repair

- The installer confirmation states the exact root directory and that uninstall
  removes everything there except `workspace`.
- Isolated environments are prepared only through dependency repair; the
  separate environment panel was removed.
- Remote runs skip local environment preparation because the server already
  performed it.
