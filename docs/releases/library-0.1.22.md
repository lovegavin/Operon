# Operator Library 0.1.22

Released 2026-11-16. This is a library-only release; the application line is
unchanged and the repository `latest` pointer stays with the newest application
release (`v5.3.0`).

## What changed

`antibody_developability` counted isomerisation motifs as `DP` only, so it
reported zero isomerisation sites for sequences whose only such motifs were
`DG`. The liability scan in the same library flagged those sites, which is how
the defect surfaced: two operators over the same sequence disagreed, and both
scores were kept with their operator identity rather than averaged.

The panel now counts `DP` and `DG`:

```python
float(count_motif(clean, "DP") + count_motif(clean, "DG"))
```

## Evidence

| Candidate | Liability scan | Panel before 0.1.22 | Panel after 0.1.22 |
|---|---|---|---|
| round-4 design 3 (iPTM 0.904) | 1 `DG` site (D63) | 0 | 1 |
| round-4 design 4 (iPTM 0.887) | 2 `DG` sites (D14, D63) | 0 | 2 |

Re-run jobs: `req-3c121a41e225827ddfbe3f0e` (design 3) and
`req-5ab6e5d1086ce6e3dd90e454` (design 4), both submitted through MCP against
0.1.22. `docs/releases/design-loop.md` records the surrounding provenance.

## Contents

- 7 packages, **1069 operators**, **108 readers**, **1177 descriptors**, 79 routes, 0 registry errors.
- No application code is required or changed by this release; it installs on the
  same application that accepted 0.1.20/0.1.21 (`bundle_format` 1).

## Assets

| Asset | Bytes | SHA-256 |
|---|---:|---|
| `operon-library-main-v0.1.22.operon-library.zip` | 6,870,118 | `682a78491612e7f6b1c715c56f43a02cd0070b6378cec3a94f532057d8547049` |
| `operon-routes-main-v0.1.22.zip` | 201,351 | `6edce3920c3b95c165085525d8b76038fcfadd9942dc7392c97f9ae0b17d41d7` |

`operon_library_builder gate --dist` passes: bundle structure and SHA256SUMS, no
`operon` import in the builder, descriptor schemas, and all seven wheel
archives with their identity records.

## Upgrading

A library with the same `library_name` cannot be replaced in place yet
(`operon/library_install.py` reports a `library` conflict for a new label of the
same name), so the supported path is remove-then-install:

```text
operon_library_remove("main-v0.1.21")
operon_library_install(path="operon-library-main-v0.1.22.operon-library.zip")
```

The application keeps serving during the gap, but its catalog is empty until the
new library is registered.
