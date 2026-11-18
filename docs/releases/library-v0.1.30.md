# Operator library main-v0.1.30

Released 2026-11-18. Requires Operon Studio 5.5.3 or newer.

This bundle makes the resource link layer operate on the official directory or
file of each resource instead of on an invented allow-list, and records the state
of a resource from the file system so links created outside Operon are reported
correctly.

- Every resource declares `link_root`, the directory or file name the upstream
  project documents (for example `afdb` for AlphaFold2 parameters, `ProteinMPNN`
  for ProteinMPNN, `Pfam-A.hmm` and `Rfam.cm` for the HMM databases). The
  application shows that name in the link dialog and in the resource card.
- `resource_link.link(resource, source, replace=False, unit=None)` accepts
  `allowed_roots=None`, which turns the legacy allow-list off; the default
  manifest value keeps the compatibility behaviour for existing callers.
  `resource_link.unlink(resource, unit=None)` and the receipts written by both
  helpers now carry the list of `units` they touched.
- `_resources_common` gains `link_unit_of`, `link_units`, `link_mode` and
  `_file_entry`; `check_resource` returns `state`, `root_linked`, `root_mode`,
  `root_target` and `units`, and `link_state` derives the state from the file
  system rather than from receipts alone, so a junction created with
  `mklink /J` or a symlink created with `ln -s` is reported as linked with
  `receipt: false`.
- `check_resource` evaluates every entry of `expected_files` (falling back to
  `files`), so a resource that is not installed lists all of its declared files
  as absent instead of only the first one.
- Resource manifest: sixteen resources with `link_unit` (`tree` for ten
  resources, `items` for six), `link_root` for all sixteen, nine
  `expected_files` for `alphafold2` (parameters, UniRef90, UniRef30, BFD,
  MGnify, PDB70, PDB mmCIF, PDB seqres, UniProt), and no `link_roots` entries
  for the resources whose upstream layout is documented as a single directory.

Contents: 7 packages, 1069 operators, 108 Readers, 1177 descriptors.
