# Real Linux/SSH pool acceptance

The release pass on 2026-11-08 completed real two-client SSH, numeric worker,
upload/reuse, independent cancellation, reconnect and actual pool CLI crash
recovery checks. See [current evidence](server_engine_acceptance.md). The older
`pool_linux_not_run_2026-11-08.json` records the earlier blocked implementation
pass only. The checklist below remains useful for deployment validation.

## Preconditions

- An existing, authorized Linux host with the candidate installed is reachable.
- The operator confirms it is healthy and grants use of its Python/runtime.
- Two private workspace roots and two non-sensitive test graphs exist.
- No other legacy launcher or job occupies the shared admission directory.
- The service is started explicitly, not by a hidden auto-start path.

## Server setup

Use the candidate checkout and a dedicated pool state root:

```bash
export PYTHONPATH=/opt/operon
python3 -m operon pool serve --config /etc/operon/pool.json
```

`pool.json` follows [pool_service.md](pool_service.md).  Keep the token file
mode `0600` and do not place it in a public workspace.  The runner requires an
explicit `token` and `port` in the config so it can start the client; generated
tokens are for interactive `pool serve` only.

## Evidence run

```bash
chmod +x scripts/acceptance/pool_linux.sh scripts/acceptance/pool_client_checks.py
scripts/acceptance/pool_linux.sh \
  /etc/operon/pool.json /srv/ws-a /srv/ws-b \
  /srv/acceptance/graph-a.json /srv/acceptance/graph-b.json \
  /srv/acceptance/evidence/pool-run.json
```

The runner starts the real pool CLI, waits for the control channel, submits two
workspace runs through `PoolClient`, reconnects after a disconnect, verifies a
duplicate request id has one run, cancels only workspace A, and writes raw
snapshots plus the server log.  It does not use mocks or a test shim.

## Manual checks that must accompany the JSON evidence

1. **Budget:** `pool.status` `coordinator.pool.used.ram` never exceeds
   `capacity_bytes`; sum active lease reservations equals used.
2. **Duplicate/lost response:** submit the same request id twice; exactly one
   run and one attempt.  Kill a client after submit; the worker continues.
3. **Fairness:** one principal with several client connections cannot obtain a
   second aggregate share.  A queued large job eventually obtains capacity
   after smaller work drains; record the queue reason and age.
4. **Cancellation:** cancel A; B remains running; A's lease is released only
   after its process tree is confirmed gone.
5. **Session/workspace close:** close one client/workspace session; the other
   workspace and the pool remain alive.
6. **Restart:** stop the pool process without cancelling workers; restart it
   with the same config; verify adoption, one attempt, no duplicate launch.
7. **Environment gate:** while A is running, attempt dependency repair in B;
   expect `environment_busy`.  Different interpreter/prefix identities may
   proceed independently; record both identities.
8. **Failure recovery:** simulate a durable-store or staging failure; record
   the visible job/run state, artifact state and whether the lease remains
   charged.  Restart and verify reconciliation.
9. **SSH:** repeat submit/query/cancel/reconnect through the existing SSH
   client/server path; record control latency separately from scientific wall
   time.  A simulated loopback SSH test is not this gate.

## Evidence fields

The JSON from `pool_client_checks.py` contains `initial_status`, `runs`,
`snapshots`, `status_after_submit`, `cancelled_a`, `workspace_b_after_cancel`,
`status_after_cancel`, timestamps and any exception.  Store it with the server
log and the exact git revision, OS, Python, filesystem and command line.

## Pass criteria

- All steps `ok` are true.
- No budget overrun at any snapshot.
- One durable run/attempt for the duplicate request.
- A cancellation does not change B's run.
- Restart makes zero duplicate launches.
- Every failure has a documented state; no lease is released without confirmed
  process-tree exit.
- If a platform permission blocks a check, mark it **not passed** and attach
  the command output; do not substitute a shim result.
