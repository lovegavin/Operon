"""The ``auto`` device has to ask JAX as well as torch.

ColabFold runs on JAX, and its environment carries a CPU torch build next to a
CUDA-enabled jaxlib, so a torch-only probe would quietly send the model to the
CPU.  These tests pin the two probes down without needing a GPU.
"""

from __future__ import annotations

import subprocess

def test_module_is_importable_from_the_steps_package():
    from src.task.step.steps import _device_common

    assert callable(_device_common.cuda_available)


def test_jax_devices_report_cuda_only_for_gpu_names():
    from src.task.step.steps import _device_common

    assert _device_common._jax_devices_report_cuda(["cuda:0", "cpu"]) is True
    assert _device_common._jax_devices_report_cuda(["gpu:1"]) is True
    assert _device_common._jax_devices_report_cuda(["cpu"]) is False
    assert _device_common._jax_devices_report_cuda([]) is False
    assert _device_common._jax_devices_report_cuda([object()]) is False


def test_the_external_probe_accepts_a_jax_only_host(monkeypatch):
    from src.task.step.steps import _device_common

    def fake_run(*args, **kwargs):
        return subprocess.CompletedProcess(args, 0, stdout="jax\n", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    assert _device_common._external_cuda_available("python3") is True


def test_the_external_probe_ignores_an_empty_answer(monkeypatch):
    from src.task.step.steps import _device_common

    def fake_run(*args, **kwargs):
        return subprocess.CompletedProcess(args, 0, stdout="\n", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    assert _device_common._external_cuda_available("python3") is False


def test_the_external_probe_ignores_noise_on_stdout(monkeypatch):
    from src.task.step.steps import _device_common

    def fake_run(*args, **kwargs):
        return subprocess.CompletedProcess(args, 0, stdout="warning\n", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    assert _device_common._external_cuda_available("python3") is False


def test_auto_prefers_cuda_when_only_jax_sees_it(monkeypatch):
    from src.task.step.steps import _device_common

    monkeypatch.setattr(_device_common, "_torch_cuda_available", lambda: False)
    monkeypatch.setattr(_device_common, "_jax_cuda_available", lambda: True)
    monkeypatch.setattr(_device_common, "_external_cuda_available", lambda python: False)
    assert _device_common.resolve_device("auto", "colabfold_predict") == "cuda"


def test_auto_stays_on_the_cpu_without_any_device(monkeypatch):
    from src.task.step.steps import _device_common

    monkeypatch.setattr(_device_common, "_torch_cuda_available", lambda: False)
    monkeypatch.setattr(_device_common, "_jax_cuda_available", lambda: False)
    monkeypatch.setattr(_device_common, "_external_cuda_available", lambda python: False)
    assert _device_common.resolve_device("auto", "colabfold_predict") == "cpu"
