# Operon Studio 5.10.0

## Highlights

- **Compute-node inventory.** Every dispatch host now reports its CPU count, load,
  memory, disk headroom, GPUs and (when a Slurm client is present) the visible
  Slurm partition nodes. `GET /api/nodes`, `GET /api/v1/nodes`,
  `GET /api/nodes/{key}` and the MCP tool `operon_nodes` expose the same
  snapshot; a disconnected server stays in the list with its error instead of
  disappearing.
- **Capacity-aware automatic placement.** With execution mode `auto`, planning
  now orders eligible hosts by a documented score (free memory 0.5, CPU headroom
  0.3, disk headroom 0.2, GPU bonus 0.15) and pins each operator to the roomiest
  capable host, instead of falling back to the first host in connection order.
  Manual mode is unchanged: an explicitly selected host is never replaced.
- **Node capacity in the UI.** The execution settings show a `查看节点容量`
  panel in automatic mode; it loads on demand (no request while rendering) and
  lists each node with its score and capacity details.
- **Resource roots reach operator workers.** Operators that run in an isolated
  environment now inherit the environment variables declared by linked
  resources (`OPERON_ALPHAFOLD_DATA`, `OPERON_PROTEINMPNN_PATH`, ...), so a
  freshly installed server no longer demands paths that the resource panel
  already knows.
- **`alphafold2_code` resource.** A shared, read-only AlphaFold-2 checkout can
  be linked once per machine; it publishes `OPERON_ALPHAFOLD2_HOME`, which is
  what `alphafold2_predict`/`alphafold2_batch_predict` use to find
  `run_alphafold.py`.

## Compatibility

- Library **2.1.0** adds the `alphafold2_code` resource and exports declared
  resource roots inside environment-bridged steps; it requires Operon Studio
  5.10.0 or newer.
- One graph still dispatches to one host. Cross-host fan-out remains out of
  scope for this release; the inventory is the foundation for it.
