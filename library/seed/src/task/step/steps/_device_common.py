"""Resolve the compute device for the deep-learning operators.

The operators used to default to ``cpu`` because the first machines that ran
them had no usable CUDA.  A machine with a GPU should not pay for that default,
so the parameter now accepts ``auto``: it means "cuda when the environment that
runs the model can actually see a device, cpu otherwise".
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from src.core import StepError

CPU = "cpu"
CUDA = "cuda"
AUTO = "auto"


def _torch_cuda_available() -> bool:
    try:
        import torch  # noqa: PLC0415 - optional, only present in the model env
    except Exception:  # pragma: no cover - the operator raises a clearer message
        return False
    try:
        return bool(torch.cuda.is_available())
    except Exception:  # pragma: no cover - broken driver must not crash planning
        return False


_PROBE_SCRIPT = r"""
import sys

found = []
try:
    import torch
except Exception:
    pass
else:
    try:
        if torch.cuda.is_available():
            found.append("torch")
    except Exception:
        pass

try:
    import jax
except Exception:
    pass
else:
    try:
        names = [str(device).lower() for device in jax.devices()]
    except Exception:
        names = []
    if any("cuda" in name or "gpu" in name for name in names):
        found.append("jax")

print(",".join(found))
"""


def _jax_devices_report_cuda(devices) -> bool:
    """Return True when any JAX device names a CUDA or GPU backend."""

    for device in devices:
        try:
            text = str(device).lower()
        except Exception:  # pragma: no cover - a broken device must not crash
            continue
        if "cuda" in text or "gpu" in text:
            return True
    return False


def _jax_cuda_available() -> bool:
    try:
        import jax  # noqa: PLC0415 - optional, only present in the model env
    except Exception:
        return False
    try:
        return _jax_devices_report_cuda(jax.devices())
    except Exception:  # pragma: no cover - a broken driver must not crash planning
        return False


def _external_cuda_available(python: str) -> bool:
    """Return True when the interpreter reports torch or JAX CUDA devices."""
    executable = str(python or "").strip()
    if not executable:
        return False
    if not Path(executable).is_file():
        found = shutil.which(executable)
        if not found:
            return False
        executable = found
    try:
        completed = subprocess.run(
            [executable, "-c", _PROBE_SCRIPT],
            capture_output=True,
            text=True,
            timeout=180,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    if completed.returncode != 0:
        return False
    backends = {item.strip() for item in completed.stdout.strip().split(",")}
    return bool(backends & {"torch", "jax"})


def cuda_available(python: str = "") -> bool:
    """Return True when torch or JAX sees a CUDA device here or in ``python``.

    A model that runs on JAX (ColabFold) can see a device while torch in the
    same environment is a CPU build, so both frameworks have to be asked.
    """

    if _torch_cuda_available() or _jax_cuda_available():
        return True
    return _external_cuda_available(python)


def resolve_device(value, operator: str, *, python: str = "") -> str:
    """Return ``cpu`` or ``cuda`` for a parameter value.

    ``auto`` (or an empty value) picks CUDA when it is usable.  Anything else
    must be one of the two concrete names so a typo fails loudly.
    """

    text = str(value or "").strip().lower() or AUTO
    if text in (AUTO, "gpu", "cuda:0"):
        return CUDA if cuda_available(python) else CPU
    if text in (CPU, CUDA):
        return text
    raise StepError(
        f"{operator}: device must be 'auto', 'cpu' or 'cuda', got {value!r}"
    )
