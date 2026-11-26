# Operon for contributors

You are adding an operator, a Reader, a route or an engine fix. The contract is
written down, and the tooling checks it; start from the declaration rather than
from a copied file.

## The rule that shapes everything

An operator or Reader is a literal class declaration. Next to it live a separate
JSON parameter schema and an adjacent Markdown document. The registry compiles
those into a content hash, and the hash is what a saved workflow pins. That is
why:

- the implementation class is the single source of truth for ports and types;
- generated indexes are never edited by hand — `operon registry build` writes them;
- a documentation-only change must not change execution identity.

Read [operator_protocol.md](../operator_protocol.md) and the SDK pages before
writing code: [sdk_quickstart.md](../sdk_quickstart.md),
[sdk_reference.md](../sdk_reference.md).

## A first operator

The walk-through is `examples/` — `examples/dropins/scale.py` is a complete
single-file operator, and `examples/resource_plugin` shows a disk Reader with a
bounded stream:

```bash
python -m operon plugin init lab_scale
python -m operon plugin check  <source>
python -m operon plugin test   <source>
python -m operon plugin build  <source>
```

`plugin init --template reader` starts a Reader instead. To ship into the bundled
library, the seed lives under `library/seed/`: `src/task/step/steps/` (class,
schema, doc), `src/reader/readers/`, `routes/`, and the package metadata in
`library/seed/operon/`.

## Readers, steps, extensions

- [reader_extensions.md](../reader_extensions.md) — file formats and readers.
- [step_extensions.md](../step_extensions.md) — a step that is not a full operator.
- [library_extensions.md](../library_extensions.md) — distributing a library branch.
- [package_protocol.md](../package_protocol.md) — what a package may declare.
- [plugins.md](../plugins.md) — local plugin development and enable/disable.

## Validate before you send it

```bash
python -m operon registry check          # declaration, ports, hashes, docs
python -m pytest tests/test_contracts.py -q
python scripts/build_operator_docs.py    # only when authoring metadata changed
```

The five layers of evidence are defined in
[verification/five-layer-test-standard.md](../verification/five-layer-test-standard.md);
a claim about behaviour needs the layer it was tested at plus the tree it was
tested on.

## What belongs where

The application and the bundled library are separate release lines that live in
one tree. Application changes stay outside `library/seed/`; operator code, its
sidecars and template routes belong inside it. Preserve existing v3 entry-point
names and do not raise the application version for a library-only change:
[application_library_boundary.md](../application_library_boundary.md).

## Documentation

Prose is English, links are relative, and pages do not link into `library/seed/`.
New pages are registered in [docs/README.md](../README.md) — grouped by the reader
they are for, not by the month they were written.
