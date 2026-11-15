"""Create an offline acceptance recipe from an upstream archive and exact wheels.

This only records inputs. Use environment_store prepare explicitly to install;
normal application startup and workflow compilation never call this script.
"""
from __future__ import annotations

import argparse
from email.parser import BytesParser
import json
from pathlib import Path
import sys
import tarfile
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from operon.contracts.base import sha256_hex
from operon.contracts.run_plan import EnvironmentRequirement, TargetSpec
from operon.environment_store.builders import LockedArchive
from operon.environment_store.python_builder import LockedWheel, PythonWheelhouseBuilder
from operon.environment_store.verification import file_digest


def create(assets, *, runtime_digest, os_name, arch, executable):
    assets = Path(assets).resolve()
    archive = assets / 'cpython311.tar.gz'
    if file_digest(archive) != runtime_digest:
        raise ValueError('Runtime differs from upstream authenticated release digest')
    with tarfile.open(archive) as source:
        allowance = sum(item.size for item in source)
    runtime = LockedArchive(archive, runtime_digest, 'runtime', allowance, 'tar.gz')
    wheels, entries, pins, names = [], [], [], set()
    for path in sorted((assets / 'wheelhouse').glob('*.whl')):
        with zipfile.ZipFile(path) as source:
            metadata = [name for name in source.namelist() if name.endswith('.dist-info/METADATA')]
            if len(metadata) != 1:
                raise ValueError('Wheel must have exactly one distribution metadata file')
            record = BytesParser().parsebytes(source.read(metadata[0]))
        name, version = record['Name'], record['Version']
        normalized = name.lower().replace('_', '-')
        if normalized in names:
            raise ValueError('Ambiguous wheelhouse distribution: ' + name)
        names.add(normalized)
        digest = file_digest(path)
        wheels.append(LockedWheel(path, digest))
        entries.append({'source': path.relative_to(assets).as_posix(), 'sha256': digest})
        pins.append(name + '==' + version + ' --hash=sha256:' + digest)
    lock = '\n'.join(pins) + '\n'
    imports = ['psutil', 'pydantic', 'yaml', 'jsonschema', 'numpy', 'packaging']
    builder = PythonWheelhouseBuilder(runtime, wheels, lock, executable=executable, imports=imports)
    requirement = EnvironmentRequirement(target=TargetSpec(os=os_name, arch=arch, python_abi='cp311'),
        runtime='cpython-3.11', dependency_lock={'artifact_hashes': [runtime.sha256, *[x.sha256 for x in wheels]],
                                             'requirements': lock}, recipe_digest=sha256_hex(builder.recipe()))
    value = {'kind': 'cpython-wheelhouse-v1', 'requirement': requirement.model_dump(mode='json'),
        'runtime': {'source': archive.name, 'sha256': runtime.sha256, 'destination': runtime.destination,
                    'format': runtime.format, 'max_unpacked_bytes': runtime.max_unpacked_bytes},
        'wheels': entries, 'lock': lock, 'executable': executable, 'imports': imports, 'timeout': builder.timeout}
    (assets / 'recipe.json').write_text(json.dumps(value, indent=2), encoding='utf-8')
    return {'recipe': str(assets / 'recipe.json'), 'requirement': sha256_hex(requirement),
            'wheels': len(wheels), 'runtime_sha256': runtime_digest}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--assets', required=True, type=Path)
    parser.add_argument('--runtime-digest', required=True)
    parser.add_argument('--os', dest='os_name', required=True)
    parser.add_argument('--arch', required=True)
    parser.add_argument('--executable', required=True)
    print(json.dumps(create(**vars(parser.parse_args())), indent=2))
