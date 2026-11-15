# K00 control performance baseline and final acceptance

Date: 2026-11-14. **PASS for the specified Windows K00-K02 gate.** The final
grouped test batch and fixed-workload comparison followed development freeze.
The prior repeatable submission-tail regression is resolved; no additional
parameter sweep or repeat of passed suites was used after this final result.

## Method and scope

Pinned source: `600eed6f53b6db01f7391f408ade1e950d8679b3` (5.1.9).
Runtime: `3.12.14 (main, Aug 25 2026, 14:01:42) [MSC v.1944 64 bit (AMD64)]`; `Windows-11-10.0.26200-SP0`.
Hardware: AMD64 Family 25 Model 97 Stepping 2, AuthenticAMD; 16 logical CPUs; 30.9 GiB RAM.

The same harness runs the real framed ControlLoop, SQLite StateStore and graph
compiler against the untouched baseline archive and candidate. It has 16 TCP
clients and seven rounds, each with 12 cycles per client: status, submit,
events, compile, browse, status, transfer, cancel, probe. Graphs have 3 or 201
nodes (25% large). Browse lists files with a controlled 150-ms wait; transfer
reads 64 KiB with a 20-ms wait. Probes spawn the actual Python interpreter.
These controlled I/O stalls are not real SSH/SFTP traffic. Authenticated
principal quotas and the separate saturated pool lifecycle listener have their
own product tests, not this low-level dispatch benchmark.

Cold means the first mixed round, not a fresh process for every request or an
OS-cold filesystem. Warm percentiles pool raw samples from six later rounds.
Nearest-rank p50/p95/p99 are reported below; no percentile-of-percentiles is used
for request latency. Functional tests finish before timed measurement starts.

## Request latency (milliseconds)

| Phase | Request | Baseline p50 / p95 / p99 | Candidate p50 / p95 / p99 | p95 change | p99 change |
|---|---|---|---|---:|---:|
| cold | status | 16.1 / 100.3 / 146.5 | 3.5 / 23.0 / 46.2 | -77.1% | -68.5% |
| cold | events | 15.8 / 234.2 / 435.5 | 5.9 / 26.0 / 38.1 | -88.9% | -91.3% |
| cold | submit | 12.6 / 101.8 / 135.7 | 8.8 / 27.5 / 51.4 | -72.9% | -62.1% |
| cold | cancel | 6.6 / 196.8 / 210.2 | 4.5 / 26.9 / 32.5 | -86.3% | -84.5% |
| cold | compile | 116.3 / 466.0 / 492.1 | 24.4 / 145.8 / 181.5 | -68.7% | -63.1% |
| warm | status | 15.7 / 116.3 / 202.6 | 3.0 / 23.0 / 33.9 | -80.3% | -83.3% |
| warm | events | 9.4 / 261.5 / 417.9 | 5.2 / 35.7 / 52.6 | -86.3% | -87.4% |
| warm | submit | 9.5 / 95.7 / 142.3 | 8.1 / 28.7 / 52.5 | -70.0% | -63.1% |
| warm | cancel | 9.8 / 212.5 / 309.2 | 4.1 / 25.7 / 49.0 | -87.9% | -84.2% |
| warm | compile | 111.7 / 291.6 / 353.6 | 25.7 / 87.2 / 112.8 | -70.1% | -68.1% |

There are 384 cold and 2,304 warm status samples; each other operation has
192 cold and 1,152 warm samples. Both runs returned zero control errors.

## Writer, memory and retained work

Writer measurements cover only outer SQLite transactions, including acquisition
of the process lock and BEGIN IMMEDIATE. The following writer figures are the
**median of per-round warm p95/p99**, since raw per-transaction samples are not
retained. They are not pooled percentiles.

| Metric | Baseline | Candidate |
|---|---:|---:|
| Writer wait p95, ms | 95.10 | 12.41 |
| Writer wait p99, ms | 190.85 | 18.75 |
| Writer hold p95, ms | 8.57 | 4.48 |
| Writer hold p99, ms | 92.48 | 12.76 |
| Peak process RSS, MiB | 117.17 | 116.50 |
| Peak process threads (all roles) | 102.00 | 89.00 |
| Peak accounted request bytes, MiB | 0.04 | 5.39 |

Thread peaks include in-process clients, native-library threads and monitoring,
not just the 32 request handlers. RSS stayed bounded over the seven rounds;
this is not a long-duration soak-test claim. Candidate byte accounting includes
decoded objects throughout dispatch; the old implementation released its raw
reservation early. A larger accounting value is not a larger measured RSS.

Each round retains 193 queued runs. The separate sustained-admission test
accepts 8 runs and rejects 1,000 more while run/request/event counts remain
unchanged. This is not a throughput measurement at the 100,000-receipt default
ceiling. Disk/WAL and free-space watermarks do not impose hard filesystem quotas.

Large-graph calibration measured roughly 233 KiB decoded peak from 41 KiB JSON,
with about 1.33 MiB reserved. The calibration uses tracemalloc outside the timed
dispatch phase. Frame, decoded-byte, depth and cardinality limits remain active.

## Scientific worker and catalog timing

| Measurement, seconds | Baseline | Candidate |
|---|---:|---:|
| JobService catalog/startup | 5.072 | 4.345 |
| First scientific run | 2.921 | 2.972 |
| Warm scientific run 1 | 2.789 | 2.728 |
| Warm scientific run 2 | 2.817 | 2.810 |

All six real NpyReader -> PCA -> Describe workers completed. These small-fixture
times include launch/import/cleanup and are not a large-dataset throughput
claim. The independent K02 suite verifies branched plots, metadata, managed
memory, outputs and process cancellation. No material worker-time regression
was observed. Catalog timing is not an interactive desktop startup measurement.

## Regression history and remediation

Earlier experiment files are retained: initial/expanded/final/repeat, optimized,
bounded-planning (4), serial-planning (1), two-planners (2), confirmation,
combined-query and submission-profile. Those intermediate results did not pass
the gate. The final settings are 2 planning handlers, configurable independently
of scientific CPU allocation, plus the dedicated lifecycle endpoint.

Moving disk sampling and plan encoding outside the writer, combining quota
counts and replay lookup, and bounding planning concurrency preserved correctness
but alone did not eliminate submission-tail regression. Attribution recorded
writer waiting under CPU-heavy compilation; storage sampling itself was usually
sub-millisecond to a few milliseconds. Code inspection found repeated full JSON
Schema checks for the same declaration at every node. A bounded successful-schema
cache now removes that redundant work. Each parameter value is still validated;
changed declarations, bad values and forbidden external references remain errors.
The cache retains at most 128 ASCII snapshots of 64 KiB each, not operator code,
parameter values or scientific data. This final fixed comparison shows improved
cold and warm p95/p99 for every measured request class.

## Reproduction and evidence

Use `verification/backend/run_gate_checks.ps1` with explicit `-Python312`,
`-Python311` and `-BaselineSource` arguments. The last points to an untouched
archive of the pinned commit. Read the file before rerunning: it also executes
the grouped functional checks. A diagnostic-only `--profile-submissions` option
is available in the benchmark; it was **off** in both final comparisons.

Final raw inputs: `verification/backend/performance-baseline-gate.json` and
`performance-candidate-gate.json`. Their shared harness hash is:
`d56611df029aa0bedc73b5e84b73124d84fbcde54ed3e8d46ec925b0c3714b26`.

`k00-runtime-final-py311.json` and `k00-runtime-final-py312.json` identify the
dirty source by file hashes and exact installed package metadata.
`gate-evidence.json` records report hashes and the numerical gate decision.

Scope remains Windows local components/product paths. No Linux/SSH, systemd,
network-failure, real disk-full, multi-host scaling, interactive Setup or
release/package acceptance is implied. No scientific library source was changed.
