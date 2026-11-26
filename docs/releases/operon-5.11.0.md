# Operon 5.11.0 — compute nodes you can see, rank and choose

This release adds Slurm compute-node discovery to the execution settings and
routes a job's worker process through the node you pick.

## What changed

- **Capacity inventory.** `operon/nodes.py` measures every reachable capacity
  domain (the local host and each connected SSH server). For a server with
  Slurm it parses `sinfo -h -N -o '%N|%P|%a|%t|%C|%m|%e|%G'`, so each compute
  node reports allocated/idle CPUs, memory, free memory, GPU count, state and
  partition.
- **Readiness-weighted score.** The score folds environment readiness into the
  number itself instead of sorting in a separate tier:
  `C = [0.5·mem_free + 0.3·cpu_idle] × state + 0.15·GPU`, `b = min(C/0.95, 1)`,
  `score = 0.5 + 0.5·b` for a ready node and `score = 0.5·b` otherwise. Ready
  nodes therefore occupy `[0.5, 1.0]`, unready nodes `[0, 0.5)`, and when every
  node is unready the relative capacity order is preserved. Readiness is probed
  with `srun -w <node> -N1 -n1 test -x <environment python>` and cached.
- **Warm cache on connect.** A successful server connection now primes the
  inventory in the background, so the panel and automatic placement open with
  current scores.
- **Node picker in the UI.** The execution settings show `计算节点` for an SSH
  target in manual mode: `登录节点` (default) or any Slurm node with its idle
  CPUs, state, reason and score.
- **Job launcher.** When `runtime.execution.node` is set, the per-job worker
  command is wrapped with
  `srun -N 1 -n 1 --nodelist <node> -c <threads> --time 1440 --export=ALL`,
  and the job records `execution_node`. A request for a node without `srun`
  fails with a clear message instead of silently running on the login host.

## Compatibility

- Application 5.11.0; operator library stays 2.1.1 (no library change).
- `POST /api/nodes`, `GET /api/v1/nodes`, `GET /api/nodes/{key}` and the MCP
  `operon_nodes` tool report the new `capacity`, `score`, `rank`, `env_ready`
  and `selectable` fields; existing fields keep their meaning.
- Jobs without `runtime.execution.node` behave exactly as before.

## Known limits

- Placement is per job, not per step: the whole worker runs on the chosen node.
- A compute node must see the same shared filesystem and environment; sites
  without shared storage still run on the login host.
- `srun` uses the cluster's default partition, account and wall clock unless
  the site changes the wrapper.
