# Operon Studio 5.1.17-rc7 (source candidate)

This is a source-only candidate. No installer, server package, wheel or GitHub
release was published for rc7.

## Highlights

- GPU scheduling: jobs may request `gpu_count` (or `device=cuda`), the admission
  layer reserves concrete device indices, and workers receive
  `CUDA_VISIBLE_DEVICES` / `NVIDIA_VISIBLE_DEVICES`.
- Difficulty-based CPU allocation: managed jobs get a small thread floor and grow
  with graph size; unmanaged jobs remain exclusive.
- CUDA environments: environment specs support `torch_cuda`,
  `torch_index_url`, `torch_version`, `torch_wheel` and `torch_wheelhouse`.
  `boltz` and `esmfold` install CUDA 12.1 torch wheels on GPU hosts.
- Environment probes assert `torch.cuda.is_available()` for CUDA specs.
- Shared-pool requirements now carry reserved GPU devices.
- Coordinated executor assigns GPU device ids before starting the worker.

## Verification

- `tests/test_gpu_rc7.py`, `tests/test_job_admission.py`,
  `tests/test_environment_agent_permissions.py`: 33 passed.
- Local RTX 3090 proof through MCP: a zero-input probe job completed with
  `CUDA_VISIBLE_DEVICES=0`, `NVIDIA_VISIBLE_DEVICES=0`,
  `OPERON_CPU_LIMIT=3` and `nvidia-smi -L` reporting the RTX 3090.
- `boltz` CUDA environment: `torch 2.3.1+cu121`,
  `torch.cuda.is_available() == True`, `boltz 2.2.1`.

## Library

Library source is bumped to 0.1.19 for the CUDA environment declarations and is
built locally, but is not published as a release.

## Boundaries

- The full de novo minibinder design chain (RFdiffusion, ProteinMPNN, Boltz,
  ESMFold, ESM3, interface and developability) has not yet been run end to end.
- Remote `licai-srv` still runs 5.1.17 / library 0.1.18; rc7 has not been
  deployed there.
- ESMFold/ESM3 install stalls at ~2.17 GB are not yet root-caused.
