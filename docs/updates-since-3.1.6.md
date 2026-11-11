# What changed since Operon Studio 3.1.6

This page is for people upgrading from **3.1.6**. It summarizes the changes that
affect day-to-day use. Detailed release notes are in `docs/releases/`.

## The short version

- The product is now called **Operon Studio** everywhere. The old Biopipe name
  is not kept as a compatibility alias.
- The bundled operator library is **8.0.2**: 1,063 operators, 108 Readers,
  1,171 descriptors and 79 built-in routes.
- Installing or upgrading a Linux server is one action in the desktop app.
  There is no per-package incremental upload.
- New Windows installations keep their workspace under the installation root.
- 4.0.3 adds a force-upgrade option for a remote server and removes the old
  "disconnect MCP first" uninstall warning.
- 4.0.4 is an installer hotfix: Setup no longer crashes when you browse to or
  type a non-empty folder that is not an existing Operon installation.

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

## What did not change

- Wire protocol 3 and SDK 3.7.
- Saved workflow JSON and operator parameters remain valid.
- The 8.0.2 operator and Reader APIs.
- Linux x86_64 is still the supported automatic server target.

## Known limitations

- The 4.0.2 workspace move is not an automatic data migration for existing
  4.0.x profiles.
- The 4.0.3 server archive was not deployed during release acceptance; the
  one-click server path was verified with the 4.0.1 build and the same install
  code.
- Historical design and verification pages keep their original version numbers
  and machine paths. They are records, not current setup instructions.
