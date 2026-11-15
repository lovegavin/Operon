"""Owned fixture providers for native invocation bootstrap; no library seed."""
from copy import deepcopy
import hashlib
import json
import sys

import pytest

from operon.contracts.base import ContractError, sha256_hex
from operon.contracts.run_plan import EnvironmentRequirement, TargetSpec
from operon.execution.adapters.native import NativeInvocationAdapter
from operon.execution.invocation import InvocationContext
from operon.execution.native_bootstrap import NativeRuntimeSnapshot, register_native_runtime, validate_native_descriptors
from operon.planning import WorkflowCompiler
from operon.planning.authoring_v2 import normalize
from operon.planning.descriptor_snapshot import execution_descriptor, execution_schema


@pytest.fixture
def provider(tmp_path, monkeypatch):
    monkeypatch.setenv('OPERON_REGISTRY_MAINTENANCE', '1')
    from src.task.step import STEPS
    from src.reader import READERS
    registry_before = (dict(STEPS.factories), dict(STEPS.loaded), dict(STEPS.declarations), list(READERS))
    package = tmp_path / 'owned_native_provider'
    package.mkdir()
    (package / '__init__.py').write_text('', encoding='utf-8')
    (package / 'operators.py').write_text('''from src.task.step.base import Step
from src.reader.base import Reader

class ReadNumbers(Reader):
    def read(self, path, dims, labels, **args):
        import numpy as np
        from src.core import Form
        data = np.array([float(value) for value in path.read_text().split()]).reshape(-1, 1)
        return Form(data, dims, {dims[0]: {str(i): i for i in range(len(data))}, dims[1]: {'value': 0}})

class Identity(Step):
    def run(self, ctx, inputs):
        self.values = {key: value for key, value in ctx.step_params.items() if not key.startswith('_')}
        ctx[ctx.step_params['output']] = inputs[0]
    def export(self, ctx):
        return {'values': self.values}
''', encoding='utf-8')
    from operon_sdk.declarations import compile_declaration
    common = {'protocol_version': 3, 'version': '1.0.0', 'title': 'Fixture',
              'parameters_schema': {'type': 'object', 'properties': {}, 'additionalProperties': False},
              'resources': {'memory_modes': ['full'], 'supports_cuda': False}}
    reader = {**deepcopy(common), 'id': 'OwnedReader', 'kind': 'reader',
        'entry_point': 'owned_native_provider.operators:ReadNumbers', 'extensions': ['.owned'],
        'contracts': {'version': 1, 'inputs': [], 'output': {'kind': 'form', 'ndim': 2}}}
    operator = {**deepcopy(common), 'id': 'owned.identity', 'kind': 'operator',
        'entry_point': 'owned_native_provider.operators:Identity', 'inputs_arity': 1,
        'outputs': [], 'output_parameter': 'output',
        'contracts': {'version': 1, 'inputs': [{'kind': 'form'}], 'output': {'mode': 'passthrough', 'input': 0}},
        'parameters_schema': {'type': 'object', 'additionalProperties': False,
                              'properties': {'new_default': {'type': 'integer', 'default': 999}}}}
    descriptors = [compile_declaration(item, tmp_path) for item in (reader, operator)]
    for item in descriptors:
        item['distribution'] = 'owned-native-provider'
        item['implementation'] = {'package': 'owned-native-provider', 'version': '1.0.0',
                                  'code_sha': item['code_sha'], 'declaration_sha': item['declaration_sha']}
    from src.web.operator_catalog import catalog_from_descriptors
    catalog = catalog_from_descriptors(descriptors)
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.setenv('OPERON_BASE_PATHS', json.dumps([str(tmp_path)]))
    yield tmp_path, catalog
    STEPS.clear()
    READERS.clear()
    STEPS.factories.update(registry_before[0])
    STEPS.loaded.update(registry_before[1])
    STEPS.declarations.update(registry_before[2])
    READERS.extend(registry_before[3])
    for name in list(sys.modules):
        if name == 'owned_native_provider' or name.startswith('owned_native_provider.'):
            sys.modules.pop(name, None)


def graph(root):
    return {'schema_version': 2, 'name': 'owned native fixture', 'base_dir': str(root),
        'memory': {'enabled': False},
        'nodes': [
            {'id': 'input', 'kind': 'source', 'position': {'x': 0, 'y': 0},
             'source': {'path': str(root / 'numbers.owned'), 'reader': 'OwnedReader'}},
            {'id': 'transform', 'kind': 'operator', 'operator': 'owned.identity',
             'position': {'x': 1, 'y': 0}, 'params': {'output': 'result'}},
        ], 'edges': [{'id': 'edge', 'source': 'input', 'target': 'transform'}]}


def snapshot(plan):
    unit = plan.units[0]
    return NativeRuntimeSnapshot(descriptors=unit.payload['native_descriptors'],
        implementations=unit.payload['native_implementations'],
        audit_descriptors=plan.diagnostics['native_descriptor_audit'])


def test_frozen_script_plan_uses_json_wire_validation_without_mutation():
    from pathlib import Path
    from operon.workflow_spec import load_workflow
    root = Path(__file__).resolve().parents[1] / 'examples/workflows/script_pipeline'
    plan = WorkflowCompiler().compile(load_workflow(root / 'workflow.yaml'), None, {}, root=root)
    unit = plan.units[0]
    before = plan.model_dump(mode='json')
    script = unit.payload['task_manifest']['steps'][0]['params']['script']
    assert isinstance(script['dependencies'], tuple)
    validate_native_descriptors(unit.payload['native_descriptors'], plan.implementations,
                                unit.payload['task_manifest'])
    assert plan.model_dump(mode='json') == before
    from operon.script_operators import validate_script
    with pytest.raises(ValueError, match='dependencies must be a list'):
        validate_script({**before['units'][0]['payload']['task_manifest']['steps'][0]['params']['script'],
                         'dependencies': 'numpy'})


def test_compiler_snapshot_is_lazy_and_default_only_drift_keeps_plan_identity(provider):
    root, catalog = provider
    compiler = WorkflowCompiler()
    first = compiler.compile(graph(root), None, catalog, root=root, freeze_defaults=False)
    assert 'owned_native_provider.operators' not in sys.modules
    changed = deepcopy(catalog)
    changed['operators'][0]['parameters_schema']['properties']['new_default']['default'] = 17
    changed['operators'][0]['title'] = 'Changed title'
    changed['operators'][0]['runtime_defaults']['new_default'] = 17
    from operon_sdk.declarations import declaration_hash
    changed['operators'][0]['declaration_sha'] = declaration_hash(changed['operators'][0])
    changed['operators'][0]['implementation']['declaration_sha'] = changed['operators'][0]['declaration_sha']
    second = compiler.compile(graph(root), None, changed, root=root, freeze_defaults=False)
    assert first.plan_id == second.plan_id
    assert first.diagnostics != second.diagnostics
    selected = first.units[0].payload['native_descriptors']
    assert {item['id'] for item in selected} == {'OwnedReader', 'owned.identity'}
    assert all('declaration_sha' not in item for item in selected)
    assert 'default' not in selected[1]['parameters_schema']['properties']['new_default']


def test_bootstrap_loads_only_selected_classes_and_never_injects_schema_defaults(provider, monkeypatch):
    root, catalog = provider
    plan = WorkflowCompiler().compile(graph(root), None, catalog, root=root, freeze_defaults=False)
    import operon.packages
    monkeypatch.setattr(operon.packages, 'bundled_entries', lambda *args: pytest.fail('Unexpected library discovery'))
    register_native_runtime(snapshot(plan), plan.units[0].payload['task_manifest'], code_roots=[str(root)])
    from src.task.step import STEPS
    from src.reader import READERS
    assert list(STEPS) == ['owned.identity']
    assert len(READERS) == 1
    assert 'owned_native_provider.operators' not in sys.modules
    cls = STEPS['owned.identity']
    assert cls.__name__ == 'Identity'
    assert 'default' not in cls.parameters_schema['properties']['new_default']
    from operon_sdk.protocol import validate_parameters
    assert validate_parameters(cls.parameters_schema, {}) == {}
    assert READERS[0]._instance is None


def test_native_worker_runs_owned_reader_and_operator_through_context_bridge(provider):
    root, catalog = provider
    (root / 'numbers.owned').write_text('1 2 3', encoding='utf-8')
    plan = WorkflowCompiler().compile(graph(root), None, catalog, root=root, freeze_defaults=False)
    unit = plan.units[0]
    payload = unit.model_dump(mode='json')['payload']
    payload['native_descriptor_audit'] = plan.model_dump(mode='json')['diagnostics']['native_descriptor_audit']
    context = InvocationContext(root / 'attempt', 'attempt-1', 'run-1', unit.unit_id, 1, payload,
                                memory_bytes=0, threads=1)
    prepared = NativeInvocationAdapter().prepare(unit.invocation, context)
    from operon.execution.worker_main import main
    assert main(['--invocation', str(context.attempt_root / 'invocation.json')]) == 0
    output = json.loads((context.attempt_root / 'output_manifest.json').read_text(encoding='utf-8'))
    assert output['status'] == 'complete'
    summary = json.loads((prepared.output_dir / 'run_summary.json').read_text(encoding='utf-8'))
    assert summary['steps'][0]['name'] == 'owned.identity'
    exported = json.loads((prepared.output_dir / summary['steps'][0]['export_path']).read_text(encoding='utf-8'))
    assert exported['values'] == {'output': 'result'}


def test_bootstrap_rejects_code_identity_audit_structural_drift_and_missing_environment(provider):
    root, catalog = provider
    plan = WorkflowCompiler().compile(graph(root), None, catalog, root=root, freeze_defaults=False)
    manifest = plan.units[0].payload['task_manifest']
    value = snapshot(plan).model_dump(mode='json')
    value['descriptors'][1]['implementation']['code_sha'] = '0' * 64
    with pytest.raises(ContractError, match='changed after compilation'):
        register_native_runtime(value, manifest, code_roots=[str(root)])
    value = snapshot(plan).model_dump(mode='json')
    value['audit_descriptors']['owned.identity']['parameters_schema']['additionalProperties'] = True
    with pytest.raises(ContractError, match='audit descriptors'):
        register_native_runtime(value, manifest, code_roots=[str(root)])
    descriptors = [deepcopy(item) for item in plan.units[0].payload['native_descriptors']]
    descriptors[1]['resources']['environment'] = 'mutable-env'
    with pytest.raises(ContractError) as caught:
        validate_native_descriptors(descriptors, plan.implementations, manifest)
    assert caught.value.code == 'unsupported_boundary'
    validate_native_descriptors(descriptors, plan.implementations, manifest, environment_requirement_digest='a' * 64)


def test_invocation_snapshot_hash_and_contained_path_are_checked(provider):
    root, catalog = provider
    plan = WorkflowCompiler().compile(graph(root), None, catalog, root=root, freeze_defaults=False)
    unit = plan.units[0]
    payload = unit.model_dump(mode='json')['payload']
    payload['native_descriptor_audit'] = plan.model_dump(mode='json')['diagnostics']['native_descriptor_audit']
    context = InvocationContext(root / 'attempt', 'a', 'r', unit.unit_id, 1, payload, memory_bytes=0, threads=1)
    NativeInvocationAdapter().prepare(unit.invocation, context)
    from operon.execution.worker_main import WorkerInvocation, read_native_runtime
    invocation = WorkerInvocation.model_validate_json((context.attempt_root / 'invocation.json').read_text(encoding='utf-8'))
    assert read_native_runtime(context.attempt_root, invocation)['descriptors']
    (context.attempt_root / 'native-runtime.json').write_text('{}', encoding='utf-8')
    with pytest.raises(ValueError, match='hash differs'):
        read_native_runtime(context.attempt_root, invocation)
    wire = invocation.model_dump(mode='json')
    wire['native_runtime_ref'] = '../outside.json'
    with pytest.raises(ValueError):
        WorkerInvocation.model_validate(wire)


def test_execution_schema_preserves_properties_and_const_named_default():
    schema = {'type': 'object', 'properties': {'default': {'type': 'string', 'default': 'x'},
        'record': {'const': {'default': 'literal'}, 'title': 'Ignored'}}, 'required': ['default']}
    projected = execution_schema(schema)
    assert projected['properties']['default'] == {'type': 'string'}
    assert projected['properties']['record']['const'] == {'default': 'literal'}
    assert projected['required'] == ['default']


def authoring(root):
    return {'format': 'operon.workflow', 'schema_version': 2, 'params_file': 'parameters.json',
        'processes': {'Identity': {'runner': 'native', 'operator': 'owned.identity', 'environment': 'locked',
                                  'input': {'data': {'type': 'form'}}, 'output': {'result': {'type': 'form'}}}},
        'workflow': {'name': 'native locked environment', 'defaults': {'executor': 'local',
                     'resources': {'memory': '32MiB', 'cpus': 2}},
            'take': {'input': {'type': 'form', 'source': {'reader': 'OwnedReader', 'path': str(root / 'numbers.owned')}}},
            'steps': {'transform': {'process': 'Identity', 'in': {'data': {'ref': 'workflow.input'}}}},
            'emit': {'result': {'ref': 'transform.result'}}, 'memory': {'enabled': False}}}


def test_native_authoring_binds_one_exact_environment_and_rejects_unsplit_groups(provider):
    root, catalog = provider
    requirement = EnvironmentRequirement(target=TargetSpec(os='linux', arch='x86_64'), runtime='cpython-3.11',
        dependency_lock={'artifact_hashes': ['a' * 64]})
    environments = {'locked': {'requirement': requirement.model_dump(mode='json'), 'executable': 'runtime/bin/python'}}
    raw = authoring(root)
    value = normalize(raw, root, initial=True, parameters={'params': {}}, environments=environments, catalog=catalog)
    plan = value.compile(catalog)
    assert plan.units[0].invocation.environment_ref == 'locked'
    assert plan.execution_policy['environment_refs'] == {'locked': sha256_hex(requirement)}
    assert plan.environment_requirements == (requirement,)
    assert plan.units[0].resource_request.cpu_threads == 2
    assert plan.units[0].resource_request.process_reservation_bytes == 32 * 1024**2
    assert plan.units[0].resource_request.managed_budget_bytes == 0
    assert plan.units[0].payload['native_environment_requirement_digest'] == sha256_hex(requirement)
    raw['processes']['Second'] = {**deepcopy(raw['processes']['Identity']), 'environment': 'other'}
    raw['workflow']['steps']['second'] = {'process': 'Second', 'in': {'data': {'ref': 'transform.result'}}}
    other = requirement.model_copy(update={'dependency_lock': {'artifact_hashes': ['b' * 64]}})
    environments['other'] = {'requirement': other.model_dump(mode='json'), 'executable': 'runtime/bin/python'}
    value = normalize(raw, root, initial=True, parameters={'params': {}}, environments=environments, catalog=catalog)
    with pytest.raises(ContractError, match='split at explicit materialized boundaries'):
        value.compile(catalog)
