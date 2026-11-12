"""Provision isolated operator environments declared by the imported library.

The library bundle is the only dependency source. ``sources/operon/environments.json``
declares the interpreter, package list and import probes; nothing here invents
versions or reads an external manifest. Creation is staged, locked per environment
and committed by receipt, so a failed attempt never replaces a working runtime.
"""
from __future__ import annotations

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
from pathlib import Path

from . import environments

PIP_TRANSFER = ['--disable-pip-version-check', '--no-input', '--timeout', '120', '--retries', '3']
PIP_INDEX = ['--index-url', 'https://pypi.org/simple']
CONDA_FORGE = 'conda-forge'
ERRORS = '.operon-environment-errors'
PROGRESS = '.operon-environment-progress'


def base(root=None) -> Path:
    return environments.root() if root is None else Path(root).expanduser()


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


def progress_path(name: str, root=None) -> Path:
    return base(root) / PROGRESS / f'{name}.json'


def read_progress(name: str, root=None) -> dict:
    return _read(progress_path(name, root))


def _write_progress(name: str, root, value: dict) -> None:
    path = progress_path(name, root)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value, indent=2), encoding='utf-8')
    temporary.replace(path)


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


def state(name: str, root=None, source=None) -> dict:
    """Report one environment without creating or probing anything."""
    entry = environments.describe(name, source)
    directory = target(name, root)
    python = None
    for layout in ('bin/python', 'Scripts/python.exe', 'python.exe'):
        candidate = directory / layout
        if candidate.is_file() and os.access(candidate, os.X_OK):
            python = candidate
            break
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
    if python is None:
        result['status'] = 'failed' if error.get('message') else 'missing'
        result['error'] = error.get('message') or ''
    elif recorded.get('spec_sha256') != expected:
        result['status'] = 'stale'
        result['error'] = ''
    else:
        result['status'] = 'ready'
        result['error'] = ''
    result['used_by'] = []
    result['progress'] = read_progress(name, root)
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


def _emit(log, message):
    if log is not None:
        log(message)
    else:
        print(message, flush=True)


def _run(argv, *, log, env=None, timeout=3600):
    _emit(log, '$ ' + ' '.join(str(part) for part in argv))
    completed = subprocess.run([str(part) for part in argv], capture_output=True, text=True,
                               encoding='utf-8', errors='replace', env=env, timeout=timeout)
    tail = (completed.stdout or '') + (completed.stderr or '')
    for line in [line for line in tail.splitlines() if line.strip()][-25:]:
        _emit(log, '  ' + line)
    if completed.returncode:
        detail = " | ".join(line for line in tail.splitlines() if line.strip())[-600:]
        raise RuntimeError(f'{" ".join(str(p) for p in argv[:2])} exited with {completed.returncode}: {detail}')
    return tail


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
    for value in spec.get('no_build_isolation') or []:
        candidate = value.split(' @ ', 1)[1].strip() if ' @ ' in value else value.strip()
        if not (candidate.startswith('https://') or candidate.startswith('git+https://')):
            raise ValueError(f'only https package sources are allowed: {value}')


def _micromamba(directory: Path, log) -> Path:
    override = os.environ.get('OPERON_MAMBA')
    if override and Path(override).is_file():
        return Path(override)
    system, machine = platform.system(), platform.machine().lower()
    target_name = {('Windows', 'amd64'): 'win-64', ('Windows', 'x86_64'): 'win-64',
                   ('Linux', 'x86_64'): 'linux-64', ('Linux', 'aarch64'): 'linux-aarch64'}.get((system, machine))
    if target_name is None:
        raise ValueError('automatic environment creation is unavailable on this platform; set OPERON_MAMBA')
    executable = directory / ('micromamba.exe' if system == 'Windows' else 'micromamba')
    if executable.is_file():
        return executable
    directory.mkdir(parents=True, exist_ok=True)
    _emit(log, f'downloading micromamba ({target_name})')
    with tempfile.TemporaryDirectory(dir=directory) as temporary:
        archive = Path(temporary) / 'micromamba.tar.bz2'
        with urllib.request.urlopen(f'https://micro.mamba.pm/api/micromamba/{target_name}/latest', timeout=120) as source, archive.open('wb') as output:
            shutil.copyfileobj(source, output)
        with tarfile.open(archive) as bundle:
            member = bundle.getmember('Library/bin/micromamba.exe' if system == 'Windows' else 'bin/micromamba')
            if not member.isfile():
                raise ValueError('invalid micromamba archive')
            staged = Path(temporary) / executable.name
            with bundle.extractfile(member) as source, staged.open('wb') as output:
                shutil.copyfileobj(source, output)
            staged.chmod(0o755)
            staged.replace(executable)
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


def _create(entry: dict, staging: Path, log, root=None):
    if entry.get('venv_shared'):
        _run([sys.executable, '-m', 'venv', '--system-site-packages', staging], log=log, timeout=900)
        return
    mamba = _micromamba(base(root), log)
    env = _mamba_env(base(root))
    if entry.get('clone_shared'):
        _run([mamba, '--no-rc', 'create', '-y', '-p', staging, '--clone', sys.prefix], log=log, env=env, timeout=1800)
    else:
        _run([mamba, '--no-rc', 'create', '-y', '-p', staging, '-c', CONDA_FORGE, '--override-channels',
              '--strict-channel-priority', 'python=' + str(entry.get('python', '3.11')), 'pip'],
             log=log, env=env, timeout=1800)


def _install(entry: dict, staging: Path, log, root=None):
    python = _python(staging)
    conda_packages = entry.get('conda_packages') or []
    if conda_packages:
        mamba = _micromamba(base(root), log)
        _run([mamba, '--no-rc', 'install', '-y', '-p', staging, '-c', CONDA_FORGE, '--override-channels',
              '--strict-channel-priority', *conda_packages], log=log, env=_mamba_env(base(root)), timeout=1800)
    if entry.get('torch_cpu'):
        _run([python, '-m', 'pip', 'install', *PIP_TRANSFER, 'torch',
              '--index-url', 'https://download.pytorch.org/whl/cpu'], log=log, timeout=1800)
    direct = entry.get('pip_pypi') or []
    if direct:
        _run([python, '-m', 'pip', 'install', *PIP_TRANSFER, *PIP_INDEX, *direct], log=log, timeout=1800)
    wheels = entry.get('pip_wheels') or []
    if wheels:
        _run([python, '-m', 'pip', 'install', *PIP_TRANSFER, '--only-binary=:all:', *PIP_INDEX, *wheels],
             log=log, timeout=1800)
    requirements = entry.get('requirements') or []
    if requirements:
        _run([python, '-m', 'pip', 'install', *PIP_TRANSFER, '--prefer-binary', *PIP_INDEX, *requirements],
             log=log, timeout=2400)
    no_deps = entry.get('no_deps') or []
    if no_deps:
        _run([python, '-m', 'pip', 'install', *PIP_TRANSFER, '--no-deps', *PIP_INDEX, *no_deps], log=log, timeout=2400)
    no_build = entry.get('no_build_isolation') or []
    if no_build:
        _run([python, '-m', 'pip', 'install', *PIP_TRANSFER, '--no-build-isolation', *no_build], log=log, timeout=3600)


def _probe(python: Path, entry: dict, log):
    modules = entry.get('imports') or []
    if not modules:
        return ''
    script = ';'.join('import ' + module for module in modules)
    _run([python, '-c', script], log=log, timeout=600)
    return script


def prepare(name: str, root=None, source=None, log=None) -> dict:
    """Create or refresh one declared environment; safe to call concurrently."""
    manifest = environments.manifest_path(source)
    if not manifest.is_file():
        raise FileNotFoundError(
            f"Operator library does not declare isolated environments: {manifest}")
    entry = environments.describe(name, source)
    _validate(entry)
    base(root).mkdir(parents=True, exist_ok=True)
    from src.web.storage import FileLock
    lock = FileLock(base(root) / f'.{name}.lock', timeout=1)
    try:
        lock.__enter__()
    except TimeoutError:
        raise RuntimeError(f'environment {name} is already being prepared')
    staging = base(root) / f'.staging-{name}-{uuid.uuid4().hex[:8]}'
    now = lambda: time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
    progress = {'name': name, 'phase': 'creating', 'detail': '', 'bytes': 0, 'files': 0,
                'started_at': now(), 'updated_at': now()}
    _write_progress(name, root, progress)
    stop = threading.Event()

    def note(line):
        progress['detail'] = str(line)[:400]
        progress['lines'] = progress.get('lines', 0) + 1
        if log is not None:
            log(line)

    def watch():
        while not stop.wait(2.0):
            try:
                size, files = _usage(staging, base(root) / 'packages')
            except OSError:
                continue
            progress.update({'bytes': size, 'files': files, 'updated_at': now()})
            _write_progress(name, root, progress)

    threading.Thread(target=watch, name=f'environment-progress-{name}', daemon=True).start()
    try:
        note(f'preparing isolated environment {name} at {target(name, root)}')
        _create(entry, staging, note, root)
        progress['phase'] = 'installing'
        _install(entry, staging, note, root)
        progress['phase'] = 'probing'
        python = _python(staging)
        script = _probe(python, entry, note)
        progress['phase'] = 'committing'
        (staging / 'receipt.json').write_text(json.dumps({
            'schema': 1, 'name': name, 'python': str(entry.get('python', '3.11')),
            'spec_sha256': spec_sha256(entry), 'imports': script,
            'created_at': now(),
        }, indent=2), encoding='utf-8')
        final = target(name, root)
        previous = None
        if final.exists():
            previous = final.with_name(f'.previous-{name}-{uuid.uuid4().hex[:8]}')
            final.rename(previous)
        staging.rename(final)
        if previous is not None:
            shutil.rmtree(previous, ignore_errors=True)
        _error_path(name, root).unlink(missing_ok=True)
        progress['phase'] = 'ready'
        note(f'environment {name} is ready')
    except BaseException as error:
        progress['phase'] = 'failed'
        progress['error'] = str(error)
        shutil.rmtree(staging, ignore_errors=True)
        path = _error_path(name, root)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({'message': str(error), 'at': now()}, indent=2), encoding='utf-8')
        raise
    finally:
        stop.set()
        try:
            size, files = _usage(target(name, root), base(root) / 'packages')
            progress.update({'bytes': size, 'files': files, 'updated_at': now()})
            _write_progress(name, root, progress)
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
