# Operon Studio 5.7.0

## Added

- **Forced server library sync.** `GET /api/remote/{key}/library/plan` reports the packages a
  connected server is missing and the packages it has that the initiating machine does not;
  `POST /api/remote/{key}/library/sync` then installs the missing packages and removes the extra
  ones so the server library becomes a copy of the local one. The settings page exposes this as
  "强制同步算子库" with an add/remove preview before the transfer starts. Remote agents advertise
  the new `library_remove_v1` capability; older agents keep working with install-only sync.
- **AlphaFold2 operator set.** `alphafold2_predict`, `alphafold2_batch_predict`,
  `alphafold2_msa_search` and `alphafold2_rank_models` join the library and declare the
  `alphafold2` environment, which is no longer marked as planned. The operators read the `afdb`
  resource root (parameters and MSA databases) and accept an absolute `run_alphafold.py` path.
- **Remote environment cards reuse local metadata.** Titles, subtitles, notes, dependency lists
  and operator counts for a connected server are taken from the local library by environment
  name, so a remote card reads exactly like the local one even before the server library is
  synced. Server-only entries are still listed in the mismatch warning.
- **Planned environments are labelled.** Environments without bundled operators show a "预留"
  badge and explain that no built-in operator declares them yet.

## Fixed

- F-55: the isolated-environment bridge dropped `FileArtifact` inputs and outputs. `_write_form`
  and `_run_step` in `operon/environments.py` and both sides of `operon/env_worker.py` now carry
  `kind: "file"` payloads, so file-input operators (VCF/FASTQ/FASTA/chain/SBML/pairs/TSV/GFF3)
  can run inside managed environments instead of failing with
  `AttributeError: 'FileArtifact' object has no attribute 'data'`.
- F-57: remote environment snapshots only contained planner state, which is why connected servers
  showed ids instead of titles, empty notes and zero dependencies. The desktop now merges local
  metadata, and the new sync endpoint makes the server library itself identical.
- F-58: the remote library panel issued a comparison request on every render; it now checks once
  per connection and only when the handshake did not already include a comparison.

## Notes

- The sync endpoint requires an agent that advertises `library_sync_v1`; removal additionally
  requires `library_remove_v1`. Without removal support the sync only fills in missing packages
  and reports why extras were kept.
- `operon environment status <name>` still resolves operator environments relative to the working
  directory; use `operon environment list` for an inventory.
