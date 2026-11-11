# Operator library extension forms

This guide describes every supported way to extend the Operon operator library in
Operon Studio 4.0.2 and later. The application ships the **8.0.2** library and
requires **8.0.0 or newer**. It is written for library maintainers and for authors
who publish independent providers, routes, or complete libraries.

## Protocol and SDK status

The wire protocol is still **protocol 3**. The SDK is **3.7.0**. Moving the
application from 3.1.9 to 4.0.0 did not create a new wire major or a new SDK
major; it changed the bundled library and made the 8.x library the supported
baseline.

New declarations use:

```python
protocol_version = 3
protocol_revision = "3.7"
```

Every new operator and Reader must declare both `data_formats.inputs` and
`data_formats.outputs`, including `[]` for a Reader input or a report-only
operator output. Older v3 declarations remain readable, but new packages should
not rely on inferred formats. Use the static inspection and migration commands in
[data formats](data_formats.md) and [format migration](format_migration_v37.md).

There is no `biopipe` compatibility layer. A package that contains
`sources/biopipe/**`, imports `biopipe`/`biopipe_sdk`, or uses the old package IDs
is rejected. Rebuild it with the current names before publishing.

## Choose an extension form

| Form | Use it for | Distribution | Install/import |
| --- | --- | --- | --- |
| Single Python operator | One atomic calculation | Source tree or provider wheel | Refresh or `operon plugin install` |
| Step operator | Advanced execution with explicit export | Source tree or provider wheel | Same |
| Reader | A new file format or representation | Source tree or provider wheel | Same |
| Script operator | A small workflow-local calculation | Workflow JSON, then promoted | Workflow import, then package build |
| Route operator | A reusable graph with typed inputs/outputs | `.operon.zip` or a route collection `.zip` | Route import |
| Provider wheel | A versioned group of operators/Readers | `.whl` | Library manager or CLI |
| Complete library | A tested replacement library | `.operon-library.zip` | Library manager or CLI |

The forms are independent. A provider wheel can contain operators and Readers; a
complete library contains the provider and Reader sources, indexes, and
packaged provider wheels that make up a release; route templates are distributed
separately.

## 1. Single operator

An operator owns its implementation, its adjacent parameter schema, and its
Markdown documentation:

```text
pca.py
pca.parameters.json
pca.md
```

The class carries a literal `definition` dictionary. It must not compute values,
call functions, or import modules inside that dictionary; the static tools read
the AST and JSON without executing module top-level code.

```python
from operon_sdk import Operator, port

class PCA(Operator):
    definition = {
        "protocol_version": 3,
        "protocol_revision": "3.7",
        "id": "pca",
        "version": "1.0.0",
        "kind": "operator",
        "title": "Principal component analysis",
        "contracts": {
            "version": 1,
            "inputs": [{"name": "matrix", "contract": {"ndim": 2}}],
            "output": {"kind": "form", "ndim": 2},
        },
        "data_formats": {
            "inputs": [{"kind": "form", "ndim": 2}],
            "outputs": [{"kind": "form", "ndim": 2}],
        },
        "parameters_file": "pca.parameters.json",
        "category": "analysis",
    }

    def compute(self, inputs, params, context):
        ...
```

Use `port(...)` and the parameter JSON for the interface. Do not duplicate
`parameters_schema` or `ui_defaults` in the class. The parameter JSON is the
authoring schema; saved routes freeze their own values and jobs record the values
they actually used. A later default change does not rewrite a saved route.

The Markdown file is part of the package and is indexed by the SDK. It should
state the scientific purpose, assumptions, input requirements, parameter choices,
and interpretation of outputs, not just repeat the parameter table.

## 2. Step operator

Use `Step` when the calculation needs explicit control over outputs or an export
phase:

```python
from operon_sdk import Step, port

class Quantify(Step):
    definition = {
        "protocol_version": 3,
        "protocol_revision": "3.7",
        "id": "quantify",
        "version": "1.0.0",
        "kind": "operator",
        "title": "Quantify features",
        "contracts": {
            "version": 1,
            "inputs": [{"name": "matrix", "contract": {"ndim": 2}}],
            "output": {"kind": "form", "ndim": 2},
        },
        "data_formats": {
            "inputs": [{"kind": "form", "ndim": 2}],
            "outputs": [{"kind": "form", "ndim": 2}],
        },
        "parameters_file": "quantify.parameters.json",
    }

    def run(self, ctx, inputs):
        ...

    def export(self, ctx):
        ...
```

Keep output ports fixed and declared. Report-only terminals have no data output;
native `FileArtifact` outputs remain file-backed. See
[step extensions](step_extensions.md).

## 3. Reader

A Reader converts an external file into a `Form` or a supported native bridge:

```python
from operon_sdk import Reader, reader_contract

class MyMatrixReader(Reader):
    definition = {
        "protocol_version": 3,
        "protocol_revision": "3.7",
        "id": "my_matrix",
        "version": "1.0.0",
        "kind": "reader",
        "title": "My matrix reader",
        "contracts": {"version": 1, "inputs": [], "output": {"kind": "form", "ndim": 2}},
        "data_formats": {"inputs": [], "outputs": [{"kind": "form", "ndim": 2}]},
        "extensions": [".mymatrix"],
        "parameters_file": "my_matrix.parameters.json",
    }

    def read(self, path, dims, labels, **args):
        ...
```

Declare `extensions` or a stronger `file_input` hint only when the Reader really
owns that format. Do not claim a lossless conversion that the code does not
perform. For zero-copy mapped arrays, use `NativeArray` and the supported SDK 3.7
bridge; a filename alone is not evidence of a Form conversion. See
[Reader extensions](reader_extensions.md).

## 4. Script operator

A workflow-local script is the smallest authoring form. It can start without
sidecar files and is executable inside a saved workflow. Promotion turns it into
an ordinary package with a real descriptor, parameter JSON, and Markdown:

```bash
operon plugin init my_operator
# edit my_operator.py, my_operator.parameters.json, my_operator.md
operon plugin build my_operator --output build/packages
```

Do not leave a promoted operator as an untracked script. Promotion is what gives
the operator a stable ID, version, documentation entry, and package hash. See
[script operators](script_operators_v3.md).

## 5. Route operator

A route operator is a saved graph with a typed interface. It is a separate form
from a Python operator and does not add a new protocol version.

A single route package is a `.operon.zip` with this layout:

```text
my_route.operon.zip
  route.json          # key/name and route metadata
  task.yaml           # the graph and its interface
  parameters.json     # the route's saved parameter values
  README.md           # optional explanation
  meta.json           # optional presentation metadata
```

A **route collection** is one ordinary `.zip` container. Operon scans any path
component named `route` or `routes` and imports every entry whose name ends in
`.operon.zip`:

```text
routes-8.0.2.zip
  route/
    gwas.operon.zip
    survival.operon.zip
    proteomics_de.operon.zip
  README.md
```

Import the container as a whole; do not preselect individual files. The importer
saves and registers each route independently and returns both successful routes
and per-route errors. A failed route does not roll back the routes that did
register. Paths must be safe relative names; encrypted, oversized, and traversal
entries are rejected.

The equivalent API is `POST /api/routes/import-archive`. A single `.operon.zip`
continues to use the ordinary workflow import path. See
[route operators](route_operators.md) and
[importing libraries and routes](library_import_compatibility.md).

## 6. Provider wheel

A provider wheel groups related operators and Readers and is the recommended unit
for third-party distribution. Build it from a source directory that contains the
literal declarations and adjacent JSON/Markdown files:

```bash
operon plugin init my-provider
operon plugin build my-provider --output build/packages
operon plugin install build/packages/my_provider-1.0.0-py3-none-any.whl
```

A protocol v3 wheel contains an `operon.json` manifest inside the wheel. It
declares `name`, `version`, `protocol_version: 3`, `origin`, dependencies, and
descriptors. The wheel metadata remains authoritative for pip dependencies, and
the manifest identity must match it. Bundled provider names own their established
IDs: a replacement package must preserve those IDs, while third-party packages use
a namespaced provider such as `lab.scale`.

Installed wheels are immutable generations. Disabling or removing a provider
affects new, unpinned graphs; saved jobs retain their pinned implementation. See
[package protocol](package_protocol.md) and [library management](plugins.md).

## 7. Complete operator library

A complete library is a versioned replacement of the operator and Reader
sources, not a wheel and not a generic ZIP of miscellaneous files. Use the
`.operon-library.zip` suffix:

```text
Operon-Library-v8.0.2-Windows.operon-library.zip
  library.json
  packages/operon_core-1.0.0-py3-none-any.whl
  packages/operon_readers-1.0.0-py3-none-any.whl
  ...
  sources/operon/builtin_packages.json
  sources/src/task/step/steps/...
  sources/src/reader/readers/...
```

`library.json` declares the library version, protocol version, minimum
application, package list, and a checksum for every file. The archive must
contain only the native `sources/operon/**` and `sources/src/**` trees;
`sources/biopipe/**` is not accepted. Route templates are **not** part of this
archive: they are built into the application or distributed as a separate route
collection. The manifest data lives in `library.json` and the provider index;
there is no separate `manifest.json` entry.

Build and verify it with the maintenance tools from the released application:

```bash
python -I scripts/release_library.py --output build/library --tag library-v8.0.2
python -I scripts/verify_library_release.py \
  --bundle build/library/Operon-Library-v8.0.2-Windows.operon-library.zip \
  --work build/library-verify
```

The library manager accepts `.whl` and `.operon-library.zip` only for the main
operator library. A generic `.zip` is reserved for route collections and must not
be accepted as a complete library. See
[library releases](library_releases.md) and
[importing libraries and routes](library_import_compatibility.md).

## 8. Data formats and contracts

`data_formats` describes what the code actually reads and writes; `contracts`
describes the logical interface used by graph validation. Keep logical types and
physical representations separate. `Form` is the default port kind; a
`FileArtifact` is an explicit file-backed output.

For SDK 3.7 declarations:

- `data_formats.inputs` and `data_formats.outputs` are required arrays.
- A Reader has no data inputs: `inputs: []`.
- A report-only operator has no data outputs: `outputs: []`.
- Use `ndim`, `dims`, and `kind` consistently with the implementation.
- Do not add a format declaration just to silence validation; the scanner and
  validator treat contradictory code as review-required.

Inspect an existing tree without importing it:

```bash
operon registry formats path/to/operators > format-review.json
operon registry formats path/to/operators --apply
```

The apply step creates `.pre-sdk37` backups and never changes implementation
bodies or parameter values. Rebuild the static registry and run representative
workflows before publishing. See [data formats](data_formats.md) and
[format migration](format_migration_v37.md).

## 9. Registry, packaging, and verification

After adding or changing declarations, regenerate the static registry and route
indexes:

```bash
operon registry build
operon registry check
operon registry discover
```

For a bundled library, the release builder refreshes the provider index and route
templates before packaging:

```bash
python scripts/build_builtin_packages.py --refresh
python scripts/build_builtin_routes.py build
```

A direct source tree must match the descriptor hashes used at runtime. If a
library is assembled from sources but the manifest still carries a provider-wheel
`code_sha`, loading can fail with `Implementation code hash mismatch`. Rebuilding
the index and provider descriptors from the source tree is required before
publishing.

Minimum acceptance for a new library:

1. Install it into a clean profile; `operon plugin list` shows the expected
   providers and versions.
2. Start the headless server; all built-in routes either install or are reported
   with a specific incompatibility, and the registry contains the expected
   count.
3. Import the complete route collection as one ZIP; successful and failed routes
   are reported separately.
4. Run one representative route end to end and inspect its artifact and report.
5. Run `operon registry check` and the focused library, route, package, and
   desktop tests.

## 10. Versioning and release rules

- The application version and library version are independent. A 4.0.0
  application may ship an 8.0.2 library.
- A library declares `minimum_application` and `build_application`; both must be
  tested, and a newer SDK feature may require a newer application.
- Operator/provider versions express interface changes. Do not bump the
  application version for an operator-only library update.
- Never move a published tag. Rebuild a failed library on a new version.
- Publish the Windows and Linux library bundles separately; do not attach the
  application payload or unrelated wheels to a library release.

## Common errors

| Symptom | Cause | Action |
| --- | --- | --- |
| `Unexpected library file: sources/biopipe/builtin_packages.json` | Legacy 7.x bundle still contains the old source tree | Rebuild the library with `sources/operon/**` only |
| `Required plugin versions are unavailable` when adding a route | Route pins a different library generation | Install the matching library, or rebuild the route against the active library |
| `Choose a Reader ... multiple Readers match` | Two Readers claim the same extension and no stronger contract disambiguates | Declare `dims`/formats or narrow the Reader `extensions`; do not rely on file suffix alone |
| `Implementation code hash mismatch` | Manifest was built from wheels but sources were replaced | Refresh indexes/descriptors from the final source tree |
| Route collection imports nothing | The outer ZIP has no `route/` or `routes/` entry ending in `.operon.zip` | Put route bundles under `route/` and import the container as one file |

## Related pages

- [Operator protocol](operator_protocol.md)
- [SDK reference](sdk_reference.md)
- [Package protocol](package_protocol.md)
- [Reader extensions](reader_extensions.md)
- [Step extensions](step_extensions.md)
- [Script operators](script_operators_v3.md)
- [Route operators](route_operators.md)
- [Library releases](library_releases.md)
- [Importing libraries and routes](library_import_compatibility.md)
- [Registry maintenance](registry_maintenance.md)
