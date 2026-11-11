# Remote recovery incident note (3.1.6)

This note separates confirmed application defects from hypotheses about a
private VHH report. It is not a claim that the author's exact server incident was
reproduced; the original graph and complete remote traceback were not supplied.

## Confirmed

1. `RemoteManager.ensure()` called `.get()` on the list returned by
   `status()`. The production status shape was list-shaped, and the old test
   fixture mistakenly mocked a dictionary. The ensure path now selects the
   requested profile from the real list and preserves host-key/password rules.
2. The SSH bridge only ensured the shared RPC daemon at startup. If the daemon
   idle-exited while the SSH channel stayed open, the next request hit a missing
   Unix socket. The bridge now classifies a failure before transmission, calls
   the existing locked `ensure_daemon()` and retries the same request exactly
   once. Post-transmission failures are unknown outcomes and are not replayed.
3. Snapshot file I/O errors could escape `validated_pins()`. Missing and
   unreadable generations are now classified and remain unavailable; no
   fallback generation is fabricated.
4. `ExecutionService.infos(graph=...)` queried every connected host even for an
   explicit local/different-host target. A broken unrelated host could raise
   before the requested target was considered. Explicit targets are now isolated;
   automatic placement records and excludes an unavailable candidate.

## Not established

- Whether the original author's host had an expired daemon, a stale registry,
  a bad Reader/port edge, or a different installed-library mismatch. Those are
  distinct hypotheses. The deterministic CDR contract error must not be
  presented as a transport error.
- Whether the original private workflow would pass. A synthetic but real
  FASTA/FastaReader/CDR path is tested; it is not that workflow.

The diagnostics `bridge.events.jsonl` and `dispatch.events.jsonl` are the first
places to inspect. Include the trace ID and request ID when reporting a remote
failure; do not include passwords, tokens or private input data.
