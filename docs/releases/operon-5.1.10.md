# Operon Studio 5.1.10 — changes since 5.1.9

Released 2026-11-14. This note covers only what changed after 5.1.9.

5.1.9 already contained the Windows-safe environment commit, the extended-length
path normalization, UTF-8 child probes, and the vendored PDBFixer/resources
payload. Those are baseline here, not new in 5.1.10.

## Summary

| Area | 5.1.9 | 5.1.10 |
|---|---|---|
| Remote managed installs | `library_root()` only recognized `versions/<version>/library`; managed servers returned `None` and fell back to `operon/_no_library` | Both desktop and managed layouts are recognized |
| Environment dependency repair | `environment_prepare` checked all 1174 operators and held the plugin lock for tens of minutes | Checks only the `used_by` operators of the requested environments |
| Library content | main 0.1.1, 1174 descriptors, 79 routes | Unchanged |
| Protocol | 3 / revision 3.7 | Unchanged |

## 1. Remote managed-server libraries are recognized

### Symptom

On a managed server, `operon_environments` reported no environment manifest and
`operon_environments_prepare(["openmm81"])` returned `started: []`. The reported
fallback path was:

```text
.../operon/_no_library/operon/environments.json
```

The library itself was installed and its
`managed-v1/code-<id>/library/environments.json` existed.

### Root cause

`operon/installation.py::library_root()` only accepted
`<install>/versions/<version>/library`. A server installed by the remote installer
uses `<install>/code-<id>/library`, so the function returned `None`.
`operon/environments.py::manifest_path(None)` then fell through to
`library_location.asset_path()` and resolved the `_no_library` asset path.

### Change

`library_root()` now returns `parent / "library"` for a candidate whose
`registry.json` is a file or whose `libraries/` directory exists, covering both:

```text
<install>/versions/<version>/library
<install>/code-<id>/library
```

`_native_library_directory()` also strips the `\\?\` prefix (and restores the
`\\?\UNC\` form), so a path produced by an installed launcher still resolves.

### Verification

- Added `tests/test_library_root_layouts.py` covering both layouts.
- `pytest tests/test_library_root_layouts.py tests/test_environment_manifest_516.py`
  -> 6 passed.
- On the managed server with the patched module, the check printed the expected
  library root and manifest path and listed:
  `antifold`, `boltz`, `esm3`, `openmm81`.
- The `openmm81` descriptor resolved with `imports: ["openmm", "numpy"]`,
  Python 3.11, and pip wheels `setuptools>=68,<81`, `wheel`.

## 2. Environment preparation no longer sweeps the whole library

### Symptom

`operon_submit` timed out while returning, and `operon_jobs` never showed the
new job. The remote server appeared busy but no task had been created.

### Root cause

`environment_prepare(dependencies=True)` called:

```python
service.dependencies.check(repair=True, repair_r=True)
```

without ids. That expanded to all 1174 installed operators. The remote
`dependency-checks.log` showed a 1174-id batch starting at
`2026-11-13T19:06:08Z`, then one operator every ~3 seconds. This held the plugin
manager lock for tens of minutes, and submission waited behind it.

### Change

`operon/remote/server.py::environment_prepare` now:

1. reads the requested environment names;
2. collects each environment's `used_by` descriptors;
3. calls `dependencies.check(..., ids=ids)` with that scoped list;
4. skips the repair thread entirely when the list is empty.

Only the operators that actually need the requested environments are checked.

### Verification

- The all-operator batch no longer starts when preparing `openmm81`.
- The previous full sweep was confirmed from the remote log rather than inferred.
- The remote daemon must be restarted by the desktop client after the upgrade;
  do not start `operon.remote.server --serve` detached over SSH. It is an SSH
  stdio transport and a detached process leaves the client disconnected.

## Upgrade

1. Install `Operon_Setup-5.1.10.exe` over the existing installation.
2. Start the application once. The built-in `main` 0.1.1 library is materialized
   under the new version directory; keep the window open until the operator
   catalog finishes loading.
3. Reconnect each SSH execution profile, then run **Install / upgrade server**
   so the server receives the 5.1.10 payload and the two fixes above.
4. Existing libraries, routes, workspaces, and isolated environments are
   preserved. No operator or route re-import is required.

## Verification performed

- Installed `an isolated test install`, version `5.1.10-18f1895f8819`; the app reported
  `5.1.10`.
- Built-in library `main-v0.1.1`, 7 packages, 1174 descriptors.
- Environment manifest present at `library/environments.json` with
  `antifold`, `boltz`, `esm3`, `openmm81`.
- `tests/test_library_root_layouts.py` + `tests/test_environment_manifest_516.py`
  -> 6 passed.
- Published release `v5.1.10` (id 444662358); GitHub API reported
  `latest = v5.1.10`.

## Known issues not fixed in 5.1.10

- **First start after a version upgrade is slow.** The version-scoped base
  library is materialized on first launch. Measured on 5.1.10: backend start
  03:45:23, 7 wheels extracted by 03:45:35 (7,299 files, 44.5 MB), 1,174 operator
  metadata files and 1,174 documentation files written by 03:46:04, 5.9 MB
  `registry.json` at 03:46:05, backend ready 03:46:09, frontend ready 03:46:11.
  The catalog is empty during this window. Planned for 5.1.11: pre-materialize
  the base library in the payload or reuse a shared cache, and expose progress.
- **Persisted `venv_shared` environments can outlive their base interpreter.**
  An environment created under `versions/4.2.3-...` keeps that interpreter path
  in `pyvenv.cfg`; after the old version directory is removed it fails with
  `No Python at ...`. 5.1.10 does not repair or rebase such environments. Delete
  the stale environment and prepare it again; a rebase/recreate step is planned
  for 5.1.11.

## Artifacts

| Asset | Size | SHA-256 |
|---|---:|---|
| `Operon_Setup.exe` | 396,534,852 | `30f6ad2c6c75bc2cf0d621350a7be31f23d1c64dc7c3194e7a74cb924c464628` |
| `Operon-5.1.10-Server.zip` | 9,154,369 | `fbe392ae3aced84c260cc27275b1d962c1d9b5fffba587d3692f60f1ec45d9ae` |
| `operon_studio-5.1.10-py3-none-any.whl` | 672,838 | `f582a3df5b2e30ef3ae132bf4f771f08cdceb8c496c685fd46f9d11f808ffcf3` |

Release: https://github.com/lovegavin/Operon/releases/tag/v5.1.10

## Compatibility

- Application 5.1.10.
- `bundle_format` 1, operator protocol 3 / revision 3.7.
- Built-in library `main` 0.1.1 and route collection `main` 0.1.1 are unchanged
  from 5.1.9.
- Canvas routes remain pin-free; operators are resolved by id from the installed
  library.
