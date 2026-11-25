"""Resolve the interpreter of an isolated environment for subprocess-based steps."""
from __future__ import annotations

import os
import sys
from pathlib import Path

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
        found = None
    if found:
        return str(found)
    # Operators execute inside their own environment prefix, which is usually a
    # sibling of the environment they need; fall back to that layout so a step
    # can launch a tool from another declared environment.
    layouts = ('bin/python', 'Scripts/python.exe', 'python.exe')
    bases = []
    for value in (Path(sys.prefix), Path(sys.prefix).resolve()):
        bases.append(value.parent)
        bases.extend(value.parent.glob(f'env-*/external/{name}'))
        bases.append(value.parent / 'external' / name)
    for base in bases:
        for layout in layouts:
            candidate = base / name / layout if base.name != name else base / layout
            if candidate.is_file() and os.access(candidate, os.X_OK):
                return str(candidate)
    return ""
