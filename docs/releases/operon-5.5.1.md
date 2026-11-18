# Operon Studio 5.5.1

Released 2026-11-18.

This release fixes the environment-preparation race that made five of the seven
isolated environments fail on a first-time setup, serialises preparation behind a
visible queue with expected sizes and percentage progress, splits the runtime
status cards into four states, and extends large-resource linking to remote
servers so an MSA database can stay where it already lives. The operator library
is unchanged at `main-v0.1.29`; the application version is the only new artifact.

## Added

- **Serial preparation queue.** "Install all" no longer starts every environment
  at once. Preparations run one at a time in ascending order of expected size, so
  the smallest environment becomes usable first and a failure cannot leave several
  half-downloaded staging trees behind. Queued environments report `status:
  "queued"` with a `queue_position`, and an entry can be cancelled while it is
  still waiting.
- **Expected install sizes.** `operon/environment_estimates.py` carries a static
  estimate for every built-in environment, scaled per platform, and replaces it
  with the measured size of a completed install (`.operon-environment-sizes.json`
  under the environment root). `GET /api/environments` reports `expected_bytes`
  next to `size_bytes`, and the panel draws a determinate progress bar from
  `progress.bytes / expected_bytes`.
- **Resource linking on remote servers.** `GET /api/remote/{key}/resources`,
  `POST /api/remote/{key}/resources/{name}/link` and `DELETE` on the same path
  forward to the remote agent's new `resources`, `resources_link` and
  `resources_unlink` methods. MCP exposes `profile_id` on `operon_resources`,
  `operon_resource_link` and `operon_resource_unlink`, so an agent can point a
  remote resource root at an existing checkout without copying bytes.
- **Link dialog in the settings page.** The large-resource page now opens a
  dialog that lists linkable resources (databases and model weights only,
  dependencies excluded), accepts a source path and an optional target host
  (local or a connected server), and shows the allowed link roots. Linking is
  possible while the resource is still missing, so an install can consume a
  database that is already on disk.

## Changed

- **Four environment states.** Cards now distinguish 未安装 (missing), 准备安装
  (queued), 安装中 (installing) and 已安装 (ready); stale and failed keep their
  own tones. The summary strip counts each state separately.
- **Full operator list in a dropdown.** The "used by" row is a collapsible list
  instead of a truncated line, and the API cap for that list rises from 8 to 64
  entries (`used_by_count` still reports the total).
- **Failed cards show the reason.** A failed environment prints the recorded
  error summary instead of only the word "failed".

## Fixed

- **Concurrent micromamba bootstrap (F-11).** Six parallel preparations each
  downloaded micromamba and raced to replace the shared executable; the first
  process to start it kept the file busy and every other replace failed with
  `[WinError 5] Access is denied`, which surfaced as five failed environments.
  The bootstrap is now guarded by a process lock, retries the atomic replace with
  backoff, and reuses an executable that another preparation installed.
- **Empty "disk usage" row (F-12).** The row was computed from the final install
  directory only, so it was blank before an environment existed. It now reads
  "not installed", the in-flight byte count while installing, or the measured
  directory size once ready.
- **Truncated operator lists (F-13).** A single-line `text-overflow: ellipsis`
  rule clipped long dependency lists; the row is a dropdown with a scrollable
  list.
- **No error on failed cards (F-14).** The recorded `error` was neither returned
  consistently to the panel nor rendered.
- **Cancel ignored queued entries (F-15).** Cancelling an environment that was
  still waiting left it in the queue.
- **A stalled download froze the whole queue (F-16).** The micromamba bootstrap
  used a blocking `urlopen` plus `copyfileobj`, so a slow CDN response was
  neither cancellable nor bounded. The worker thread kept the only preparation
  slot and the bootstrap lock, every later environment stayed `queued`, and the
  card kept showing 安装中. The download now copies in 1 MiB chunks, checks the
  cancellation signal between chunks, and fails after a 420 s total deadline;
  the cancellation also writes a `cancelled` progress state so the card falls
  back immediately instead of waiting for the worker.
- **Cancelling a running environment raised HTTP 500 (F-17).** The helper that
  records the cancelled progress state passed its arguments in the wrong order
  (`name, progress, root` against the `name, root, value` signature), so the
  endpoint failed with `TypeError: expected str, bytes or os.PathLike object,
  not dict` after the environment had already stopped. The call order is fixed
  and a regression test exercises the helper directly.
- **The agent bridge lacked the resource endpoints (F-18).** The desktop bridge
  that serves MCP clients only exposed the remote environment endpoints, so
  `operon_resources`, `operon_resource_link` and `operon_resource_unlink` with a
  `profile_id` reached `/api/agent/remote/<profile>/resources` and answered
  `404 Not Found` (or `405 Method Not Allowed` for the link route) instead of
  forwarding to the connected server. The bridge now serves
  `GET /api/agent/remote/<profile>/resources` and
  `POST|DELETE /api/agent/remote/<profile>/resources/<name>/link` through the
  same remote manager the local API uses.
- **The "used by" count rendered its placeholder (F-19).** The status card passed
  `{count}` of the operator list where the translated string expects `{n}`, so
  `{n} 个算子` appeared literally under every environment. The call now passes the
  matching name and a render test asserts the substituted number.
- **A cancelled environment could still be reported as failed (F-20).** The
  request thread and the worker wrote the progress file through the same fixed
  temporary name, so a cancellation that landed during a progress update made
  the writer fail with `[WinError 5]` and the environment stayed `failed` with
  that message even though the operation was cancelled. Each write now uses a
  thread-unique temporary file with retries, a recorded cancellation is never
  replaced by a failure, and the worker removes the stale error file.

## Verification

A clean silent install of the shipped 5.5.1 installer reports `5.5.1` from
`/api/version` and from the MCP `serverInfo` handshake, exposes seven isolated
environments and sixteen large resources, and keeps the library at
`main-v0.1.29` with seven packages, 1,069 operators and 108 readers. The
preparation queue was exercised with six simultaneous requests: exactly one
environment starts, the rest report `queued` with consecutive positions, the
first request is the smallest environment, and no `WinError 5` staging failure
appears. Resource linking was exercised locally, including linking a directory
before the resource is installed and unlinking it again; the remote variants are
covered by unit tests and answer `404` for an unknown profile. Frontend unit
tests and the backend suites that cover environments, resources, remote dispatch
and control API errors pass; details and evidence references are in the 5.5.1
test report.
