"""Resolve the interpreter of an isolated environment for subprocess-based steps."""
from __future__ import annotations

import os

__all__ = ["environment_python"]


def environment_python(name: str) -> str:
    """Return the interpreter of ``name``, or an empty string when it cannot be resolved.

    Subprocess-based operators must not fall back to the interpreter that runs the
    engine: on Windows that interpreter is the application runtime, which does not
    contain the operator's dependencies and produces ``WinError 193`` style failures.
    """
    override = os.environ.get(f"OPERON_ENV_{name.upper()}")
    if override:
        return override
    try:
        from operon import environments
    except Exception:  # noqa: BLE001 - the pipeline may run without the app package
        return ""
    try:
        found = environments.resolve(name)
    except Exception:  # noqa: BLE001
        return ""
    return str(found) if found else ""
