"""Explicit CPython/wheelhouse preparation; no host environment mutation.

Resolution produces the hashed lock and wheelhouse before this offline builder
is called. Every wheel is an input artifact. The interpreter must be a clean
relocatable runtime archive, not a virtualenv copied from the developer machine.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import shutil

from operon.contracts.base import ContractError, sha256_hex
from .builders import LockedArchiveBuilder, probe
from .verification import confined, file_digest


@dataclass(frozen=True)
class LockedWheel:
    source: Path
    sha256: str


class PythonWheelhouseBuilder(LockedArchiveBuilder):
    def __init__(self, runtime, wheels, lock, *, executable, imports=(), timeout=300):
        self.wheels = tuple(wheels)
        self.lock = str(lock)
        self.executable = executable
        self.imports = tuple(imports)
        if not self.wheels or not self.lock.strip():
            raise ContractError('A complete hashed wheel lock is required', code='unlocked_artifact')
        # pip handles full requirements syntax and hashes; prohibit references
        # outside the supplied wheelhouse or options that alter installation.
        for line in self.lock.splitlines():
            clean = line.strip()
            if clean and not clean.startswith(('#', '--hash=')) and clean != '\\':
                if clean.startswith('-') or ' @ ' in clean or '://' in clean or '==' not in clean:
                    raise ContractError('Use exact version pins and SHA256 hashes only', code='unlocked_artifact')
        checks = [(executable, '-I', '-B', '-c',
                   'import importlib; ' + '; '.join('importlib.import_module(' + repr(name) + ')' for name in imports)),
                  (executable, '-I', '-B', '-m', 'pip', 'check')]
        super().__init__([runtime], checks, timeout=timeout)

    def recipe(self):
        return {**super().recipe(), 'builder': 'cpython-wheelhouse-v1',
                'wheel_hashes': sorted(item.sha256 for item in self.wheels),
                'lock_sha256': sha256_hex(self.lock), 'executable': self.executable}

    def resolve(self, requirement):
        # Archive resolver requires the full declared closure. Validate the wheel
        # set here, then pass an archive-only projection without weakening the
        # original identity or changing its actual builder recipe.
        declared = requirement.dependency_lock.get('artifact_hashes')
        hashes = [item.sha256 for item in (*self.archives, *self.wheels)]
        if not declared or sorted(declared) != sorted(hashes):
            raise ContractError('Lock must include runtime and every wheel', code='unlocked_artifact')
        projected = requirement.model_copy(update={'dependency_lock': {
            **requirement.dependency_lock, 'artifact_hashes': [item.sha256 for item in self.archives]}})
        super().resolve(projected)

    def build(self, destination, store, *, cancel=None):
        super().build(destination, store, cancel=cancel)
        target = confined(destination, self.executable)
        if (target.parent / 'pyvenv.cfg').exists():
            raise ContractError('A virtualenv is not a portable runtime', code='invalid_environment')
        wheelhouse = destination / 'wheelhouse'
        wheelhouse.mkdir()
        for item in self.wheels:
            if cancel and cancel():
                raise InterruptedError('Python preparation cancelled')
            if not item.source.name.endswith('.whl'):
                raise ContractError('Only prebuilt wheels are allowed in this recipe', code='unlocked_artifact')
            blob = store.ingest(item.source, item.sha256)
            shutil.copyfile(blob, wheelhouse / item.source.name)
        (destination / 'requirements.lock').write_text(self.lock, encoding='utf-8')
        probe(destination, (self.executable, '-I', '-B', '-m', 'pip', 'install',
            '--disable-pip-version-check', '--no-input', '--no-index', '--no-deps',
            '--no-compile', '--require-hashes', '--find-links', 'wheelhouse',
            '-r', 'requirements.lock'), timeout=self.timeout, cancel=cancel)
        return self.recipe()
