"""Pick an OpenMM platform for the OpenMM operators.

The pip wheel ships Reference and CPU every time, and OpenCL or CUDA when the
build has GPU support.  The CPU platform starts one busy-waiting thread per
core, which pegs a whole node when the host admits the job with a single CPU,
so the operators pass the admitted CPU count through as the thread count.
"""

from __future__ import annotations

import os

GPU_PLATFORMS = ("CUDA", "OpenCL", "HIP")
FALLBACK_PLATFORMS = ("CPU", "Reference")


def _visible_cpus() -> int:
    try:
        return max(1, len(os.sched_getaffinity(0)))
    except (AttributeError, OSError):
        return max(1, os.cpu_count() or 1)


def _admitted_cpus() -> int:
    for name in ("OPERON_CPU_LIMIT", "OPERON_THREADS", "OMP_NUM_THREADS"):
        raw = os.environ.get(name, "").strip()
        if raw.isdigit() and int(raw) > 0:
            return int(raw)
    return 0


def available_platforms(openmm) -> dict:
    return {
        openmm.Platform.getPlatform(index).getName(): openmm.Platform.getPlatform(index)
        for index in range(openmm.Platform.getNumPlatforms())
    }


def select_platform(
    openmm, requested: str = "auto", threads: int = 0, precision: str = "mixed"
):
    """Return ``(name, platform, properties)`` for the requested preference.

    ``precision`` only applies to the GPU platforms; ``double`` is required for
    implicit-solvent MD, where mixed precision can drift into non-finite energies.
    """

    platforms = available_platforms(openmm)
    request = str(requested or "auto").strip()
    if request.lower() in ("", "auto"):
        chosen = next((name for name in GPU_PLATFORMS + FALLBACK_PLATFORMS if name in platforms), "")
        if not chosen:
            raise RuntimeError(f"no OpenMM platform is available; found {sorted(platforms)}")
    else:
        chosen = request
        if chosen not in platforms:
            raise RuntimeError(f"OpenMM platform {chosen!r} is not available; found {sorted(platforms)}")

    properties: dict[str, str] = {}
    if chosen in GPU_PLATFORMS:
        wanted = str(precision or "mixed").strip().lower()
        if wanted not in ("single", "mixed", "double"):
            raise RuntimeError(f"unsupported OpenMM precision {precision!r}")
        properties["Precision"] = wanted
    elif chosen == "CPU":
        count = int(threads or 0) or _admitted_cpus() or _visible_cpus()
        properties["Threads"] = str(max(1, count))
    return chosen, platforms[chosen], properties


def describe(name: str, properties: dict) -> dict:
    return {"platform": name, "platform_properties": dict(properties)}
