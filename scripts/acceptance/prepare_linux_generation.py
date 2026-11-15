"""Prepare a real Linux CPython generation for opt-in portable acceptance.

Acquisition is explicit: supply a trusted standalone runtime and its SHA256.
Wheels are downloaded by pip into the requested isolated directory, then every
resolved distribution/version/hash is frozen before the offline product builder.
No system interpreter, profile, operator library or global service is changed.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
import subprocess
import sys
import tarfile

from packaging.utils import parse_wheel_filename
from operon.contracts.base import sha256_hex
from operon.contracts.run_plan import EnvironmentRequirement, TargetSpec
from operon.environment_store import EnvironmentStore
from operon.environment_store.builders import LockedArchive
from operon.environment_store.python_builder import LockedWheel, PythonWheelhouseBuilder


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime', type=Path, required=True)
    parser.add_argument('--sha256', required=True)
    parser.add_argument('--work', type=Path, required=True)
    args = parser.parse_args()
    if sys.platform != 'linux':
        parser.error('Run on the Linux build target')
    runtime = args.runtime.resolve()
    if digest(runtime) != args.sha256:
        raise ValueError('Standalone runtime SHA256 differs')
    root = args.work.resolve()
    root.mkdir(parents=True, exist_ok=False)
    wheelhouse = root / 'wheelhouse'
    wheelhouse.mkdir()
    requirements = [name + '==' + importlib.metadata.version(name) for name in
                    ('numpy', 'pydantic', 'PyYAML', 'psutil', 'jsonschema', 'packaging')]
    with (root / 'acquisition.log').open('wb') as output:
        subprocess.run([sys.executable, '-m', 'pip', 'download', '--disable-pip-version-check',
                        '--only-binary=:all:', '--dest', str(wheelhouse), *requirements],
                       stdout=output, stderr=subprocess.STDOUT, timeout=600, check=True)
    wheels, lines = [], []
    for path in sorted(wheelhouse.glob('*.whl')):
        name, version, _, _ = parse_wheel_filename(path.name)
        sha = digest(path)
        wheels.append(LockedWheel(path, sha))
        lines.append(f'{name}=={version} --hash=sha256:{sha}')
    lock = '\n'.join(lines) + '\n'
    (root / 'requirements.lock').write_text(lock, encoding='utf-8')
    with tarfile.open(runtime, 'r:*') as archive:
        unpacked = sum(member.size for member in archive)
    executable = 'runtime/python/bin/python3'
    builder = PythonWheelhouseBuilder(
        LockedArchive(runtime, args.sha256, 'runtime', unpacked, 'tar.gz'), wheels, lock,
        executable=executable, imports=('numpy', 'pydantic', 'yaml', 'psutil', 'jsonschema'), timeout=300)
    requirement = EnvironmentRequirement(target=TargetSpec(os='linux', arch=platform.machine(),
        python_abi='cp311'), runtime='cpython-3.11', dependency_lock={
        'artifact_hashes': [args.sha256, *(wheel.sha256 for wheel in wheels)], 'requirements': lock},
        recipe_digest=sha256_hex(builder.recipe()))
    store = EnvironmentStore(root / 'store')
    binding = store.prepare(requirement, builder)
    report = {'store': str(store.root), 'binding': binding.model_dump(mode='json'),
              'requirement': requirement.model_dump(mode='json'), 'executable': executable}
    (root / 'environment.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2), flush=True)


if __name__ == '__main__':
    main()
