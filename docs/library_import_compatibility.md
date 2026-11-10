# Importing independently published libraries and routes

Use **Add operators → Import package** for `.whl`, `.operon-library.zip` or legacy
`.operon-library.zip` files. The two library suffixes are transport aliases for
the same v3 library envelope, with either `operon.library` or `operon.library`
as its format. Archive checksums, safe paths, protocol requirements and the
source-to-wheel reproducibility check are still required.

The separate `Operon-Routes-<version>.zip` asset is a **collection**. Extract it,
then select the individual `routes/*.operon.zip` bundles in **File → Import** or
**Add operators → Route operators**. Submitting the collection or a library
bundle to the workflow importer now identifies the wrong archive type.

Individual `.operon`, `.operon.zip`, `.operon`, `.operon.zip` and `.zip` bundles
use the same validated archive path. Both branded and legacy parameter/execution
sidecars are supported. Names do not change frozen parameters, memory budgets,
source paths or graph topology. The CLI accepts the same suffix aliases. YAML
uses `operon.workflow`; old `operon.workflow` documents and sidecars remain valid.

## Provider ownership and source-authored pins

Seven official distribution renames are recognized for ownership and replacement:
`core`, `readers`, `expression`, `genetics`, `plots`, `microbiome`, and `hic`, with
either the `operon-` or `operon-` prefix. Installing the renamed distribution
replaces that provider once and preserves its disabled state. This does not give
arbitrary `operon-*` packages permission to claim built-in IDs, nor does it allow
one official provider to claim another provider's IDs. Historical packages and
saved pin hashes are not renamed in place.

A source-authored route and the wheel built from it have different code hashes:
wheel construction rewrites imports into a private provider namespace. After
rebuilding the included source into a byte-identical wheel, library installation
records a `library_source_pins` receipt. It independently verifies the full
source code-tree hash rather than trusting the source manifest's claim.

Resolution first prefers a compatible retained generation. If none exists, the
receipt can map an exact source package/version/code identity to that verified
wheel only. Declaration-only source index changes do not replace frozen values.
Unknown code, changed versions, disabled providers, a different wheel digest or
an explicit nonmatching wheel execution identity remain rejected. Standalone
wheel installation does not create this receipt. Reimporting an already installed
library can add the missing receipt as a new generation after full verification;
it does not overwrite old generation locks. New-run resolutions expose
`library_pin_updates` for provenance.

## Legacy union input contracts

A legacy v3 operator may explicitly accept `kind: [form, file]` without the newer
`data_formats` field. A connected source's declared logical type selects the
corresponding Form or FileArtifact branch. This is contract projection, not
scientific inference: matrix/list mismatches and missing contracts remain blocked.
Native-array-to-Form wrapping still requires the registered converter and runtime
type validation. The library source and its declaration files are not modified.

## Verification boundary

The regression reproducer uses the original GitHub `library-v6.0.1` Windows asset
and its separate 78-route collection, checked against published SHA256 digests.
Import/save/register tests do not run the 78 scientific analyses or establish
availability of their external tools, models or datasets. Source tests and a
frontend build are not a Windows Setup or remote Linux deployment acceptance.


The checked v6.0.1 assets contain three ambiguous source selections. The original
bundles import and save, but registering these routes requires an explicit Reader:

| Route | Input | Reader selected in the isolated acceptance copy |
| --- | --- | --- |
| `gwas` | `geno` | `VcfReader` |
| `proteomics_de` | `meta`, `proteins` | `TxtReader` |
| `survival` | `clinical` | `TsvReader` |

The original 75 other routes register directly; these three also register after
only those Reader choices. No scientific inputs were read, no tasks were started,
and the published library source/route files were not modified. Conditional v3
output contracts (`mode: choose`) are projected using their frozen parameters,
which allows the Hi-C contact-window and sequence-statistics branches to retain
accurate Form/FileArtifact declarations.
