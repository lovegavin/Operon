"""Explicit offline preparation of a real desktop plan acceptance fixture.

Run with the installed application's private Python. The chosen private runtime
is hashed, archived and prepared by the existing immutable environment builder;
original and relocated import probes must pass. This is preparation, never an
automatic side effect of opening the application. No downloads or pip installs.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import platform
import stat
import sys
import tarfile


SCRIPT = '''# input: data file.json
# output: result file.json
import argparse,json,os
from pathlib import Path
p=argparse.ArgumentParser()
p.add_argument('--in-data',required=True)
p.add_argument('--out-result',required=True)
a=p.parse_args()
params=json.loads(Path(os.environ['OPERON_PARAMETERS_FILE']).read_text(encoding='utf-8'))
source=json.loads(Path(a.in_data).read_text(encoding='utf-8'))
Path(a.out_result).write_text(json.dumps({'value':source['value']*params['factor']},sort_keys=True),encoding='utf-8')
print('Desktop acceptance result written',flush=True)
'''


def workflow():
    from operon.script_operators import inspect_source
    snapshot = inspect_source('multiply.py', SCRIPT)
    snapshot['parameters_schema']['properties']['factor'] = {'type': 'integer'}
    return {'format': 'operon.workflow', 'schema_version': 2,
        'processes': {'Multiply': {'runner': 'python_script', 'environment': 'python', 'script': snapshot,
            'input': {'data': {'type': 'path', 'format': 'json'}},
            'output': {'result': {'type': 'path', 'format': 'json'}}}},
        'workflow': {'name': 'Desktop plan acceptance',
            'defaults': {'executor': 'local', 'resources': {'memory': '128MiB', 'cpus': 1}},
            'take': {'data': {'type': 'path', 'format': 'json', 'source': {'path': {'input': 'data'}}}},
            'steps': {'first': {'process': 'Multiply', 'in': {'data': {'ref': 'workflow.data'}},
                                'params': {'factor': 2}},
                      'second': {'process': 'Multiply', 'in': {'data': {'ref': 'first.result'}},
                                 'params': {'factor': 3}}},
            'emit': {'result': {'ref': 'second.result'}}}, 'profiles': {}}


def archive_runtime(home, archive):
    """Freeze the supplied private runtime without following outside aliases."""
    from operon.bytecode import io_path
    from operon.environment_store.verification import inventory, verify_inventory
    home = Path(home).resolve(strict=True)
    if (home / 'pyvenv.cfg').exists():
        raise ValueError('A virtual environment is not a relocatable private runtime')
    for parent, directories, files in os.walk(io_path(home), followlinks=False):
        for name in directories + files:
            value = (Path(parent) / name).lstat()
            if os.name == 'nt' and getattr(value, 'st_file_attributes', 0) & 0x400:
                raise ValueError('Private runtime must not contain Windows reparse aliases')
            if not (stat.S_ISREG(value.st_mode) or stat.S_ISDIR(value.st_mode) or stat.S_ISLNK(value.st_mode)):
                raise ValueError('Private runtime contains a special file')
    records = inventory(home)
    with tarfile.open(io_path(archive), 'x', format=tarfile.PAX_FORMAT) as output:
        for relative, item in sorted(records.items()):
            info = tarfile.TarInfo(relative)
            info.mtime, info.uid, info.gid = 0, 0, 0
            if item['kind'] == 'symlink':
                info.type, info.linkname, info.mode = tarfile.SYMTYPE, item['target'], 0o777
                output.addfile(info)
            else:
                info.size, info.mode = item['size'], 0o755 if item['executable'] else 0o644
                with io_path(home / relative).open('rb') as source:
                    output.addfile(info, source)
    verify_inventory(home, records)
    return sum(item.get('size', 0) for item in records.values())


def write_fixture(workspace, folder, application_root, requirement, generation, executable):
    """Compile through the shared authoring path and materialize its source refs."""
    from operon.bytecode import io_path
    from operon.contracts.plan_operations import PlanCompileRequest, PlanExecutionBinding
    from operon.contracts.plan_export import PlanExportRequest
    from operon.engine.fs import atomic_json
    from operon.environment_store.verification import file_digest
    from operon.export.collector import collect, kernel_files
    from operon.planning.authoring_v2 import normalize
    from operon.planning.validation import validate_run_plan
    root = workspace / folder
    package = root / 'code'
    collect(application_root, package, kernel_files(application_root))
    source = root / 'input.json'
    atomic_json(source, {'value': 7})
    declarations = {'python': {'requirement': requirement.model_dump(mode='json'), 'executable': executable}}
    request = PlanCompileRequest(kind='authoring-v2', workflow=workflow(), directory=folder,
        parameters={'params': {}}, inputs={'data': 'input.json'}, environments=declarations,
        initial=True, require_files=True)
    normalized = normalize(request.workflow, root, parameters=request.parameters, inputs=request.inputs,
        environments=request.environments, initial=True)
    plan = validate_run_plan(normalized.compile(require_files=True))
    for unit in plan.units:
        resource = unit.payload['script_resource']
        target = io_path(package / resource['path'])
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(resource['content'].encode('utf-8'))
    binding = PlanExecutionBinding(package_root=folder + '/code', environment_store=folder + '/env',
        environments={'python': {'generation_id': generation, 'executable': executable}},
        inputs={'data': {'path': folder + '/input.json', 'representation': 'json',
                         'size_bytes': source.stat().st_size, 'sha256': file_digest(source)}})
    export = PlanExportRequest(plan=plan, request_id='desktop-export-' + plan.plan_id,
        source_root=binding.package_root, environment_store=binding.environment_store,
        output=folder + '/exported', environments=binding.environments,
        management_environment='python', input_bindings={'data': folder + '/input.json'},
        input_formats={'data': 'json'})
    for name, value in {'compile-request.json': request.model_dump(mode='json'),
        'binding.json': binding.model_dump(mode='json'),
        'execution-plan.json': {'plan': plan.model_dump(mode='json'), 'binding': binding.model_dump(mode='json')},
        'export-request.json': export.model_dump(mode='json'),
        'expected.json': {'first': {'value': 14}, 'second': {'value': 42}}}.items():
        atomic_json(root / name, value)
    return {'fixture': str(root), 'plan_id': plan.plan_id, 'generation_id': generation,
            'compile_request': str(root / 'compile-request.json'), 'binding': str(root / 'binding.json'),
            'plan': str(root / 'execution-plan.json'), 'expected_final': {'value': 42},
            'source_root': binding.package_root, 'environment_store': binding.environment_store,
            'export_output': export.output}


def prepare(*, workspace, application_root, python_home, folder='desktop-plan-acceptance',
            python_executable=None, prepare_environment=False):
    from operon.bytecode import io_path
    from operon.contracts.base import sha256_hex
    from operon.contracts.plan_operations import binding_path
    from operon.contracts.run_plan import EnvironmentRequirement, TargetSpec
    from operon.engine.fs import atomic_json
    from operon.environment_store import EnvironmentStore
    from operon.environment_store.builders import LockedArchive, LockedArchiveBuilder
    from operon.environment_store.verification import confined, file_digest
    if not prepare_environment:
        raise ValueError('Pass --prepare-environment to explicitly copy and execute runtime verification probes')
    workspace, application_root, home = (Path(item).resolve(strict=True) for item in
                                         (workspace, application_root, python_home))
    folder = binding_path(folder)
    root = confined(workspace, folder)
    if root == workspace or root.exists() or home.is_relative_to(root) or root.is_relative_to(home):
        raise ValueError('Choose a fresh fixture folder, separate from the private runtime')
    relative_executable = binding_path(python_executable or ('python.exe' if os.name == 'nt' else 'bin/python3'))
    if not confined(home, relative_executable).is_file():
        raise ValueError('Private Python executable is missing')
    root.mkdir(parents=True)
    archive = root / 'private-runtime.tar'
    allowance = archive_runtime(home, archive)
    executable = 'runtime/' + relative_executable
    # The stdlib fixture also exports a management kernel, whose real imports
    # must resolve inside this exact copied runtime, never the developer profile.
    check = ('import importlib,sys,pathlib; '
        'assert sys.version_info >= (3,11); assert sys.prefix == sys.base_prefix; '
        'root=pathlib.Path(sys.prefix).resolve(); '
        "modules=[importlib.import_module(x) for x in ('psutil','pydantic','yaml','jsonschema','numpy','packaging')]; "
        'assert all(pathlib.Path(x.__file__).resolve().is_relative_to(root) for x in modules)')
    artifact = LockedArchive(archive, file_digest(archive), 'runtime', allowance, 'tar')
    builder = LockedArchiveBuilder([artifact], [(executable, '-I', '-B', '-c', check)], timeout=120)
    arch = {'amd64': 'x86_64', 'arm64': 'aarch64'}.get(platform.machine().lower(), platform.machine().lower())
    requirement = EnvironmentRequirement(target=TargetSpec(os=platform.system().lower(), arch=arch),
        runtime='cpython-private-desktop-acceptance', dependency_lock={'artifact_hashes': [artifact.sha256]},
        recipe_digest=sha256_hex(builder.recipe()))
    store = EnvironmentStore(root / 'env')
    verified = store.prepare(requirement, builder)
    # Only this helper's redundant source archive is removed; the immutable
    # builder blob, generation and verification records remain authoritative.
    io_path(archive).unlink()
    atomic_json(root / 'environment.json', {'store': str(store.root), 'binding': verified.model_dump(mode='json'),
        'requirement': requirement.model_dump(mode='json'), 'executable': executable})
    report = write_fixture(workspace, folder, application_root, requirement, verified.generation_id, executable)
    atomic_json(root / 'preparation.json', {**report, 'status': 'prepared', 'runtime_archive_sha256': artifact.sha256,
        'runtime_unpacked_bytes': allowance, 'verification': verified.verification_receipt})
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace', required=True, type=Path)
    parser.add_argument('--application-root', required=True, type=Path)
    parser.add_argument('--python-home', required=True, type=Path)
    parser.add_argument('--python-executable')
    parser.add_argument('--folder', default='desktop-plan-acceptance')
    parser.add_argument('--prepare-environment', action='store_true')
    args = parser.parse_args()
    sys.path.insert(0, str(args.application_root.resolve(strict=True)))
    print(json.dumps(prepare(**vars(args)), indent=2), flush=True)


if __name__ == '__main__':
    main()
