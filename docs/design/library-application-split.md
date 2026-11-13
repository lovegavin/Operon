# Library and Application Separation

Status: proposed refactor. Supersedes the library 8.x release train.
Target tags: `operon-library-v0.0.0` (library), `v5.0.0` (application).

## 1. Decision

The current library release has a build-time dependency on the application
Python package. `scripts/release_library.py` imports the installed `operon`
package and calls `build_bundle()` and `provider_wheel()`. The library wheel,
the manifest and the route pins therefore acquire identities from different
code paths.

This design removes that dependency:

- The library repository owns the canonical source, descriptors, routes and
  the release builder.
- The application repository consumes two immutable ZIP files and contains
  only installation, validation and execution logic.
- The library is reset to `0.0.0`. The tag namespace is
  `operon-library-v*`.
- The application is released as `5.0.0`.
- The user-facing workflow remains: import the library ZIP, import the routes
  ZIP, then let the application install, register, prepare environments and
  execute. No user-side Python, pip or path setup is required.

The existing 8.0.10 release remains immutable and is treated as legacy. The
unpublished 8.0.11 work is abandoned rather than shipped with a version
(4.2.5) that does not exist.

## 2. Problem being removed

The observed failure is an identity mismatch:

- The installed library manifest carried one `code_sha` value.
- The route bundle `plugin_lock` carried a different value.
- The application's route import path did not refresh pins, and the values
  could not be proven equivalent, so import failed.

The deeper cause is architectural:

1. The library cannot build its own release artifact.
2. The application rewrites wheel entry points and recomputes identity.
3. Source, wheel and route packages are built at different times from
   different inputs.
4. There is no single release gate that compares all three.

A change in application packaging code can therefore invalidate an already
published library. That must not be possible after this refactor.

## 3. Goals and non-goals

### Goals

- Build the library without importing the application package.
- One canonical identity per package, reused by manifest, wheels and routes.
- Two user-visible ZIP files only: library and routes.
- Generic application installer; no library-specific build logic at runtime.
- Reproducible library builds and a release gate with zero mismatch.
- Clear version/tag namespaces and independent release cadence.
- Clean installation and execution on Windows and Linux without a user shell.

### Non-goals

- Changing the operator protocol v3 or `data_formats` semantics.
- Changing biological algorithms or operator IDs in this refactor.
- Preserving import compatibility with 8.x library bundles in application
  5.0.0. Legacy bundles must fail with an explicit migration message.
- Eliminating the need for a documented bundle/protocol contract. The
  contract is the separation boundary; it is not a build dependency.

## 4. Repository and ownership boundary

Recommended layout (separate repositories):

```text
operon-library/                    application: Operon/
  src/operon_library/                operon/                 engine
  operators/                         src/web/                installer/API
  readers/                           frontend/               UI
  routes/                            tests/
  contracts/                         docs/
  tools/operon_library_builder/      scripts/
  tests/
  docs/
```

Ownership:

| Concern | Library | Application |
|---|---|---|
| Operator/Reader source | yes | no |
| Descriptor schema and docs | yes | reads only |
| Bundle format | defines, versioned | reads only |
| Canonical identity | computes | reads only |
| Wheel contents/entry points | builds | installs, never rewrites |
| Routes and route pins | builds | imports, never regenerates |
| Install/load/run | no | yes |
| Environment installation | declares | executes |
| Release gate | yes | consumes evidence |

The application may depend on a tiny shared `operon-contracts` package that
contains JSON Schemas and protocol constants. It must not depend on the
library builder. The builder must not import `operon`.

## 5. Contract A: library ZIP

File name:

```text
operon-library-v0.0.0.zip
```

This is one universal pure-Python bundle. It is not duplicated per operating
system. Platform-specific dependencies belong in environment declarations,
not in the library ZIP.

Layout:

```text
operon-library-v0.0.0.zip
  library.json
  descriptors.json
  environments.json
  wheels/
    operon_core-0.0.0-py3-none-any.whl
    operon_readers-0.0.0-py3-none-any.whl
    ...
  docs/
  SHA256SUMS
```

### library.json

```json
{
  "format": "operon.library",
  "bundle_format": 1,
  "library_version": "0.0.0",
  "operator_protocol": {"version": 3, "revision": "3.7"},
  "minimum_application": "5.0.0",
  "builder": {"name": "operon-library-builder", "version": "1.0.0"},
  "packages": [
    {
      "name": "operon-core",
      "version": "0.0.0",
      "wheel": "wheels/operon_core-0.0.0-py3-none-any.whl",
      "wheel_sha256": "...",
      "code_sha": "...",
      "entry_points": {
        "interface_alanine_scan": "operon_core.steps.interface_alanine_scan:InterfaceAlanineScanStep"
      }
    }
  ]
}
```

Rules:

- `bundle_format` is owned by the library and changes only for structural
  changes.
- `operator_protocol` follows the existing protocol version, currently 3.
- `code_sha` is the canonical identity. The application must not recompute it
  from installed bytes.
- `wheel_sha256` is integrity only, not identity.
- Entry points are canonical module paths. The application imports exactly
  these paths. No `provider_wheel` rewrite is allowed.

## 6. Contract B: routes ZIP

File name:

```text
operon-routes-v0.0.0.zip
```

Layout:

```text
operon-routes-v0.0.0.zip
  routes.json
  routes/
    assembly_ngx_qc.operon.zip
    ...
  SHA256SUMS
```

Each route ZIP keeps the existing three-member format:
`graph.json`, `parameters.json`, `execution.json`.

Every `plugin_lock` entry in `execution.json` must copy the package identity
from the same library build:

```json
{
  "package": "operon-core",
  "version": "0.0.0",
  "code_sha": "..."
}
```

No wheel `sha256` in the pin. The route builder receives the library manifest
as its only source of identity. It must not query an installed application.

## 7. Contract C: application installation and loading

Application 5.0.0 exposes generic operations:

```text
install_library(zip_path) -> LibraryInstall
install_routes(zip_path)  -> RouteInstall
```

`install_library`:

1. Verify `SHA256SUMS` and optional signature.
2. Read `library.json`; reject unknown `format`/`bundle_format`.
3. Check `minimum_application` and `operator_protocol`.
4. Install each wheel into the managed environment with the existing plugin
   installer. Do not rewrite entry points or metadata.
5. Register descriptors and the canonical entry points.
6. Record `{library_version, code_sha, install_root}`.

`install_routes`:

1. Read `routes.json`, verify checksums.
2. For each route, read `execution.json`.
3. Require every pin's `(package, version, code_sha)` to equal an installed
   library package. A missing or different value is an error; no silent
   fallback.
4. Register the graph; do not compile or execute as part of import.

The application may provide an explicit migration tool for a legacy 8.x
workflow, but import itself must not guess or repair pins.

## 8. Library builder

New package in the library repository:

```text
operon_library_builder/
  identity.py     canonical hash
  wheel.py        wheel assembly
  descriptors.py  descriptor extraction
  routes.py       route assembly and pins
  gate.py         manifest/wheel/routes consistency
  cli.py          build, verify, gate
```

Commands:

```bash
python -m operon_library_builder build  --source . --output dist/
python -m operon_library_builder verify --dist dist/
python -m operon_library_builder gate   --dist dist/
```

Requirements:

- No `import operon` and no dependency on an installed Studio.
- Deterministic file ordering and timestamps (or a documented reproducible
  zip policy).
- Identity is computed once, before wheels and routes.
- `gate` fails on any manifest/wheel/route identity mismatch, missing
  descriptor, or duplicate entry point.

### Identity definition

For each package, hash a sorted list of relative paths and file bytes:

```text
sha256( for each file: path + "\0" + content + "\0" )
```

Excluded: `__pycache__`, `*.pyc`, build output, test caches, VCS metadata.
The exact algorithm and exclusion list are part of `bundle_format=1`.

The same value is written to:

- `library.json` package record;
- the wheel's generated `operon_identity.json`;
- every route pin for that package.

## 9. Application 5.0.0 changes

Remove from the application runtime:

- `operon.library_bundle` as a library build dependency;
- `source_library.provider_wheel()` identity rewriting;
- `load_entry_point`/`load_code_sha` workaround fields;
- any route import path that calls a library-specific pin repair.

Keep or add:

- generic ZIP validation and checksum verification;
- generic wheel installation;
- canonical entry point loading;
- exact pin comparison;
- environment declaration execution;
- clear errors for legacy bundles.

Application version 5.0.0 is a major release because old 8.x bundles are not
accepted. The error must state the required pair, for example:

```text
This library bundle uses the legacy 8.x format.
Install an operon-library-v0.0.x bundle built for Operon 5.0.0.
```

## 10. Versioning and tags

| Artifact | Version | Tag |
|---|---|---|
| Library | `0.0.0` | `operon-library-v0.0.0` |
| Application | `5.0.0` | `v5.0.0` |
| Bundle format | `1` | not a release tag |
| Operator protocol | `3` / revision `3.7` | unchanged |

Rules:

- Library tags must match `^operon-library-v[0-9]+\.[0-9]+\.[0-9]+$`.
- Application tags must match `^v[0-9]+\.[0-9]+\.[0-9]+$`.
- Old `library-v8.*` tags remain immutable and are not reused or moved.
- Library and application release independently. A library patch does not
  require an application release unless the bundle format or protocol
  compatibility changes.
- `minimum_application` is a real, existing version. A library must not
  require a future application release.

## 11. Two-ZIP user workflow

The complete import workflow is:

1. Download `operon-library-v0.0.0.zip`.
2. Download `operon-routes-v0.0.0.zip`.
3. In the application, choose **Import library** and select ZIP 1.
4. Choose **Import routes** and select ZIP 2.
5. The application installs wheels, registers operators, validates pins,
   prepares declared environments and runs the routes.

No additional ZIP, installer script or manual `pip` command is required for
normal use. Optional quickstart/audit artifacts may be published separately,
but they are not part of the import contract.

## 12. CI and release gates

Library CI:

1. Unit, contract, composition and route tests.
2. Build twice; require identical artifact hashes.
3. `gate`: manifest/wheel/routes identity mismatch `0`.
4. Check that the builder has no `operon` import.
5. Verify descriptors and docs are complete.
6. Publish only the two required ZIPs plus checksums.

Application CI:

1. Download the latest published library and routes ZIPs.
2. Install them into a clean 5.0.0 profile.
3. Import both ZIPs; assert no manual pin repair.
4. Run a fixed smoke route set.
5. Upgrade the application patch version; import the same ZIPs again.
6. Assert that neither ZIP changed and no rebuild occurred.

Release acceptance is not satisfied by building from a source tree. It must
use the frozen published ZIPs in a clean profile, as required by
`docs/verification/five-layer-test-standard.md`.

## 13. Migration plan

### Phase 0 - freeze

- Keep 8.0.10 immutable; do not publish 8.0.11.
- Tag the current application state if needed as a legacy reference.

### Phase 1 - library extraction

- Create the `operon-library` repository or top-level library workspace.
- Port operators, readers, routes and docs without algorithm changes.
- Add `operon_library_builder`.
- Build `0.0.0` and run the identity gate.

### Phase 2 - application installer

- Add generic `install_library`/`install_routes`.
- Remove builder calls from runtime.
- Reject legacy 8.x bundles with an explicit message.

### Phase 3 - release

- Publish `operon-library-v0.0.0` with the two ZIPs.
- Publish application `v5.0.0`.
- Run the clean-profile acceptance on Linux and Windows.

### Phase 4 - cleanup

- Delete obsolete builder code and old release scripts.
- Update docs and CI.
- Keep a migration note for 8.x users.

## 14. Test matrix

| Area | Test |
|---|---|
| Builder isolation | import guard: builder must not import `operon` |
| Identity | source, wheel and route pins equal; mismatch gate fails |
| Reproducibility | two clean builds produce identical ZIP SHA256 |
| Install | library ZIP installs into a clean 5.0.0 profile |
| Routes | routes ZIP imports with zero pin repair |
| Execution | at least 8 representative routes run |
| Upgrade | app 5.0.1 imports the same library/routes ZIPs |
| Negative | tampered ZIP, wrong protocol, missing pin, legacy 8.x ZIP |
| Platforms | Linux and Windows clean profiles |

## 15. Confirmed decisions

- **Separate repositories.** `operon-library` and `Operon` are developed and
  released independently. The library builder must not import the
  application; the application must not build or rewrite the library.
- **Application 5.0.0 rejects all old libraries.** Any `library-v8.*`
  bundle, unknown `bundle_format`, or incompatible operator protocol is
  rejected with an explicit migration message. There is no silent pin
  repair and no legacy read path in 5.0.0.
- **Per-package identity.** A change in one wheel does not invalidate every
  route; each package has its own canonical `code_sha`.
- **One universal library ZIP.** The library is pure Python; platform
  dependencies belong in environment declarations, not separate library
  ZIPs.
- **No signing in the first cut.** SHA256SUMS is mandatory; signing can be
  added without changing the bundle contract.
- **Preserve operator namespaces in 0.0.0.** Avoid a 1063-operator rename;
  only the builder, identity and installation layers change.

## 16. Definition of done

- Library builds with no application import.
- `operon-library-v0.0.0` and `v5.0.0` exist with immutable artifacts.
- The two ZIPs install and run on clean Linux and Windows profiles.
- Manifest, wheel and route identities have zero mismatch.
- Application upgrade does not require rebuilding the library.
- Legacy 8.x import fails with a clear, documented migration message.
