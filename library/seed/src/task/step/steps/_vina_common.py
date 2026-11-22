"""Shared helper for the AutoDock Vina operators."""

from __future__ import annotations

import os
import shutil
from pathlib import Path

_BINARY_NAMES = ("vina_1.2.5_linux_x86_64", "vina", "vina_1.2.5")


def resolve_binary(name: str = "vina") -> str:
    """Return a usable vina executable: PATH first, then the declared resource."""

    candidate = str(name or "vina").strip() or "vina"
    found = shutil.which(candidate)
    if found:
        return found
    if Path(candidate).expanduser().is_file():
        return str(Path(candidate).expanduser())
    try:
        from ._resources_common import check_resource, load_resources, resolved_path
    except Exception:  # pragma: no cover - helper import guard
        return candidate
    try:
        resource = load_resources()["vina"]
        check = check_resource(resource)
    except Exception:  # pragma: no cover - manifest guard
        return candidate
    if check.get("status") != "ok":
        return candidate
    root = Path(check["root"])
    for entry in _BINARY_NAMES:
        path = resolved_path(root, entry)
        if path.is_file():
            try:
                if not os.access(path, os.X_OK):
                    path.chmod(0o755)
            except OSError:  # pragma: no cover - read-only link
                pass
            return str(path)
    return candidate
