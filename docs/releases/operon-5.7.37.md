# Operon Studio 5.7.37

## Fixed

- A graph that names a remote target explicitly (`runtime.execution.kind = "ssh"` with a
  `profile_id`) now counts as a remote graph even when it carries no file source, so the
  source-less operators (structure prediction, design and embedding families) can be
  submitted to a server. Previously they fell through to the local shared pool and were
  reported as `503 engine_unavailable` with `Unknown resource: '找不到服务器连接配置。'`.
- The job list no longer reads every console tail, child result and artifact set while
  building itself. With a few thousand recorded jobs a single poll could take seconds and
  starve unrelated endpoints such as `/api/bootstrap` and the environment snapshot; the
  list now reads the job summary only, while `/api/jobs/<id>` keeps the full record.

## Notes

- No library change; this release ships with library 1.1.23.
