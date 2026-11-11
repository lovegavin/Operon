# Operon control-plane baseline and post-change measurement (P00)

**Date:** 2026-11-07 (Asia/Shanghai)\
**Branch:** `fix/3.0.1-installation`\
**Released baseline:** `c7bd2c6d73c600e899121f335a267c2c64140d94` (3.0.2 / SDK 3.7);
later commits on this branch are transfer/setup only.\
**Harness:** `scripts/benchmarks/control_plane.py`\
**Raw samples:** [`evidence/control_plane_benchmark_2026-11-07.json`](evidence/control_plane_benchmark_2026-11-07.json)

## What was measured

Both modes run the same framed JSON fixture over loopback TCP and the same
dispatch function.  A slow request (400 ms) is admitted first and occupies the
legacy loop; sixteen clients then issue twenty status requests each.  The
measurement is the **server-side request loop**; it excludes network RTT, UI
rendering and scientific worker startup.

| Mode | Meaning |
| --- | --- |
| `baseline` | Faithful reproduction of the pre-change `serve` loop: accept one connection, read one frame, dispatch, reply, close, then accept the next. |
| `concurrent` | `ControlLoop` with 32 bounded handlers, aggregate byte admission and absolute deadlines. |

```powershell
python scripts/benchmarks/control_plane.py --mode both --clients 16 `
  --requests 20 --slow-seconds 0.4 --output .verify-tmp/control-benchmark.json
```

Machine manifest recorded by the harness:

- Windows 11 (10.0.26200), CPython 3.12.14, 16 logical CPUs
- loopback TCP, framed JSON, 16 clients × 20 status requests
- one 400 ms slow request admitted before the status workload
- 320 status samples per mode, zero transport errors in both modes

## Results

| Metric | Baseline serial loop | Bounded concurrent loop | Change |
| --- | ---: | ---: | ---: |
| p50 | 14.9 ms | 4.2 ms | −71% |
| p95 | 26.1 ms | 5.7 ms | −78% |
| p99 | 401.6 ms | 26.6 ms | −93% |
| max | 401.9 ms | 29.5 ms | −93% |
| errors | 0 / 320 | 0 / 320 | — |

The baseline p99 is dominated by clients that arrived while the slow request
held the serial accept loop.  Under the concurrent loop those requests are
served by other bounded handlers, so the slow request itself still takes
~401 ms while unrelated status calls stay in single-digit milliseconds.

**Interpretation limits:** this is an in-process/loopback reproduction of the
released loop, not a real SSH/Linux deployment; no claim is made about network
RTT, full application latency, dependency probing, worker startup or scientific
throughput.  The 50% p95 reduction target is met **for this control-loop
microbenchmark**, not for the product as a whole.  Raw samples are retained so
the distribution, not only the summary, can be inspected.

## Baseline test observations (same machine, before the engine changes)

Commands used the project virtual environment and a workspace-local temporary
directory to survive the DSH Windows file sandbox (pytest's `0o700` temp
directories are not listable under that sandbox; a test-only
`os.mkdir` mode shim was used and is not part of the repository).

| Suite | Result | Notes |
| --- | --- | --- |
| `tests/test_contracts.py`, `tests/test_job_admission.py` | 29 passed, 2 failed, 1 error | Two real-worker/memory-pressure cases failed before any engine change. |
| `tests/test_execution_service.py`, `test_remote.py`, `test_remote_handshake.py`, `test_remote_transfer.py`, `test_memory_runtime.py`, `test_server_cli.py` | 79 passed, 9 failed | Remote/SSH fixtures require a Linux peer or dependency probes. |

Environment limitation observed throughout: dependency probes launched through
`subprocess` pipes fail with `(pid=...)` under the DSH sandbox, and
`psutil.Process.resume()` is denied.  Those cases are not evidence of engine
regressions; the same failures reproduce without the new engine modules loaded.
The new engine suites run with real subprocesses because they use file-backed
stdio rather than the sandbox-restricted pipe path.

## Performance targets for subsequent waves

- Server-side p95 status/cancel acknowledgement ≤ 200 ms at 16 clients under
  bounded mixed load; this baseline is at 5.7 ms under the synthetic fixture.
- Dispatch of a feasible ready unit within 500 ms of a release: the
  coordinator launches outside the state transaction and wakes on completion;
  measured in the DAG tests but not yet under full scientific load.
- No monotonic unowned growth in buffered streaming bytes: covered by
  `test_engine_channels.py` with a fixed 8-byte credit budget.
