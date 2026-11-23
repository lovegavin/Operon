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


def _external_cuda_available(python: str) -> bool:
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
            [executable, "-c", "import torch; print(torch.cuda.is_available())"],
            capture_output=True,
            text=True,
            timeout=120,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return completed.returncode == 0 and completed.stdout.strip() == "True"


def cuda_available(python: str = "") -> bool:
    """Return True when torch in-process or in ``python`` sees a CUDA device."""

    if _torch_cuda_available():
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
