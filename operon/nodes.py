"""Discover compute nodes and rank them by free capacity.

The pool service is the only allocator inside one physical capacity domain.
This module measures the domains the desktop can dispatch to (the local host
and every configured SSH server) so automatic placement can prefer the node
with the most headroom instead of the first one listed. A probe is read-only:
it allocates nothing, reserves nothing and transfers nothing.
"""
from __future__ import annotations

import os
import platform
import shutil
import subprocess
import threading
import time
from pathlib import Path

CACHE_SECONDS = 20.0
PROBE_TIMEOUT = 8.0
WEIGHT_MEMORY = 0.5
WEIGHT_CPU = 0.3
WEIGHT_DISK = 0.2
GPU_BONUS = 0.15
SLURM_NODE_LIMIT = 256

_CACHE: dict[int, tuple[float, list]] = {}
_LOCK = threading.Lock()


def _slurm_nodes() -> dict:
    """Read the batch inventory when this host runs Slurm; empty otherwise."""
    binary = shutil.which('sinfo')
    if not binary:
        return {'available': False, 'nodes': [], 'idle': 0}
    try:
        output = subprocess.run(
            [binary, '-h', '-N', '-o', '%N|%P|%a|%t|%c|%m|%G'],
            check=False, capture_output=True, text=True,
            timeout=PROBE_TIMEOUT).stdout
    except (OSError, subprocess.TimeoutExpired):
        return {'available': False, 'nodes': [], 'idle': 0}
    nodes = []
    for line in output.splitlines():
        parts = line.strip().split('|')
        if len(parts) < 7:
            continue
        name, partition, availability, state, cpus, memory, gres = parts[:7]
        nodes.append({'name': name, 'partition': partition,
                      'available': availability.lower().startswith('up'),
                      'state': state,
                      'cpus': int(cpus) if cpus.strip().isdigit() else 0,
                      'memory_mb': int(memory) if memory.strip().isdigit() else 0,
                      'gres': gres})
    idle = sum(1 for node in nodes if node['state'].startswith('idle'))
    return {'available': True, 'nodes': nodes[:SLURM_NODE_LIMIT], 'idle': idle}


def _gpu_count() -> int:
    try:
        return sum(1 for _ in Path('/dev').glob('nvidia[0-9]*'))
    except OSError:
        return 0


def snapshot(root='.') -> dict:
    """Measure one host: CPU, load, memory, disk, GPUs and batch inventory."""
    cpu = os.cpu_count() or 1
    try:
        load = float(os.getloadavg()[0])
    except (AttributeError, OSError):
        load = None
    memory = {'total_bytes': 0, 'available_bytes': 0}
    disk = {'total_bytes': 0, 'free_bytes': 0}
    try:
        import psutil
        usage = psutil.virtual_memory()
        memory = {'total_bytes': int(usage.total), 'available_bytes': int(usage.available)}
    except Exception:  # noqa: BLE001 - a probe never fails the caller
        pass
    try:
        usage = shutil.disk_usage(str(Path(root).expanduser().resolve()))
        disk = {'total_bytes': int(usage.total), 'free_bytes': int(usage.free)}
    except OSError:
        pass
    return {'host': platform.node(), 'platform': f'{platform.system().lower()}-{platform.machine()}',
            'cpu_count': cpu, 'load': load, 'memory': memory, 'disk': disk,
            'gpus': _gpu_count(), 'slurm': _slurm_nodes()}


def score(value: dict) -> float:
    """Rank a snapshot: more free memory, CPU and disk headroom scores higher."""
    memory = value.get('memory') or {}
    disk = value.get('disk') or {}
    total_memory = int(memory.get('total_bytes') or 0)
    total_disk = int(disk.get('total_bytes') or 0)
    memory_ratio = (int(memory.get('available_bytes') or 0) / total_memory) if total_memory else 0.0
    load = value.get('load')
    cpu = max(int(value.get('cpu_count') or 1), 1)
    cpu_free = 1.0 - min(float(load) / cpu, 1.0) if load is not None else 0.5
    disk_ratio = (int(disk.get('free_bytes') or 0) / total_disk) if total_disk else 0.0
    total = WEIGHT_MEMORY * memory_ratio + WEIGHT_CPU * cpu_free + WEIGHT_DISK * disk_ratio
    if int(value.get('gpus') or 0) > 0:
        total += GPU_BONUS
    return round(total, 4)


def order(nodes) -> list[str]:
    """Target keys in preferred dispatch order: available first, then capacity."""
    return [node['target'] for node in sorted(
        nodes, key=lambda node: (not node.get('available'), -float(node.get('score') or 0.0)))]


def _local(service) -> dict:
    root = getattr(service, 'root', None) or '.'
    node = {'target': 'local', 'kind': 'local', 'name': '本机', 'connected': True,
            'available': True, 'error': ''}
    try:
        node.update(snapshot(root))
    except Exception as exc:  # noqa: BLE001 - keep the node visible when a probe fails
        node.update({'host': platform.node(), 'platform': platform.system().lower(),
                     'cpu_count': os.cpu_count() or 1, 'load': None,
                     'memory': {'total_bytes': 0, 'available_bytes': 0},
                     'disk': {'total_bytes': 0, 'free_bytes': 0}, 'gpus': 0,
                     'slurm': {'available': False, 'nodes': [], 'idle': 0},
                     'error': f'{type(exc).__name__}: {exc}'})
    node['score'] = score(node)
    return node


def _remote(remotes, item: dict) -> dict:
    profile = item.get('profile') or {}
    key = str(profile.get('id') or '')
    node = {'target': key, 'kind': 'ssh', 'name': str(profile.get('name') or key),
            'host': str(profile.get('host') or ''), 'platform': '',
            'connected': bool(item.get('connected')), 'available': False, 'error': '',
            'cpu_count': 0, 'load': None,
            'memory': {'total_bytes': 0, 'available_bytes': 0},
            'disk': {'total_bytes': 0, 'free_bytes': 0}, 'gpus': 0,
            'slurm': {'available': False, 'nodes': [], 'idle': 0}, 'score': 0.0}
    if not node['connected']:
        node['error'] = '服务器未连接'
        return node
    try:
        value = remotes.call(key, 'host_capacity', {})
    except Exception as exc:  # noqa: BLE001 - one unreachable node must not break the list
        node['error'] = f'{type(exc).__name__}: {exc}'
        return node
    if not isinstance(value, dict):
        node['error'] = 'host_capacity returned no measurement'
        return node
    for field in ('host', 'platform', 'cpu_count', 'load', 'memory', 'disk', 'gpus', 'slurm'):
        if field in value:
            node[field] = value[field]
    node['available'] = True
    node['score'] = score(node)
    return node


def inventory(service, *, refresh: bool = False) -> list[dict]:
    """List this desktop and every configured server with its free capacity."""
    key = id(service)
    now = time.monotonic()
    if not refresh:
        with _LOCK:
            entry = _CACHE.get(key)
            if entry and entry[0] > now:
                return entry[1]
    nodes = [_local(service)]
    remotes = getattr(service, 'remotes', None)
    if remotes is not None:
        for item in remotes.status():
            nodes.append(_remote(remotes, item))
    with _LOCK:
        _CACHE[key] = (now + CACHE_SECONDS, nodes)
    return nodes
