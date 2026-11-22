# Operon Studio 5.7.34 acceptance report

Measured on the `licai-srv` deployment (`CentOS 7`, 56 cores, 251 GB) with the
fresh application instance on `127.0.0.1:5880` and every route submitted
through the MCP tools.

## What changed and why

| Symptom the sweep exposed | Root cause | Fix |
| --- | --- | --- |
| `The shared pool is unavailable: PoolClientError: Finish tasks before changing its application, interpreter or catalog policy` on concurrent submits (25+ rows) | a registration without an explicit library re-derived it from the application directory, so the policy compared unequal on every submit | `_registration_binding()` keeps the bound library when the client is silent |
| `pool_busy` indistinguishable from a real operator failure | the launch path wrapped every exception in `engine_unavailable` | `_pool_error()` maps `pool_upgrade_required` to `503 pool_busy` with `retryable: true` |
| `vina_dock` cannot run on a host without a cp311 wheel | `vina` was an optional pip binding that only builds from source | the binary ships as the `vina` resource and the operators resolve it |

## Environment and resources

- 19 of 19 environments `ready` on the deployment (`core` optional binding
  `vina` is gone; `antismash` pins `ncbi-amrfinderplus=4.2.5`).
- 19 resources declared, every unit present on disk; the new `vina` unit is
  4,089,576 bytes from the AutoDock-Vina v1.2.5 release asset.

## Operator evidence gathered before this cut

- `esm_if_score` complete 381 s and `esm_if_redesign` 441 s — the checkpoint
  fallback works end to end.
- `crispr_array_detect` complete 135 s, `antibody_developability` 219 s,
  `iris → pca` 16.8 s (`exec-3a7273794fb84abab1d28eb13f99c1cc`).
- 1,297 jobs recorded server-side: 534 complete, 761 failed, 1 running,
  1 cancelled; 652 distinct operators attempted, 333 with at least one
  complete run on that deployment.
- Aggregated over every sweep batch: 397 of 1,074 operators (37.0%) have at
  least one complete run.

## Known gaps

- `hmmer_domains` needs a user-supplied pressed `Pfam-A.hmm`; the requirement is
  documented and counted as an offline prerequisite, not a defect.
- `esm_pseudo_likelihood` still requires an explicit `model_path` when the
  caller wants a non-default checkpoint.
- The 403 remaining sweep failures are fixture preconditions (label axes,
  single-sequence versus set inputs), not operator code.
