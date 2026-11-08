# Operon naming and compatibility

The application is named **Operon** starting with the 3.0.0 candidate. BioPipe is
the earlier product name. The rename changes the product presentation, not the
meaning of a saved scientific workflow or an installed operator ID.

| Surface | Naming policy |
| --- | --- |
| Windows application, installer and shortcuts | Operon Studio; the distributable installer is `Operon_Setup.exe` and the workspace displays Operon |
| Application version | Independent of the operator-library version |
| Python package and source directories | Existing `biopipe`, `biopipe_sdk` and `src` imports remain valid |
| Command-line automation | Existing `biopipe` / `python -m biopipe` remain supported; `operon` and `python -m operon` are the branded aliases |
| MCP names | Existing `biopipe_*` tools and resource identifiers remain valid |
| HTTP routes and authentication | Existing application/agent API paths and scopes remain valid |
| Saved formats | New workflow YAML and parameter/execution sidecars use `operon.*`; exact `biopipe.*` aliases remain readable. Plugin IDs and historical implementation pins retain their identities |
| Operator protocol | Base major 3; existing v3/v3.5 packages remain accepted; optional SDK 3.6 format capabilities are independent of the product name |
| Previous evidence and documentation | Historical release names, filenames, URLs and log records retain their original spelling |

Do not rename a plugin ID, Python import or JSON discriminator merely to make it
look branded. A public identifier is an interoperability contract. The product
name in a window is display text.

New canvas exports use `.operon.zip`; older `.biopipe.zip` bundles remain importable.
Visible worker and launcher labels use Operon. New browser preferences, clipboard
fragments and drag MIME types use Operon identifiers; import reads the exact
legacy counterparts. Python imports, MCP tool identifiers and shared admission
ledger paths remain compatible. Renaming the admission directory alone would
create a second resource authority on the same machine, which is not allowed.

## Installation and old data

Setup creates a new software installation and a fresh isolated profile, then uses
its adjacent bundled Python. It must not redirect an existing BioPipe installation
to the new interpreter, rewrite its global runtime hint or silently migrate its
old plugin registry. Import saved workflows explicitly into the new workspace.
Old user profiles and analysis outputs remain available.

New Setup receipts declare `product: "operon"`; their profiles live under
`%USERPROFILE%\.operon\profiles\<installation-id>`. Receipts from older BioPipe
installations without this marker retain their original `.biopipe/profiles`
resolution. This compatibility rule does not copy old state into the fresh Operon
profile. Read the actual receipt rather than constructing the random ID yourself.

Locate the current executable, profile, workspace and logs from the current
installation receipt and desktop startup log. Do not assume that replacing the
word `BioPipe` in an old filesystem path identifies the new location. Internal
compatibility filenames can retain that spelling. No test or script should embed
a developer's home directory or machine-specific installation path.

The application and scientific library remain separate distributions. A branding
change does not require changing every scientific provider or reinstalling an
unrelated user's environments. Standard v3 library installation, refresh and
dependency preparation retain their existing responsibilities.

## Workflow file names

Studio exports a workflow bundle as `NAME.operon.zip`. Workflow import, saved-route
import, route-operator registration and the CLI also accept `.operon` and
`.biopipe` aliases, as well as `.operon.zip`, `.biopipe.zip` and `.zip`. These
aliases contain the same ZIP bundle; they are not JSON/YAML text or a new protocol.
Import still verifies the graph, frozen parameter values and execution settings.
JSON and YAML keep their existing separate import paths.

In released 3.1.2 and earlier builds, standalone `.operon`/`.biopipe` suffixes
were missing from the import dispatch. For a valid ZIP workflow bundle, renaming
a copy to `NAME.operon.zip` allows the existing archive importer to read it.
If Windows hides known extensions, check the full file name first. A file already
ending in `.operon.zip` does not need this workaround; inspect the actual import
error instead. Renaming a non-bundle file does not convert its contents.

This filename workaround does **not** repair all library-v6.0.1 imports in released
3.1.2. Its routes also use `operon.*` sidecars and source-authored pins. See
[library import compatibility](library_import_compatibility.md) for the separate
transport, provider ownership and verified source/wheel fixes in the working tree.

## Acceptance boundary

The [3.0 acceptance guide](OPERON_3_TEST_ACCEPTANCE.md) checks actual Setup and
shortcut launches, preserved BioPipe state, version/title visibility, legacy
automation, new authoring features and uninstall behavior. A passing source test
or a renamed executable alone is not evidence that the installer passed.

The 3.0 candidate does not claim a universal standalone scientific exporter,
automatic provisioning for every script dependency, or Windows verification of
Linux-only tools. See [implementation scope](V3_IMPLEMENTATION.md) before writing
release notes.
