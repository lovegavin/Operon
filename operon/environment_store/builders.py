"""Offline, locked archive builder shared by target builders and bundle import.

Runtime archives must be produced by the existing relocatable runtime builder or
a target-specific R/native builder. This does not copy a developer virtualenv.
Conda archives require an explicit prefix-fixup command before verification.
"""
from __future__ import annotations

from dataclasses import dataclass
from contextlib import contextmanager
import os
from pathlib import Path
import platform
import shutil
import subprocess
import tarfile
import tempfile
import time
import zipfile

from operon.contracts.base import ContractError, sha256_hex
from operon.processes import owned_process
from operon.bytecode import io_path, executable_path
from .verification import confined, file_digest


@contextmanager
def temporary_directory(prefix):
    """Owned temporary tree with Windows long-path-safe cleanup."""
    parent = Path(tempfile.gettempdir()).resolve()
    directory = Path(tempfile.mkdtemp(prefix=prefix, dir=parent)).resolve()
    if directory.parent != parent or not directory.name.startswith(prefix):
        raise ValueError('Temporary directory escaped its requested parent')
    try:
        yield directory
    finally:
        shutil.rmtree(io_path(directory))


@dataclass(frozen=True)
class LockedArchive:
    source: Path
    sha256: str
    destination: str
    # The uncompressed allowance is part of the build recipe, not a dataset cap.
    max_unpacked_bytes: int
    format: str = 'zip'


def extract_locked(archive, destination, *, format, maximum, cancel=None):
    destination.mkdir(parents=True, exist_ok=True)
    total = 0
    seen = set()

    def member(name, size):
        nonlocal total
        path = confined(destination, name.rstrip('/'))
        normalized = os.path.normcase(str(path))
        if normalized in seen:
            raise ContractError('Duplicate archive member', code='invalid_environment')
        seen.add(normalized)
        if size < 0 or maximum < total + size:
            raise ContractError('Archive exceeds its declared build allowance', code='invalid_environment')
        total += size
        if cancel and cancel():
            raise InterruptedError('Archive extraction cancelled')
        return path

    if format == 'zip':
        with zipfile.ZipFile(archive) as source:
            for entry in source.infolist():
                path = io_path(member(entry.filename, entry.file_size))
                mode = entry.external_attr >> 16
                if mode & 0o170000 == 0o120000:
                    raise ContractError('ZIP symlinks require a target tar recipe', code='invalid_environment')
                if entry.is_dir():
                    path.mkdir(parents=True, exist_ok=True)
                else:
                    path.parent.mkdir(parents=True, exist_ok=True)
                    with source.open(entry) as inp, path.open('xb') as out:
                        shutil.copyfileobj(inp, out, 1024 * 1024)
                    if os.name != 'nt' and mode:
                        path.chmod(mode & 0o777)
    elif format in ('tar', 'tar.gz', 'tar.xz'):
        # No tar.extractall, devices, FIFOs or link traversal. Links are created
        # after regular files so a later member cannot write through a link.
        links = []
        with tarfile.open(archive, 'r:*') as source:
            for entry in source:
                path = io_path(member(entry.name, entry.size))
                if entry.isdir():
                    path.mkdir(parents=True, exist_ok=True)
                elif entry.isfile():
                    path.parent.mkdir(parents=True, exist_ok=True)
                    with source.extractfile(entry) as inp, path.open('xb') as out:
                        shutil.copyfileobj(inp, out, 1024 * 1024)
                    path.chmod(entry.mode & 0o777)
                elif entry.issym():
                    if Path(entry.linkname).is_absolute() or not (path.parent / entry.linkname).resolve().is_relative_to(destination.resolve()):
                        raise ContractError('Archive link escapes root', code='path_escape')
                    links.append((path, entry.linkname))
                else:
                    raise ContractError('Archive contains unsupported special member', code='invalid_environment')
        for path, target in links:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.symlink_to(target)
    else:
        raise ContractError('Unknown archive format', code='invalid_environment')


def isolated_environment(root, *, extra=None):
    """Only OS boot necessities; never inherit user Python/R/Conda paths."""
    environment = {key: value for key, value in os.environ.items()
                   if key.upper() in ('SYSTEMROOT', 'WINDIR', 'COMSPEC', 'PATHEXT', 'LANG', 'LC_ALL')}
    root = Path(os.path.abspath(root))
    environment.update(PYTHONNOUSERSITE='1', PYTHONDONTWRITEBYTECODE='1', PYTHONUTF8='1',
                       R_ENVIRON_USER='', R_PROFILE_USER='', R_LIBS_USER=str(root / 'packages'),
                       R_LIBS_SITE=str(root / 'packages'), PATH=str(root / 'runtime' / 'bin'))
    environment.update(extra or {})
    return environment


def probe(root, argv, *, timeout=60, cancel=None, environment=None):
    root = Path(root).resolve()
    executable = confined(root, argv[0])
    if not io_path(executable).is_file():
        raise ContractError('Required environment executable is missing: ' + argv[0], code='environment_unverified')
    # File-backed bounded-tail diagnostics avoid stdout pipe deadlocks/whole logs.
    with temporary_directory('operon-probe-') as temp:
        log = Path(temp) / 'probe.log'
        env = isolated_environment(root, extra=environment)
        env.update(TEMP=str(temp), TMP=str(temp), TMPDIR=str(temp), HOME=str(temp), USERPROFILE=str(temp))
        with log.open('wb') as output, owned_process([executable_path(executable), *argv[1:]], cwd=io_path(root),
                env=env, stdin=subprocess.DEVNULL, stdout=output, stderr=subprocess.STDOUT) as process:
            deadline = time.monotonic() + timeout
            while process.poll() is None:
                if cancel and cancel():
                    raise InterruptedError('Environment probe cancelled')
                if time.monotonic() > deadline:
                    raise TimeoutError('Environment probe timed out')
                if log.stat().st_size > 4 * 1024 * 1024:
                    raise ContractError('Environment probe exceeded log allowance', code='environment_unverified')
                time.sleep(.02)
            code = process.returncode
        if code:
            with log.open('rb') as stream:
                stream.seek(max(0, log.stat().st_size - 8192))
                detail = stream.read().decode('utf-8', errors='replace')
            raise ContractError(f'Environment probe exited {code}: {detail}', code='environment_unverified')
    return {'argv': list(argv), 'exit_code': code, 'executable_sha256': file_digest(executable)}


class LockedArchiveBuilder:
    """Prepare an exact target closure; installation/acquisition is a prior step."""
    def __init__(self, archives, probes, *, fixups=(), timeout=120, environment=None):
        self.archives = tuple(archives)
        self.probes = tuple(tuple(item) for item in probes)
        self.fixups = tuple(tuple(item) for item in fixups)
        self.timeout = timeout
        self.environment = dict(environment or {})

    def resolve(self, requirement):
        system = platform.system().lower()
        arch = {'amd64': 'x86_64', 'arm64': 'aarch64'}.get(platform.machine().lower(), platform.machine().lower())
        if requirement.target.os != system or requirement.target.arch != arch:
            raise ContractError('Environment must be built and probed on its target', code='wrong_build_target')
        if not self.archives or not self.probes:
            raise ContractError('Runtime artifacts and probes are mandatory', code='environment_unverified')
        declared = requirement.dependency_lock.get('artifact_hashes')
        if not declared or sorted(declared) != sorted(item.sha256 for item in self.archives):
            raise ContractError('Requirement lock must name every materialized archive', code='unlocked_artifact')
        # Fixups are code. Their identity, probes and environment must be pinned.
        recipe = self.recipe()
        if requirement.recipe_digest != sha256_hex(recipe):
            raise ContractError('Builder recipe differs from requirement identity', code='unlocked_recipe')

    def recipe(self):
        return {'builder': 'locked-archives-v1', 'artifacts': [
            {'sha256': a.sha256, 'destination': a.destination, 'format': a.format,
             'max_unpacked_bytes': a.max_unpacked_bytes} for a in self.archives],
            'probes': [list(x) for x in self.probes], 'fixups': [list(x) for x in self.fixups],
            'environment': self.environment, 'timeout': self.timeout}

    def build(self, destination, store, *, cancel=None):
        self._store = store
        for item in self.archives:
            blob = store.ingest(item.source, item.sha256)
            extract_locked(blob, confined(destination, item.destination), format=item.format,
                           maximum=item.max_unpacked_bytes, cancel=cancel)
        for command in self.fixups:
            probe(destination, command, timeout=self.timeout, cancel=cancel, environment=self.environment)
        return self.recipe()

    def verify(self, root, *, cancel=None):
        original = [probe(root, command, timeout=self.timeout, cancel=cancel, environment=self.environment)
                    for command in self.probes]
        with temporary_directory('operon-relocated-') as directory:
            moved = Path(directory) / 'relocated environment'
            if self.fixups:
                # conda-unpack is not repeatable on an already unpacked prefix.
                # Always derive a new deployment from the immutable packed input.
                moved.mkdir()
                self.build(moved, self._store, cancel=cancel)
            else:
                shutil.copytree(io_path(root), io_path(moved), symlinks=True)
            relocated = [probe(moved, command, timeout=self.timeout, cancel=cancel, environment=self.environment)
                         for command in self.probes]
        return {'status': 'passed', 'relocation': 'passed', 'probes': original, 'relocated_probes': relocated}
