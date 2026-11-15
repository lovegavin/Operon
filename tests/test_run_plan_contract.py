"""K01 contract, identity, schema and compiler tests."""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys

import numpy as np
import pytest
from pydantic import ValidationError

from operon.contracts import (ContractError, FrozenParameters, ResourceRequestSpec, RunPlan,
                              WorkflowSpec, canonical_json, domain_digest, sha256_hex)
from operon.contracts.schemas import PUBLIC_MODELS, schemas
from operon.planning import WorkflowCompiler, validate_run_plan, workflow_revision
from operon.planning.legacy import LegacyPlanAdapter
from src.web.operator_catalog import catalog_from_descriptors
from src.web.service import JobService, Settings

ROOT = Path(__file__).resolve().parents[1]
CANONICAL_VECTOR = {'text': 'héllo', 'null': None, 'ints': [1, -2], 'float': 1.5,
                    'order': {'b': 2, 'a': 1}}


def simple_graph(root: Path, *, positions=(0, 1)) -> dict:
    return {
        'schema_version': 2, 'name': 'contract', 'base_dir': str(root),
        'memory': {'enabled': True, 'auto_spill': True, 'budget_mb': 32, 'process_limit_mb': 512},
        'nodes': [
            {'id': 'input', 'kind': 'source', 'position': {'x': positions[0], 'y': 0},
             'source': {'path': 'input.npy', 'dims': ['sample', 'feature'],
                        'labels': {'sample': 'auto', 'feature': 'builtin'}, 'reader': 'NpyReader'}},
            {'id': 'pca', 'kind': 'operator', 'operator': 'pca',
             'position': {'x': positions[1], 'y': 0},
             'params': {'dim': 'feature', 'n_components': 2, 'output': 'pcs'}},
        ],
        'edges': [{'id': 'e', 'source': 'input', 'target': 'pca',
                   'targetHandle': 'in-0', 'sourceHandle': 'out'}],
    }


@pytest.fixture()
def service(tmp_path):
    np.save(tmp_path / 'input.npy', np.arange(40, dtype=np.float32).reshape(10, 4))
    value = JobService(Settings(tmp_path, tmp_path / '.studio', tmp_path / 'ui',
                                 testing=True, code_root=ROOT), catalog_from_descriptors())
    try:
        yield value
    finally:
        value.shutdown()


def test_canonical_json_and_domain_vectors_are_frozen():
    assert canonical_json(CANONICAL_VECTOR) == (
        '{"float":1.5,"ints":[1,-2],"null":null,"order":{"a":1,"b":2},"text":"héllo"}')
    assert sha256_hex(CANONICAL_VECTOR) == 'c17441941519cee045183521e908ae9aea8ac3f1e814d776a9d144ef1a2d5ed9'
    assert domain_digest('operon:run-plan:v1', CANONICAL_VECTOR) == (
        'cf65486c6bdfbdaca612a04427de998b6c3c4b3274d00dbd3ad406f0876bbe5d')
    assert canonical_json({'a': ('x', 2)}) == '{"a":["x",2]}'
    with pytest.raises(ContractError):
        canonical_json({'x': float('nan')})


def test_code_identity_excludes_declarations_but_retains_executable_content():
    from operon.planning.identity import implementation_digest
    record = {'id': 'pca', 'kind': 'operator', 'origin': 'bundled',
              'implementation': {'version': '1', 'package': 'core', 'code_sha': 'a' * 64,
                                 'declaration_sha': 'b' * 64, 'sha256': 'c' * 64}}
    before = implementation_digest(record)
    record['implementation'].update(declaration_sha='d' * 64, sha256='e' * 64)
    assert implementation_digest(record) == before
    record['implementation']['code_sha'] = 'f' * 64
    assert implementation_digest(record) != before


def test_web_compiler_is_the_same_planning_implementation():
    import src.web.graph as old
    from operon.planning import graph_compiler
    assert old is graph_compiler


def test_strict_resources_and_unknown_fields():
    with pytest.raises(ValidationError):
        ResourceRequestSpec(managed_budget_bytes=True)
    with pytest.raises(ValidationError):
        ResourceRequestSpec(managed_budget_bytes=1, process_reservation_bytes=0)
    with pytest.raises(ValidationError):
        WorkflowSpec.model_validate({'nodes': [], 'unknown': 1})
    with pytest.raises(ValidationError):
        WorkflowSpec.model_validate({'nodes': []})


def test_public_contracts_do_not_coerce_or_expose_mutable_values(tmp_path):
    from operon.contracts.run_plan import CacheContract, RetryPolicy, StorageRef, InvocationSpec, CodeRef
    for model, fields in ((CacheContract, {'eligible': 'false'}),
                          (RetryPolicy, {'maximum_attempts': True}),
                          (RetryPolicy, {'maximum_attempts': '2'})):
        with pytest.raises(ValidationError):
            model.model_validate(fields)
    for path in ('../outside', '/absolute', 'C:\\outside', 'a/../../outside'):
        with pytest.raises(ValidationError):
            StorageRef(storage_id='workspace', relative_path=path)
    with pytest.raises(ValidationError):
        InvocationSpec(kind='native', entrypoint='worker', code_ref=CodeRef(kind='workflow'),
                       output_manifest='../outside.json')
    spec = WorkflowSpec.from_graph(simple_graph(tmp_path))
    with pytest.raises(TypeError):
        spec.nodes[1].params['n_components'] = 99
    with pytest.raises(ContractError):
        canonical_json({1: 'integer-key', '1': 'text-key'})
    with pytest.raises(ContractError):
        canonical_json({'not_json': {1, 2}})


def test_execution_payload_is_bound_to_plan_identity(service, tmp_path):
    plan = WorkflowCompiler(LegacyPlanAdapter()).compile(
        WorkflowSpec.from_graph(simple_graph(tmp_path)), None, service.catalog, root=tmp_path)
    value = plan.model_dump(mode='json')
    value['units'][0]['payload']['task_manifest']['steps'][0]['params']['n_components'] = 1
    changed = RunPlan.model_validate(value)
    with pytest.raises(ContractError, match='identity'):
        validate_run_plan(changed)
    from operon.planning.identity import plan_identity
    assert plan_identity(plan) == plan.plan_id


def test_nested_route_plan_has_complete_implementation_closure(service, tmp_path):
    from src.web.models import Graph
    from src.web.routes import prepare_interface
    inner = prepare_interface(Graph.model_validate(simple_graph(tmp_path)), service.catalog, tmp_path)
    outer = simple_graph(tmp_path)
    outer['nodes'][1] = {'id': 'pca', 'kind': 'route', 'position': {'x': 1, 'y': 0},
                        'route': {'id': 'route_123456abcdef', 'version': 1, 'name': 'inner',
                                  'graph': inner.model_dump(mode='json')}}
    plan = WorkflowCompiler(LegacyPlanAdapter()).compile(
        WorkflowSpec.from_graph(outer), None, service.catalog, root=tmp_path)
    assert 'pca' in plan.implementations
    assert 'NpyReader' in plan.implementations


def test_frozen_values_and_ui_coordinates_do_not_change_identity(tmp_path):
    one = WorkflowSpec.from_graph(simple_graph(tmp_path, positions=(0, 1)))
    two = WorkflowSpec.from_graph(simple_graph(tmp_path / 'elsewhere', positions=(900, 1000)))
    assert workflow_revision(one) == workflow_revision(two)
    values = FrozenParameters.from_values({
        'format': 'operon.workflow-parameters', 'schema_version': 1,
        'steps': {'pca': {'params': {'dim': 'feature', 'n_components': 0,
                                     'output': 'pcs', 'flag': False, 'optional': None}}},
        'sources': {'input': {'args': {'allow_pickle': False}}}})
    frozen = one.apply_values(values)
    assert frozen.nodes[1].params == {'dim': 'feature', 'n_components': 0, 'output': 'pcs',
                                               'flag': False, 'optional': None}
    assert frozen.nodes[0].source.args == {'allow_pickle': False}
    assert workflow_revision(frozen) != workflow_revision(one)


def test_native_compiler_is_metadata_only_and_deterministic(service, tmp_path):
    catalog = deepcopy(service.catalog)
    next(d for d in catalog['operators'] if d['id'] == 'pca')['dependencies'] = ['numpy>=1']
    compiler = WorkflowCompiler()
    spec = WorkflowSpec.from_graph(simple_graph(tmp_path))
    first = compiler.compile(spec, FrozenParameters(), catalog, root=tmp_path)
    second = compiler.compile(spec, FrozenParameters(), catalog, root=tmp_path)
    assert first.plan_id == second.plan_id
    assert first.units[0].payload['task_manifest']['steps'][0]['params']['n_components'] == 2
    assert first.workflow_revision == workflow_revision(WorkflowSpec.from_graph(first.units[0].payload['graph']))
    assert first.units[0].resource_request.managed_budget_bytes == 32 * 1024 * 1024
    assert first.units[0].resource_request.process_reservation_bytes == 512 * 1024 * 1024
    assert first.model_dump(mode='json')['environment_requirements'][0]['dependency_lock']['requirements'] == ['numpy>=1']
    assert first.compute_id() == first.plan_id
    assert validate_run_plan(first) == first


def test_legacy_adapter_preserves_frozen_values_and_deterministic_plan(service, tmp_path):
    graph = simple_graph(tmp_path)
    values = FrozenParameters.from_values({
        'format': 'operon.workflow-parameters', 'schema_version': 1,
        'steps': {'pca': {'params': {'dim': 'feature', 'n_components': 1, 'output': 'pcs'}}}})
    compiler = WorkflowCompiler(LegacyPlanAdapter())
    first = compiler.compile(WorkflowSpec.from_graph(graph), values, service.catalog, root=tmp_path)
    second = compiler.compile(WorkflowSpec.from_graph(graph), values, service.catalog, root=tmp_path)
    assert first.plan_id == second.plan_id
    task = first.units[0].payload['task_manifest']
    assert task['steps'][0]['params']['n_components'] == 1
    assert task['steps'][0]['params']['dim'] == 'feature'
    assert first.parameters_digest == second.parameters_digest
    assert first.model_dump(mode='json')['environment_requirements'][0]['dependency_lock']['requirements'] == []


def test_nested_route_uses_existing_expansion_through_legacy_adapter(service, tmp_path):
    from src.web.models import Graph, GraphNode
    from src.web.routes import prepare_interface
    graph = simple_graph(tmp_path)
    catalog = service.catalog
    inner = Graph.model_validate({
        'name': 'inner', 'base_dir': str(tmp_path),
        'nodes': [graph['nodes'][0], graph['nodes'][1]],
        'edges': [graph['edges'][0]],
    })
    inner = prepare_interface(inner, catalog, tmp_path)
    route = GraphNode.model_validate({
        'id': 'route_pca', 'kind': 'route', 'title': 'inner',
        'position': {'x': 1, 'y': 0},
        'route': {'id': 'route_123456abcdef', 'version': 1, 'name': 'inner',
                  'graph': inner.model_dump(mode='json')}})
    outer = Graph.model_validate({
        'schema_version': 2, 'name': 'outer', 'base_dir': str(tmp_path),
        'memory': {'enabled': True}, 'nodes': [graph['nodes'][0], route],
        'edges': [{'id': 'e', 'source': 'input', 'target': 'route_pca',
                   'targetHandle': 'in-0', 'sourceHandle': 'out'}]})
    plan = WorkflowCompiler(LegacyPlanAdapter()).compile(
        WorkflowSpec.from_graph(outer), FrozenParameters(), catalog, root=tmp_path)
    assert len(plan.units[0].payload['task_manifest']['steps']) == 1
    assert plan.units[0].payload['task_manifest']['steps'][0]['name'] == 'pca'
    assert plan.workflow_revision


def test_generated_schemas_match_public_models():
    generated = schemas()
    assert set(generated) == set(PUBLIC_MODELS)
    for name, model in PUBLIC_MODELS.items():
        assert generated[name] == model.model_json_schema()
        path = ROOT / 'operon' / 'contracts' / 'schemas' / f'{name}.json'
        assert json.loads(path.read_text(encoding='utf-8')) == generated[name]


def test_planning_import_boundary_has_no_web_or_scientific_import():
    code = ("import sys, operon.planning, operon.contracts; "
            "bad=[name for name in sys.modules if name.startswith(('src.web','src.task.step.steps','matplotlib','torch','paramiko','fastapi'))]; "
            "assert not bad, bad; print('ok')")
    completed = subprocess.run([sys.executable, '-c', code], cwd=ROOT, capture_output=True, text=True)
    assert completed.returncode == 0, completed.stderr



def test_legacy_projection_round_trips_durable_fields(tmp_path):
    value = simple_graph(tmp_path)
    value['plugin_lock'] = {'pca': {'version': '1.0.0', 'code_sha': 'a' * 64}}
    spec = WorkflowSpec.from_graph(value)
    projected = spec.to_legacy_dict()
    assert projected['nodes'][0]['source']['dims'] == ['sample', 'feature']
    assert projected['nodes'][0]['position'] == {'x': 0, 'y': 0}
    assert projected['edges'][0]['sourceHandle'] == 'out'
    assert projected['memory']['budget_mb'] == 32
    assert projected['plugin_lock'] == value['plugin_lock']
    assert WorkflowSpec.from_graph(projected).to_legacy_dict() == projected


def test_shared_compiler_rejects_duplicate_ports(service, tmp_path):
    value = simple_graph(tmp_path)
    value['edges'].append({'id': 'back', 'source': 'pca', 'target': 'pca',
                           'targetHandle': 'in-0', 'sourceHandle': 'out'})
    with pytest.raises(ContractError, match='输入口只能连接一次|输入|cycle'):
        WorkflowCompiler().compile(WorkflowSpec.from_graph(value), FrozenParameters(), service.catalog,
                                   root=tmp_path)


def test_default_and_application_adapter_share_converters_and_auto_reader(tmp_path):
    from test_format_adaptation import graph, catalog
    from src.web.graph import compile_graph
    value, metadata = graph(), catalog()
    manifest, ids = compile_graph(value, metadata, tmp_path)
    spec = WorkflowSpec.from_graph(value)
    direct = WorkflowCompiler().compile(spec, None, metadata, root=tmp_path)
    adapter = WorkflowCompiler(LegacyPlanAdapter()).compile(spec, None, metadata, root=tmp_path)
    assert direct == adapter
    assert direct.model_dump(mode='json')['units'][0]['payload']['task_manifest'] == manifest
    assert direct.units[0].payload['step_ids'] == tuple(ids)
    assert 'TestReader' in direct.implementations
    assert direct.implementations['converter:matrix.npy.write']['implementation']['code_sha']


def test_compiled_script_dependencies_and_code_are_pinned(tmp_path):
    from operon.script_operators import inspect_script
    path = tmp_path / 'script.py'
    path.write_text('# /// script\n# dependencies = ["numpy==2.0.0"]\n# ///\n'
                    '# output: result file.txt\nraise RuntimeError("must not import")\n')
    graph = {'nodes': [{'id': 'script', 'kind': 'script', 'script': inspect_script(path),
                        'position': {'x': 0, 'y': 0}, 'params': {}}], 'edges': []}
    plan = WorkflowCompiler().compile(graph, None, {'operators': [], 'readers': []}, root=tmp_path)
    descriptor = next(iter(plan.implementations.values()))
    assert descriptor['implementation']['code_sha'] == graph['nodes'][0]['script']['code_sha']
    assert plan.environment_requirements[0].dependency_lock['requirements'] == ('numpy==2.0.0',)


def test_defaults_freeze_once_and_new_defaults_do_not_rewrite_plan(service, tmp_path):
    from operon.planning.legacy import freeze_spec
    from operon.planning.resolver import as_catalog
    value = simple_graph(tmp_path)
    del value['nodes'][1]['params']['n_components']
    metadata = deepcopy(service.catalog)
    schema = next(d for d in metadata['operators'] if d['id'] == 'pca')['parameters_schema']
    schema['properties']['n_components']['default'] = 2
    frozen = freeze_spec(WorkflowSpec.from_graph(value), as_catalog(metadata), tmp_path)
    first = WorkflowCompiler().compile(frozen, None, metadata, root=tmp_path)
    schema['properties']['n_components']['default'] = 3
    second = WorkflowCompiler().compile(frozen, None, metadata, root=tmp_path)
    assert first.identity_payload() == second.identity_payload()
    assert first.plan_id == second.plan_id
    assert first.units == second.units
    assert first.diagnostics['native_descriptor_audit']['pca']['parameters_schema']['properties']['n_components']['default'] == 2
    assert second.diagnostics['native_descriptor_audit']['pca']['parameters_schema']['properties']['n_components']['default'] == 3
    assert second.units[0].payload['task_manifest']['steps'][0]['params']['n_components'] == 2


def test_application_saved_values_do_not_refill_missing_current_defaults(service, tmp_path):
    from operon.application import Application
    app = Application.__new__(Application)
    app.service = service
    metadata = deepcopy(service.catalog)
    app.catalog_for = lambda graph: metadata
    app.prepare = lambda graph: pytest.fail('Saved snapshots must not re-enter initial default preparation')
    frozen = FrozenParameters(steps={'pca': {'dim': 'feature', 'output': 'pcs'}})
    value = simple_graph(tmp_path)
    first = app.compile_plan(value, frozen)
    schema = next(item for item in metadata['operators'] if item['id'] == 'pca')['parameters_schema']
    schema['properties']['n_components']['default'] = 3
    second = app.compile_plan(value, frozen)
    assert first.plan_id == second.plan_id
    assert first.units[0].payload['task_manifest']['steps'][0]['params'] == {'dim': 'feature', 'output': 'pcs'}
    assert value['nodes'][1]['params']['n_components'] == 2


def test_source_bindings_preserve_subdirectories_and_distinguish_external_roots(tmp_path):
    from operon.planning.compiler import _storage_bindings
    value = simple_graph(tmp_path)
    source = value['nodes'][0]
    source['source']['path'] = 'nested/input.npy'
    second = deepcopy(source)
    second['id'] = 'external-a'
    second['source']['path'] = str(tmp_path.parent / 'outside-a' / 'input.npy')
    third = deepcopy(second)
    third['id'] = 'external-b'
    third['source']['path'] = str(tmp_path.parent / 'outside-b' / 'input.npy')
    value['nodes'].extend([second, third])
    bindings = _storage_bindings(WorkflowSpec.from_graph(value), tmp_path)
    assert bindings[0].storage_id == 'workflow'
    assert bindings[0].relative_path == 'nested/input.npy'
    assert bindings[1].storage_id == 'source:external-a'
    assert bindings[2].storage_id == 'source:external-b'
    assert bindings[1].relative_path == bindings[2].relative_path == 'input.npy'


def test_graph_expansion_limit_is_checked_before_model_validation():
    with pytest.raises(ContractError) as error:
        WorkflowCompiler().compile({'nodes': [{}] * 4097, 'edges': []}, None, {})
    assert error.value.code == 'payload_too_large'
    for nodes in (None, 'not-an-array', {}):
        with pytest.raises(ContractError) as error:
            WorkflowCompiler().compile({'nodes': nodes, 'edges': []}, None, {})
        assert error.value.code == 'invalid_workflow'


def test_actual_compilation_does_not_import_scientific_implementations(service, tmp_path):
    payload = tmp_path / 'compile.json'
    payload.write_text(json.dumps({'graph': simple_graph(tmp_path), 'catalog': service.catalog}), encoding='utf-8')
    code = '''
import importlib.abc, json, sys
from pathlib import Path
class BlockScience(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, *args):
        if fullname.split('.')[0] in {'numpy', 'scipy', 'pandas', 'sklearn', 'matplotlib', 'torch'}:
            raise AssertionError('Planning imported ' + fullname)
        if fullname == 'src.web' or fullname.startswith(('src.web.', 'src.reader.readers.', 'src.task.step.steps.')):
            raise AssertionError('Planning imported operator ' + fullname)
sys.meta_path.insert(0, BlockScience())
from operon.planning import WorkflowCompiler
path = Path(sys.argv[1]); value = json.loads(path.read_text(encoding='utf-8'))
plan = WorkflowCompiler().compile(value['graph'], None, value['catalog'], root=path.parent)
assert plan.units and plan.implementations
print(plan.plan_id)
'''
    completed = subprocess.run([sys.executable, '-c', code, str(payload)], cwd=ROOT,
                               capture_output=True, text=True, timeout=30)
    assert completed.returncode == 0, completed.stderr
