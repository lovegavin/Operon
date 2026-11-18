"""Rough install sizes for the declared isolated environments.

The panel needs a denominator before anything is downloaded, so each built-in
environment carries a studied estimate. Real sizes recorded after a successful
install take precedence, which keeps the bar accurate on repeat machines.
"""
from __future__ import annotations

import json
import platform
from pathlib import Path

from . import environments

LEARNED = '.operon-environment-sizes.json'

# Median download+install footprint of one environment, in bytes. The numbers
# follow the pinned wheels: torch builds dominate every entry except openmm.
ESTIMATES = {
    'antifold': 2_200_000_000,
    'boltz': 3_900_000_000,
    'colabfold': 2_600_000_000,
    'esm3': 5_400_000_000,
    'esmfold': 2_100_000_000,
    'openfold': 3_100_000_000,
    'openmm81': 145_000_000,
}
FALLBACK = 2_000_000_000

# CPU-only Linux images are slightly smaller; macOS wheels are larger.
_PLATFORM_FACTOR = {'win32': 1.0, 'linux': 0.92, 'darwin': 1.05}


def learned(root=None) -> dict:
    path = environments.root() if root is None else environments._native_path(Path(root))
    try:
        value = json.loads((Path(path) / LEARNED).read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return {}
    return value if isinstance(value, dict) else {}


def _scale(value: int) -> int:
    factor = _PLATFORM_FACTOR.get(platform.system().lower(), 1.0)
    return int(value * factor)


def expected(name: str, entry=None, root=None) -> int | None:
    """Best available size estimate for one environment, in bytes."""
    recorded = learned(root).get(name)
    if isinstance(recorded, (int, float)) and recorded > 0:
        return int(recorded)
    value = ESTIMATES.get(name)
    if value:
        return _scale(value)
    entry = entry if isinstance(entry, dict) else {}
    hinted = entry.get('size_bytes')
    if isinstance(hinted, (int, float)) and hinted > 0:
        return int(hinted)
    return _scale(FALLBACK)


def record(name: str, size: int, root=None) -> None:
    """Remember a measured size so the next machine with the same library is exact."""
    if not isinstance(size, (int, float)) or size <= 0:
        return
    path = environments.root() if root is None else environments._native_path(Path(root))
    path = Path(path)
    values = learned(root)
    values[name] = int(size)
    try:
        path.mkdir(parents=True, exist_ok=True)
        temporary = path / (LEARNED + '.tmp')
        temporary.write_text(json.dumps(values, indent=2, sort_keys=True), encoding='utf-8')
        temporary.replace(path / LEARNED)
    except OSError:
        return
