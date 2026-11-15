"""Saved selections become authorized execution bindings; no data relay."""
from copy import deepcopy
import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from operon.contracts.base import ContractError
from operon.contracts.storage import StorageInputRef, storage_input_path
from operon.contracts.workflow import WorkflowSpec
from operon.planning.graph_models import Graph, Source
from operon.storage import LocalStorage, MountMap, SFTPStorage, StorageError, StorageService
from operon.storage.configuration import PROFILE_OWNER
from operon.storage.inputs import (StorageInputBindings, prepare_plan_inputs, resolve_input,
                                   selected_target, verify_execution_inputs)


def selected(storage, path='input.csv', storage_id='data'):
    ref = storage.stat({'storage_id': storage_id, 'relative_path': path}, principal=PROFILE_OWNER).ref
    return StorageInputRef.model_validate(ref.model_dump())


def graph_for(ref):
    return Graph.model_validate({'name': 'Selected input', 'base_dir': '.', 'nodes': [
        {'id': 'input', 'kind': 'source', 'position': {'x': 0, 'y': 0}, 'source': {
            'path': storage_input_path(ref), 'storage_ref': ref.model_dump(mode='json'),
            'dims': ['sample', 'feature'], 'labels': {'sample': 'auto', 'feature': 'builtin'}}},
        {'id': 'summary', 'kind': 'operator', 'operator': 'describe', 'position': {'x': 1, 'y': 0}}],
        'edges': [{'id': 'edge', 'source': 'input', 'target': 'summary'}]})


@pytest.fixture
def bound_app(tmp_path):
    content = tmp_path / 'files'; content.mkdir()
    (content / 'input.csv').write_text('a,b\n1,2\n3,4\n', encoding='utf-8')
    mounts = MountMap(); mounts.register('data', LocalStorage(content), principals=[PROFILE_OWNER])
    storage = StorageService(mounts)
    app = SimpleNamespace(storage=storage, service=SimpleNamespace(root=tmp_path,
        settings=SimpleNamespace(input_roots=None), remotes=None))
    app.storage_inputs = StorageInputBindings(app)
    try:
        yield app
    finally:
        storage.close()


def test_versioned_selection_roundtrips_without_absolute_paths_and_legacy_shape_unchanged(bound_app):
    ref = selected(bound_app.storage)
    graph = graph_for(ref)
    spec = WorkflowSpec.from_graph(graph)
    assert spec.nodes[0].source.storage_ref == ref
    assert Graph.model_validate(spec.to_legacy_dict()).nodes[0].source.storage_ref == ref
    assert str(bound_app.service.root) not in graph.model_dump_json()
    legacy = Source(path='input.csv').model_dump(mode='json')
    assert set(legacy) == {'reader', 'path', 'dims', 'labels', 'args', 'location'}
    raw = graph.model_dump(mode='json'); raw['nodes'][0]['source'].pop('storage_ref')
    raw['nodes'][0]['source']['path'] = 'input.csv'
    assert 'storage_ref' not in WorkflowSpec.from_graph(raw).nodes[0].source.model_dump(mode='json')


@pytest.mark.parametrize('changed', [{'schema_version': 2}, {'schema_version': True}, {'version': None},
    {'relative_path': '../escape'}, {'relative_path': 'folder\\input.csv'}, {'relative_path': './input.csv'},
    {'relative_path': 'file:stream'}, {'credential': 'must-not-persist'}])
def test_saved_selection_is_strict(bound_app, changed):
    with pytest.raises(ValidationError):
        StorageInputRef.model_validate({**selected(bound_app.storage).model_dump(), **changed})


def test_cannot_replace_uri_with_absolute_path_or_override_mount_location(bound_app):
    raw = graph_for(selected(bound_app.storage)).model_dump(mode='json')
    for fields in ({'path': str(bound_app.service.root / 'files/input.csv')},
                   {'location': {'kind': 'local'}}):
        item = deepcopy(raw); item['nodes'][0]['source'].update(fields)
        with pytest.raises(ValidationError):
            Graph.model_validate(item)


def test_binding_preserves_saved_selection_and_metadata_audit_rechecks_at_worker_start(bound_app):
    graph = graph_for(selected(bound_app.storage))
    before = graph.model_dump(mode='json')
    bound = bound_app.storage_inputs.bind(graph)
    assert bound.nodes[0].source.storage_ref is None
    path = bound.nodes[0].source.path
    assert path == str(bound_app.service.root / 'files/input.csv')
    assert graph.model_dump(mode='json') == before
    manifest = {'sources': {'input': {'path': path}}, 'runtime': bound.runtime}
    verify_execution_inputs(manifest)
    relative = deepcopy(manifest)
    relative['sources']['input']['path'] = 'files/input.csv'
    verify_execution_inputs(relative, root=bound_app.service.root)
    Path(path).write_text('changed after queued submission', encoding='utf-8')
    with pytest.raises(StorageError) as caught:
        verify_execution_inputs(manifest)
    assert caught.value.code == 'storage_changed'
    with pytest.raises(StorageError, match='select the current version'):
        bound_app.storage_inputs.bind(graph)
    assert graph.model_dump(mode='json') == before


def test_grants_are_checked_even_in_metadata_only_prepare(bound_app):
    graph = graph_for(selected(bound_app.storage))
    bound_app.storage.mounts.register('data', LocalStorage(bound_app.service.root / 'files'), principals=['other'])
    with pytest.raises(StorageError) as caught:
        bound_app.storage_inputs.authorize(graph)
    assert caught.value.code == 'storage_forbidden'


def test_browse_grant_does_not_widen_execution_roots(bound_app, tmp_path):
    workspace = tmp_path / 'workspace'; workspace.mkdir()
    bound_app.service.root = workspace
    with pytest.raises(ValueError):
        bound_app.storage_inputs.bind(graph_for(selected(bound_app.storage)))


def test_auto_and_cross_host_routes_fail_before_any_copy(bound_app):
    graph = graph_for(selected(bound_app.storage))
    graph.runtime['execution'] = {'mode': 'auto'}
    with pytest.raises(StorageError, match='explicit single-host'):
        bound_app.storage_inputs.bind(graph)
    graph.runtime['execution'] = {'kind': 'ssh', 'profile_id': 'compute'}
    with pytest.raises(StorageError) as caught:
        bound_app.storage_inputs.bind(graph)
    assert caught.value.code == 'storage_route_unavailable'
    graph.nodes.append(graph.nodes[-1].model_copy(update={'id': 'other'}))
    graph.runtime['execution']['node_targets'] = {'other': {'kind': 'local'}}
    with pytest.raises(StorageError, match='across execution hosts'):
        selected_target(graph)


def test_storage_only_sftp_requires_explicit_exact_compute_mapping(tmp_path):
    from test_storage_service import FakeSFTP
    content = tmp_path / 'store'; content.mkdir(); (content / 'input.csv').write_bytes(b'a\n1\n')
    opened = []
    def connector():
        sftp = FakeSFTP(tmp_path); opened.append(sftp)
        return SimpleNamespace(sftp=sftp, close=sftp.close)
    backend = SFTPStorage('/store', connector)
    mounts = MountMap(); mounts.register('data', backend, principals=[PROFILE_OWNER])
    storage = StorageService(mounts)
    try:
        ref = selected(storage)
        target = {'kind': 'ssh', 'profile_id': 'compute'}
        profiles = lambda _: {'host': 'host.test', 'port': 22, 'username': 'account'}
        count = len(opened)
        with pytest.raises(StorageError, match='no explicit compute profile'):
            resolve_input(storage, ref, principal=PROFILE_OWNER, execution_target=target, remote_profile=profiles)
        assert len(opened) == count
        mounts.register('data', backend, principals=[PROFILE_OWNER], execution_profile_id='compute',
                        endpoint=('host.test', 22, 'different-account'))
        with pytest.raises(StorageError, match='does not match'):
            resolve_input(storage, ref, principal=PROFILE_OWNER, execution_target=target, remote_profile=profiles)
        assert len(opened) == count
        mounts.register('data', backend, principals=[PROFILE_OWNER], execution_profile_id='compute',
                        endpoint=('HOST.test', 22, 'account'))
        value = resolve_input(storage, ref, principal=PROFILE_OWNER, execution_target=target, remote_profile=profiles)
        assert value['path'] == '/store/input.csv' and value['location'] == target
        assert all(item.closed and not item.reads for item in opened)
    finally:
        storage.close()


def test_selected_content_digest_is_not_mistaken_for_verified_content(bound_app):
    ref = selected(bound_app.storage).model_copy(update={'digest': '1' * 64})
    with pytest.raises(StorageError) as caught:
        bound_app.storage_inputs.bind(graph_for(ref))
    assert caught.value.code == 'storage_digest_unverified'


def test_compiler_keeps_uri_identity_and_attempt_binds_confined_root(bound_app):
    from operon.planning import WorkflowCompiler, validate_run_plan
    from operon.execution.unit_executor import bind_paths
    from src.web.operator_catalog import catalog_from_descriptors
    from src.web.service import JobService, Settings
    graph = graph_for(selected(bound_app.storage))
    root = bound_app.service.root
    service = JobService(Settings(root, root / '.studio', root / 'ui', testing=True,
                                  code_root=Path(__file__).resolve().parents[1]), catalog_from_descriptors())
    try:
        plan = WorkflowCompiler().compile(WorkflowSpec.from_graph(graph), None, service.catalog, root=root)
    finally:
        service.shutdown()
    validate_run_plan(plan)
    assert plan.storage_bindings[0].storage_id == 'data'
    assert plan.storage_bindings[0].version == graph.nodes[0].source.storage_ref.version
    assert plan.units[0].input_bindings['input'] == graph.nodes[0].source.path
    bindings = {'data': str(bound_app.service.root / 'files')}
    payload = bind_paths(plan.units[0].model_dump(mode='json')['payload'], bindings,
                         encoded_refs={graph.nodes[0].source.path})
    assert 'storage_ref' not in payload['graph']['nodes'][0]['source']
    prepare_plan_inputs(plan, payload['task_manifest'], bindings)
    verify_execution_inputs(payload['task_manifest'])
    (bound_app.service.root / 'files/input.csv').unlink()
    with pytest.raises(StorageError):
        verify_execution_inputs(payload['task_manifest'])


def test_uri_encoding_roundtrip_does_not_turn_filename_percent_into_traversal(bound_app):
    from operon.execution.unit_executor import bind_paths
    ref = selected(bound_app.storage).model_copy(update={'relative_path': '资料/100% #.csv', 'storage_id': 'data #1'})
    uri = storage_input_path(ref)
    assert uri == 'storage://data%20%231/%E8%B5%84%E6%96%99/100%25%20%23.csv'
    resolved = bind_paths(uri, {'data #1': str(bound_app.service.root)}, encoded_refs={uri})
    assert resolved == str(bound_app.service.root / '资料/100% #.csv')
    assert bind_paths('storage://data/literal%20.csv', {'data': str(bound_app.service.root)}) == str(
        bound_app.service.root / 'literal%20.csv')


def test_application_validation_and_submission_pass_bound_graph_to_existing_service(bound_app, monkeypatch):
    from operon.application import Application, TaskService
    graph = graph_for(selected(bound_app.storage))
    app = bound_app
    app.executions = SimpleNamespace(applies=lambda _: False)
    calls = []
    app.service.validate_graph = lambda value, **_: calls.append(('validate', value)) or {'valid': True}
    from operon.readiness import ReadinessService, _digest, semantic_graph
    app.readiness = SimpleNamespace(validate=lambda value, *_, **__: {
        'status': 'ready', 'graph_digest': _digest(semantic_graph(value))}, require_ready=ReadinessService.require_ready)
    app.validate = lambda value, **kw: Application.validate(app, value, **kw)
    app._execution_binding = lambda value, checked: Application._execution_binding(app, value, checked)
    app.service.launch = lambda value: calls.append(('launch', value)) or {'id': 'existing-pool-job'}
    response = app.validate(graph, require_files=True)
    assert response['readiness']['bound_graph_digest'] != response['readiness']['graph_digest']
    assert response['graph']['nodes'][0]['source']['storage_ref']['version'] == selected(app.storage).version
    assert TaskService(app)._launch(graph) == {'id': 'existing-pool-job'}
    assert [kind for kind, _ in calls] == ['validate', 'validate', 'launch']
    assert all(value.nodes[0].source.storage_ref is None for _, value in calls)
    assert all(value.nodes[0].source.path == str(app.service.root / 'files/input.csv') for _, value in calls)
    changed = graph.model_copy(deep=True); changed.nodes[1].params['changed'] = True
    with pytest.raises(ValueError, match='changed after'):
        app._execution_binding(changed, response)
    (app.service.root / 'files/input.csv').write_text('changed after preflight', encoding='utf-8')
    with pytest.raises(StorageError) as caught:
        app._execution_binding(graph, response)
    assert caught.value.code == 'storage_changed'


def test_runplan_mount_binding_cannot_substitute_another_authorized_path(bound_app):
    from operon.contracts.plan_operations import PlanExecutionBinding
    ref = selected(bound_app.storage)
    plan = SimpleNamespace(execution_policy={'storage_input_refs': [ref.model_dump(mode='json')]}, units=[])
    def binding(root):
        return PlanExecutionBinding(package_root='.', environment_store='env',
            environments={'runtime': {'generation_id': 'fixture', 'executable': 'python'}}, storage={'data': root})
    bound_app.storage_inputs.validate_plan(plan, binding('files'))
    with pytest.raises(StorageError) as caught:
        bound_app.storage_inputs.validate_plan(plan, binding('.'))
    assert caught.value.code == 'storage_path_forbidden'


def test_export_rejects_machine_stat_relocation_without_starting_builder(bound_app, tmp_path):
    from test_plan_export_service import create_service, payload
    from operon.contracts.run_plan import RunPlan
    value = payload()
    raw = value['plan']; raw['execution_policy']['storage_input_refs'] = [selected(bound_app.storage).model_dump()]
    value['plan'] = RunPlan.model_validate(raw).with_identity().model_dump(mode='json')
    exports, calls = create_service(tmp_path)
    try:
        with pytest.raises(ContractError, match='explicit portable input') as caught:
            exports.submit(value)
        assert caught.value.code == 'storage_route_unavailable' and calls == []
    finally:
        exports.close()


def test_selected_file_runs_through_authenticated_existing_job_api(tmp_path, monkeypatch):
    """One real local CSV -> describe run, through the shared worker/pool."""
    from fastapi.testclient import TestClient
    from operon.headless import create_headless_app
    from src.web.service import Settings
    from test_headless_application import auth, wait_job
    root = Path(__file__).resolve().parents[1]
    data = tmp_path / '.studio'; data.mkdir()
    (tmp_path / 'input.csv').write_text('a,b\n1,2\n3,4\n', encoding='utf-8')
    (data / 'storage-mounts.json').write_text(json.dumps({'mounts': [
        {'kind': 'local', 'storage_id': 'data', 'root': str(tmp_path), 'principals': [PROFILE_OWNER]}]}), encoding='utf-8')
    monkeypatch.setenv('PYTHONUTF8', '1')
    monkeypatch.setenv('PYTHONIOENCODING', 'utf-8')
    monkeypatch.setenv('OPERON_REGISTRY_MAINTENANCE', '1')
    app = create_headless_app(Settings(tmp_path, data, tmp_path / 'ui', testing=True, code_root=root))
    with TestClient(app, base_url='http://127.0.0.1') as client:
        headers = auth(client, app, ['context', 'edit', 'run'])
        metadata = client.post('/api/v1/storage/stat', headers=headers,
                               json={'storage_id': 'data', 'relative_path': 'input.csv'}).json()
        ref = StorageInputRef.model_validate(metadata['ref'])
        graph = graph_for(ref); graph.memory.update(budget_mb=32, process_limit_mb=512)
        saved = graph.model_dump(mode='json')
        preflight = client.post('/api/v1/workflows/validate', headers=headers,
                                json={'graph': saved, 'require_files': True})
        assert preflight.status_code == 200, preflight.text
        checked = preflight.json()
        assert checked['readiness']['status'] == 'ready'
        assert checked['graph']['nodes'][0]['source']['storage_ref'] == saved['nodes'][0]['source']['storage_ref']
        response = client.post('/api/v1/jobs', headers=headers, json={'graph': saved, 'request_id': 'selected-local'})
        assert response.status_code == 202, response.text
        receipt = response.json()
        job = wait_job(lambda key: client.get('/api/v1/jobs/' + key, headers=headers).json(), receipt['id'])
        assert job['status'] == 'complete', job
        assert graph.model_dump(mode='json') == saved
        (tmp_path / 'input.csv').write_text('different size after completion', encoding='utf-8')
        stale = client.post('/api/v1/jobs', headers=headers, json={'graph': saved, 'request_id': 'selected-stale'})
        assert stale.status_code == 409 and stale.json()['code'] == 'storage_changed', stale.text
