# Route collections

A route collection is a ZIP of saved routes that a user can import into a
workspace. Operon ships one for the operator library it is built with, but the
format is intentionally open: anybody can build a collection for their own
library, a fork, or a pinned subset of operators.

## What a collection contains

```
operon-routes-main-v0.1.28.zip
├── routes.json                     # [{file, key, name, sha256}]
└── routes/<name>.operon.zip        # graph.json + parameters.json + execution.json
```

`routes.json` only lists members; each member is a normal workflow bundle.

## Operator names, not packages

Route graphs are compiled from operator identifiers. On import Operon resolves
every identifier against the installed library and stores the graph without
plugin pins. The installed library is the single source of truth at run time:

- a route needs the operator id to exist in the installed library;
- package names, wheel hashes and library versions are not required to match;
- the pins a bundle was compiled with are kept in the collection manifest as
  provenance only (`routes[].pins`), never as an import gate.

This is what makes third-party collections practical. A collection authored
against `main` 0.1.28 imports into an installation carrying `main` 0.1.29 as
long as the operators it names still exist. A collection that references an
operator the installation does not have fails at import with the missing ids,
which is the only compatibility requirement.

## Pins are provenance

Before 5.4.8, importing a collection verified each graph pin against the
installed wheels. Because bundle pins carry `package`/`version`/`code_sha`
while wheel descriptors also carry a wheel `sha256`, the comparison could not
succeed and an otherwise valid collection was rejected with

```
Required plugin versions are unavailable; install the original packages.
Unknown or wheel pins are not automatically replaced.
```

5.4.8 keeps the information and drops the gate: `strip_pins` removes
`plugin_lock` from every graph in the bundle (including nested route nodes) and
the importer records the removed pins in
`<workspace>/.studio/workflows/collections/<slug>.json`.

## Authoring a collection

1. Build routes in the canvas against the library you target.
2. Export each route as `.operon.zip` (graph, parameters, execution).
3. Put them under `routes/` and write `routes.json` with `sha256` of each
   member.
4. Zip the folder; import it under **Add operators → Route operators**.

No official packaging step or signing exists, and none is required. The
collection is reproducible because its manifest records the pins it was built
with and its member hashes; it is portable because resolution happens by
operator id.
