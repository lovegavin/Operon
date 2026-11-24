"""Provision isolated operator environments declared by the imported library.

The library bundle is the only dependency source. ``sources/operon/environments.json``
declares the interpreter, package list and import probes; nothing here invents
versions or reads an external manifest. Creation is staged, locked per environment
and committed by receipt, so a failed attempt never replaces a working runtime.
"""
from __future__ import annotations
import re

import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import tarfile
import tempfile
import threading
import time
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path

from . import environment_estimates as estimates
from . import environments

PIP_TRANSFER = ['--disable-pip-version-check', '--no-input', '--timeout', '120', '--retries', '3', '--progress-bar', 'off']
PIP_INDEX = ['--index-url', os.environ.get('OPERON_PIP_INDEX') or 'https://pypi.org/simple']
PIP_TRUSTED = ['--trusted-host', os.environ['OPERON_PIP_TRUSTED_HOST']] if os.environ.get('OPERON_PIP_TRUSTED_HOST') else []
CONDA_FORGE = 'conda-forge'
CONDA_BIOCONDA = 'bioconda'
BIOCONDA_MARKERS = ('hmmer', 'infernal', 'prodigal', 'amrfinder', 'antismash')

PLATFORM = 'windows' if os.name == 'nt' else ('darwin' if sys.platform == 'darwin' else 'linux')
UNSUPPORTED_HINT = (
    '该环境依赖的命令行工具只有 Linux/macOS 构建（bioconda 与 conda-forge 都没有 win-64 包）。'
    '请在远程 Linux 服务器上准备该环境，或在本机手动安装后把目录链接进资源库。'
)
STALL_SECONDS = 60.0
BUILD_STALL_SECONDS = STALL_SECONDS
# The first line can take a while: pip resolves a large dependency graph before it
# prints anything, and micromamba unpacks its payload before the first progress bar.
# Only the silence *after* the command started talking is limited by ``stall``.
STARTUP_SECONDS = 300.0
# micromamba writes nothing to a pipe while it resolves and unpacks packages,
# so conda steps get a longer silent start-up window than pip steps.
CONDA_STARTUP_SECONDS = 1800.0
_CONDA_MISSING = re.compile(r'[\u251c\u2514]\S*\s*([A-Za-z0-9_.+\-]+)\s*=?\s*\S*\s*\*?\s*does not exist')


def platform_supported(entry) -> bool:
    """Return False when the manifest restricts an environment to other systems."""
    if not isinstance(entry, dict):
        return True
    platforms = entry.get('platforms') or ()
    if not platforms:
        return True
    return PLATFORM in {str(item).strip().lower() for item in platforms}


def unsupported_reason(entry) -> str:
    """Readable explanation for an environment that cannot run on this system."""
    if platform_supported(entry):
        return ''
    platforms = ', '.join(str(item) for item in (entry.get('platforms') or ()))
    title = str(entry.get('title') or 'this environment')
    return f'{title} 仅支持 {platforms}，当前系统为 {PLATFORM}。{UNSUPPORTED_HINT}'


def readable_conda_error(text: str) -> str:
    """Turn micromamba's solver dump into a short, actionable message."""
    value = str(text or '')
    if 'does not exist' not in value:
        return value
    missing: list[str] = []
    for line in value.splitlines():
        match = _CONDA_MISSING.search(line)
        if match:
            name = match.group(1).strip()
            if name and name not in missing and 'critical' not in name:
                missing.append(name)
    if not missing:
        return value
    listed = '、'.join(missing)
    return (
        f'当前系统找不到这些 conda 包：{listed}。'
        f'它们通常只有 Linux/macOS 的 bioconda 构建，Windows 没有对应包。{UNSUPPORTED_HINT}'
    )
LOGS = '.operon-environment-logs'
ERRORS = '.operon-environment-errors'
PROGRESS = '.operon-environment-progress'
MAMBA_MIN_BYTES = 1_000_000
# Concurrent preparations share one micromamba binary and one disk. Without
# these guards, six environments download it six times and replace an image a
# sibling process is already running, which Windows rejects with
# ``[WinError 5] access denied``.
_MAMBA_LOCK = threading.Lock()
_PREPARE_SLOTS: dict[str, threading.BoundedSemaphore] = {}
_PREPARE_SLOTS_LOCK = threading.Lock()


def _slot_for(root) -> threading.BoundedSemaphore:
    """Return the installation slot for one environment root.

    Local installs and remote-agent installs run against different roots and
    must not block each other, so the in-process serialisation is keyed by the
    resolved root instead of being global.
    """
    key = str(base(root))
    with _PREPARE_SLOTS_LOCK:
        slot = _PREPARE_SLOTS.get(key)
        if slot is None:
            slot = threading.BoundedSemaphore(1)
            _PREPARE_SLOTS[key] = slot
        return slot


def base(root=None) -> Path:
    return environments.root() if root is None else environments._native_path(Path(root).expanduser())


def target(name: str, root=None) -> Path:
    return base(root) / name


def spec_sha256(entry: dict) -> str:
    return hashlib.sha256(json.dumps(entry, sort_keys=True, ensure_ascii=True).encode('utf-8')).hexdigest()


def _read(path: Path):
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return {}


def receipt(name: str, root=None) -> dict:
    return _read(target(name, root) / 'receipt.json')


def _error_path(name: str, root=None) -> Path:
    return base(root) / ERRORS / f'{name}.json'


def log_path(name: str, root=None) -> Path:
    """Persistent, append-only log for every operation on one environment."""
    return base(root) / LOGS / f'{name}.log'


def append_log(name: str, line: str, root=None) -> None:
    """Write one timestamped line; never let logging break an install."""
    try:
        target = log_path(name, root)
        target.parent.mkdir(parents=True, exist_ok=True)
        stamp = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
        with target.open('a', encoding='utf-8') as handle:
            handle.write(f'[{stamp}] {line}\n')
    except OSError:
        pass


def progress_path(name: str, root=None) -> Path:
    return base(root) / PROGRESS / f'{name}.json'


def read_progress(name: str, root=None) -> dict:
    return _read(progress_path(name, root))


def _write_progress(name: str, root, value: dict) -> None:
    path = progress_path(name, root)
    path.parent.mkdir(parents=True, exist_ok=True)
    if value.get('phase') == 'failed' and read_progress(name, root).get('phase') == 'cancelled':
        # A cancellation recorded by the request thread must not be replayed as a
        # failure by the worker that was stopped halfway.
        return
    if value.get('phase') in ('ready', 'failed', 'cancelled'):
        # Transient download bookkeeping must not outlive the run: a ready
        # environment that still advertises "stage: downloading" confuses the panel.
        value = {key: item for key, item in value.items()
                 if key not in ('stage', 'fetched', 'pid', 'command')}
    temporary = path.with_name(
        f'.{path.name}.{os.getpid()}-{threading.get_ident()}-{uuid.uuid4().hex[:6]}.tmp'
    )
    temporary.write_text(json.dumps(value, indent=2), encoding='utf-8')
    for attempt in range(5):
        try:
            os.replace(temporary, path)
            return
        except PermissionError:
            if attempt == 4:
                raise
            time.sleep(0.05 * (attempt + 1))


def _usage(*directories) -> tuple[int, int]:
    size = files = 0
    for directory in directories:
        for parent, _, names in os.walk(directory):
            for item in names:
                try:
                    size += (Path(parent) / item).stat().st_size
                    files += 1
                except OSError:
                    pass
    return size, files


def mark_cancelled(name: str, root=None) -> bool:
    """Report a cancelled preparation immediately instead of waiting for the worker.

    Returns ``False`` when the environment already finished, so callers can tell the
    difference between a cancelled preparation and one that was committed first.
    """
    progress = read_progress(name, root)
    phase = str(progress.get('phase') or '')
    if phase not in {'queued', 'creating', 'installing', 'probing', 'committing'}:
        return False
    progress.update({'phase': 'cancelled', 'detail': 'cancelled by user', 'error': '',
                     'updated_at': _now()})
    _write_progress(name, root, progress)
    return True


def mark_failed(name: str, root, error) -> bool:
    """Record why a preparation stopped so the panel can show it.

    The worker used to swallow the exception, which left a request that returned
    200 with the last recorded phase still in place: pressing "prepare" again
    looked like a no-op.  A failure is a state, so it belongs in the progress file.
    """
    progress = read_progress(name, root) or {'name': name}
    if str(progress.get('phase') or '') == 'ready':
        return False
    message = f'{type(error).__name__}: {error}'
    progress.update({'phase': 'failed', 'detail': message[:400], 'error': message[:4000],
                     'updated_at': _now()})
    _write_progress(name, root, progress)
    return True



def _split_dependency_counts(rows) -> dict:
    """Count required dependencies apart from the optional ones.

    Only a missing *required* dependency makes an environment unusable, and the
    panel derives that from these two counters.  An optional binding that cannot
    be installed (``vina`` has no cp311 wheel) used to hold the card at
    "依赖缺失" even when every required dependency was in place.
    """
    required = [row for row in rows if not row.get('optional')]
    optional = [row for row in rows if row.get('optional')]
    return {
        'dependency_total': len(required),
        'dependency_installed': sum(1 for row in required if row.get('installed')),
        'optional_total': len(optional),
        'optional_installed': sum(1 for row in optional if row.get('installed')),
        'optional_missing': [str(row.get('name')) for row in optional if not row.get('installed')][:8],
    }


def dependency_counts(rows) -> dict:
    """Public form of the required/optional split for callers outside this module.

    The remote snapshot used to overwrite ``dependency_total`` with the combined
    count, which is why a ready environment with one optional binding still read
    as "依赖缺失" in the panel.
    """
    return _split_dependency_counts(rows)


def _dependency_fields(result: dict, entry: dict, directory: Path) -> None:
    """Attach declared-dependency counts even when the environment is not built yet.

    A brand new install has no interpreter, so the card used to hide "0 of 19"
    and the only visible state was "not installed" with no hint about what an
    install would bring.  Reporting the counts here keeps every state honest.
    """
    try:
        installed, total, rows = dependency_status(entry, directory)
    except Exception:
        return
    result['dependencies'] = rows
    result.update(_split_dependency_counts(rows))
    result['missing_dependencies'] = [str(row.get('name')) for row in rows
                                      if not row.get('installed') and not row.get('optional')][:8]


PREPARABLE_STATUSES = frozenset({'missing', 'failed', 'stale', 'incomplete'})


def needs_preparation(status: str) -> bool:
    """Return True when an environment in ``status`` should be prepared."""
    return status in PREPARABLE_STATUSES


def state(name: str, root=None, source=None) -> dict:
    """Report one environment without creating or probing anything."""
    entry = environments.describe(name, source)
    directory = target(name, root)

    def interpreter():
        for layout in ('bin/python', 'Scripts/python.exe', 'python.exe'):
            candidate = directory / layout
            if candidate.is_file() and os.access(candidate, os.X_OK):
                return candidate
        return None

    python = interpreter()
    if python is None and entry.get('venv_shared') and directory.is_dir():
        # A new server build replaces the interpreter this venv inherits from, so
        # its links dangle until they are pointed at the running interpreter.
        try:
            if rebind_venv(str(directory)):
                python = interpreter()
        except OSError:
            python = None
    expected = spec_sha256(entry)
    recorded = receipt(name, root)
    error = _read(_error_path(name, root))
    result = {
        'name': name,
        'python': str(entry.get('python', '3.11')),
        'spec_sha256': expected,
        'interpreter': str(python) if python else '',
        'location': str(directory),
        'imports': list(entry.get('imports') or []),
    }
    if not platform_supported(entry):
        # An environment the current platform cannot build is not a failed install:
        # it is simply not available here, and the reason travels with the note.
        result['status'] = 'missing'
        result['error'] = error.get('message') or unsupported_reason(entry)
        _dependency_fields(result, entry, directory)
    elif python is None:
        if error.get('message'):
            result['status'] = 'failed'
            result['error'] = error['message']
        elif directory.is_dir():
            # The directory exists but cannot start: call that failed rather than
            # "not installed", which hid a broken interpreter behind a fresh-install
            # button that would have refused to run.
            result['status'] = 'failed'
            result['error'] = 'the environment directory exists but its interpreter cannot start'
        else:
            result['status'] = 'missing'
            result['error'] = ''
        _dependency_fields(result, entry, directory)
    elif recorded.get('spec_sha256') != expected:
        result['status'] = 'stale'
        result['error'] = ''
    else:
        # Being installed is not the same as being usable: an environment whose
        # declared dependencies are missing still reports a working interpreter,
        # which used to surface as "ready" next to "0 of 19 installed" and then
        # failed every operator at run time.
        installed, total, rows = dependency_status(entry, directory)
        result['dependencies'] = rows
        result.update(_split_dependency_counts(rows))
        missing = [str(row.get('name')) for row in rows
                   if not row.get('installed') and not row.get('optional')]
        optional = [str(row.get('name')) for row in rows
                    if not row.get('installed') and row.get('optional')]
        result['missing_dependencies'] = missing[:8]
        result['optional_missing'] = optional[:8]
        if missing:
            detail = ', '.join(missing[:5])
            if len(missing) > 5:
                detail += f' (+{len(missing) - 5} more)'
            result['status'] = 'incomplete'
            result['error'] = (f'{installed} of {total} declared dependencies are installed; '
                               f'missing: {detail}')
        else:
            result['status'] = 'ready'
            result['error'] = error.get('message') or ''
    result['used_by'] = []
    reap_stale(name, root)
    progress = read_progress(name, root)
    result['progress'] = progress
    if progress.get('phase') == 'queued':
        result['status'] = 'queued'
        result['error'] = ''
    elif progress.get('phase') in {'creating', 'installing', 'probing', 'committing'}:
        result['status'] = 'installing'
        result['error'] = ''
    return result


def plan(root=None, descriptors=None, source=None) -> dict:
    """Plan every declared environment, optionally annotating operator owners."""
    owners = {}
    for descriptor in descriptors or ():
        name = (descriptor.get('resources') or {}).get('environment')
        if name:
            owners.setdefault(name, []).append(descriptor.get('id'))
    result = {}
    for name in sorted(environments.load(source)):
        item = state(name, root, source)
        item['used_by'] = sorted(owners.get(name, []))
        result[name] = item
    return result


def _now() -> str:
    return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())


_ACTIVE_PHASES = frozenset({'queued', 'creating', 'installing', 'probing', 'committing'})
_STALE_AFTER = 180.0


def _age_seconds(stamp) -> float:
    """Seconds since an ``updated_at`` marker; unknown stamps count as stale."""
    try:
        moment = datetime.strptime(str(stamp), '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return float('inf')
    return (datetime.now(timezone.utc) - moment).total_seconds()


def progress_stale(progress: dict, stale_after: float = _STALE_AFTER) -> bool:
    """True when an active phase was last touched too long ago to still be running."""
    if str(progress.get('phase') or '') not in _ACTIVE_PHASES:
        return False
    return _age_seconds(progress.get('updated_at')) > stale_after


def reap_stale(name: str, root=None) -> str:
    """Turn an orphaned active phase into a readable failure; return its message."""
    progress = read_progress(name, root)
    if not progress_stale(progress):
        return ''
    message = '上次安装已中断（安装进程已退出），请重新准备该环境。'
    base(root).mkdir(parents=True, exist_ok=True)
    path = _error_path(name, root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({'message': message, 'at': _now()}, indent=2), encoding='utf-8')
    _write_progress(name, root, {**progress, 'phase': 'failed', 'detail': 'interrupted',
                                 'error': message, 'updated_at': _now()})
    return message


def _emit(log, message):
    if log is not None:
        log(message)
    else:
        print(message, flush=True)


class Cancelled(RuntimeError):
    """Raised when the user cancels an environment preparation."""


class _Control:
    """Cooperative cancellation handle shared by the web layer and the installer."""

    def __init__(self, event=None):
        self.event = event or threading.Event()
        self.process = None

    @property
    def stopped(self):
        return self.event.is_set()

    def check(self):
        if self.event.is_set():
            raise Cancelled('preparation was cancelled')

    def stop(self):
        self.event.set()
        process = self.process
        if process is not None and process.poll() is None:
            try:
                process.kill()
            except OSError:
                pass



_PIP_BYTES = re.compile(r'\(\s*(\d+(?:\.\d+)?)(?:\s*/\s*\d+(?:\.\d+)?)?\s*([kKmMgG]i?[bB])\s*\)')


def _gpu_available() -> bool:
    """True when a CUDA device is visible on this machine."""
    if shutil.which('nvidia-smi') is None:
        return False
    try:
        probe = subprocess.run(['nvidia-smi', '-L'], capture_output=True, text=True, timeout=20)
    except (OSError, subprocess.SubprocessError):
        return False
    return probe.returncode == 0 and 'GPU' in (probe.stdout or '')


def _cpu_entry(entry: dict) -> dict:
    """Drop CUDA torch pins and let the installer fetch the CPU wheel instead."""
    def wanted(value: str) -> bool:
        return not re.match(r'^\s*torch[a-z]*([=<>!~ ]|$)', str(value), re.IGNORECASE)

    updated = dict(entry)
    for key in ('requirements', 'pip_wheels', 'pip_pypi', 'no_deps'):
        values = entry.get(key)
        if isinstance(values, list):
            updated[key] = [item for item in values if wanted(item)]
    updated['torch_cpu'] = True
    updated['torch_cuda'] = False
    return updated


def _track_line(line: str, progress: dict) -> None:
    text = line.strip()
    if not text:
        return
    match = _PIP_BYTES.search(text)
    if match and 'ownloading' in text:
        scale = {'kb': 1024.0, 'kib': 1024.0, 'mb': 1024.0 ** 2, 'mib': 1024.0 ** 2,
                 'gb': 1024.0 ** 3, 'gib': 1024.0 ** 3}.get(match.group(2).lower())
        if scale:
            fetched = int(progress.get('fetched') or 0) + int(float(match.group(1)) * scale)
            progress['fetched'] = fetched
            progress['bytes'] = max(int(progress.get('bytes') or 0), fetched)
            progress['stage'] = 'downloading'
            progress['files'] = int(progress.get('files') or 0) + 1
            progress['detail'] = text[:200]
            progress['updated_at'] = _now()
        return
    if text.startswith('Collecting ') or text.startswith('Requirement already satisfied'):
        progress['files'] = int(progress.get('files') or 0) + 1
        progress['updated_at'] = _now()


def _flush_progress(progress: dict) -> None:
    name = progress.get('name')
    root = progress.get('root')
    if not name or not root:
        return
    payload = {key: value for key, value in progress.items() if key != 'root'}
    try:
        _write_progress(name, root, payload)
    except OSError:
        pass

def _mamba_cache(root) -> Path | None:
    """Return the micromamba package cache when it lives outside the environment root."""

    override = os.environ.get('OPERON_MAMBA_CACHE') or os.environ.get('MAMBA_ROOT_PREFIX')
    candidates = []
    if override:
        candidates.append(Path(override).expanduser() / 'pkgs')
    try:
        candidates.append(base(root).parent / 'mamba-cache' / 'pkgs')
    except Exception:
        pass
    for candidate in candidates:
        try:
            if candidate.is_dir():
                return candidate
        except OSError:
            continue
    return None

def _process_io(pid):
    """Return the byte counters this process has moved, when the kernel exposes them."""

    try:
        with open(f'/proc/{pid}/io', 'rb') as handle:
            total = 0
            for line in handle.read().decode('ascii', 'replace').splitlines():
                key, _, value = line.partition(':')
                if key in ('read_bytes', 'write_bytes', 'rchar', 'wchar'):
                    total += int(value.strip())
            return total
    except (OSError, ValueError):
        return None


def _activity_signature(paths):
    signature = []
    for path in paths:
        try:
            signature.append((str(path), len(os.listdir(path))))
        except OSError:
            signature.append((str(path), -1))
    return tuple(signature)


def _run(argv, *, log, env=None, timeout=3600, progress=None, control=None,
         stall=BUILD_STALL_SECONDS, watch=None, deadline=None, startup=None):
    command = [str(part) for part in argv]
    if control is not None:
        control.check()
    _emit(log, '$ ' + ' '.join(command))
    if progress is not None:
        progress.update({'command': ' '.join(command)[:400], 'pid': None, 'updated_at': _now()})
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                               bufsize=0, env=env)
    if progress is not None:
        progress['pid'] = process.pid
        progress['updated_at'] = _now()
    if control is not None:
        control.process = process
    deadline = time.monotonic() + timeout if timeout else None
    chunks: list[str] = []
    last_flush = [time.monotonic()]
    started_at = time.monotonic()
    last_output = [started_at]
    first_output = [0.0]

    def drain():
        buffer = b''
        try:
            stream = process.stdout
            while True:
                block = stream.read(4096)
                if not block:
                    break
                last_output[0] = time.monotonic()
                buffer += block
                while True:
                    cut = min((index for index in (buffer.find(b'\r'), buffer.find(b'\n'))
                               if index >= 0), default=-1)
                    if cut < 0:
                        break
                    raw, buffer = buffer[:cut], buffer[cut + 1:]
                    line = raw.decode('utf-8', 'replace').strip()
                    if not line:
                        continue
                    chunks.append(line)
                    if progress is not None:
                        _track_line(line, progress)
                        if time.monotonic() - last_flush[0] > 1.5:
                            last_flush[0] = time.monotonic()
                            _flush_progress(progress)
            if buffer:
                line = buffer.decode('utf-8', 'replace').strip()
                if line:
                    if not first_output[0]:
                        first_output[0] = time.monotonic()
                    chunks.append(line)
        except Exception:
            pass

    reader = threading.Thread(target=drain, name='operon-run-reader', daemon=True)
    reader.start()
    watched = [Path(item) for item in (watch or ()) if item]
    activity = _activity_signature(watched)
    sampled = time.monotonic()
    sampled_io = [time.monotonic()]
    io_mark = [_process_io(process.pid)]
    try:
        while process.poll() is None:
            if control is not None and control.stopped:
                process.kill()
                raise Cancelled(f'preparation was cancelled during {" ".join(command[:2])}')
            if watched and time.monotonic() - sampled > 5.0:
                sampled = time.monotonic()
                current = _activity_signature(watched)
                if current != activity:
                    activity = current
                    last_output[0] = time.monotonic()
            if time.monotonic() - sampled_io[0] > 1.0:
                sampled_io[0] = time.monotonic()
                current_io = _process_io(process.pid)
                if current_io is not None:
                    if io_mark[0] is not None and current_io > io_mark[0]:
                        last_output[0] = time.monotonic()
                    io_mark[0] = current_io
            waited = time.monotonic() - last_output[0]
            if first_output[0]:
                limit, what = stall, f'produced no output for {stall:.0f}s'
            else:
                grace = STARTUP_SECONDS if startup is None else startup
                limit, what = grace, f'printed nothing in {grace:.0f}s'
            if limit and waited > limit:
                process.kill()
                raise RuntimeError(
                    f'{" ".join(command[:2])} {what}; '
                    f'aborted instead of waiting for the {timeout}s limit')
            if deadline is not None and time.monotonic() > deadline:
                process.kill()
                raise RuntimeError(f'{" ".join(command[:3])} timed out after {timeout}s')
            if progress is not None:
                progress['updated_at'] = _now()
            time.sleep(0.4)
    finally:
        if control is not None:
            control.process = None
    reader.join(timeout=10)
    output = '\n'.join(chunks)
    if progress is not None:
        _flush_progress(progress)
    if control is not None and control.stopped:
        raise Cancelled(f'preparation was cancelled during {" ".join(command[:2])}')
    tail = output or ''
    for line in [line for line in tail.splitlines() if line.strip()][-25:]:
        _emit(log, '  ' + line)
    if process.returncode:
        detail = " | ".join(line for line in tail.splitlines() if line.strip())[-600:]
        readable = readable_conda_error(detail)
        if readable != detail:
            raise RuntimeError(readable)
        raise RuntimeError(f'{" ".join(command[:2])} exited with {process.returncode}: {detail}')
    return tail


_SPACE_MARGIN = 1.25
_SPACE_FLOOR = 512 * 1024 * 1024


def require_space(root, needed, *, what='installation') -> int:
    """Refuse to start when the destination volume cannot hold ``needed`` bytes."""

    destination = base(root)
    try:
        destination.mkdir(parents=True, exist_ok=True)
        usage = shutil.disk_usage(str(destination))
    except OSError:
        return 0
    required = int(max(needed, 0) * _SPACE_MARGIN) + _SPACE_FLOOR
    if needed and usage.free < required:
        raise RuntimeError(
            f'not enough free space for {what}: {required} bytes required, '
            f'{usage.free} bytes available at {destination}')
    return usage.free


def _validate(spec: dict):
    if not isinstance(spec, dict):
        raise ValueError('invalid environment declaration')
    version = str(spec.get('python', '3.11'))
    if not version.replace('.', '').isdigit():
        raise ValueError(f'invalid Python version: {version}')
    for field in ('requirements', 'pip_pypi', 'pip_wheels', 'no_build_isolation', 'no_deps', 'conda_packages'):
        value = spec.get(field) or []
        if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
            raise ValueError(f'invalid environment field: {field}')
    for value in (spec.get('requirements') or []) + (spec.get('pip_pypi') or []) + (spec.get('pip_wheels') or []):
        lowered = value.lower()
        if 'file:' in lowered or 'ssh:' in lowered or lowered.startswith(('/', '.')) or 'git@' in lowered:
            raise ValueError(f'unsupported package source: {value}')
    build_env = spec.get('build_env') or {}
    if not isinstance(build_env, dict) or any(
            not isinstance(key, str) or not isinstance(value, str) for key, value in build_env.items()):
        raise ValueError('invalid environment field: build_env')
    for value in spec.get('no_build_isolation') or []:
        candidate = value.split(' @ ', 1)[1].strip() if ' @ ' in value else value.strip()
        if '://' not in candidate:
            # A bare requirement names a package that the environment already
            # declares; building it without isolation is the whole point of the
            # field, so there is no remote source to vet here.
            continue
        if not (candidate.startswith('https://') or candidate.startswith('git+https://')):
            raise ValueError(f'only https package sources are allowed: {value}')


def _mamba_usable(path: Path) -> bool:
    """A micromamba download only counts once the whole binary is on disk."""
    try:
        return path.is_file() and path.stat().st_size >= MAMBA_MIN_BYTES
    except OSError:
        return False


_INSTALL_LOCK = '.operon-install.lock'
_LOCK_STATE: dict[str, object] = {'handle': None}


def _lock_handle(handle) -> None:
    if os.name == 'nt':
        import msvcrt

        handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
    else:
        import fcntl

        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)


def _unlock_handle(handle) -> None:
    if os.name == 'nt':
        import msvcrt

        handle.seek(0)
        try:
            msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        except OSError:
            pass
    else:
        import fcntl

        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        except OSError:
            pass


def _acquire_slot(control, root=None) -> None:
    """Hold the single installation slot shared by every process.

    Environments are created by several processes at once (desktop API, remote
    agent, CLI). A threading semaphore only serialises one process, so the slot
    is also backed by an OS file lock under the environment root: two installs
    can never unpack into the same disk region concurrently.
    """
    slot = _slot_for(root)
    while not slot.acquire(timeout=0.5):
        control.check()
    try:
        directory = base(root)
        directory.mkdir(parents=True, exist_ok=True)
        handle = (directory / _INSTALL_LOCK).open('a+b')
        waited = False
        while True:
            try:
                _lock_handle(handle)
                break
            except OSError:
                if not waited:
                    waited = True
                    control.check()
                control.check()
                time.sleep(2.0)
        _LOCK_STATE['handle'] = handle
        _LOCK_STATE['slot'] = slot
    except BaseException:
        slot.release()
        raise


def _release_slot() -> None:
    handle = _LOCK_STATE.pop('handle', None)
    if handle is not None:
        try:
            _unlock_handle(handle)
        finally:
            try:
                handle.close()
            except OSError:
                pass
    try:
        slot = _LOCK_STATE.pop('slot', None)
        if slot is None:
            slot = _slot_for(None)
        slot.release()
    except ValueError:
        pass


def _download(url: str, destination: Path, log, control=None, *, timeout: float = 45.0,
              deadline: float = 420.0) -> int:
    """Stream one HTTPS payload with a hard deadline and cooperative cancellation.

    A stalled CDN connection used to freeze the whole preparation queue: the worker
    held the single slot while ``urlopen`` waited forever, so cancelling the job left
    the environment stuck in ``creating``. Chunked reads keep the control flag live.
    """
    started = time.monotonic()
    request = urllib.request.Request(url, headers={'User-Agent': 'operon-environment/1'})
    written = 0
    with urllib.request.urlopen(request, timeout=timeout) as source, destination.open('wb') as output:
        while True:
            if control is not None:
                control.check()
            if time.monotonic() - started > deadline:
                raise RuntimeError(f'download exceeded {deadline:.0f}s: {url}')
            chunk = source.read(1 << 20)
            if not chunk:
                break
            output.write(chunk)
            written += len(chunk)
    return written


def _conda_channels(environment) -> list[str]:
    """Conda builds of the CLI tools (hmmer, samtools, viennarna, minimap2…) live on bioconda.

    bioconda can only add resolution candidates, and strict channel priority keeps
    conda-forge ahead of it, so it is enabled whenever the environment installs any
    conda package at all instead of guessing from the package names.
    """
    packages = environment.get('conda_packages', ()) if isinstance(environment, dict) else environment or ()
    channels = [CONDA_FORGE]
    if packages:
        channels.append(CONDA_BIOCONDA)
    return channels


def _conda_flags(environment) -> list[str]:
    """Channel flags for one environment's conda packages."""

    # Operators on restricted networks can point conda at a mirror without
    # editing the library manifest: OPERON_CONDA_CHANNELS=https://mirror/conda-forge
    override = os.environ.get('OPERON_CONDA_CHANNELS')
    if override:
        channels = [item.strip() for item in override.split(',') if item.strip()]
    else:
        channels = _conda_channels(environment)
    flags: list[str] = []
    for channel in channels:
        flags.extend(['-c', channel])
    flags.append('--override-channels')
    return flags


def _micromamba(directory: Path, log, control=None) -> Path:
    override = os.environ.get('OPERON_MAMBA')
    if override and Path(override).is_file():
        return Path(override)
    system, machine = platform.system(), platform.machine().lower()
    target_name = {('Windows', 'amd64'): 'win-64', ('Windows', 'x86_64'): 'win-64',
                   ('Linux', 'x86_64'): 'linux-64', ('Linux', 'aarch64'): 'linux-aarch64'}.get((system, machine))
    if target_name is None:
        raise ValueError('automatic environment creation is unavailable on this platform; set OPERON_MAMBA')
    executable = directory / ('micromamba.exe' if system == 'Windows' else 'micromamba')
    if _mamba_usable(executable):
        return executable
    directory.mkdir(parents=True, exist_ok=True)
    # Serialise the download: replacing a running micromamba.exe fails on Windows.
    with _MAMBA_LOCK:
        if _mamba_usable(executable):
            return executable
        _emit(log, f'downloading micromamba ({target_name})')
        with tempfile.TemporaryDirectory(dir=directory) as temporary:
            archive = Path(temporary) / 'micromamba.tar.bz2'
            _download(f'https://micro.mamba.pm/api/micromamba/{target_name}/latest', archive, log, control)
            if archive.stat().st_size < MAMBA_MIN_BYTES:
                raise RuntimeError('micromamba download was incomplete')
            with tarfile.open(archive) as bundle:
                member = bundle.getmember('Library/bin/micromamba.exe' if system == 'Windows' else 'bin/micromamba')
                if not member.isfile():
                    raise ValueError('invalid micromamba archive')
                staged = Path(temporary) / executable.name
                with bundle.extractfile(member) as source, staged.open('wb') as output:
                    shutil.copyfileobj(source, output)
                staged.chmod(0o755)
                for attempt in range(6):
                    try:
                        staged.replace(executable)
                        break
                    except OSError as error:
                        if _mamba_usable(executable):
                            _emit(log, f'reusing the existing micromamba at {executable}')
                            break
                        if attempt == 5:
                            raise RuntimeError(
                                f'could not install micromamba at {executable}: {error}') from error
                        time.sleep(0.5 * (attempt + 1))
    return executable


def _python(directory: Path) -> Path:
    for layout in ('Scripts/python.exe', 'bin/python', 'python.exe'):
        candidate = directory / layout
        if candidate.is_file():
            return candidate
    raise RuntimeError('environment creation produced no interpreter')


def _mamba_env(directory: Path) -> dict:
    env = dict(os.environ)
    env['MAMBA_ROOT_PREFIX'] = str(directory / 'mamba')
    env['CONDA_PKGS_DIRS'] = str(directory / 'packages')
    env.setdefault('HOME', str(directory / 'home'))
    env.setdefault('USERPROFILE', str(directory / 'home'))
    return env


def _rewrite_shebangs(root: Path, stale: Path | None = None) -> int:
    """Point entry-point scripts at the promoted tree instead of the staging copy."""

    replacement = str(root).replace('\\', '/')
    needle = str(stale).replace('\\', '/') if stale is not None else ''
    if needle and needle == replacement:
        return 0
    changed = 0
    for folder in ('Scripts', 'bin'):
        directory = root / folder
        if not directory.is_dir():
            continue
        for script in directory.rglob('*'):
            if not script.is_file():
                continue
            try:
                with script.open('rb') as handle:
                    head = handle.readline(512)
            except OSError:
                continue
            if not head.startswith(b'#!'):
                continue
            first, separator, rest = b'', b'', b''
            try:
                data = script.read_bytes()
                first, separator, rest = data.partition(b'\n')
            except OSError:
                continue
            original = first.decode('utf-8', 'replace')
            if needle:
                if needle not in original:
                    continue
                updated = original.replace(needle, replacement)
            else:
                marker = '.staging-'
                index = original.find(marker)
                if index < 0:
                    continue
                tail = original.find('/', index)
                if tail < 0:
                    continue
                if not original.startswith('#!'):
                    continue
                updated = original[:2] + replacement + original[tail:]
            if updated == original:
                continue
            try:
                script.write_bytes(updated.encode('utf-8') + separator + rest)
                changed += 1
            except OSError:
                continue
    return changed


STAGING_MARKER = re.compile(r'\.staging-[^/\s:;\'"()]+')


def _relocate(root: Path, stale: Path | None = None) -> int:
    """Replace a staging prefix that a promoted tree still mentions.

    Conda packages bake their build prefix into generated wrappers, ``.pc``
    files, Perl module loaders and configuration files, not only into shebangs.
    Renaming the staging directory leaves those references dangling, so an
    environment can read as ready and still fail the moment a helper runs.
    """

    replacement = str(root).replace('\\', '/')
    literal = str(stale).replace('\\', '/') if stale is not None else None
    if literal is not None and literal == replacement:
        return 0
    changed = 0
    for entry in root.rglob('*'):
        try:
            if entry.is_symlink():
                text = os.readlink(entry).replace('\\', '/')
                if literal is not None and literal in text:
                    entry.unlink()
                    entry.symlink_to(text.replace(literal, replacement))
                    changed += 1
                continue
            if not entry.is_file() or entry.suffix in {'.pyc', '.so', '.dylib', '.a'}:
                continue
            if entry.stat().st_size > TEXT_LIMIT:
                continue
            data = entry.read_bytes()
            if b'\x00' in data[:8192]:
                continue
            if literal is not None:
                current = literal.encode('utf-8')
                if current not in data:
                    continue
                updated = data.replace(current, replacement.encode('utf-8'))
            else:
                original = data.decode('utf-8', 'surrogateescape')
                rewritten = STAGING_MARKER.sub(replacement, original)
                if rewritten == original:
                    continue
                updated = rewritten.encode('utf-8', 'surrogateescape')
            mode = entry.stat().st_mode
            entry.write_bytes(updated)
            os.chmod(entry, mode)
            changed += 1
        except OSError:
            continue
    return changed


def repair(name: str, root=None) -> dict:
    """Rewrite stale staging shebangs in an environment that is already installed."""

    directory = base(root) / name
    if not directory.is_dir():
        raise ValueError(f'environment {name!r} is not installed')
    changed = _rewrite_shebangs(directory)
    changed += _relocate(directory)
    return {'name': name, 'directory': str(directory), 'rewritten': changed}


def rebind_venv(location) -> int:
    """Point a ``--system-site-packages`` venv back at the running interpreter.

    These environments inherit everything from the interpreter that created them,
    which lives under the deployment directory.  Installing a new server build
    replaces that directory, so the recorded ``pyvenv.cfg`` home and the
    ``bin/python*`` links end up dangling: the environment still holds its own
    packages, but no interpreter can start, and the panel reported it as
    "not installed".  Rebinding rewrites the three paths and repairs the links.
    """
    root = Path(location)
    config = root / 'pyvenv.cfg'
    changed = 0
    if config.is_file():
        home = Path(sys.executable).parent
        lines = []
        for line in config.read_text(encoding='utf-8', errors='replace').splitlines():
            key = line.partition('=')[0].strip().lower()
            if key == 'home':
                lines.append(f'home = {home}')
            elif key == 'executable':
                lines.append(f'executable = {sys.executable}')
            elif key == 'command':
                lines.append(f'command = {sys.executable} -m venv --system-site-packages {root}')
            else:
                lines.append(line)
        updated = '\n'.join(lines) + '\n'
        if updated != config.read_text(encoding='utf-8', errors='replace'):
            config.write_text(updated, encoding='utf-8')
            changed += 1
    bin_dir = root / 'bin'
    if not bin_dir.is_dir():
        return changed
    for name in ('python3.11', 'python3.12', 'python3.13'):
        if (bin_dir / name).is_symlink() or (bin_dir / name).exists():
            link = bin_dir / name
            try:
                link.unlink()
            except OSError:
                pass
            link.symlink_to(sys.executable)
            changed += 1
            break
    for name in ('python', 'python3'):
        link = bin_dir / name
        if link.is_symlink() and os.readlink(link).endswith('python3.11'):
            continue
        if link.exists() and not link.is_symlink():
            continue
        try:
            if link.is_symlink():
                link.unlink()
        except OSError:
            continue
        link.symlink_to('python3.11')
        changed += 1
    return changed


def _commit(name: str, staging: Path, final: Path) -> None:
    """Swap a finished staging tree into place without losing the working copy.

    Windows refuses to rename a directory while any process keeps it as its
    working directory. Probes run from the system temporary directory, but a
    task may still hold the old environment. Retry briefly; if the swap still
    fails, restore the previous environment instead of leaving the name empty.
    """
    previous = None
    if final.exists():
        previous = final.with_name(f'.previous-{name}-{uuid.uuid4().hex[:8]}')
        final.rename(previous)
    try:
        for attempt in range(12):
            try:
                staging.rename(final)
                break
            except OSError:
                if attempt == 11:
                    raise
                time.sleep(0.25)
    except OSError as error:
        if previous is not None and not final.exists():
            previous.rename(final)
        raise RuntimeError(
            f'could not commit environment {name}: its directory is still in use '
            f'by a running probe or task; stop the task and retry ({error})') from error
    _rewrite_shebangs(final, staging)
    _relocate(final, staging)
    if previous is not None:
        shutil.rmtree(previous, ignore_errors=True)


TEXT_LIMIT = 8 * 1024 * 1024


PIP_STARTUP_SECONDS = 3600.0


def _pip_env(python: Path, extra: dict[str, str] | None = None) -> dict[str, str]:
    """Return the environment for one pip run.

    pip's progress bar writes carriage returns and only flushes when its buffer
    fills, so over a pipe a long resolve or download can look silent long enough
    to trip the launch grace even though work is progressing. Unbuffered output
    keeps the log alive so the grace only fires on a real stall.
    """
    env = _probe_environment(python)
    env['PYTHONUNBUFFERED'] = '1'
    # The progress bar repaints one line with carriage returns, so over a pipe
    # the whole download looks like one unfinished line: nothing reaches the
    # log until it ends. Plain lines are what a captured log wants.
    env['PIP_PROGRESS_BAR'] = 'off'
    env['PIP_DISABLE_PIP_VERSION_CHECK'] = '1'
    for name, value in (extra or {}).items():
        env[str(name)] = str(value)
    return env


def _pip_prefix(staging: Path) -> list[str]:
    """Return the pip ``--prefix`` flags for one staging environment.

    pip appends relative segments such as ``../../Scripts/<name>`` to the
    prefix; Windows rejects that join with Errno 22 when the prefix carries the
    extended ``\\\\?\\`` form, so prefer the plain path unless the location is
    long enough to need the extended form.
    """
    if os.name != "nt":
        return []
    plain = str(staging)
    if len(plain) <= 200:
        return ["--prefix", plain]
    from .bytecode import filesystem_path
    return ["--prefix", filesystem_path(staging)]


def _create(entry: dict, staging: Path, log, root=None, progress=None, control=None):
    if entry.get('venv_shared'):
        _run([sys.executable, '-m', 'venv', '--system-site-packages', staging], log=log, timeout=900,
             progress=progress, control=control)
        return
    mamba = _micromamba(base(root), log, control)
    env = _mamba_env(base(root))
    if entry.get('clone_shared'):
        _run([mamba, '--no-rc', 'create', '-y', '-p', staging, '--clone', sys.prefix], log=log, env=env,
             timeout=1800, progress=progress, control=control, stall=BUILD_STALL_SECONDS,
             startup=CONDA_STARTUP_SECONDS, watch=[base(root), staging, _mamba_cache(root)])
    else:
        _run([mamba, '--no-rc', 'create', '-y', '-p', staging, *_conda_flags(entry),
              '--strict-channel-priority', 'python=' + str(entry.get('python', '3.11')), 'pip'],
             log=log, env=env, timeout=1800, progress=progress, control=control, stall=BUILD_STALL_SECONDS,
             startup=CONDA_STARTUP_SECONDS, watch=[base(root), staging, _mamba_cache(root)])


def _attempt_best_effort(items, attempt, log):
    """Install each optional requirement on its own and report what failed.

    A single source-only binding (vina needs SWIG) used to fail the whole batch,
    which silently left the other optional imports, including the binary reader
    dependencies, uninstalled.
    """
    skipped = []
    for item in items or []:
        try:
            attempt(item)
        except Exception as exc:  # noqa: BLE001 - best effort by contract
            skipped.append(item)
            log(f'best-effort dependency {item} was skipped: {exc}')
    return skipped



_PEP440 = re.compile(
    r'^(?:\d+!)?\d+(?:\.\d+)*'
    r'(?:[-_\.]?(?:a|b|c|rc|alpha|beta|pre|preview)[-_\.]?\d*)?'
    r'(?:-\d+|[-_\.]?(?:post|rev|r)[-_\.]?\d*)?'
    r'(?:[-_\.]?dev[-_\.]?\d*)?'
    r'(?:\+[a-z0-9]+(?:[-_\.][a-z0-9]+)*)?$',
    re.IGNORECASE,
)


def _version_is_pep440(text: str) -> bool:
    """Report whether ``text`` is a version ``packaging`` accepts."""

    value = str(text or '').strip()
    return bool(value) and bool(_PEP440.match(value))


def _site_packages_directories(prefix: Path) -> list[Path]:
    base = Path(prefix)
    found = [path for path in sorted(base.glob('lib/python*/site-packages')) if path.is_dir()]
    windows = base / 'Lib' / 'site-packages'
    if windows.is_dir():
        found.append(windows)
    return found


def _conda_package_version(prefix: Path, project: str) -> str:
    """Read the version conda recorded for ``project``."""

    meta = Path(prefix) / 'conda-meta'
    if not meta.is_dir():
        return ''
    wanted = _normalise_package(project)
    for item in sorted(meta.glob('*.json')):
        try:
            payload = json.loads(item.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            continue
        if _normalise_package(str(payload.get('name') or '')) != wanted:
            continue
        version = str(payload.get('version') or '').strip()
        if _version_is_pep440(version):
            return version
    return ''


def repair_metadata_versions(prefix: Path, log=None) -> int:
    """Rewrite non-PEP 440 metadata versions a conda build left behind.

    A conda package may ship legacy ``*.egg-info`` metadata whose ``Version`` is
    a build tag such as ``aafe735-mod`` (the AutoDock Vina bindings do). pip reads
    it through ``pkg_resources`` and aborts every later ``pip install`` in that
    environment with ``InvalidVersion`` before installing anything. The recipe
    knows the real version, so rewrite the metadata instead of failing.
    """

    repaired = 0
    for site in _site_packages_directories(Path(prefix)):
        try:
            entries = sorted(site.iterdir())
        except OSError:
            continue
        for entry in entries:
            suffix = next((text for text in ('.dist-info', '.egg-info') if entry.name.endswith(text)), '')
            if not suffix or not entry.is_dir():
                continue
            info = entry / ('METADATA' if suffix == '.dist-info' else 'PKG-INFO')
            try:
                lines = info.read_text(encoding='utf-8', errors='replace').splitlines()
            except OSError:
                continue
            project = version = ''
            for line in lines:
                if line.startswith('Name:') and not project:
                    project = line.split(':', 1)[1].strip()
                elif line.startswith('Version:') and not version:
                    version = line.split(':', 1)[1].strip()
            if not project or not version or _version_is_pep440(version):
                continue
            replacement = _conda_package_version(Path(prefix), project)
            if not replacement:
                continue
            updated = [
                f'Version: {replacement}' if line.startswith('Version:') else line
                for line in lines
            ]
            try:
                info.write_text('\n'.join(updated) + '\n', encoding='utf-8')
            except OSError:
                continue
            directory = f"{project.replace('-', '_').replace('.', '_')}-{replacement}{suffix}"
            target = site / directory
            try:
                if not target.exists():
                    entry.rename(target)
            except OSError:
                pass
            repaired += 1
            if log is not None:
                log(f'rewrote metadata version {version!r} as {replacement!r} for {project}')
    return repaired


def _install(entry: dict, staging: Path, log, root=None, progress=None, control=None):
    python = _python(staging)
    # Use the extended prefix only for pip filesystem writes. Keep the actual
    # interpreter and DLL lookup paths native (the retained 5.1.9 loader fix).
    prefix = _pip_prefix(staging)
    install = [python, '-X', 'utf8', '-m', 'pip', 'install', *prefix]
    direct = entry.get('pip_pypi') or []
    # Base build tooling must exist before any source build or `--no-build-isolation` install.
    # `pkg_resources` ships with setuptools below 81; some packages (pdbfixer) still import it.
    _run([*install, *PIP_TRANSFER, '--no-input', *PIP_INDEX, *PIP_TRUSTED,
          'setuptools>=68,<81', 'wheel'], log=log, timeout=900, env=_pip_env(python),
         startup=PIP_STARTUP_SECONDS, progress=progress, control=control, stall=BUILD_STALL_SECONDS)
    conda_packages = entry.get('conda_packages') or []
    if conda_packages:
        mamba = _micromamba(base(root), log, control)
        _run([mamba, '--no-rc', 'install', '-y', '-p', staging, *_conda_flags(entry),
              '--strict-channel-priority', *conda_packages], log=log, env=_mamba_env(base(root)),
             timeout=1800, progress=progress, control=control, stall=BUILD_STALL_SECONDS,
             startup=CONDA_STARTUP_SECONDS, watch=[base(root), staging, _mamba_cache(root)])
        repair_metadata_versions(staging, log)
    if entry.get('torch_cpu'):
        _run([*install, *PIP_TRANSFER, 'torch',
              '--index-url', 'https://download.pytorch.org/whl/cpu'], log=log, timeout=1800,
             env=_pip_env(python), startup=PIP_STARTUP_SECONDS, progress=progress, control=control)
    if entry.get('torch_cuda'):
        version = str(entry.get('torch_version') or '').strip()
        target = f'torch=={version}' if version else 'torch'
        index = str(entry.get('torch_index_url') or '').strip()
        extra = ['--index-url', index] if index else []
        _run([*install, *PIP_TRANSFER, *extra, target], log=log, timeout=3600,
             env=_pip_env(python), startup=PIP_STARTUP_SECONDS, progress=progress, control=control)
    if direct:
        _run([*install, *PIP_TRANSFER, *PIP_INDEX, *PIP_TRUSTED, *direct], log=log,
             timeout=1800, progress=progress, control=control, stall=BUILD_STALL_SECONDS,
             env=_pip_env(python), startup=PIP_STARTUP_SECONDS, watch=[base(root), staging])
    wheels = entry.get('pip_wheels') or []
    if wheels:
        _run([*install, *PIP_TRANSFER, '--only-binary=:all:', *PIP_INDEX, *PIP_TRUSTED, *wheels],
             log=log, timeout=1800, progress=progress, control=control, stall=BUILD_STALL_SECONDS,
             env=_pip_env(python), startup=PIP_STARTUP_SECONDS, watch=[base(root), staging])
    requirements = entry.get('requirements') or []
    if requirements:
        _run([*install, *PIP_TRANSFER, '--prefer-binary', *PIP_INDEX, *PIP_TRUSTED, *requirements],
             log=log, timeout=5400, progress=progress, control=control, stall=BUILD_STALL_SECONDS,
             env=_pip_env(python), startup=PIP_STARTUP_SECONDS)
    best_effort = entry.get('best_effort') or []
    if best_effort:
        # Declared, attempted, and reported, but never fatal: these are the
        # modules that need a compiler the host may not have.
        _attempt_best_effort(
            best_effort,
            lambda requirement: _run(
                [*install, *PIP_TRANSFER, '--prefer-binary', *PIP_INDEX, *PIP_TRUSTED, requirement],
                log=log, timeout=5400, progress=progress, control=control,
                stall=BUILD_STALL_SECONDS, env=_pip_env(python), startup=PIP_STARTUP_SECONDS),
            log)
    no_deps = entry.get('no_deps') or []
    if no_deps:
        _run([*install, *PIP_TRANSFER, '--no-deps', *PIP_INDEX, *PIP_TRUSTED, *no_deps], log=log,
             timeout=5400, progress=progress, control=control, stall=BUILD_STALL_SECONDS,
             env=_pip_env(python), startup=PIP_STARTUP_SECONDS)
    no_build = entry.get('no_build_isolation') or []
    if no_build:
        # A source build that runs inside the environment must not resolve its own
        # build dependencies: pip would fetch numpy 2 headers while the environment
        # pins numpy 1.x, and a package such as scikit-learn would then be rebuilt
        # from source for no reason.  The environment declares every runtime
        # dependency next to the entry, so `--no-deps` keeps the tree untouched.
        # A declaration may carry build flags the host compiler needs: the
        # system gcc of an older server still defaults to C89, and a Cython
        # extension generated for C99 then fails to compile.
        _run([*install, *PIP_TRANSFER, '--no-build-isolation', '--no-deps', *no_build], log=log,
             timeout=3600, progress=progress, control=control, stall=BUILD_STALL_SECONDS,
             env=_pip_env(python, entry.get('build_env')), startup=PIP_STARTUP_SECONDS)


def _probe_environment(python: Path) -> dict[str, str]:
    env = os.environ.copy()
    base = python.parent.parent if python.parent.name.lower() in {'scripts', 'bin'} else python.parent
    folders = [python.parent, base, base / 'Library' / 'bin', base / 'bin']
    env['PATH'] = os.pathsep.join(
        [*(str(item) for item in folders if item.is_dir()), env.get('PATH', '')])
    return env


def _probe(python: Path, entry: dict, log, progress=None, control=None):
    python = environments._native_path(python)
    modules = entry.get('imports') or []
    if not modules:
        return ''
    script = ';'.join('import ' + module for module in modules)
    # The probe prints nothing on success, so a slow import chain (jax alone can
    # take minutes on a shared filesystem) looked like a stalled command and was
    # killed by the startup grace.  Announce every module first so the reader
    # keeps seeing output and the log names the slow import.
    narrated = ';'.join(
        ['import sys'] + [part for module in modules
                          for part in ('sys.stdout.write("import %s\\n");sys.stdout.flush()' % module,
                                       'import ' + module)])
    _run([python, '-X', 'utf8', '-c', narrated], log=log, env=_probe_environment(python),
         timeout=600, startup=600, progress=progress, control=control, stall=STALL_SECONDS)
    return script


def _force_remove(function, path, excinfo):
    """Retry a removal after making the entry writable (Windows keeps read-only flags)."""
    try:
        os.chmod(path, 0o700)
    except OSError:
        pass
    try:
        function(path)
    except OSError:
        pass


def _remove_tree(path, *, attempts=6, delay=0.3) -> bool:
    """Remove a staging tree even while a killed interpreter still holds handles."""
    path = Path(path)
    for attempt in range(attempts):
        if not path.exists():
            return True
        shutil.rmtree(path, onerror=_force_remove)
        if not path.exists():
            return True
        time.sleep(delay * (attempt + 1))
    shutil.rmtree(path, ignore_errors=True)
    return not path.exists()


_DEPENDENCY_TTL = 20.0
_dependency_cache: dict[str, tuple[float, dict, set, set]] = {}


def _normalise_package(name: str) -> str:
    return str(name).strip().lower().replace('_', '-').replace(' ', '-')


def _wheel_project(value: str) -> str:
    """Return the project of a wheel URL or path, or '' when this is not one."""
    head = str(value).strip()
    if not head.lower().endswith('.whl'):
        return ''
    base = head.replace('\\', '/').rsplit('/', 1)[-1]
    return base.split('-', 1)[0]


def _requirement_name(value: str) -> str:
    head = str(value).split(';')[0].strip()
    project = _wheel_project(head)
    if project:
        return _normalise_package(project)
    for marker in ('[', '=', '<', '>', '!', '~', ' '):
        head = head.split(marker)[0]
    return _normalise_package(head)


def metadata_name(filename: str) -> tuple[str, str]:
    """Split a ``.dist-info``/``.egg-info`` directory name into project and version.

    pip replaces runs of ``-``, ``.`` and ``_`` in the project name with ``_``
    before it names the ``.dist-info`` directory, so there the first hyphen
    separates project from version (``torch_geometric-2.4.0.dist-info``).
    Legacy ``.egg-info`` directories keep their hyphens, so the version starts
    at the first segment that begins with a digit.
    """
    for suffix in ('.dist-info', '.egg-info'):
        if not filename.endswith(suffix):
            continue
        stem = filename[:-len(suffix)]
        if suffix == '.dist-info':
            project, _, version = stem.partition('-')
            return project, version
        project, _, version = stem.rpartition('-')
        while project and not version[:1].isdigit():
            project, _, version = project.rpartition('-')
        return (project, version) if project else (stem, '')
    return '', ''


def _site_packages(location: str):
    base = Path(location)
    candidates = [base / 'Lib' / 'site-packages']
    candidates.extend(sorted(base.glob('lib/python*/site-packages')))
    for candidate in candidates:
        if candidate.is_dir():
            return candidate
    return None


def _inherited_site_packages(location: str):
    """Return the base interpreter's site-packages for a ``--system-site-packages`` venv.

    A venv created with system site packages only stores the packages installed
    into it; everything it inherits (``wheel``, ``setuptools``, ...) lives in the
    base interpreter.  Reporting those as missing made a finished environment look
    incomplete and kept it out of the ready set forever.
    """
    try:
        text = (Path(location) / 'pyvenv.cfg').read_text(encoding='utf-8', errors='replace')
    except OSError:
        return None
    inherited = False
    home = ''
    for line in text.splitlines():
        key, _, value = line.partition('=')
        key = key.strip().lower()
        value = value.strip()
        if key == 'include-system-site-packages':
            inherited = value.lower() == 'true'
        elif key == 'home':
            home = value
    if not inherited or not home:
        return None
    prefix = Path(home).parent
    candidates = [prefix / 'Lib' / 'site-packages']
    candidates.extend(sorted(prefix.glob('lib/python*/site-packages')))
    for candidate in candidates:
        if candidate.is_dir():
            return candidate
    return None


def _scan_site_packages(site, versions: dict, imports: set) -> None:
    if site is None:
        return
    try:
        entries = list(site.iterdir())
    except OSError:
        return
    for entry in entries:
        name = entry.name
        if name.endswith('.dist-info') or name.endswith('.egg-info'):
            project, version = metadata_name(name)
            if project:
                versions.setdefault(_normalise_package(project), version)
        imports.add(_normalise_package(name.split('.')[0].lower()))
        if name.endswith('.py'):
            imports.add(_normalise_package(name[:-3]))
        elif name.endswith('.pyc'):
            imports.add(_normalise_package(name[:-4]))


def installed_index(location: str):
    if not location:
        return {}, set(), set()
    stamp = time.monotonic()
    cached = _dependency_cache.get(location)
    if cached and stamp - cached[0] < _DEPENDENCY_TTL:
        return cached[1], cached[2], cached[3]
    versions: dict[str, str] = {}
    packages: set[str] = set()
    imports: set[str] = set()
    base = Path(location)
    _scan_site_packages(_site_packages(location), versions, imports)
    _scan_site_packages(_inherited_site_packages(location), versions, imports)
    meta = base / 'conda-meta'
    if meta.is_dir():
        for entry in meta.glob('*.json'):
            chunk = entry.stem.rsplit('-', 2)
            if len(chunk) >= 2:
                packages.add(_normalise_package(chunk[0]))
                versions.setdefault(_normalise_package(chunk[0]), chunk[1])
    _dependency_cache[location] = (stamp, versions, packages, imports)
    return versions, packages, imports


def dependency_rows(entry) -> list:
    """Flatten one environment declaration into the rows the UI reports.

    The same project can be declared twice (``wheel`` sits in both
    ``requirements`` and ``pip_wheels`` because the bootstrap wheel is also a
    runtime dependency).  Counting it twice inflated the total and repeated the
    name in "missing:", so installable declarations are de-duplicated by project
    name while ``imports`` and ``binaries`` stay separate checks.
    """
    rows = []
    entry = entry if isinstance(entry, dict) else {}
    declared: set[str] = set()
    for key, kind in (('requirements', 'requirements'), ('pip_wheels', 'wheel'),
                      ('pip_pypi', 'pypi'), ('conda_packages', 'conda')):
        for value in entry.get(key) or []:
            name = str(value)
            marker = _requirement_name(name)
            if marker and marker in declared:
                continue
            if marker:
                declared.add(marker)
            rows.append({'kind': kind, 'name': name})
    for value in entry.get('best_effort') or []:
        name = str(value)
        marker = _requirement_name(name)
        if marker and marker in declared:
            continue
        if marker:
            declared.add(marker)
        rows.append({'kind': 'best_effort', 'name': name, 'optional': True})
    seen_imports: set[str] = set()
    for value in entry.get('imports') or []:
        name = str(value)
        marker = _normalise_package(name.split('.')[0].lower())
        if marker in seen_imports:
            continue
        seen_imports.add(marker)
        rows.append({'kind': 'import', 'name': name})
    for value in entry.get('binaries') or []:
        rows.append({'kind': 'binary', 'name': str(value)})
    return rows


def dependency_installed(row: dict, location: str) -> bool:
    versions, packages, imports = installed_index(location)
    kind = str(row.get('kind') or '')
    name = str(row.get('name') or '')
    if kind in ('requirements', 'pypi', 'wheel'):
        return _requirement_name(name) in versions
    if kind == 'best_effort':
        marker = _requirement_name(name)
        return marker in versions or marker in imports
    if kind == 'conda':
        return _requirement_name(name) in packages or _requirement_name(name) in versions
    if kind == 'import':
        return _normalise_package(name.split('.')[0].lower()) in imports
    if kind == 'binary':
        if not location:
            return False
        base = Path(location)
        executable = name.split(' ')[0]
        for folder in ('Scripts', 'bin', ''):
            base_dir = (base / folder) if folder else base
            for suffix in ('', '.exe', '.cmd', '.bat'):
                if (base_dir / f'{executable}{suffix}').exists():
                    return True
        return False
    return False


def dependency_status(entry, location: str):
    rows = dependency_rows(entry)
    flags = [{**row, 'installed': bool(location) and dependency_installed(row, location)} for row in rows]
    installed = sum(1 for flag in flags if flag['installed'])
    return installed, len(rows), flags


# The panel labels dependency rows with display kinds; the manifest buckets that
# actually carry installable requirements have their own names.  /api/v1 accepts
# both shapes, so resolve the display kinds before validating.
_KIND_ALIASES = {
    'wheel': 'pip_wheels',
    'pypi': 'pip_pypi',
    'conda': 'conda_packages',
}


def install_dependency(name: str, kind: str, requirement: str, root=None, log=None,
                       control=None, source=None) -> dict:
    """Install a single declared dependency, waiting for the installation slot."""
    control = control or _Control()
    _acquire_slot(control, root)
    try:
        return _install_dependency(name, kind, requirement, root, log, control, source)
    finally:
        _release_slot()


def _install_dependency(name: str, kind: str, requirement: str, root=None, log=None,
                        control=None, source=None) -> dict:
    """Install a single declared dependency into one environment."""
    control = control or _Control()
    entry = environments.describe(name, source)
    requirement = str(requirement or '').strip()
    if not requirement:
        raise ValueError('missing dependency name')
    declared = {
        'requirements': entry.get('requirements') or [],
        'pip_wheels': entry.get('pip_wheels') or [],
        'pip_pypi': entry.get('pip_pypi') or [],
        'conda_packages': entry.get('conda_packages') or [],
        'no_deps': entry.get('no_deps') or [],
        'no_build_isolation': entry.get('no_build_isolation') or [],
    }
    kind = _KIND_ALIASES.get(kind, kind)
    if kind not in declared:
        raise ValueError(f"dependency kind {kind!r} cannot be installed one by one")
    if requirement not in [str(item) for item in declared[kind]]:
        raise ValueError(f"dependency {requirement!r} is not declared by environment {name}")
    base(root).mkdir(parents=True, exist_ok=True)
    final = target(name, root)
    note = log or (lambda line: None)
    if not final.exists():
        require_space(root, 2 * 1024 ** 3, what=f'environment {name}')
        staging = base(root) / f'.staging-{name}-{uuid.uuid4().hex[:8]}'
        try:
            _create(entry, staging, note, root, control=control)
            _commit(name, staging, final)
        finally:
            if staging.exists():
                _remove_tree(staging, attempts=2)
    progress = {'name': name, 'phase': 'installing', 'detail': f'installing {requirement}',
                'bytes': 0, 'files': 0, 'started_at': _now(), 'updated_at': _now(),
                'expected_bytes': int(estimates.expected(name, entry, base(root)) or 0)}
    _write_progress(name, root, progress)
    control.check()
    if kind == 'conda_packages':
        mamba = _micromamba(base(root), note, control)
        _run([mamba, '--no-rc', 'install', '-y', '-p', str(final), *_conda_flags([requirement]),
              '--strict-channel-priority', requirement],
             log=note, env=_mamba_env(base(root)), timeout=3600, control=control, stall=BUILD_STALL_SECONDS,
             startup=CONDA_STARTUP_SECONDS, watch=[base(root), final, _mamba_cache(root)])
    else:
        python = _python(final)
        prefix = _pip_prefix(final)
        flags = ['--no-deps'] if kind == 'no_deps' else []
        if kind == 'no_build_isolation':
            flags = ['--no-build-isolation']
        extra = ['--prefer-binary'] if kind == 'requirements' else []
        if kind == 'pip_wheels':
            extra = ['--only-binary=:all:']
        _run([python, '-X', 'utf8', '-m', 'pip', 'install', *prefix, *PIP_TRANSFER,
              *(flags or []), *(extra or []), *PIP_INDEX, *PIP_TRUSTED, requirement],
             log=note, timeout=3600, progress=progress, control=control, stall=BUILD_STALL_SECONDS,
             env=_pip_env(python), startup=PIP_STARTUP_SECONDS)
    progress['phase'] = 'complete'
    progress['detail'] = f'installed {requirement}'
    progress['updated_at'] = _now()
    progress['root'] = str(base(root))
    _write_progress(name, root, progress)
    return {'environment': name, 'kind': kind, 'requirement': requirement, 'status': 'installed'}


def prepare(name: str, root=None, source=None, log=None, control=None) -> dict:
    """Create or refresh one declared environment; safe to call concurrently."""
    control = control or _Control()
    manifest = environments.manifest_path(source)
    if not manifest.is_file():
        raise FileNotFoundError(
            f"Operator library does not declare isolated environments: {manifest}")
    entry = environments.describe(name, source)
    _validate(entry)
    if not platform_supported(entry):
        message = unsupported_reason(entry)
        base(root).mkdir(parents=True, exist_ok=True)
        path = _error_path(name, root)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({'message': message, 'at': _now()}, indent=2), encoding='utf-8')
        raise RuntimeError(message)
    if entry.get('torch_cuda') and not _gpu_available():
        entry = _cpu_entry(entry)
    base(root).mkdir(parents=True, exist_ok=True)
    require_space(root, estimates.expected(name, entry, base(root)),
                  what=f'environment {name}')
    from src.web.storage import FileLock
    lock = FileLock(base(root) / f'.{name}.lock', timeout=1)
    try:
        lock.__enter__()
    except TimeoutError:
        raise RuntimeError(f'environment {name} is already being prepared')
    for leftover in base(root).glob(f'.staging-{name}-*'):
        _remove_tree(leftover, attempts=1)
    staging = base(root) / f'.staging-{name}-{uuid.uuid4().hex[:8]}'
    now = lambda: time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
    progress = {'name': name, 'phase': 'queued', 'detail': '', 'bytes': 0, 'files': 0,
                'started_at': now(), 'updated_at': now(),
                'expected_bytes': estimates.expected(name, entry, base(root))}
    _write_progress(name, root, progress)
    append_log(name, f'preparing isolated environment {name} at {base(root) / name}', root)
    stop = threading.Event()

    def note(line):
        progress['detail'] = str(line)[:400]
        progress['lines'] = progress.get('lines', 0) + 1
        append_log(name, str(line), root)
        if log is not None:
            log(line)

    def watch():
        while not stop.wait(2.0):
            try:
                size, files = _usage(staging, base(root) / 'packages')
            except OSError:
                continue
            progress['bytes'] = max(int(progress.get('bytes') or 0), int(size))
            progress.update({'files': max(int(progress.get('files') or 0), files),
                             'updated_at': _now()})
            _write_progress(name, root, progress)

    threading.Thread(target=watch, name=f'environment-progress-{name}', daemon=True).start()
    slot = False
    try:
        _acquire_slot(control, root)
        slot = True
        progress['phase'] = 'creating'
        _write_progress(name, root, progress)
        note(f'preparing isolated environment {name} at {target(name, root)}')
        control.check()
        _create(entry, staging, note, root, progress=progress, control=control)
        control.check()
        progress['phase'] = 'installing'
        _install(entry, staging, note, root, progress=progress, control=control)
        control.check()
        progress['phase'] = 'probing'
        python = _python(staging)
        script = _probe(python, entry, note, progress=progress, control=control)
        control.check()
        progress['phase'] = 'committing'
        (staging / 'receipt.json').write_text(json.dumps({
            'schema': 1, 'name': name, 'python': str(entry.get('python', '3.11')),
            'spec_sha256': spec_sha256(entry), 'imports': script,
            'bootstrap': 'setuptools>=68,<81 wheel', 'installer': 'environment_install/2',
            'created_at': now(),
        }, indent=2), encoding='utf-8')
        final = target(name, root)
        _commit(name, staging, final)
        _error_path(name, root).unlink(missing_ok=True)
        progress['phase'] = 'ready'
        note(f'environment {name} is ready')
    except Cancelled:
        progress['phase'] = 'cancelled'
        progress.pop('error', None)
        _remove_tree(staging)
        try:
            _error_path(name, root).unlink(missing_ok=True)
        except OSError:
            pass
        raise
    except BaseException as error:
        if read_progress(name, root).get('phase') == 'cancelled':
            progress.update({'phase': 'cancelled', 'detail': 'cancelled by user', 'error': '',
                             'updated_at': _now()})
            try:
                _error_path(name, root).unlink(missing_ok=True)
            except OSError:
                pass
            raise
        progress['phase'] = 'failed'
        progress['error'] = str(error)
        for leftover in base(root).glob(f'.failed-{name}-*'):
            shutil.rmtree(leftover, ignore_errors=True)
        try:
            failed = base(root) / f'.failed-{name}-{uuid.uuid4().hex[:8]}'
            staging.rename(failed)
            progress['staging'] = str(failed)
        except OSError:
            shutil.rmtree(staging, ignore_errors=True)
        path = _error_path(name, root)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({'message': str(error), 'at': now()}, indent=2), encoding='utf-8')
        raise
    finally:
        stop.set()
        if slot:
            _release_slot()
        try:
            size, files = _usage(target(name, root), base(root) / 'packages')
            progress.update({'bytes': size, 'files': files, 'updated_at': _now()})
            _write_progress(name, root, progress)
            if progress.get('phase') == 'ready':
                estimates.record(name, size, base(root))
        except OSError:
            pass
        lock.__exit__(None, None, None)
    return state(name, root, source)


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(description='Prepare declared isolated operator environments.')
    parser.add_argument('name', nargs='?')
    parser.add_argument('--all', action='store_true')
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args()
    names = [args.name] if args.name else sorted(environments.load())
    if not args.name and not args.all:
        print(json.dumps(plan(), indent=2))
        return 0
    failed = False
    for name in names:
        try:
            prepare(name)
        except Exception as error:  # keep going so every environment reports
            failed = True
            print(f'FAIL {name}: {error}', flush=True)
    return 1 if failed else 0


if __name__ == '__main__':
    raise SystemExit(main())
