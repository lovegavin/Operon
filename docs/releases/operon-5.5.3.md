# Operon Studio 5.5.3

5.5.3 turns the large-resource panel into the same card layout used by the
environment list, and makes every resource state answerable from the file
system.

## Added

- **Resource cards.** Large resources now live at the bottom of the runtime
  status panel as cards grouped by environment, with the same card design as
  the environment list. Each card shows the official directory or file name
  (`official_root`: `afdb`, `ProteinMPNN`, `RFdiffusion`, `Pfam-A.hmm`,
  `Rfam.cm`, ...), the space used, the consuming operators and the link unit.
- **Missing-file detail.** Opening a card lists the official files the resource
  expects and marks each one present or missing. For AlphaFold2 this is the
  parameter file plus the eight reference databases (`uniref90`, `uniref30`,
  `bfd`, `mgnify`, `pdb70`, `pdb_mmcif`, `pdb_seqres`, `uniprot`). The dialog
  offers *re-link this directory*, *download*, *unlink* and *close*.
- **Official-name linking.** The link dialog asks for a directory or file whose
  name matches the official one and explains what will be checked afterwards,
  so a user can point Operon at an existing `afdb` tree without copying bytes.
- **Link without an allow-list.** `link_roots` is no longer enforced when the
  manifest leaves the allow-list empty, so a cluster path such as
  `/public5/home/<user>/alphafold-2.3.1/afdb` can be linked directly.
- **Web and MCP parity.** `POST /api/v1/large-resources/{name}/link`,
  `DELETE /api/v1/large-resources/{name}/link` and the MCP tools
  `operon_resource_link` / `operon_resource_unlink` accept an optional `unit`
  and keep `profile_id` for remote agents.

## Changed

- Resource state is decided by the file system, not by a receipt: a link created
  with `ln -s` or `mklink /J` reports `linked` with `receipt: false`, a missing
  target reports `missing`, and a partially populated tree reports `partial`.
- The resource panel moved from Settings to the runtime status panel; Settings
  keeps server, output, appearance and language sections.
- `link_unit` is declared per resource in the library manifest (currently ten
  tree resources and six item resources). The UI links whole trees only.

## Fixed

- **F-24** Junction links were reported as downloaded: `Path.is_symlink()`
  returns false for a Windows junction, so a manually linked directory looked
  like a local copy. Reparse tags are now checked directly
  (`st_reparse_tag == 0xA0000003`) and a junction is unlinked as a junction.
- **F-25** `official_root` was missing from the resource snapshot, so cards
  could not name the directory the user is expected to link.
- **F-26** AlphaFold2 declared a single parameter file, so a complete `afdb`
  tree still reported every database as present. The manifest now declares the
  nine official entries.
- **F-27** `check_resource` compared only the legacy `files` list while the
  snapshot advertises `expected_files`, so a resource with both fields reported
  one file and the card dialog marked the other eight as present. The check now
  walks `expected_files(resource)`, so every declared entry appears in `files`
  with its real presence.

## Verification

Clean install of the released build, then a headless server on a spare port:

- `/api/v1/large-resources` returns sixteen resources, each with
  `official_root`, `link_unit`, `state`, `link_target`, `root_linked`,
  `root_target` and `units`; `alphafold2` reports `official_root: "afdb"` with
  nine expected files and state `missing`.
- State distribution on a fresh profile: one linked, two downloaded, one
  partial, twelve missing; a junction created with `mklink /J` is reported as
  `linked` with `receipt: false`, and unlinking returns it to `missing`.
- The runtime panel renders sixteen resource cards grouped by environment with
  the official name on each card; the AlphaFold2 detail dialog lists the nine
  official entries with missing markers and offers re-link, download, unlink.
- Remote resource endpoints answer `404` with
  `找不到服务器连接配置。` for an unknown profile.

Library `main-v0.1.30` carries the manifest change; the application release
records `5.5.3`.
