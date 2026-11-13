# Operon Studio 5.x cumulative update (5.0.0 to 5.1.12)

This note summarizes the application-side changes since the 5.x split.
There is no `5.0.9` release in this repository; the 5.x line starts at
`5.0.0`. If a narrower baseline is needed, use the per-version notes in
`docs/releases/`.

## At a glance

| Version | Main change |
| --- | --- |
| 5.0.0 | Application and operator library split; two-ZIP install; library 0.0.0 |
| 5.0.1 | Library stored per application version; canvas no longer pins operators |
| 5.1.0 | Multiple equal-status libraries (`main`, `fork1`); per-run provenance and run folders |
| 5.1.1 | Import UI shows library types, not versioned filenames |
| 5.1.2 | Library name/version come from the bundle manifest; no user-entered names |
| 5.1.3 | Remote install delivers and installs the selected library branches |
| 5.1.4 | Base `main` library ships with the app and installs on first start |
| 5.1.5 | Route collection filenames such as `operon-routes-main-v0.1.0.zip` are accepted |
| 5.1.6 | Installed library environment manifests persist and are exposed to the UI |
| 5.1.7 | Probe subprocesses force UTF-8 (Chinese Windows locale fix) |
| 5.1.8 | Windows-safe environment commit, PATH-safe probes, extended `\\?\` path handling |
| 5.1.9 | Vendored PDBFixer files and `resources.json` ship with the library; library 0.1.1 |
| 5.1.10 | Managed-server library layout recognized; dependency repair scoped to used operators |
| 5.1.11 | Stale remote build cache rejected; remote poll accepts task-folder run events |
| 5.1.12 | Remote provisioning tolerates the optional Hi-C requirements file; footer version fixed |

## What changed for users

### Library and workspace layout

- The application is installed per version under `<install>/versions/<version>`.
- Each version owns its library at `<version>/library`; the workspace holds task
  folders and `.studio` state, not operator sources.
- The workspace model is one folder per task: `<workspace>/<task>/input` for
  inputs and `<workspace>/<task>/results/<job>` for results and run records.
- The canvas stores no operator pins. At run time operators and Readers are
  resolved from the libraries currently installed.

### Multiple libraries

- Libraries are equal-status branches, addressed by `<name>-v<version>`
  (for example `main-v0.1.1`, `fork1-v0.0.0`).
- A bundle declares its own `library_name`; the UI has no free-form naming
  fields. Duplicate primary names, package names, modules and operator ids are
  rejected.
- Each run records only the operators it actually used, together with the
  library label and code hashes, in `job.json` and `plugins.lock.json`.

### Remote execution

- Remote installs receive the application plus every selected library branch.
- The remote server resolves its library from `code-<id>/library` as well as
  the desktop `versions/<version>/library` layout.
- Remote dependency repair now checks only the operators used by the requested
  environment; it no longer sweeps all installed operators.
- A stale `<profile>.catalog.json` is deleted after a server upgrade or an
  application version change, so the UI cannot keep showing an older build.

### Isolated environments

- Library bundles carry `environments.json`; the application persists it per
  branch and composes the root manifest.
- Environment install and probe are separate from readiness: probes return
  `installing` while a commit is in progress.
- Environment commits on Windows retry the directory swap and restore the
  previous environment if the rename cannot complete.
- Probe children run with `-X utf8` and a PATH that includes the environment's
  `Scripts` / `Library/bin`, and `\\?\` paths are normalized before spawning.

## Compatibility

- `bundle_format`: 1
- Operator protocol: 3, revision 3.7
- Bundled library: `main` 0.1.1 — 7 packages, 1174 descriptors, 79 routes
- Minimum application declared by the bundled library: 5.1.9
- Legacy 8.x libraries remain rejected with an explicit migration message.

## 5.1.12 artifacts

| Asset | Size | SHA-256 |
| --- | ---: | --- |
| `Operon_Setup.exe` | 396,537,538 | `a604b98852168f079de82fed4420602e992fb93c026c0bdbbeca3e647008a72e` |
| `Operon-5.1.12-Server.zip` | 9,158,813 | `8c2a1d488216f7a0a8a73bb0f662187a5d1bb48718df7208abdfadb4ad2241c8` |
| `operon_studio-5.1.12-py3-none-any.whl` | 673,249 | `acbd155f9f393b4047bad57b512106934563945900cb5a23cef086564eee3b6c` |

## Known limitations

- First start after an application upgrade still materializes the base library
  (7 wheels, 1174 metadata/doc files, about 45 s on a warm disk). The window can
  show an empty operator panel until materialization completes.
- A `venv_shared` environment created by an older version keeps the old base
  interpreter path in `pyvenv.cfg`; after that version is removed the environment
  must be recreated.
- The 5.1.12 frontend reuses the existing 5.1.5 UI bundle with the version
  literal corrected. A full Vite rebuild and a dist-version packaging guard are
  still pending.