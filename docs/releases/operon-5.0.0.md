# Operon Studio 5.0.0

Operon Studio 5.0.0 splits the application from the operator library. The
application no longer bundles a library; users import a library ZIP and a routes
ZIP built for this application version. The library also restarts its own version
line at **0.0.0**, so the two products are tagged and released independently.

## Two-ZIP installation

Download `operon-library-v0.0.0.zip` and `operon-routes-v0.0.0.zip`, then:

1. Import the library ZIP with `install_library(zip_path)`.
2. Import the routes ZIP with `install_routes(zip_path)`.

The library import verifies the bundle checksums, installs the packaged wheels
without rewriting their entry points or metadata, registers the descriptors and
entry points, and records each package's canonical `code_sha` from the library
manifest. The routes import validates the bundle checksums and then requires every
route `plugin_lock` entry (`package`, `version`, `code_sha`) to equal an installed
library package. A missing or different pin is an error, not a silent fallback.
Route import registers the workflow graph without compiling or executing it.

No third ZIP, `pip install` or manual copy path is needed.

## Library bundle format

The library manifest declares `format: operon.library`, `bundle_format: 1`,
`library_version: 0.0.0`, operator protocol 3 (revision 3.7) and
`minimum_application: 5.0.0`. The application rejects unknown formats and bundle
formats, and checks `minimum_application` and the operator protocol before
installing anything. `code_sha` is the canonical identity; `wheel_sha256` covers
integrity only.

## Legacy 8.x libraries are rejected

Every library from the 8.x train is refused, including 8.0.10, with the legacy
format message:

```text
This library bundle uses the legacy 8.x format.
Install an operon-library-v0.0.x bundle built for Operon 5.0.0.
```

Published 8.x tags and artifacts remain immutable; they are not updated or
re-signed.

## Payload without the library

The Windows payload no longer contains `library/seed`, `library/seed/routes`,
`library/release.json`, `library/pyproject.toml`, `library/README.md` or
`operon/builtin_packages.json`. `scripts/package_release.py` copies the old
layout only when `--with-library-seed` is passed explicitly; the default build
for 5.0.0 omits the library. `library/seed` remains in the repository for
development and CI.

## Tags and versioning

- Application: `v5.0.0`
- Operator library: `operon-library-v0.0.0`

Each library ZIP declares the minimum application it supports, and each routes ZIP
pins exact library package identities. Operator protocol 3 (revision 3.7) is
unchanged, so saved workflows keep working when the installed library provides
their operators.
