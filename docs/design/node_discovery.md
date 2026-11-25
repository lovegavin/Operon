# Compute-node discovery and allocation (5.10.0)

The desktop can dispatch to the local host and to every saved SSH server. Until
5.10.0 the graph target was chosen manually and automatic placement used the
order `ExecutionService.infos()` returned (local first, then servers as listed),
so a busy local host always won.

## What a node reports

`operon.nodes.snapshot(root)` measures one host:

- `cpu_count` and `load` (1-minute average when the platform provides it);
- `memory.total_bytes` / `memory.available_bytes`;
- `disk.total_bytes` / `disk.free_bytes` for the workspace root;
- `gpus`, counted from `/dev/nvidia*`;
- `slurm` with `sinfo` nodes (name, partition, availability, state, CPUs,
  memory, GRES) and the idle count, or `available: false` without Slurm.

`host_capacity` in `operon/remote/server.py` returns that snapshot for a
managed server. The desktop caches inventories for 20 seconds
(`operon.nodes.CACHE_SECONDS`); `refresh=true` bypasses the cache.

## How auto placement uses it

`nodes.score` combines free memory (0.5), CPU headroom (0.3), disk headroom
(0.2) and a 0.15 GPU bonus. In `mode: "auto"` only, `ExecutionService.infos`
orders candidates by availability and then score, so `make_plan` assigns each
node to the host with the most headroom. Manual mode and explicit per-node
targets are untouched, and the chosen host's pool service remains the only
allocator inside that physical capacity domain.

## Surfaces

- `GET /api/nodes` and `GET /api/v1/nodes` (plus `/{key}`) on the desktop.
- MCP `operon_nodes(profile_id=None, refresh=False)`.
- The execution settings panel shows the ordering in auto mode: `查看节点容量`
  lists every node with its free CPU, memory, disk, GPU count and score.

Cross-host splitting of one graph is not part of this release: one dispatch
host per graph is still the rule, and the experimental `operon/cluster`
components remain unwired.
