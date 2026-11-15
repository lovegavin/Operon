"""Actual portable subprocess gates, enabled only with a verified target store.

Set OPERON_ACCEPTANCE_ENV_STORE and OPERON_ACCEPTANCE_ENV_GENERATION. Missing
target artifacts are a skip, never a synthetic runtime success.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

from operon.contracts.base import sha256_hex
from operon.contracts.run_plan import (CodeRef, InvocationSpec, ParametersRef, PlacementPolicy,
    ResourceRequestSpec, RunPlan, UnitSpec, EnvironmentRequirement, OutputContract)
from operon.environment_store import EnvironmentStore
from operon.engine.fs import atomic_json
from operon.export.service import ExportService
from operon.bytecode import io_path


SCRIPT = '''import argparse,json,os
from pathlib import Path
p=argparse.ArgumentParser()
p.add_argument('--input',action='append',default=[])
p.add_argument('--output',required=True)
a=p.parse_args()
params=json.loads(Path(os.environ['OPERON_PARAMETERS_FILE']).read_text())
assert int(os.environ['OPERON_MEMORY_BYTES']) > 0, 'Foreign resource hint lost its process reservation'
assert int(os.environ['OMP_NUM_THREADS']) > 0
if params.get('fail_once'):
    marker=Path(params['fail_once'])
    if not marker.exists():
        marker.write_text('test-owned transient failure injected')
        raise SystemExit(9)
total=sum(json.loads(Path(x).read_text())['value'] for x in a.input)
Path(a.output).write_text(json.dumps({'value':total*params['factor']}))
'''


def make_plan(requirement, executable, source, *, failure_marker=None):
    digest = hashlib.sha256(SCRIPT.encode()).hexdigest()
    script_ref = 'scripts/' + digest[:16] + '/transform.py'
    units = []
    for identifier, parents, factor in [('a', ['input:data'], 2), ('b', ['input:data'], 3),
                                         ('join', ['artifact:a/result', 'artifact:b/result'], 1)]:
        params = {'factor': factor}
        if identifier == 'join' and failure_marker is not None:
            params['fail_once'] = str(failure_marker)
        arguments = []
        bindings = {}
        for index, parent in enumerate(parents):
            port = 'in' + str(index)
            arguments.extend(['--input', {'input': port}])
            bindings[port] = parent
        arguments.extend(['--output', {'output': 'result'}])
        units.append(UnitSpec(unit_id=identifier, node_ids=(identifier,),
            invocation=InvocationSpec(kind='python_script', entrypoint='script',
                code_ref=CodeRef(kind='script', ref=script_ref, digest=digest), environment_ref='python',
                parameters_ref=ParametersRef(digest=sha256_hex(params))),
            input_bindings=bindings,
            output_contracts=(OutputContract(name='result', representation='json'),),
            resource_request=ResourceRequestSpec(
                process_reservation_bytes=64*1024**2, cpu_threads=1),
            placement=PlacementPolicy(target=requirement.target),
            payload={'parameters': params, 'executable': executable, 'arguments': arguments,
                     'outputs': {'result': {'path': 'result.json', 'representation': 'json'}},
                     'script_resource': {'path': script_ref, 'sha256': digest, 'content': SCRIPT}}))
    edges = tuple({'source': parent, 'target': 'join', 'source_handle': 'result',
                   'target_handle': 'in'+str(i)} for i, parent in enumerate(('a', 'b')))
    return RunPlan(plan_id='pending', workflow_revision='a'*64, units=tuple(units), edges=edges,
        parameters_digest=sha256_hex({u.unit_id: u.payload['parameters'] for u in units}),
        environment_requirements=(requirement,), execution_policy={
            'environment_refs': {'python': sha256_hex(requirement)}, 'input_files': {'data': str(source)}},
        compiler_version='acceptance-real-portable/1').with_identity()


@pytest.fixture
def target_store():
    root = os.environ.get('OPERON_ACCEPTANCE_ENV_STORE')
    generation = os.environ.get('OPERON_ACCEPTANCE_ENV_GENERATION')
    if not root or not generation:
        pytest.skip('Actual target environment not supplied; no portability acceptance claimed')
    store = EnvironmentStore(root, create=False)
    store.binding(generation)
    _, manifest, _ = store._manifest(generation)
    executable = os.environ.get('OPERON_ACCEPTANCE_ENV_EXECUTABLE', 'runtime/python/python.exe')
    return store, generation, EnvironmentRequirement.model_validate(manifest['requirement']), executable


def test_real_export_moved_bundle_branch_join_parameter_input_resume(target_store, tmp_path, monkeypatch):
    store, generation, requirement, executable = target_store
    import operon.export.service as export_module
    original_probe = export_module.probe
    probes = []
    def observe_probe(root, argv, **kwargs):
        probes.append(argv)
        return original_probe(root, argv, **kwargs)
    monkeypatch.setattr(export_module, 'probe', observe_probe)
    source = tmp_path / 'input.json'
    atomic_json(source, {'value': 7})
    # Explicit test-owned transient failure; no cache eligibility is claimed.
    plan = make_plan(requirement, executable, source, failure_marker=tmp_path/'fault.once')
    export = ExportService(Path(__file__).resolve().parents[1], store, tmp_path/'receipts')
    directory = tmp_path / 'initial'
    result = export.build(plan, directory, implementations={},
        environments={'python': {'generation_id': generation, 'executable': executable}},
        management_environment='python', input_formats={'data': 'json'})
    assert result['status'] == 'complete'
    assert any('--check' in argv for argv in probes)
    if not store._manifest(generation)[1]['identity']['builder'].get('fixups'):
        assert not any('--prepare-only' in argv for argv in probes)
    moved = tmp_path / 'moved package'
    directory.rename(moved)
    runtime = moved / 'payload/environments/generations' / generation / 'payload' / executable
    home = tmp_path / 'blank-home'; home.mkdir()
    environment = {key: value for key, value in os.environ.items()
                   if key.upper() in ('SYSTEMROOT', 'WINDIR', 'COMSPEC', 'TEMP', 'TMP')}
    environment.update(HOME=str(home), USERPROFILE=str(home), PYTHONNOUSERSITE='1', PYTHONDONTWRITEBYTECODE='1')
    def launch(*extra, expected_code=0):
        process = subprocess.run([str(io_path(runtime)), '-I', '-B', str(io_path(moved/'run.py')),
            '--memory', str(256*1024**2), '--threads', '2', *extra], cwd=home,
            executable=str(io_path(runtime)), env=environment, capture_output=True,
            text=True, encoding='utf-8', timeout=180)
        assert process.returncode == expected_code, process.stdout + process.stderr
        return json.loads(process.stdout)
    failed = launch(expected_code=1)
    assert failed['status'] == 'failed'
    first = launch('--resume')
    assert first['status'] == 'complete'
    assert first['run_id'] != failed['run_id']
    import sqlite3
    with sqlite3.connect(moved/'work/engine.sqlite') as state:
        reused = state.execute('SELECT count(*) FROM unit_reuses x JOIN units u ON u.id=x.unit_id WHERE u.run_id=?',
                               (first['run_id'],)).fetchone()[0]
        assert reused == 2, 'Both completed ancestor branches must attach without a new attempt'
    published = json.loads((Path(first['results'])/'join.json').read_text())
    assert json.loads(Path(published['outputs']['result']['path']).read_text()) == {'value': 35}
    repeated = launch('--resume')
    assert repeated['run_id'] == first['run_id'] and repeated['reused']
    changed = json.loads((moved/'parameters.json').read_text())
    changed['a']['factor'] = 4
    atomic_json(moved/'parameters.json', changed)
    new_source = tmp_path / 'renamed.json'; atomic_json(new_source, {'value': 2})
    atomic_json(moved/'inputs.json', {'data': str(new_source)})
    second = launch('--resume')
    assert second['run_id'] != first['run_id']
    outputs = json.loads((Path(second['results'])/'join.json').read_text())['outputs']
    assert json.loads(Path(outputs['result']['path']).read_text()) == {'value': 14}
    leases = [json.loads(p.read_text()) for p in (moved/'work/environments/leases').glob('*.json')]
    assert leases and all(item['state'] == 'released' for item in leases)
