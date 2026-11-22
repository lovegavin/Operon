# Operon Studio 5.7.36

## Added

- **Unbounded parallelism.** `parallel_tasks` now accepts `0`, which means "use
  every unit the host allows" instead of a fixed per-job count. The setting is
  honoured by the planner, the admission capacity and the executor, so a job
  takes the whole host only when it asks for it.
- **Batch submission over MCP.** `operon_submit_many` submits a list of graphs
  concurrently (default 16 workers) and `operon_jobs_many` reads many job states
  in one call; `operon_submit` gained `max_parallel_tasks`. UI-only capability is
  now reachable from the MCP server as well.

## Fixed

- **Shared databases no longer hide a finished environment.** An environment
  that merely names a shared resource (a database several toolchains read) was
  downgraded to `incomplete` whenever that database was missing, so a client that
  gates on a ready status stalled even though every declared dependency was
  installed. Shared units are reported as `resources_warning`; only a unit the
  environment declares still changes the status.
- **BED interval columns resolve under their documented names.** `annotation_*`
  and `peak_*` operators ask for `start`/`end` while `BedReader` labels the same
  columns `chromStart`/`chromEnd`, so a BED route failed with "column 'start' is
  required" although the file was read correctly. Both spellings now resolve and
  the error lists the columns that were available.
- **`psutil` is declared by every environment that runs bridge steps.** The
  workspace processes and the bridge import it, so an environment without it
  failed every step with `No module named 'psutil'`; 17 environments now declare
  `psutil>=5.9`.

## Notes

- The library moves to `1.1.23` for the reader and environment-declaration
  changes; `minimum_application` stays at 5.7.20.
