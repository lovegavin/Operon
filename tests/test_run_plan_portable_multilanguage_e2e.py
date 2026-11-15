"""Real Windows Python/R/C acceptance, using explicitly prepared generations.

No downloads, compiler invocation, substitute interpreter, or mock supervisor.
Missing opt-in artifacts skip; supplied artifacts that fail are test failures.
"""
from __future__ import annotations

import csv
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import uuid

import pytest

from test_run_plan_portable_e2e import target_store as target_store

from operon.bytecode import io_path
from operon.contracts.base import sha256_hex
from operon.contracts.run_plan import EnvironmentRequirement
from operon.engine.artifacts import ArtifactCommitter
from operon.environment_store import EnvironmentStore
from operon.environment_store.verification import confined, inventory
from operon.export.environments import collect_packed_inputs
from operon.export.service import ExportService
from operon.planning.authoring_v2 import export_mapping, normalize
from operon.execution.unit_executor import unit_dependencies
from operon.engine.fs import atomic_json


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / 'tests/fixtures/backend_multilanguage'
pytestmark = pytest.mark.skipif(os.name != 'nt', reason='This acceptance gate requires actual Windows Rscript and native C executables')


def _json(path):
    return json.loads(io_path(path).read_text(encoding='utf-8'))


def _extra_environment(kind, default_executable):
    prefix = 'OPERON_ACCEPTANCE_' + kind + '_ENV_'
    root, generation = os.environ.get(prefix + 'STORE'), os.environ.get(prefix + 'GENERATION')
    if not root or not generation:
        pytest.skip('Actual ' + kind + ' generation not supplied; no multilanguage acceptance claimed')
    store = EnvironmentStore(root, create=False)
    store.binding(generation)  # Missing/corrupt supplied generations fail.
    _, manifest, _ = store._manifest(generation)
    executable = os.environ.get(prefix + 'EXECUTABLE', default_executable)
    path = confined(store.root / 'generations' / generation / 'payload', executable)
    with io_path(path).open('rb') as stream:
        assert stream.read(2) == b'MZ', kind + ' executable must be a real Windows PE binary'
    return store, generation, EnvironmentRequirement.model_validate(manifest['requirement']), executable


@pytest.fixture
def multilanguage_store(target_store, tmp_path):
    supplied = {
        'python': target_store,
        'r': _extra_environment('R', 'runtime/bin/Rscript.exe'),
        'native': _extra_environment('NATIVE', 'tools/numeric_transform.exe'),
    }
    combined = EnvironmentStore(tmp_path / 'combined-store')
    environments, authoring = {}, {}
    python_target = supplied['python'][2].target
    assert python_target.os == 'windows'
    for name, (source, generation, requirement, executable) in supplied.items():
        assert (requirement.target.os, requirement.target.arch) == (python_target.os, python_target.arch)
        original, _, _ = source._manifest(generation)
        destination = combined.root / 'generations' / generation
        if not io_path(destination).exists():
            shutil.copytree(io_path(original), io_path(destination), symlinks=True)
        # Retain exact packed inputs too if a supported R/native generation
        # requires destination fixups. No verification receipt is fabricated.
        collect_packed_inputs(source, combined.root, generation)
        assert combined.binding(generation).requirement_digest == sha256_hex(requirement)
        environments[name] = {'generation_id': generation, 'executable': executable}
        authoring[name] = {'requirement': requirement.model_dump(mode='json'), 'executable': executable}
    return combined, environments, authoring


def _script(name, language, inputs, outputs, properties):
    code = io_path(FIXTURES / name).read_text(encoding='utf-8')
    return {'language': language, 'filename': name, 'code': code,
            'code_sha': hashlib.sha256(code.encode('utf-8')).hexdigest(),
            'inputs': {key: {'kind': 'file', 'format': value} for key, value in inputs.items()},
            'outputs': {key: {'kind': 'file', 'format': value} for key, value in outputs.items()},
            'parameters_schema': {'type': 'object', 'properties': properties, 'additionalProperties': False},
            'dependencies': []}


def _document():
    prepare = _script('prepare.py', 'python', {'data': 'json'}, {'result': 'tsv'},
                      {'factor': {'type': 'number', 'default': 99}})
    scale = _script('scale.R', 'r', {'data': 'tsv'}, {'result': 'tsv'},
                    {'factor': {'type': 'number', 'default': 100}})
    join = _script('join.py', 'python', {'main': 'tsv', 'branch': 'tsv'}, {'report': 'json'},
                   {'bias': {'type': 'number', 'default': 111}})

    def process(snapshot, runner, environment, memory):
        return {'runner': runner, 'script': snapshot, 'environment': environment,
                'resources': {'memory': memory, 'cpus': 1},
                'input': {key: {'type': 'path', 'format': item['format']} for key, item in snapshot['inputs'].items()},
                'output': {key: {'type': 'path', 'format': item['format']} for key, item in snapshot['outputs'].items()}}

    return {'format': 'operon.workflow', 'schema_version': 2, 'params_file': 'parameters.json',
        'inputs_file': 'inputs.json', 'environments_file': 'environments.json',
        'processes': {
            'Prepare': process(prepare, 'python_script', 'python', '192MiB'),
            'Scale': process(scale, 'r_script', 'r', '256MiB'),
            'Native': {'runner': 'command', 'environment': 'native',
                'resources': {'memory': '64MiB', 'cpus': 1},
                'input': {'data': {'type': 'path', 'format': 'tsv'}},
                'output': {'result': {'type': 'path', 'format': 'tsv'}},
                'parameters': {'offset': 999},
                'command': {'argv': [{'literal': '--input'}, {'input': 'data'},
                    {'literal': '--output'}, {'output': 'result'}, {'literal': '--offset'}, {'param': 'offset'}]}},
            'Join': process(join, 'python_script', 'python', '192MiB'),
        },
        'workflow': {'name': 'Actual Python R native C branch join', 'defaults': {'executor': 'local'},
            'take': {'data': {'type': 'path', 'format': 'json', 'source': {'path': {'input': 'data'}}}},
            'steps': {
                'prepare': {'process': 'Prepare', 'in': {'data': {'ref': 'workflow.data'}}, 'params': {'factor': 2}},
                'scale': {'process': 'Scale', 'in': {'data': {'ref': 'prepare.result'}}, 'params': {'factor': 3}},
                'native': {'process': 'Native', 'in': {'data': {'ref': 'scale.result'}}, 'params': {'offset': 5}},
                'join': {'process': 'Join', 'in': {'main': {'ref': 'native.result'}, 'branch': {'ref': 'prepare.result'}},
                         'params': {'bias': 0}},
            }, 'emit': {'result': {'ref': 'join.report'}}},
        'profiles': {}}


def _rows(reference):
    assert reference['representation'] == 'table'
    with io_path(reference['path']).open(encoding='utf-8', newline='') as stream:
        reader = csv.DictReader(stream, delimiter='\t')
        assert reader.fieldnames == ['value']
        return [float(row['value']) for row in reader]


def _assert_released_and_published(bundle, result, bindings):
    work = Path(result['work_dir'])
    published = {name: _json(Path(result['results']) / (name + '.json'))
                 for name in ('prepare', 'scale', 'native', 'join')}
    committer = ArtifactCommitter(work, None)
    for item in published.values():
        receipt = item['receipt']
        assert receipt['state'] == 'committed' and receipt['run_id'] == result['run_id']
        assert receipt['attempt_id'] and receipt['fence'] > 0
        assert committer.verify_existing(receipt)['valid']
    records = [_json(path) for path in io_path(work).rglob('invocation.json')]
    records = {value['spec']['kind']: value for value in records
               if value.get('format') == 'operon.foreign-invocation' and value.get('run_id') == result['run_id']}
    assert {'python_script', 'r_script', 'command'} <= set(records)
    for kind, environment in (('r_script', 'r'), ('command', 'native')):
        executable = records[kind]['argv'][0].replace('\\', '/').lower()
        assert executable.endswith('/' + bindings[environment]['executable'].replace('\\', '/').lower())
    assert '--vanilla' in records['r_script']['argv']
    assert '--input' in records['command']['argv'] and '--offset' in records['command']['argv']
    leases = [_json(path) for path in io_path(work / 'environments/leases').glob('*.json')]
    assert leases and all(value['state'] == 'released' for value in leases)
    assert all(value['proof']['tree_exited'] is True and value['proof']['method'] == 'windows-job' for value in leases)
    with sqlite3.connect(io_path(work / 'engine.sqlite')) as state:
        resource_leases = state.execute('SELECT state FROM leases').fetchall()
    assert len(resource_leases) >= 4 and all(row[0] == 'released' for row in resource_leases)
    # This checks the actual deployed generation after any recorded fixups.
    deployed = EnvironmentStore(work / 'environments', create=False)
    for value in leases:
        deployed.binding(value['generation_id'])
    return published


def test_actual_windows_python_r_native_c_moved_bundle_branch_join(multilanguage_store, tmp_path):
    store, bindings, declarations = multilanguage_store
    configured_work = os.environ.get('OPERON_ACCEPTANCE_FOREIGN_WORK_ROOT')
    if not configured_work:
        pytest.skip('Actual Windows R acceptance requires an explicitly short physical work root')
    work = Path(configured_work).absolute() / uuid.uuid4().hex[:8]
    assert not work.exists(), 'Each acceptance run needs an independent work partition'
    source = tmp_path / 'numbers.json'
    atomic_json(source, {'values': [1, 2, 3]})
    authored = normalize(_document(), tmp_path, initial=True, parameters={'params': {}},
                         inputs={'data': str(source)}, environments=declarations)
    snapshot = export_mapping(authored)
    replay = normalize(snapshot['workflow.yaml'], tmp_path, parameters=snapshot['parameters.json'],
                       inputs=snapshot['inputs.json'], environments=snapshot['environments.json'])
    plan = replay.compile(require_files=True)
    assert plan.plan_id == authored.compile(require_files=True).plan_id
    assert unit_dependencies(plan) == {'prepare': set(), 'scale': {'prepare'},
                                       'native': {'scale'}, 'join': {'prepare', 'native'}}
    assert {unit.unit_id: unit.invocation.kind for unit in plan.units} == {
        'prepare': 'python_script', 'scale': 'r_script', 'native': 'command', 'join': 'python_script'}
    initial = tmp_path / 'initial'
    receipt = ExportService(ROOT, store, tmp_path / 'build-receipts').build(
        plan, initial, implementations={}, environments=bindings, management_environment='python',
        input_formats={'data': 'json'})
    assert receipt['status'] == 'complete'
    moved = tmp_path / 'moved actual languages'
    io_path(initial).rename(io_path(moved))
    control = bindings['python']
    runtime = moved / 'payload/environments/generations' / control['generation_id'] / 'payload' / control['executable']
    home = tmp_path / 'clean-home'
    io_path(home).mkdir()
    empty_path = tmp_path / 'empty-path'
    io_path(empty_path).mkdir()
    environment = {key: value for key, value in os.environ.items()
                   if key.upper() in ('SYSTEMROOT', 'WINDIR', 'COMSPEC', 'TEMP', 'TMP')}
    environment.update(HOME=str(home), USERPROFILE=str(home), PATH=str(empty_path),
                       PYTHONNOUSERSITE='1', PYTHONDONTWRITEBYTECODE='1')
    expected = {'prepare': {'factor': 2}, 'scale': {'factor': 3}, 'native': {'offset': 5}, 'join': {'bias': 0}}
    assert _json(moved / 'parameters.json') == expected
    immutable = inventory(moved / 'payload')

    def launch(*options):
        completed = subprocess.run([str(io_path(runtime)), '-I', '-B', str(io_path(moved / 'run.py')),
            '--work-dir', str(work), '--memory', str(768 * 1024**2), '--threads', '2', *options],
            cwd=io_path(home), executable=str(io_path(runtime)), env=environment,
            capture_output=True, text=True, encoding='utf-8', timeout=300)
        assert completed.returncode == 0, completed.stdout + completed.stderr
        value = json.loads(completed.stdout)
        assert value['status'] == 'complete', value
        return value

    first = launch()
    publications = _assert_released_and_published(moved, first, bindings)
    assert _rows(publications['prepare']['outputs']['result']) == [2.0, 4.0, 6.0]
    assert _rows(publications['scale']['outputs']['result']) == [6.0, 12.0, 18.0]
    assert _rows(publications['native']['outputs']['result']) == [11.0, 17.0, 23.0]
    report = _json(publications['join']['outputs']['report']['path'])
    assert report == {'main': [11.0, 17.0, 23.0], 'branch': [2.0, 4.0, 6.0],
                      'main_sum': 51.0, 'branch_sum': 12.0, 'total': 63.0, 'count': 3}
    repeated = launch('--resume')
    assert repeated['run_id'] == first['run_id'] and repeated['reused'] is True
    _assert_released_and_published(moved, repeated, bindings)
    assert inventory(moved / 'payload') == immutable
    # Explicitly changing independent values starts a different real run.
    expected['scale']['factor'] = 4
    expected['native']['offset'] = -1
    atomic_json(moved / 'parameters.json', expected)
    changed = launch('--resume')
    assert changed['run_id'] != first['run_id']
    publications = _assert_released_and_published(moved, changed, bindings)
    assert _rows(publications['scale']['outputs']['result']) == [8.0, 16.0, 24.0]
    assert _rows(publications['native']['outputs']['result']) == [7.0, 15.0, 23.0]
    assert _json(publications['join']['outputs']['report']['path'])['total'] == 57.0
    assert inventory(moved / 'payload') == immutable
