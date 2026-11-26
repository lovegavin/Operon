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
import re
import shlex
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
NODE_CAPACITY = WEIGHT_MEMORY + WEIGHT_CPU + GPU_BONUS
READY_HALF = 0.5
IDLE_FACTOR = 1.0
MIXED_FACTOR = 0.8

_CACHE: dict[int, tuple[float, list]] = {}
_READY_CACHE: dict[tuple[str, str], tuple[float, bool]] = {}
_LOCK = threading.Lock()


def _as_int(text) -> int:
    text = str(text).strip()
    return int(text) if text.isdigit() else 0


def _cpu_counts(text) -> tuple[int, int, int, int]:
    parts = [part.strip() for part in str(text).split('/')]
    if len(parts) != 4 or not all(part.isdigit() for part in parts):
        return (0, 0, 0, 0)
    return tuple(int(part) for part in parts)


def _node_gpus(gres) -> int:
    text = str(gres or '')
    if 'gpu' not in text.lower():
        return 0
    counts = [int(value) for value in re.findall(r'\d+', text)]
    return max(counts) if counts else 1


def _state_factor(state) -> float:
    text = str(state or '').strip().lower()
    if text.startswith('idle'):
        return IDLE_FACTOR
    if text.startswith('mix'):
        return MIXED_FACTOR
    if text.startswith(('alloc', 'drain', 'down', 'fail', 'maint', 'power')):
        return 0.0
    return MIXED_FACTOR


def capacity(node: dict) -> float:
    """Raw capacity of one batch node from its own idle CPU and free memory."""
    total_memory = int(node.get('memory_mb') or 0)
    free_memory = int(node.get('memory_free_mb') or 0)
    memory_ratio = (free_memory / total_memory) if total_memory else 0.0
    total_cpu = int(node.get('cpus') or 0)
    idle_cpu = int(node.get('cpus_idle') or 0)
    cpu_ratio = (idle_cpu / total_cpu) if total_cpu else 0.0
    total = (WEIGHT_MEMORY * memory_ratio + WEIGHT_CPU * cpu_ratio) * _state_factor(node.get('state'))
    if int(node.get('gpus') or 0) > 0:
        total += GPU_BONUS
    return round(min(total, NODE_CAPACITY), 4)


def readiness_score(node: dict) -> float:
    """Capacity folded into the readiness bands: unready nodes stay below 0.5."""
    base = capacity(node) / NODE_CAPACITY if NODE_CAPACITY else 0.0
    base = max(0.0, min(base, 1.0))
    if node.get('env_ready') is False:
        return round(READY_HALF * base, 4)
    return round(READY_HALF + READY_HALF * base, 4)


def _node_ready(name: str, marker: str) -> bool:
    key = (str(name), str(marker))
    now = time.monotonic()
    cached = _READY_CACHE.get(key)
    if cached and cached[0] > now:
        return cached[1]
    binary = shutil.which('srun')
    ready = False
    if binary:
        try:
            done = subprocess.run(
                [binary, '-w', str(name), '-N1', '-n1', '-t', '15', 'bash', '-lc',
                 f'test -x {shlex.quote(str(marker))}'],
                check=False, capture_output=True, text=True, timeout=PROBE_TIMEOUT * 3)
            ready = done.returncode == 0
        except (OSError, subprocess.TimeoutExpired):
            ready = False
    _READY_CACHE[key] = (now + CACHE_SECONDS, ready)
    return ready


def rank_compute(items) -> list:
    """Score batch nodes and return them best first; readiness lives in the score."""
    ranked = []
    for node in items:
        item = dict(node)
        item['capacity'] = capacity(item)
        item['score'] = readiness_score(item)
        item['selectable'] = True
        item['reason'] = '' if item.get('env_ready') is not False else '环境未就绪'
        ranked.append(item)
    ranked.sort(key=lambda item: (-float(item['score']), str(item.get('name') or '')))
    for index, item in enumerate(ranked, 1):
        item['rank'] = index
    return ranked


def _slurm_nodes(ready_marker: str | None = None) -> dict:
    """Read the batch inventory when this host runs Slurm; empty otherwise."""
    binary = shutil.which('sinfo')
    if not binary:
        return {'available': False, 'nodes': [], 'idle': 0}
    try:
        output = subprocess.run(
            [binary, '-h', '-N', '-o', '%N|%P|%a|%t|%C|%m|%e|%G'],
            check=False, capture_output=True, text=True,
            timeout=PROBE_TIMEOUT).stdout
    except (OSError, subprocess.TimeoutExpired):
        return {'available': False, 'nodes': [], 'idle': 0}
    nodes = []
    for line in output.splitlines():
        parts = line.strip().split('|')
        if len(parts) < 8:
            continue
        name, partition, availability, state, cpu_states, memory, memory_free, gres = parts[:8]
        _allocated, idle, _other, total = _cpu_counts(cpu_states)
        nodes.append({'name': name, 'partition': partition,
                      'available': availability.lower().startswith('up'),
                      'state': state.split('+')[0].strip().lower(),
                      'cpus': total, 'cpus_idle': idle,
                      'memory_mb': _as_int(memory), 'memory_free_mb': _as_int(memory_free),
                      'gpus': _node_gpus(gres),
                      'env_ready': _node_ready(name, ready_marker) if ready_marker else None})
    idle = sum(1 for node in nodes if node['state'].startswith('idle'))
    return {'available': True, 'nodes': rank_compute(nodes)[:SLURM_NODE_LIMIT], 'idle': idle}


def _gpu_count() -> int:
    try:
        return sum(1 for _ in Path('/dev').glob('nvidia[0-9]*'))
    except OSError:
        return 0


def snapshot(root='.', ready_marker: str | None = None) -> dict:
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
            'gpus': _gpu_count(), 'slurm': _slurm_nodes(ready_marker)}


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
        marker = Path(root).expanduser().parent / 'environments' / 'core' / 'bin' / 'python'
        node.update(snapshot(root, ready_marker=str(marker) if marker.is_file() else None))
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

def execution_node(graph: dict) -> str:
    """Return the compute node requested by a graph runtime, if any."""
    runtime = (graph or {}).get('runtime') or {}
    execution = runtime.get('execution') or {}
    value = execution.get('node')
    return str(value).strip() if isinstance(value, str) else ''


def srun_command(command, node: str, cpus: int = 1):
    """Wrap a job command so Slurm runs it on the requested compute node."""
    node = str(node or '').strip()
    parts = [str(part) for part in command]
    if not node:
        return parts
    if not re.fullmatch(r'[A-Za-z0-9_.-]{1,120}', node):
        raise RuntimeError(f'invalid compute node name {node!r}')
    srun = shutil.which('srun')
    if not srun:
        raise RuntimeError(f'execution node {node!r} was requested but slurm (srun) is not available on this host')
    cores = max(1, int(cpus or 1))
    return [srun, '-N', '1', '-n', '1', '--nodelist', node, '-c', str(cores), '--time', '1440',
            '--export=ALL', *parts]

