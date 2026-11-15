"""K06 static authoring, frozen replay and shared-compiler acceptance fixtures.

These fixtures use synthetic metadata, never real scientific data. Execution
platform acceptance remains separate from this normalization/compilation suite.
"""
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys

import pytest

from operon.contracts import ContractError
from operon.planning.authoring_v2 import (
    AuthoringDocument, export_mapping, export_workflow, json_schema, load_workflow,
    normalize, parse, select_profile,
)


def document():
    return {
        'format': 'operon.workflow', 'schema_version': 2,
        'params_file': 'parameters.json', 'inputs_file': 'inputs.json',
        'processes': {
            'Transform': {
                'runner': 'native', 'operator': 'synthetic_transform',
                'input': {'matrix': {'type': 'form', 'handle': 'in-0'}},
                'output': {'result': {'type': 'form', 'handle': 'out'}},
                'parameters': {'threshold': 2, 'output': 'result'},
            },
        },
        'workflow': {
            'name': 'Synthetic authoring fixture',
            'take': {'matrix': {'type': 'form', 'source': {'reader': 'SyntheticReader',
                               'path': {'input': 'matrix'}, 'dims': ['sample', 'feature']}}},
            'steps': {'transform': {'process': 'Transform', 'in': {'matrix': {'ref': 'workflow.matrix'}},
                                    'params': {'threshold': {'param': 'threshold'}}}},
            'emit': {'result': {'ref': 'transform.result'}},
            'memory': {'enabled': True, 'auto_spill': True, 'budget_mb': 32, 'process_limit_mb': 64},
        },
        'profiles': {},
    }


@pytest.fixture
def catalog():
    """A metadata-only Reader/identity operator with no executable provider."""
    return {
        'operators': [{
            'id': 'synthetic_transform', 'kind': 'operator', 'title': 'Synthetic transform',
            'inputs_arity': 1, 'outputs': [], 'output_parameter': 'output',
            'parameters_schema': {'type': 'object', 'additionalProperties': False,
                                  'properties': {'threshold': {'type': 'integer', 'default': 2},
                                                 'flag': {'type': 'boolean', 'default': False}}},
            'runtime_defaults': {'threshold': 2, 'flag': False},
            'contracts': {'inputs': [{'kind': 'form'}], 'output': {'mode': 'passthrough', 'input': 0}},
            'dependencies': [], 'implementation': {'code_sha': 'a' * 64, 'version': '1'},
        }],
        'readers': [{
            'id': 'SyntheticReader', 'kind': 'reader', 'extensions': ['.fixture'],
            'parameters_schema': {'type': 'object', 'additionalProperties': False,
                                  'properties': {'flag': {'type': 'boolean', 'default': False}}},
            'runtime_defaults': {'flag': False}, 'dependencies': [],
            'contracts': {'output': {'kind': 'form', 'ndim': 2}},
            'implementation': {'code_sha': 'b' * 64, 'version': '1'},
        }],
    }


def imported(tmp_path, **options):
    return normalize(document(), tmp_path, initial=True, parameters={'params': {'threshold': 0}},
                     inputs={'matrix': 'data.fixture'}, **options)


def roundtrip(result, directory):
    files = export_mapping(result, directory)
    return normalize(files['workflow.yaml'], directory, parameters=files['parameters.json'],
                     inputs=files['inputs.json'], environments=files.get('environments.json', {}),
                     ui=files['ui.json'])


def test_typed_references_preserve_zero_false_null_and_collections(tmp_path):
    value = document()
    value['workflow']['steps']['transform']['params'].update(
        flag=False, optional=None, empty=[], nested={'value': {'param': 'record'}})
    result = normalize(value, tmp_path, initial=True,
                       parameters={'params': {'threshold': 0, 'record': {'value': [False, None, 0]}}},
                       inputs={'matrix': 'data.fixture'})
    params = result.spec.nodes[1].params
    assert params['threshold'] == 0
    assert params['flag'] is False
    assert params['optional'] is None
    assert params['empty'] == ()
    assert params['nested']['value']['value'] == (False, None, 0)
    with pytest.raises(TypeError):
        result.parameters['nodes']['transform']['params']['threshold'] = 99
    with pytest.raises(TypeError):
        result.spec.nodes[1].params['threshold'] = 99


def test_author_export_import_has_independent_values_and_ui(tmp_path):
    before = imported(tmp_path)
    exported = tmp_path / 'exported'
    export_workflow(before, exported)
    raw = parse((exported / 'workflow.yaml').read_text(encoding='utf-8'))
    assert set(raw) == {'format', 'schema_version', 'params_file', 'inputs_file', 'processes', 'workflow', 'profiles'}
    assert 'threshold' not in (exported / 'workflow.yaml').read_text(encoding='utf-8')
    assert raw['processes']['transform']['output']['result']['handle'] == 'out'
    assert raw['workflow']['emit']['result'] == {'ref': 'transform.result'}
    after = load_workflow(exported / 'workflow.yaml')
    assert after.spec.nodes == before.spec.nodes
    assert after.spec.edges == before.spec.edges
    assert after.spec.runtime == before.spec.runtime
    assert after.parameters == before.parameters
    assert (exported / 'ui.json').exists()


def test_replay_never_substitutes_changed_or_new_catalog_defaults(tmp_path, catalog):
    before = imported(tmp_path, catalog=catalog)
    files = export_mapping(before, tmp_path)
    changed = deepcopy(catalog)
    changed['operators'][0]['parameters_schema']['properties']['threshold']['default'] = 91
    changed['operators'][0]['parameters_schema']['properties']['new_default'] = {'type': 'integer', 'default': 99}
    changed['operators'][0]['runtime_defaults'].update(threshold=91, new_default=99)
    changed['readers'][0]['parameters_schema']['properties']['new_reader_default'] = {'type': 'boolean', 'default': True}
    changed['readers'][0]['runtime_defaults']['new_reader_default'] = True
    # Replay ignores inline defaults as well as changed installed metadata.
    files['workflow.yaml']['processes']['transform']['parameters'] = {'threshold': 123, 'new_default': 999}
    after = normalize(files['workflow.yaml'], tmp_path, parameters=files['parameters.json'],
                      inputs=files['inputs.json'], catalog=changed)
    assert after.spec.nodes[1].params['threshold'] == 0
    assert 'new_default' not in after.spec.nodes[1].params
    plan = after.compile(changed, root=tmp_path)
    task = plan.units[0].payload['task_manifest']
    assert task['steps'][0]['params']['threshold'] == 0
    assert 'new_default' not in task['steps'][0]['params']
    assert 'new_reader_default' not in task['sources']['matrix']['args']
    assert plan.units[0].resource_request.managed_budget_bytes == 32 * 1024**2


def test_original_and_v2_use_one_deterministic_graph_compiler(tmp_path, catalog):
    from operon.planning import WorkflowCompiler
    before = imported(tmp_path, catalog=catalog)
    restored = roundtrip(before, tmp_path)
    direct = WorkflowCompiler().compile(before.spec, None, catalog, root=tmp_path, freeze_defaults=False)
    replay = restored.compile(catalog, root=tmp_path)
    assert direct.plan_id == replay.plan_id
    assert direct.parameters_digest == replay.parameters_digest
    assert direct.units[0].payload['task_manifest'] == replay.units[0].payload['task_manifest']


def test_profiles_use_cli_then_selected_then_workflow_defaults(tmp_path):
    value = document()
    value['workflow']['defaults'] = {'executor': 'local', 'resources': {'cpus': 1, 'memory': '1GiB'},
                                     'storage': {'read': 'shared'}}
    value['profiles'] = {'cluster': {'executor': 'slurm', 'target': {'partition': 'cpu'},
                                     'resources': {'cpus': 8, 'time': '2h'}}}
    model = AuthoringDocument.model_validate(value)
    policy = select_profile(model, 'cluster', {'resources': {'cpus': 4}})
    assert policy.executor == 'slurm'
    assert policy.resources.cpus == 4
    assert policy.resources.memory == 1024**3
    assert policy.resources.time == 7200
    assert policy.storage == {'read': 'shared'}
    result = normalize(value, tmp_path, initial=True, profile='cluster', overrides={'resources': {'cpus': 4}},
                       parameters={'params': {'threshold': 0}}, inputs={'matrix': 'data.fixture'})
    with pytest.raises(ContractError) as caught:
        result.compile({})
    assert caught.value.code == 'unsupported_boundary'
    assert caught.value.details['policy']['executor'] == 'slurm'
    restored = roundtrip(result, tmp_path)
    assert restored.document.profiles == result.document.profiles


@pytest.mark.parametrize('profile', [['local', 'ssh'], 'missing'])
def test_unknown_or_multiple_profiles_fail(profile):
    with pytest.raises(ContractError):
        select_profile(AuthoringDocument.model_validate(document()), profile)


@pytest.mark.parametrize('resources', [{'cpus': True}, {'cpus': '2'}, {'memory': False},
                                        {'memory': '-1GiB'}, {'time': 'tomorrow'}, {'cpus': 0}])
def test_resource_types_are_strict(resources, tmp_path):
    value = document()
    value['workflow']['defaults'] = {'resources': resources}
    with pytest.raises(ContractError) as caught:
        normalize(value, tmp_path, initial=True, parameters={'params': {'threshold': 0}}, inputs={'matrix': 'x'})
    assert caught.value.details['errors'][0]['path'][:3] == ['workflow', 'defaults', 'resources']


@pytest.mark.parametrize('text', [
    'a: 1\na: 2', 'x: !!python/object/apply:os.system [echo]',
    'x: &x [*x]', 'a: &a 1\nb: *a', '1: invalid', 'x: .nan', 'x: .inf',
])
def test_safe_yaml_negative_cases_have_structured_errors(text):
    with pytest.raises(ContractError) as caught:
        parse(text)
    assert caught.value.code == 'invalid_workflow'
    assert caught.value.details['path'] == []


def test_yaml12_and_bounded_parser():
    assert parse('on: off\nflag: false') == {'on': 'off', 'flag': False}
    with pytest.raises(ContractError) as caught:
        parse('x: ' + '[' * 60 + '0' + ']' * 60)
    assert caught.value.code == 'payload_too_large'


@pytest.mark.parametrize('field', ['name', 'nodes', 'execution', 'unexpected'])
def test_only_normative_top_level_fields_are_allowed(field, tmp_path):
    value = document()
    value[field] = 'bad'
    with pytest.raises(ContractError):
        normalize(value, tmp_path, initial=True, parameters={'params': {'threshold': 0}}, inputs={'matrix': 'x'})


@pytest.mark.parametrize('mutation, expected_path', [
    (lambda value: value['workflow']['steps']['transform']['params'].update(threshold={'param': 'absent'}),
     ['workflow', 'steps', 'transform', 'params', 'threshold']),
    (lambda value: value['workflow']['steps']['transform']['in']['matrix'].update(ref='missing.output'),
     ['workflow', 'steps', 'transform', 'in', 'matrix']),
    (lambda value: value['workflow']['steps']['transform']['params'].update(threshold='${params.threshold}'),
     ['workflow', 'steps', 'transform', 'params', 'threshold']),
])
def test_invalid_references_have_precise_paths(mutation, expected_path, tmp_path):
    value = document()
    mutation(value)
    with pytest.raises(ContractError) as caught:
        normalize(value, tmp_path, initial=True, parameters={'params': {'threshold': 0}}, inputs={'matrix': 'x'})
    assert caught.value.details['path'] == expected_path


def test_input_expression_is_typed_and_source_path_requires_text(tmp_path):
    value = document()
    value['workflow']['steps']['transform']['in']['matrix'] = {'input': 'matrix'}
    assert normalize(value, tmp_path, initial=True, parameters={'params': {'threshold': 0}},
                     inputs={'matrix': 'data.fixture'}).spec.edges[0].source == 'matrix'
    with pytest.raises(ContractError) as caught:
        normalize(value, tmp_path, initial=True, parameters={'params': {'threshold': 0}}, inputs={'matrix': 123})
    assert caught.value.details['path'] == ['workflow', 'take', 'matrix', 'source', 'path']


def test_typed_boundary_mismatch_and_duplicate_handles_fail(tmp_path):
    value = document()
    value['processes']['Transform']['input']['matrix']['type'] = 'path'
    with pytest.raises(ContractError) as caught:
        normalize(value, tmp_path, initial=True, parameters={'params': {'threshold': 0}}, inputs={'matrix': 'x'})
    assert caught.value.code == 'incompatible_port'
    value = document()
    value['processes']['Transform']['input']['other'] = {'type': 'form', 'handle': 'in-0'}
    value['workflow']['steps']['transform']['in']['other'] = {'ref': 'workflow.matrix'}
    with pytest.raises(ContractError, match='Duplicate'):
        normalize(value, tmp_path, initial=True, parameters={'params': {'threshold': 0}}, inputs={'matrix': 'x'})


def test_replay_requires_complete_independent_snapshot(tmp_path):
    with pytest.raises(ContractError) as caught:
        normalize(document(), tmp_path, parameters={'params': {'threshold': 0}}, inputs={'matrix': 'data.fixture'})
    assert caught.value.code == 'missing_frozen_parameters'
    files = export_mapping(imported(tmp_path), tmp_path)
    files['parameters.json']['nodes'].pop('transform')
    with pytest.raises(ContractError):
        normalize(files['workflow.yaml'], tmp_path, parameters=files['parameters.json'], inputs=files['inputs.json'])


@pytest.mark.parametrize('version', [True, '2', 2.0])
def test_authoring_version_does_not_coerce_scalars(tmp_path, version):
    value = document()
    value['schema_version'] = version
    with pytest.raises(ContractError):
        normalize(value, tmp_path, initial=True, parameters={}, inputs={})


@pytest.mark.parametrize('version', [True, '1', 1.0])
def test_frozen_parameter_version_does_not_coerce_scalars(tmp_path, version):
    files = export_mapping(imported(tmp_path), tmp_path)
    files['parameters.json']['schema_version'] = version
    with pytest.raises(ContractError) as caught:
        normalize(files['workflow.yaml'], tmp_path, parameters=files['parameters.json'], inputs=files['inputs.json'])
    assert caught.value.code == 'invalid_parameters'


def test_engine_owned_parameter_rejected_in_snapshot(tmp_path):
    files = export_mapping(imported(tmp_path), tmp_path)
    files['parameters.json']['nodes']['transform']['params']['_input_names'] = ['bad']
    with pytest.raises(ContractError) as caught:
        normalize(files['workflow.yaml'], tmp_path, parameters=files['parameters.json'], inputs=files['inputs.json'])
    assert caught.value.details['path'][-1] == '_input_names'


@pytest.mark.parametrize('field', ['params_file', 'inputs_file', 'environments_file'])
def test_sidecars_cannot_escape_even_with_injected_data(tmp_path, field):
    value = document()
    value[field] = '../outside.json'
    with pytest.raises(ContractError) as caught:
        normalize(value, tmp_path, initial=True, parameters={}, inputs={}, environments={})
    assert caught.value.code == 'workflow_resource_error'
    assert caught.value.details['path'] == [field]


def test_duplicate_json_keys_rejected(tmp_path):
    value = document()
    (tmp_path / 'parameters.json').write_text('{"params": {}, "params": {}}')
    with pytest.raises(ContractError, match='Duplicate JSON'):
        normalize(value, tmp_path, inputs={'matrix': 'data.fixture'})


def test_legacy_graph_nested_routes_converters_memory_and_ui_survive(tmp_path):
    inner = imported(tmp_path).spec.to_legacy_dict()
    inner['nodes'][0]['position'] = {'x': 111, 'y': 222}
    inner['nodes'][1]['position'] = {'x': 333, 'y': 444}
    inner['nodes'][1]['params'].update(flag=False, optional=None)
    outer = deepcopy(inner)
    outer['nodes'][1] = {
        'id': 'nested', 'kind': 'route', 'position': {'x': 700, 'y': 500}, 'params': {},
        'route': {'id': 'route_123456abcdef', 'version': 1, 'name': 'Nested', 'graph': inner},
    }
    outer['edges'] = [{'id': 'fixed', 'source': 'matrix', 'target': 'nested',
                       'sourceHandle': 'out', 'targetHandle': 'in-0',
                       'adaptation': {'mode': 'fixed', 'converters': ['synthetic_converter']}}]
    outer['runtime'] = {'execution': {'kind': 'local'}, 'workflow_outputs': {'out': 'steps.nested.out'}}
    restored = normalize(outer, tmp_path)
    files = export_mapping(restored, tmp_path)
    assert files['parameters.json']['nodes']['nested']['route']['nodes']['transform']['params']['optional'] is None
    assert files['workflow.yaml']['processes']['nested']['route']['graph']['nodes'][0]['position'] == {'x': 0, 'y': 0}
    assert files['ui.json']['routes']['nested']['positions']['matrix'] == {'x': 111.0, 'y': 222.0}
    again = roundtrip(restored, tmp_path)
    assert again.spec == restored.spec
    assert again.spec.edges[0].adaptation['converters'] == ('synthetic_converter',)
    assert again.spec.runtime['memory']['budget_mb'] == 32


def test_v1_import_and_requested_lossless_legacy_export(tmp_path):
    old = {'format': 'operon.workflow', 'schema_version': 1, 'name': 'Old',
           'sources': {'data': {'path': 'data.fixture', 'reader': 'SyntheticReader'}},
           'steps': {'main': {'operator': 'synthetic_transform', 'inputs': {'in0': 'sources.data'}}},
           'parameters': {'steps': {'main': {'params': {'threshold': 0}}}}}
    migrated = normalize(old, tmp_path)
    assert migrated.spec.nodes[1].params['threshold'] == 0
    directory = tmp_path / 'legacy'
    export_workflow(migrated, directory, legacy=True)
    assert parse((directory / 'workflow.yaml').read_text(encoding='utf-8'))['schema_version'] == 1


def test_legacy_export_rejects_unrepresentable_profiles(tmp_path):
    value = document()
    value['profiles'] = {'local': {'executor': 'local'}}
    result = normalize(value, tmp_path, initial=True, parameters={'params': {'threshold': 0}}, inputs={'matrix': 'x'})
    with pytest.raises(ContractError) as caught:
        export_workflow(result, tmp_path / 'legacy', legacy=True)
    assert caught.value.code == 'unsupported_export'
    assert not (tmp_path / 'legacy').exists()


def test_command_argv_is_data_and_unsupported_execution_is_explicit(tmp_path):
    value = document()
    process = value['processes']['Transform']
    process.pop('operator')
    process.update(runner='command', command={'argv': [{'literal': 'echo'}, {'param': 'threshold'}, {'input': 'matrix'}]})
    with pytest.raises(ContractError) as caught:
        normalize(value, tmp_path, initial=True, parameters={'params': {'threshold': 0}}, inputs={'matrix': 'x'})
    assert caught.value.code == 'unsupported_boundary'
    process['command']['argv'] = ['echo', '${params.threshold}']
    with pytest.raises(ContractError) as caught:
        normalize(value, tmp_path, initial=True, parameters={'params': {'threshold': 0}}, inputs={'matrix': 'x'})
    assert caught.value.details['errors'][0]['path'][:4] == ['processes', 'Transform', 'command', 'argv']


def test_export_preserves_existing_files_and_does_not_mutate_values(tmp_path):
    result = imported(tmp_path)
    before = json.dumps(export_mapping(result), sort_keys=True)
    marker = tmp_path / 'important.txt'
    marker.write_text('keep')
    with pytest.raises(ContractError) as caught:
        export_workflow(result, tmp_path)
    assert caught.value.code == 'export_exists'
    assert marker.read_text() == 'keep'
    assert json.dumps(export_mapping(result), sort_keys=True) == before


def test_schema_matches_strict_wire_models_and_import_is_metadata_only():
    assert json_schema()['additionalProperties'] is False
    assert set(json_schema()['properties']) == {'format', 'schema_version', 'params_file', 'inputs_file',
                                               'environments_file', 'processes', 'workflow', 'profiles'}
    root = Path(__file__).resolve().parents[1]
    code = ('import sys; import operon.planning.authoring_v2; '
            'assert not any(x in sys.modules for x in ("numpy", "pandas", "scipy", "src.web.service"))')
    completed = subprocess.run([sys.executable, '-c', code], cwd=root, capture_output=True, text=True)
    assert completed.returncode == 0, completed.stderr
