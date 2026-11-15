"""Static K04/K06 foreign lowering; no language/runtime execution is claimed."""
from copy import deepcopy
import hashlib
import json

import pytest

from operon.contracts.base import ContractError, sha256_hex
from operon.contracts.run_plan import EnvironmentRequirement, TargetSpec
from operon.execution.unit_executor import unit_dependencies
from operon.planning import WorkflowCompiler
from operon.planning.authoring_v2 import export_mapping, export_workflow, load_workflow, normalize
from operon.planning.invocation_lowering import NormalizedForeignWorkflow


def script(language, name, inputs=('data',), outputs=('result',), output_format='txt'):
    code = '# Synthetic static fixture: ' + name + '\n'
    return {'language': language, 'filename': name + ('.py' if language == 'python' else '.R'),
            'code': code, 'code_sha': hashlib.sha256(code.encode('utf-8')).hexdigest(),
            'inputs': {key: {'kind': 'file', 'format': 'txt'} for key in inputs},
            'outputs': {key: {'kind': 'file', 'format': output_format} for key in outputs},
            'parameters_schema': {'type': 'object', 'additionalProperties': False, 'properties': {
                'count': {'type': 'integer', 'default': 2}, 'flag': {'type': 'boolean', 'default': False},
                'optional': {'type': ['null', 'string'], 'default': None},
                'empty': {'type': 'array', 'default': []}}}, 'dependencies': []}


def document():
    def process(runner, env, snapshot):
        return {'runner': runner, 'environment': env, 'script': snapshot,
                'input': {name: {'type': 'path', 'format': port['format']} for name, port in snapshot['inputs'].items()},
                'output': {name: {'type': 'path', 'format': port['format']} for name, port in snapshot['outputs'].items()}}
    return {'format': 'operon.workflow', 'schema_version': 2, 'params_file': 'parameters.json',
            'inputs_file': 'inputs.json', 'environments_file': 'environments.json',
            'processes': {
                'Prepare': process('python_script', 'python', script('python', 'prepare')),
                'Statistics': {**process('r_script', 'r', script('r', 'statistics')),
                               'resources': {'memory': '64MiB', 'cpus': 2}},
                'Tool': {'runner': 'command', 'environment': 'native',
                         'input': {'data': {'type': 'path', 'format': 'txt'}},
                         'output': {'result': {'type': 'path', 'format': 'txt'}},
                         'command': {'argv': [{'literal': '--input'}, {'input': 'data'},
                                              {'literal': '--output'}, {'output': 'result'},
                                              {'literal': '--count'}, {'param': 'count'}]}},
                'Finish': process('python_script', 'python', script('python', 'finish', inputs=('main', 'branch'), output_format='json')),
            },
            'workflow': {
                'name': 'Python R executable Python file pipeline',
                'defaults': {'executor': 'local', 'resources': {'memory': '32MiB', 'cpus': 1}},
                'take': {'reads': {'type': 'path', 'format': 'txt', 'source': {'path': {'input': 'reads'}}}},
                'steps': {
                    'prepare': {'process': 'Prepare', 'in': {'data': {'ref': 'workflow.reads'}},
                                'params': {'count': {'param': 'count'}}},
                    'statistics': {'process': 'Statistics', 'in': {'data': {'ref': 'prepare.result'}}},
                    'tool': {'process': 'Tool', 'in': {'data': {'ref': 'statistics.result'}}},
                    'finish': {'process': 'Finish', 'in': {'main': {'ref': 'tool.result'}, 'branch': {'ref': 'prepare.result'}}},
                },
                'emit': {'report': {'ref': 'finish.result'}},
            }, 'profiles': {}}


def environments():
    target = TargetSpec(os='linux', arch='x86_64')
    return {key: {'requirement': EnvironmentRequirement(target=target, runtime=runtime,
                        dependency_lock={'artifact_hashes': [marker * 64]}).model_dump(mode='json'),
                  'executable': executable}
            for key, runtime, executable, marker in (
                ('python', 'cpython-3.11', 'runtime/bin/python', 'a'),
                ('r', 'r-4.4', 'runtime/bin/Rscript', 'b'),
                ('native', 'native-fixture', 'tools/transform', 'c'))}


def imported(tmp_path, value=None, **options):
    return normalize(value or document(), tmp_path, initial=True, parameters={'params': {'count': 0}},
                     inputs={'reads': 'reads.txt'}, environments=environments(), **options)


def replay(value, tmp_path):
    files = export_mapping(value)
    return normalize(files['workflow.yaml'], tmp_path, parameters=files['parameters.json'],
                     inputs=files['inputs.json'], environments=files['environments.json'], ui=files['ui.json'])


def test_python_r_executable_python_branch_join_uses_existing_units_and_dependencies(tmp_path):
    normalized = imported(tmp_path)
    assert isinstance(normalized, NormalizedForeignWorkflow)
    plan = WorkflowCompiler().compile_authoring(normalized)
    assert tuple(unit.invocation.kind for unit in plan.units) == ('python_script', 'r_script', 'command', 'python_script')
    assert unit_dependencies(plan) == {'prepare': set(), 'statistics': {'prepare'},
                                       'tool': {'statistics'}, 'finish': {'prepare', 'tool'}}
    assert plan.units[0].input_bindings == {'data': 'input:reads'}
    assert plan.units[2].input_bindings == {'data': 'artifact:statistics/result'}
    assert plan.units[3].input_bindings['branch'] == 'artifact:prepare/result'
    assert plan.execution_policy['workflow_outputs'] == {'report': 'artifact:finish/result'}
    assert plan.units[3].payload['outputs']['result']['representation'] == 'json'
    assert plan.units[3].payload['outputs']['result']['path'] == 'result.json'
    assert plan.units[1].resource_request.process_reservation_bytes == 64 * 1024**2
    assert plan.units[1].resource_request.cpu_threads == 2
    assert all(unit.resource_request.managed_budget_bytes == 0 for unit in plan.units)
    assert all(unit.placement.executor == 'local' for unit in plan.units)


def test_scripts_are_hash_bound_resources_and_argv_is_only_typed_data(tmp_path):
    value = imported(tmp_path)
    plan = value.compile()
    first = plan.units[0]
    resource = first.payload['script_resource']
    assert first.invocation.code_ref.ref == resource['path']
    assert first.invocation.code_ref.digest == resource['sha256']
    assert resource['sha256'] == hashlib.sha256(resource['content'].encode('utf-8')).hexdigest()
    assert resource['path'].startswith('scripts/') and resource['path'].endswith('/prepare.py')
    assert first.payload['arguments'] == ('--in-data', {'input': 'data'}, '--out-result', {'output': 'result'})
    assert plan.units[2].payload['arguments'][-1] == {'parameter': 'count'}
    assert plan.units[2].payload['parameters']['count'] == 0
    assert first.invocation.parameters_ref.digest == sha256_hex(first.payload['parameters'])
    assert not (tmp_path / 'scripts').exists()


def test_environment_refs_name_exact_requirements_and_distinct_runtimes(tmp_path):
    plan = imported(tmp_path).compile()
    assert len(plan.environment_requirements) == 3
    expected = {name: sha256_hex(value['requirement']) for name, value in environments().items()}
    assert plan.execution_policy['environment_refs'] == expected
    assert plan.units[0].invocation.environment_ref == 'python'
    assert plan.units[1].invocation.environment_ref == 'r'
    assert plan.units[2].payload['executable'] == 'tools/transform'


def test_foreign_canonical_export_replay_preserves_identity_and_values(tmp_path):
    value = imported(tmp_path)
    files = export_mapping(value)
    assert files['parameters.json']['format'] == 'operon.frozen-parameters'
    assert set(files['parameters.json']['steps']) == set(value.document.workflow.steps)
    assert all('parameters' not in process for process in files['workflow.yaml']['processes'].values())
    assert all('params' not in step for step in files['workflow.yaml']['workflow']['steps'].values())
    restored = replay(value, tmp_path)
    assert restored.compile().plan_id == value.compile().plan_id
    assert restored.parameters == value.parameters
    assert restored.parameters['steps']['prepare']['count'] == 0
    assert restored.parameters['steps']['prepare']['flag'] is False
    assert restored.parameters['steps']['prepare']['optional'] is None
    assert restored.parameters['steps']['prepare']['empty'] == ()
    directory = tmp_path / 'exported'
    export_workflow(value, directory)
    assert load_workflow(directory / 'workflow.yaml').compile().plan_id == value.compile().plan_id
    with pytest.raises(ContractError) as caught:
        export_workflow(value, tmp_path / 'legacy', legacy=True)
    assert caught.value.code == 'unsupported_export'


def test_replay_ignores_new_inline_defaults_and_cannot_mutate_snapshot(tmp_path):
    initial = imported(tmp_path)
    files = export_mapping(initial)
    files['workflow.yaml']['processes']['Prepare']['parameters'] = {'count': 99, 'new_default': True}
    files['workflow.yaml']['workflow']['steps']['prepare']['params'] = {'count': 123}
    restored = normalize(files['workflow.yaml'], tmp_path, parameters=files['parameters.json'],
                         inputs=files['inputs.json'], environments=files['environments.json'])
    assert restored.parameters['steps']['prepare']['count'] == 0
    assert 'new_default' not in restored.parameters['steps']['prepare']
    assert restored.compile().plan_id == initial.compile().plan_id
    with pytest.raises(TypeError):
        restored.parameters['steps']['prepare']['count'] = 7


@pytest.mark.parametrize('missing', ['memory', 'cpus', 'executor'])
def test_foreign_resources_and_executor_must_be_explicit(tmp_path, missing):
    value = document()
    if missing == 'executor':
        value['workflow']['defaults'].pop('executor')
    else:
        value['workflow']['defaults']['resources'].pop(missing)
    with pytest.raises(ContractError) as caught:
        imported(tmp_path, value)
    assert caught.value.code in ('invalid_resource', 'invalid_placement')


def test_native_library_and_foreign_mixing_fails_at_concrete_boundary(tmp_path):
    value = document()
    value['processes']['Tool'] = {'runner': 'native', 'operator': 'native_operator',
        'input': {'data': {'type': 'path', 'format': 'txt'}},
        'output': {'result': {'type': 'path', 'format': 'txt'}}}
    with pytest.raises(ContractError) as caught:
        imported(tmp_path, value)
    assert caught.value.code == 'unsupported_boundary'
    assert caught.value.details['path'] == ['workflow', 'steps', 'tool', 'in', 'data']


@pytest.mark.parametrize('change', ['format', 'type', 'converter', 'missing_reference'])
def test_file_boundaries_fail_closed(tmp_path, change):
    value = document()
    if change == 'format':
        value['processes']['Tool']['input']['data']['format'] = 'csv'
    elif change == 'type':
        value['processes']['Tool']['input']['data']['type'] = 'form'
    elif change == 'converter':
        value['workflow']['steps']['tool']['in']['data']['adaptation'] = {'mode': 'fixed', 'converters': ['unknown']}
    else:
        value['workflow']['steps']['tool']['in']['data']['ref'] = 'absent.result'
    with pytest.raises(ContractError):
        imported(tmp_path, value)


def test_cycles_use_the_existing_execution_unit_validator(tmp_path):
    value = document()
    value['workflow']['steps']['prepare']['in']['data']['ref'] = 'tool.result'
    with pytest.raises(ContractError) as caught:
        imported(tmp_path, value)
    assert caught.value.code == 'invalid_plan_edge'


@pytest.mark.parametrize('token', [{'input': 'missing'}, {'output': 'missing'}, {'param': 'missing'},
                                  {'resource': 'unknown'}, {'literal': 'bad\x00argument'}])
def test_foreign_argv_missing_bindings_have_precise_paths(tmp_path, token):
    value = document()
    value['processes']['Tool']['command']['argv'] = [token]
    with pytest.raises(ContractError) as caught:
        imported(tmp_path, value)
    assert caught.value.details['path'] == ['processes', 'Tool', 'command', 'argv', 0]


def test_script_hash_and_relative_environment_executables_are_validated(tmp_path):
    value = document()
    value['processes']['Prepare']['script']['code'] += 'print("edited")\n'
    with pytest.raises(ContractError) as caught:
        imported(tmp_path, value)
    assert caught.value.code == 'invalid_script'
    envs = environments()
    envs['python']['executable'] = '../outside-python'
    with pytest.raises(ContractError):
        normalize(document(), tmp_path, initial=True, parameters={'params': {'count': 0}},
                  inputs={'reads': 'reads.txt'}, environments=envs)


def test_files_are_checked_only_when_requested_and_never_materialized(tmp_path):
    value = imported(tmp_path)
    assert value.compile().units
    with pytest.raises(ContractError) as caught:
        value.compile(require_files=True)
    assert caught.value.code == 'input_missing'
    (tmp_path / 'reads.txt').write_text('synthetic\n')
    assert value.compile(require_files=True).units
    assert sorted(path.name for path in tmp_path.iterdir()) == ['reads.txt']


def test_foreign_snapshot_requires_exact_step_ids_and_no_reader_values(tmp_path):
    files = export_mapping(imported(tmp_path))
    for change in ('missing', 'reader', 'engine'):
        parameters = deepcopy(files['parameters.json'])
        if change == 'missing':
            parameters['steps'].pop('prepare')
        elif change == 'reader':
            parameters['sources']['reads'] = {}
        else:
            parameters['steps']['prepare']['_input_names'] = []
        with pytest.raises(ContractError):
            normalize(files['workflow.yaml'], tmp_path, parameters=parameters,
                      inputs=files['inputs.json'], environments=files['environments.json'])


def native_catalog(default=2):
    return {'operators': [{
        'id': 'synthetic_transform', 'kind': 'operator', 'inputs_arity': 1,
        'outputs': [], 'output_parameter': 'output',
        'parameters_schema': {'type': 'object', 'additionalProperties': False,
                              'properties': {'threshold': {'type': 'integer', 'default': default},
                                             'flag': {'type': 'boolean', 'default': False}}},
        'runtime_defaults': {'threshold': default, 'flag': False},
        'contracts': {'inputs': [{'kind': 'form'}], 'output': {'mode': 'passthrough', 'input': 0}},
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
                         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'dependencies': [], 'implementation': {'code_sha': 'd' * 64, 'version': '1'},
    }], 'readers': []}


def mixed_document():
    value = document()
    form = {'type': 'form', 'format': 'bpform', 'contract': {'kind': 'form'}}
    value['processes']['Statistics']['output']['result'] = deepcopy(form)
    value['processes']['Statistics']['script']['outputs']['result']['format'] = 'bpform'
    value['processes']['Tool'] = {
        'runner': 'native', 'operator': 'synthetic_transform', 'environment': 'python',
        'input': {'data': deepcopy(form)}, 'output': {'result': deepcopy(form)},
    }
    value['workflow']['steps']['tool']['params'] = {'threshold': {'param': 'count'}}
    value['processes']['Finish']['input']['main'] = deepcopy(form)
    value['processes']['Finish']['script']['inputs']['main']['format'] = 'bpform'
    value['workflow']['memory'] = {'enabled': True, 'auto_spill': True, 'budget_mb': 16,
                                    'process_limit_mb': 32, 'chunk_mb': 2}
    return value


def mixed_import(tmp_path, value=None, **options):
    return normalize(value or mixed_document(), tmp_path, initial=True, parameters={'params': {'count': 0}},
                     inputs={'reads': 'reads.txt'}, environments=environments(), catalog=native_catalog(), **options)


def test_python_r_native_python_branches_use_shared_compiler_and_invocation_dag(tmp_path):
    from operon.planning.invocation_lowering import NormalizedMixedWorkflow
    value = mixed_import(tmp_path)
    assert isinstance(value, NormalizedMixedWorkflow)
    plan = value.compile(native_catalog())
    assert [unit.invocation.kind for unit in plan.units] == ['python_script', 'r_script', 'native', 'python_script']
    assert unit_dependencies(plan) == {'prepare': set(), 'statistics': {'prepare'},
                                       'tool': {'statistics'}, 'finish': {'prepare', 'tool'}}
    statistics, native, finish = plan.units[1:]
    assert statistics.payload['outputs']['result']['path'] == 'result/value.bpform'
    assert statistics.output_contracts[0].representation == 'form'
    source = next(iter(native.input_bindings))
    assert native.input_bindings[source] == 'artifact:statistics/result'
    assert source in native.payload['task_manifest']['runtime']['exchange_inputs']
    assert native.payload['task_manifest']['runtime']['exchange_contracts'][source]['kind'] == 'form'
    assert native.payload['task_manifest']['runtime']['exchange_aliases'] == {'result': 'tool'}
    assert native.payload['task_manifest']['steps'][0]['name'] == 'synthetic_transform'
    assert native.payload['task_manifest']['steps'][0]['params']['threshold'] == 0
    assert finish.input_bindings['main'] == 'artifact:tool/result'
    assert native.resource_request.managed_budget_bytes == 16 * 1024**2
    assert native.resource_request.process_reservation_bytes == 32 * 1024**2
    assert native.payload['task_manifest']['runtime']['memory']['auto_spill'] is True
    assert native.payload['task_manifest']['runtime']['memory']['chunk_mb'] == 2
    assert 'synthetic_transform' in plan.implementations
    assert not (tmp_path / '.operon-boundaries').exists()


def test_mixed_snapshot_export_replay_preserves_frozen_values_and_profile(tmp_path):
    value = mixed_document()
    value['profiles']['large'] = {'resources': {'memory': '64MiB', 'cpus': 3}}
    initial = mixed_import(tmp_path, value, profile='large', overrides={'resources': {'cpus': 2}})
    files = export_mapping(initial)
    assert files['parameters.json']['format'] == 'operon.workflow-parameters'
    assert files['parameters.json']['steps']['tool']['params'] == {'threshold': 0, 'flag': False}
    assert files['workflow.yaml']['workflow']['defaults']['resources']['cpus'] == 2
    files['workflow.yaml']['processes']['Tool']['parameters'] = {'threshold': 98, 'new_default': 123}
    restored = normalize(files['workflow.yaml'], tmp_path, parameters=files['parameters.json'],
        inputs=files['inputs.json'], environments=files['environments.json'], catalog=native_catalog(default=99))
    assert restored.parameters == initial.parameters
    assert restored.compile(native_catalog(default=99)).plan_id == initial.compile(native_catalog()).plan_id
    destination = tmp_path / 'project'
    export_workflow(initial, destination)
    loaded = load_workflow(destination / 'workflow.yaml')
    assert loaded.compile(native_catalog()).plan_id == initial.compile(native_catalog()).plan_id


def test_mixed_nested_route_stays_inside_native_graph_compiler(tmp_path):
    value = mixed_document()
    process = value['processes']['Tool']
    process.pop('operator')
    process['route'] = {'id': 'route_123456abcdef', 'version': 1, 'name': 'Synthetic native route', 'graph': {
        'name': 'Synthetic route', 'base_dir': '.', 'memory': {'enabled': True, 'auto_spill': True},
        'nodes': [
            {'id': 'source', 'kind': 'source', 'source': {'path': 'unused.bpform'}, 'position': {'x': 1, 'y': 2}},
            {'id': 'inner', 'kind': 'operator', 'operator': 'synthetic_transform',
             'params': {'threshold': 7}, 'position': {'x': 3, 'y': 4}},
        ], 'edges': [{'id': 'inner-edge', 'source': 'source', 'target': 'inner'}],
        'interface': {'version': 1, 'inputs': [{'node_id': 'source', 'label': 'Form', 'contract': {'kind': 'form'}}],
                      'outputs': [{'node_id': 'inner', 'label': 'Result', 'handle': 'out'}]},
    }}
    initial = mixed_import(tmp_path, value)
    plan = initial.compile(native_catalog())
    native = plan.units[2]
    assert native.unit_id == 'tool'
    assert native.node_ids != ('tool',)
    assert native.payload['task_manifest']['steps'][0]['params']['threshold'] == 7
    assert set(native.payload['task_manifest']['runtime']['exchange_aliases']) == {'result'}
    files = export_mapping(initial)
    assert files['parameters.json']['steps']['tool']['route']['nodes']['inner']['params']['threshold'] == 7
    assert 'params' not in files['workflow.yaml']['processes']['Tool']['route']['graph']['nodes'][1]
    restored = normalize(files['workflow.yaml'], tmp_path, parameters=files['parameters.json'],
        inputs=files['inputs.json'], environments=files['environments.json'], ui=files['ui.json'])
    assert restored.compile(native_catalog()).plan_id == plan.plan_id


@pytest.mark.parametrize('change', ['missing_codec', 'wrong_kind', 'unproven_output', 'too_small', 'cycle'])
def test_mixed_boundary_resource_and_dependency_failures(tmp_path, change):
    value, catalog = mixed_document(), native_catalog()
    if change == 'missing_codec':
        value['processes']['Tool']['input']['data'].pop('format')
    elif change == 'wrong_kind':
        value['processes']['Statistics']['output']['result']['type'] = 'path'
    elif change == 'unproven_output':
        catalog['operators'][0]['data_formats']['outputs'][0] = {
            'logical_type': 'file_artifact', 'representations': ['file_artifact'], 'metadata': {}}
        catalog['operators'][0]['contracts']['output'] = {'mode': 'file', 'kind': 'file'}
    elif change == 'too_small':
        value['processes']['Tool']['resources'] = {'memory': '8MiB'}
    else:
        value['processes']['Statistics']['input']['data'] = {'type': 'form', 'format': 'bpform'}
        value['processes']['Statistics']['script']['inputs']['data']['format'] = 'bpform'
        value['workflow']['steps']['statistics']['in']['data']['ref'] = 'tool.result'
    with pytest.raises(ContractError) as caught:
        normalized = normalize(value, tmp_path, initial=True, parameters={'params': {'count': 0}},
            inputs={'reads': 'reads.txt'}, environments=environments(), catalog=catalog)
        normalized.compile(catalog)
    assert caught.value.code in {'unsupported_boundary', 'incompatible_port', 'invalid_resource', 'invalid_plan_edge'}


def test_foreign_self_loop_is_rejected_before_unit_internal_edges_are_ignored(tmp_path):
    value = document()
    value['workflow']['steps']['prepare']['in']['data']['ref'] = 'prepare.result'
    with pytest.raises(ContractError) as caught:
        imported(tmp_path, value)
    assert caught.value.code == 'invalid_plan_edge'
