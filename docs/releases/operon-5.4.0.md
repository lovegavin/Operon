# Operon Studio 5.4.0

5.4.0 is the first application release built on the 5.3.0 stack. It carries the
capabilities that were proven on the 5.1.x candidate line onto the new storage,
cluster and run-plan layers, and it installs operator library `main-v0.1.28`.

## What moved from the 5.1.x candidate line

| Capability | Where it lives in 5.4.0 | Effect |
|---|---|---|
| Environment bridge shares native libraries | `operon/environments.py::worker_environment` | Prepends `<env>/lib` and `<env>/lib64` to `LD_LIBRARY_PATH`, so conda-provided `libstdc++` is found instead of the older system copy. Fixes `CXXABI_1.3.9` failures in PyTorch/NumPy environments. |
| GPU admission | `src/web/admission.py` | `gpu_capacity()` counts visible devices (or honours `OPERON_GPU_COUNT`); `HostAdmission` reserves device ids, `request()` derives `gpu_count` from `runtime.execution` or from a step whose `params.device` is `cuda`/`gpu`, larger graphs get extra CPU threads, and `resources()` reports `gpu_capacity`, `gpu_reserved`, `reserved_gpu_devices`, `free_gpu_devices`. |
| GPU device hand-off | `src/web/service.py` | A worker that was granted GPU capacity receives `CUDA_VISIBLE_DEVICES` and `NVIDIA_VISIBLE_DEVICES`; the launch fails loudly instead of silently running on CPU when no device id was reserved. |
| Coordinator recognises itself | `src/web/admission.py::reserve` | Ownership is decided by `(pid, created)` of the admission record instead of the bare `coordinator` flag, so the pool's own reservation is admitted while a foreign launcher is still refused. |
| Abandoned quarantine reclaim | `operon/engine/coordinator.py` | `ABANDON_AFTER_SECONDS = 300`; a quarantined attempt whose recorded worker is provably gone is failed with `recovery_abandoned`, its lease released and retries suppressed, so one dead worker no longer blocks the pool. |
| Large-resource downloads | `src/web/resource_api.py`, `operon/control_api.py`, `operon/mcp_server.py` | `GET /api/v1/large-resources` plus `download`, `cancel`, `log` and `operations/{id}` endpoints, mirrored by the MCP tools `operon_resources`, `operon_resource_download`, `operon_resource_cancel`, `operon_resource_log`; `operon_job` also answers resource operations. Downloads are HTTPS-only, stream into `.part`, verify size and SHA-256 and replace atomically. |

Version identity is 5.4.0 in `pyproject.toml`, `operon/__init__.py`,
`frontend/package.json` and its lock file, and the capability list advertises
`large-resource-download`.

## Verification on the installed build

Clean install: `Operon_Setup-5.4.0.exe --quiet --install-dir D:\OperonTest540`.

| Check | Result |
|---|---|
| Application version | `Operon 5.4.0`, version directory `5.4.0-71ee4e0535ab` |
| Built-in library | `main-v0.1.28`, 7 packages, 1069 operators, 108 readers, 1177 descriptors |
| MCP surface | 69 tools over stdio; `operon_resources` answered 200 |
| Resource catalogue | 16 declared resources, `GET /api/v1/large-resources` reachable through the MCP client |
| GPU admission (installed module) | `gpu_capacity() == 1`; a step with `device: cuda` yields `gpu_count: 1`; reserving marks device `0` as reserved, releasing frees it; a foreign launcher is refused while the coordinator is admitted |
| Real job | `req-70f12c30444cf1dcb3a02d82`, `FastaReader -> sequence_liability_scan`, status `complete`; output reports 7 liability sites (3 N-glycosylation, 2 deamidation, 1 oxidation, 1 isomerisation), matching the values recorded for the same sequence on the 5.1.x line |

The job ran through the shared pool of the installed instance, so the evidence
covers the launcher, admission, worker start-up and artifact commit paths.

## Artifacts

| Asset | Size | SHA-256 |
|---|---:|---|
| `Operon_Setup-5.4.0.exe` | 428,809,629 | `ed45acbd83e2e8a99ae4b443093fef709a6c9a5abfd907757ef889b92e7bd02a` |
| `Operon-5.4.0-Server.zip` | see `SHA256SUMS.txt` | see `SHA256SUMS.txt` |
| `operon_studio-5.4.0-py3-none-any.whl` | see `SHA256SUMS.txt` | see `SHA256SUMS.txt` |
| `SHA256SUMS.txt` | — | — |

The payload inside the installer is
`Operon-Studio-v5.4.0-Windows-x64.zip` (25,573 files,
`591b2f8c9ff79218355bcab94a3e9dc47c5e439eb947be3e2a10fb8ed60b8072`).

## Known debt

- `tests/test_job_admission.py::test_actual_scientific_workers_keep_independent_memory_and_logs`
  is order sensitive: `service.launch()` returns after marking the job `running`
  but before the worker is inserted into `service.processes`, so a later lookup
  can raise `KeyError`. The behaviour predates 5.4.0 (it reproduces on 5.3.0),
  and the four-file suite passes on repeated runs; it is recorded rather than
  papered over.
- The frontend bundle is built but not tracked (`frontend/dist` is ignored); the
  installer carries the built output.
- AF2/OpenFold full-database MSA work is not part of this release; only the
  single-sequence and subset-database results recorded in
  `docs/releases/design-loop.md` apply.

## Upgrade path

Install 5.4.0 over 5.3.0. The bundled library is installed on first start; an
existing `main-v0.1.2x` branch is replaced only after the new bundle is
verified, and unrelated branches are preserved.
