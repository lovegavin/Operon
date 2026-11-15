"""Opt-in moved-package native and native/Form/Python execution acceptance.

Requires OPERON_ACCEPTANCE_ENV_STORE and OPERON_ACCEPTANCE_ENV_GENERATION.
The supplied generation must actually contain NumPy and the management runtime
dependencies. Absence of a target store is a skip; runtime failure is a failure.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
from operon.bytecode import io_path

from test_native_runtime_snapshot import provider as provider  # Reuse owned package fixture.
from test_run_plan_portable_e2e import target_store as target_store  # Verified, opt-in real store.

from operon.environment_store.verification import file_digest, inventory
from operon.export.collector import kernel_files
from operon.export.service import ExportService
from operon.planning.authoring_v2 import normalize


ROOT = Path(__file__).resolve().parents[1]
PROVIDER_FILES = ('__init__.py', 'operators.py')
CONSUMER = '''import argparse,json,os
from pathlib import Path
from operon.execution.codecs import load

parser=argparse.ArgumentParser()
parser.add_argument('--in-data',required=True)
parser.add_argument('--out-report',required=True)
args=parser.parse_args()
references=json.loads(Path(os.environ['OPERON_INPUTS_FILE']).read_text())
reference=references['data']
assert reference['representation']=='form'
assert Path(reference['path']).resolve()==Path(args.in_data).resolve()
form=load(reference,mmap=True)
report={'sum':float(form.data.sum()),'shape':list(form.data.shape),
        'dims':form.dims,'labels':form.labels}
Path(args.out_report).write_text(json.dumps(report))
'''


def _document(source, *, consumer):
    form = {'type': 'form', 'format': 'bpform'}
    value = {'format': 'operon.workflow', 'schema_version': 2, 'params_file': 'parameters.json',
        'processes': {'Identity': {'runner': 'native', 'operator': 'owned.identity', 'environment': 'locked',
            'input': {'data': deepcopy(form)}, 'output': {'result': deepcopy(form)}}},
        'workflow': {'name': 'Portable owned native fixture',
            'defaults': {'executor': 'local', 'resources': {'memory': '192MiB', 'cpus': 1}},
            'take': {'input': {'type': 'form', 'source': {'reader': 'OwnedReader', 'path': str(source)}}},
            'steps': {'transform': {'process': 'Identity', 'in': {'data': {'ref': 'workflow.input'}},
                                    'params': {'output': 'result'}}},
            'emit': {'result': {'ref': 'transform.result'}}, 'memory': {'enabled': False}}}
    if consumer:
        script = {'language': 'python', 'filename': 'consume_form.py', 'code': CONSUMER,
            'code_sha': hashlib.sha256(CONSUMER.encode('utf-8')).hexdigest(),
            'inputs': {'data': {'kind': 'file', 'format': 'bpform'}},
            'outputs': {'report': {'kind': 'file', 'format': 'json'}},
            'parameters_schema': {'type': 'object', 'properties': {}, 'additionalProperties': False},
            'dependencies': []}
        value['processes']['Consume'] = {'runner': 'python_script', 'script': script, 'environment': 'locked',
            'input': {'data': deepcopy(form)}, 'output': {'report': {'type': 'path', 'format': 'json'}}}
        value['workflow']['steps']['consume'] = {'process': 'Consume', 'in': {'data': {'ref': 'transform.result'}}}
        value['workflow']['emit']['report'] = {'ref': 'consume.report'}
    else:
        # The existing native graph exchange contract exports a real Form.
        value['workflow']['runtime'] = {'exchange_outputs': ['result'], 'exchange_aliases': {'result': 'result'}}
    return value


def _staged_source(root, provider_root):
    """Export from an exact source-root-relative map; never copy the library."""
    staging = provider_root / 'export-source'
    staging.mkdir()
    for relative, record in kernel_files(root).items():
        destination = staging / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(root / record['path'], destination)
    files = {}
    for filename in PROVIDER_FILES:
        source = provider_root / 'owned_native_provider' / filename
        relative = 'provider-sources/owned_native_provider/' + filename
        staged = staging / relative
        staged.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, staged)
        files['owned_native_provider/' + filename] = {
            'path': relative, 'sha256': file_digest(source), 'role': 'implementation'}
    return staging, files


def _build_move_launch(provider, target_store, *, consumer):
    fixture_root, catalog = provider
    catalog = deepcopy(catalog)
    if consumer:
        # This owned identity fixture guarantees Form -> Form, declared here
        # explicitly for the cross-invocation materialization contract.
        descriptor = catalog['operators'][0]
        port = {'logical_type': 'form', 'representations': ['form'], 'metadata': {}}
        descriptor['data_formats'] = {'inputs': [deepcopy(port)], 'outputs': [deepcopy(port)]}
        descriptor['protocol_revision'] = '3.6'
        from operon_sdk.declarations import declaration_hash
        descriptor['declaration_sha'] = declaration_hash(descriptor)
        descriptor['implementation']['declaration_sha'] = descriptor['declaration_sha']
    store, generation, requirement, executable = target_store
    source = fixture_root / 'numbers.owned'
    source.write_text('1 2 3', encoding='utf-8')
    environments = {'locked': {'requirement': requirement.model_dump(mode='json'), 'executable': executable}}
    # Initial authoring without catalog extraction represents a previously
    # frozen snapshot where the optional new_default value was absent. The
    # runtime catalog still advertises default=999; it must remain unapplied.
    value = normalize(_document(source, consumer=consumer), fixture_root, initial=True,
                      parameters={'params': {}}, environments=environments, catalog=None)
    plan = value.compile(catalog, require_files=True)
    native = next(unit for unit in plan.units if unit.invocation.kind == 'native')
    assert native.payload['task_manifest']['steps'][0]['params'] == {'output': 'result'}
    staging, files = _staged_source(ROOT, fixture_root)
    providers = {key: {'implementation': deepcopy(record['implementation']), 'files': deepcopy(files)}
                 for key, record in plan.model_dump(mode='json')['implementations'].items()}
    initial = fixture_root / 'portable-initial'
    result = ExportService(staging, store, fixture_root / 'export-receipts').build(
        plan, initial, implementations=providers,
        environments={'locked': {'generation_id': generation, 'executable': executable}},
        management_environment='locked')
    assert result['status'] == 'complete'
    parameters = json.loads((initial / 'parameters.json').read_text(encoding='utf-8'))
    assert all('new_default' not in step for step in parameters[native.unit_id].values())
    moved = fixture_root / 'moved native package'
    initial.rename(moved)
    # The launched interpreter cannot fall back to the original fixture import.
    (fixture_root / 'owned_native_provider').rename(fixture_root / 'provider-unavailable')
    runtime = moved / 'payload/environments/generations' / generation / 'payload' / executable
    blank_home = fixture_root / 'blank-home'
    blank_home.mkdir()
    environment = {key: val for key, val in os.environ.items()
                   if key.upper() in ('SYSTEMROOT', 'WINDIR', 'COMSPEC', 'TEMP', 'TMP')}
    environment.update(HOME=str(blank_home), USERPROFILE=str(blank_home), PYTHONNOUSERSITE='1',
                       PYTHONDONTWRITEBYTECODE='1')
    immutable_before = inventory(moved / 'payload')
    process = subprocess.run([str(io_path(runtime)), '-I', '-B', str(io_path(moved / 'run.py')),
        '--memory', str(512 * 1024**2), '--threads', '2'], cwd=blank_home, env=environment,
        executable=str(io_path(runtime)), capture_output=True, text=True, encoding='utf-8', timeout=240)
    assert process.returncode == 0, process.stdout + process.stderr
    finished = json.loads(process.stdout)
    assert finished['status'] == 'complete', finished
    assert inventory(moved / 'payload') == immutable_before
    leases = [json.loads(path.read_text(encoding='utf-8'))
              for path in (moved / 'work/environments/leases').glob('*.json')]
    assert leases and all(item['state'] == 'released' for item in leases)
    deployed_store = type(store)(moved / 'work/environments', create=False)
    assert deployed_store.binding(generation).generation_id == generation
    publication = json.loads((Path(finished['results']) / (native.unit_id + '.json')).read_text(encoding='utf-8'))
    reference = publication['outputs']['result']
    assert reference['representation'] == 'form'
    from operon.execution.codecs import load
    form = load(reference, mmap=True)
    assert form.data.tolist() == [[1.0], [2.0], [3.0]]
    assert form.dims == ['sample', 'feature']
    assert form.labels == {'sample': {'0': 0, '1': 1, '2': 2}, 'feature': {'value': 0}}
    native_output = Path(reference['path']).parents[2]
    summary = json.loads((native_output / 'run_summary.json').read_text(encoding='utf-8'))
    assert summary['status'] == 'complete'
    assert [step['name'] for step in summary['steps']] == ['owned.identity']
    exported = json.loads((native_output / summary['steps'][0]['export_path']).read_text(encoding='utf-8'))
    assert exported['values'] == {'output': 'result'}
    return moved, finished


def test_actual_native_reader_operator_moved_portable_package(target_store, provider):
    _build_move_launch(provider, target_store, consumer=False)


def test_actual_native_form_boundary_to_python_moved_portable_package(target_store, provider):
    moved, finished = _build_move_launch(provider, target_store, consumer=True)
    publication = json.loads((Path(finished['results']) / 'consume.json').read_text(encoding='utf-8'))
    report = json.loads(Path(publication['outputs']['report']['path']).read_text(encoding='utf-8'))
    assert report == {'sum': 6.0, 'shape': [3, 1], 'dims': ['sample', 'feature'],
                      'labels': {'sample': {'0': 0, '1': 1, '2': 2}, 'feature': {'value': 0}}}
    frozen = json.loads((moved / 'parameters.json').read_text(encoding='utf-8'))
    assert frozen['transform']['transform'] == {'output': 'result'}
    assert frozen['consume'] == {}
