# Operon Studio 5.5.3

## Added

- Large resources are now part of the **Runtime status** panel: pick an execution
  location, review the resources grouped by the environment whose operators
  consume them, and expand a resource to see the databases or weights it is
  missing. The separate *Large resources* page has been removed from settings.
- Every resource declares `link_unit`: `tree` for a directory upstream publishes
  as one framework (AlphaFold-2 `afdb`, ProteinMPNN, RFdiffusion, its databases),
  `items` for resources upstream ships as loose files (ESM-2, ESM-IF1, ESMFold,
  ColabFold, Prodigal, AntiFold). A `tree` resource links or unlinks its root; an
  `items` resource links or unlinks each declared file.
- `POST /api/resources/{name}/link` and `DELETE /api/resources/{name}/link`
  accept `unit`; the control plane, the agent bridge, the remote agent dispatch,
  the remote HTTP routes and the MCP tools `operon_resource_link` /
  `operon_resource_unlink` forward it, so a single unit can be linked on this
  machine or on a connected server.

## Changed

- Linking no longer asks for an allow-list: any readable absolute path can be
  linked. The remaining checks are the ones that protect the user — the source
  must be absolute, must exist, must not be the resource root or contain it, and
  an existing target must be replaced explicitly.
- Link state is decided by the file system, not by the receipt. A link created
  with `ln -sfn` or `mklink /J` outside Operon is reported as linked, shows its
  target, and can be removed from the UI; the receipt is only extra provenance
  (`receipt: false` means Operon did not create it).
- Resource rows report one of `missing`, `downloaded`, `linked` or `partial`,
  with the link target next to the badge, and show the link unit and the number
  of operators that consume the resource.

## Fixed

- F-22 — With more than one missing environment the resource dialog could offer
  a resource that the selected environment does not use, and the environment list
  included environments without any linkable resource; the list now only offers
  environments that still have a missing resource, and narrowing to an
  environment narrows the resources.
- F-23 — A resource linked by hand was reported as missing because the receipt
  was the only thing consulted; the state now comes from the file system, so
  manual links are visible and removable.
- F-24 — On Windows a link created as a junction was reported as downloaded,
  because link detection only recognised symlinks and hard links. The reparse
  tag is read as well now (`0xA0000003` is a junction), and a linked root marks
  every unit below it as linked, so a link made outside the UI shows up as
  `已链接` with its target and can be removed from the same row.

## Verification

- `pytest tests/test_resource_units.py tests/test_remote_resources.py
  tests/test_resource_api.py tests/test_resource_link_control_api.py
  tests/test_bridge_remote_resources.py tests/test_environment_install.py` =
  49 passed.
- Library checks (`test_manifest_registry`, `test_registry_layout`,
  `test_registry_maintenance`, `test_builtin_routes`) pass after the registry
  rebuild that the operator-library change requires.
- `npm test` = 43 files, 266 tests passed; `npm run build` succeeds.
- Clean install of the release reports `5.5.3`; on the lab server a resource root
  linked with `ln -sfn` is shown as linked with its target, and unlinking it from
  the UI removes only the link.

## Operator library

`main-v0.1.30` declares `link_unit` per resource and reports `state`,
`root_target` and per-unit status from the file system. The application still
works with `main-v0.1.29`, where the link dialog only offers whole-tree links.
