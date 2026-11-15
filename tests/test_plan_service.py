"""Plan product delegation and permission tests; mock pools are not execution proof."""
import asyncio
from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient
import pytest

from operon.contracts.base import ContractError
from operon.contracts.plan_operations import PlanExecutionBinding, PlanSubmitControl
from operon.contracts.run_plan import RunPlan
from operon.plan_service import PlanService
from operon.pool_service import PoolClientError


def sample_plan():
    return RunPlan.model_validate({
        'plan_id': 'pending', 'workflow_revision': '1' * 64, 'parameters_digest': '2' * 64,
        'compiler_version': 'synthetic-test-v1', 'units': [{
            'unit_id': 'one', 'node_ids': ['one'], 'invocation': {
                'kind': 'command', 'argv': ['synthetic-command'],
                'code_ref': {'kind': 'file', 'ref': 'fixture.bin'},
                'parameters_ref': {'kind': 'none'}, 'environment_ref': 'runtime'},
            'resource_request': {'process_reservation_bytes': 1024},
            'placement': {'executor': 'local', 'target': {'os': 'linux', 'arch': 'x86_64'}}}]
    }).with_identity()


def sample_binding():
    return {'package_root': 'package', 'environment_store': 'environments',
            'environments': {'runtime': {'generation_id': 'generation-fixture', 'executable': 'bin/tool'}},
            'storage': {}, 'inputs': {}}


class Pool:
    def __init__(self): self.calls = []
    def submit_plan(self, workspace, plan, binding, **kwargs):
        self.calls.append(('submit', workspace, plan, binding, kwargs))
        return {'run_id': 'run-fixture', 'state': 'queued'}
    def plan_details(self, workspace, run_id, **kwargs):
        self.calls.append(('details', workspace, run_id, kwargs))
        return {'run_id': run_id, 'state': 'running'}
    def plan_cancel(self, workspace, run_id, **kwargs):
        self.calls.append(('cancel', workspace, run_id, kwargs))
        return {'run_id': run_id, 'state': 'cancelling'}


def application(tmp_path):
    pool = Pool()
    app = SimpleNamespace(stopping=False, service=SimpleNamespace(root=tmp_path,
        pool_remote=False, pool=pool, _pool_principal='owner', engine=SimpleNamespace(principal='owner')))
    app.compile_calls = []
    def compile_plan(workflow, values, **options):
        app.compile_calls.append((workflow, values, options))
        return sample_plan()
    app.compile_plan = compile_plan
    return app, PlanService(app), pool


def test_compile_never_submits_and_execution_requires_explicit_binding(tmp_path):
    app, plans, pool = application(tmp_path)
    plan = plans.compile({'workflow': {'nodes': [], 'edges': []}})
    assert plan.compute_id() == plan.plan_id
    assert len(app.compile_calls) == 1 and pool.calls == []
    receipt = plans.submit({'plan': plan, 'binding': sample_binding(), 'request_id': 'stable-key'})
    assert receipt['run_id'] == 'run-fixture'
    assert pool.calls[0][0] == 'submit'
    assert pool.calls[0][-1] == {'request_id': 'stable-key', 'principal': 'owner'}
    plans.details('run-fixture')
    plans.cancel('run-fixture')
    assert [call[0] for call in pool.calls] == ['submit', 'details', 'cancel']


def test_stale_identity_missing_bindings_and_missing_pool_fail_without_launch(tmp_path):
    app, plans, pool = application(tmp_path)
    broken = sample_plan().model_dump(mode='json')
    broken['units'][0]['invocation']['argv'] = ['changed']
    with pytest.raises(ContractError) as error:
        plans.submit({'plan': broken, 'binding': sample_binding(), 'request_id': 'key'})
    assert error.value.code == 'stale_plan_identity' and not pool.calls
    binding = sample_binding()
    binding['environments'] = {'different': binding['environments']['runtime']}
    with pytest.raises(ContractError) as error:
        plans.submit({'plan': sample_plan(), 'binding': binding, 'request_id': 'key'})
    assert error.value.code == 'missing_binding' and not pool.calls
    app.service.pool = None
    with pytest.raises(ContractError) as error:
        plans.submit({'plan': sample_plan(), 'binding': sample_binding(), 'request_id': 'key'})
    assert error.value.code == 'engine_unavailable'
    assert plans.compile({'workflow': {}}).plan_id == sample_plan().plan_id


@pytest.mark.parametrize('field,value', [('package_root', '../package'), ('environment_store', '/global/env'),
                                         ('package_root', 'C:\\package')])
def test_binding_roots_are_strictly_workspace_relative(field, value):
    binding = sample_binding()
    binding[field] = value
    with pytest.raises(ValueError):
        PlanExecutionBinding.model_validate(binding)


def test_binding_nested_paths_sizes_and_control_fields_are_strict():
    binding = sample_binding()
    binding['storage'] = {'input': '../outside'}
    with pytest.raises(ValueError): PlanExecutionBinding.model_validate(binding)
    binding = sample_binding()
    binding['inputs'] = {'in': {'representation': 'file', 'path': 'input.txt',
                               'size_bytes': True, 'sha256': 'a' * 64}}
    with pytest.raises(ValueError): PlanExecutionBinding.model_validate(binding)
    with pytest.raises(ValueError):
        PlanSubmitControl(workspace='workspace', plan=sample_plan(), binding=sample_binding(),
                          request_id='key', unexpected=True)


@pytest.mark.parametrize('failure', [TimeoutError('unknown reply'),
                                    PoolClientError('closed', code='response_unavailable')])
def test_uncertain_submission_never_retries_or_falls_back(tmp_path, failure):
    app, plans, pool = application(tmp_path)
    calls = []
    def request(method, payload):
        calls.append((method, payload))
        raise failure
    app.service.pool_remote = True
    app.service.pool_principal = 'owner'
    app.service.pool_session_id = 'session'
    app.service._ensure_pool_session = lambda: None
    app.service.pool_client = SimpleNamespace(request=request)
    with pytest.raises(ContractError) as error:
        plans.submit({'plan': sample_plan(), 'binding': sample_binding(), 'request_id': 'same-key'})
    assert error.value.code == 'submission_unknown'
    assert error.value.next_actions == ({'action': 'retry_same_request', 'request_id': 'same-key'},)
    assert len(calls) == 1 and calls[0][0] == 'plan.submit' and pool.calls == []
    assert calls[0][1]['principal'] == 'owner' and calls[0][1]['session_id'] == 'session'


def test_remote_details_and_cancel_use_the_same_pool_session(tmp_path):
    app, plans, pool = application(tmp_path)
    calls = []
    app.service.pool_remote = True
    app.service.pool_principal = 'owner'
    app.service.pool_session_id = 'session'
    app.service._ensure_pool_session = lambda: None
    app.service.pool_client = SimpleNamespace(request=lambda method, payload: calls.append((method, payload)) or {})
    plans.details('run-fixture')
    plans.cancel('run-fixture')
    assert [call[0] for call in calls] == ['plan.details', 'plan.cancel']
    assert all(call[1] == {'workspace': str(tmp_path), 'principal': 'owner',
                          'session_id': 'session', 'run_id': 'run-fixture'} for call in calls)
    assert not pool.calls


def test_plan_api_and_mcp_separate_compile_permission_from_execution(tmp_path, monkeypatch):
    from operon.client import Client
    from operon.headless import create_headless_app
    from src.web.service import Settings
    root = Path(__file__).resolve().parents[1]
    http_app = create_headless_app(Settings(tmp_path, tmp_path / '.studio', tmp_path / 'no-ui', testing=True, code_root=root))
    app, plans, pool = application(tmp_path)
    http_app.state.application.plans = plans
    body = {'plan': sample_plan().model_dump(mode='json'), 'binding': sample_binding(), 'request_id': 'key'}
    with TestClient(http_app, base_url='http://127.0.0.1') as client:
        def auth(scopes):
            value = client.post('/api/agent/connect', headers={'X-Operon-Bridge': http_app.state.bridge.secret},
                                json={'name': 'Plan test', 'scopes': scopes}).json()
            client.headers['Authorization'] = 'Bearer ' + value['token']
        auth(['context', 'edit'])
        compiled = client.post('/api/v1/plans/compile', json={'workflow': {}})
        assert compiled.status_code == 200 and not pool.calls
        assert client.post('/api/v1/plans', json=body).status_code == 403
        assert client.post('/api/v1/plans/run-fixture/cancel', json={}).status_code == 403
        auth(['context', 'run'])
        receipt = client.post('/api/v1/plans', json=body)
        assert receipt.status_code == 202 and receipt.json()['run_id'] == 'run-fixture'
        assert client.get('/api/v1/plans/run-fixture').json()['state'] == 'running'
        assert client.post('/api/v1/plans/run-fixture/cancel', json={}).json()['state'] == 'cancelling'
        bad = deepcopy(body)
        bad['plan']['units'][0]['invocation']['argv'] = ['mutated']
        result = client.post('/api/v1/plans', json=bad)
        assert result.status_code == 409 and result.json()['code'] == 'stale_plan_identity'
        assert result.json()['request_id'] and 'next_actions' in result.json()
        schema = client.get('/api/v1/openapi.json').json()
        assert schema['components']['schemas']['PlanExecutionBinding']['additionalProperties'] is False
        assert [call[0] for call in pool.calls] == ['submit', 'details', 'cancel']


def test_mcp_plan_tools_only_forward_to_shared_plan_api():
    pytest.importorskip('mcp')
    from operon.mcp_server import create_server
    calls = []
    client = SimpleNamespace(request=lambda path, payload=None: calls.append((path, payload)) or {'ok': True})
    server = create_server(client)
    async def run():
        await server.call_tool('operon_plan_compile', {'request': {'workflow': {}}})
        await server.call_tool('operon_plan_submit', {'plan': {'plan_id': 'x'}, 'binding': {}, 'request_id': 'key'})
        await server.call_tool('operon_plan_status', {'run_id': 'run-fixture'})
        await server.call_tool('operon_plan_cancel', {'run_id': 'run-fixture'})
    asyncio.run(run())
    assert [call[0] for call in calls] == ['/v1/plans/compile', '/v1/plans',
                                         '/v1/plans/run-fixture', '/v1/plans/run-fixture/cancel']


@pytest.mark.parametrize('action,run_scope', [('compile', False), ('submit', True), ('details', False), ('cancel', True)])
def test_cli_plan_permissions_and_forwarding(tmp_path, monkeypatch, action, run_scope):
    from operon import cli
    source = tmp_path / 'plan.json'
    source.write_text(json.dumps(sample_plan().model_dump(mode='json') if action == 'submit' else {'nodes': [], 'edges': []}))
    binding = tmp_path / 'binding.json'
    binding.write_text(json.dumps(sample_binding()))
    created, calls = [], []
    class Client:
        def __init__(self, *args, **kwargs): created.append(kwargs)
        def request(self, path, payload=None): calls.append((path, payload)); return {'ok': True}
        def close(self): pass
    monkeypatch.setattr(cli, 'Client', Client)
    value = str(source) if action in ('compile', 'submit') else 'run-fixture'
    argv = ['--workspace', str(tmp_path), 'plan', action, value]
    if action == 'submit': argv += ['--binding', str(binding), '--request-id', 'key']
    cli.execute(cli.parser().parse_args(argv))
    assert ('run' in created[0]['scopes']) is run_scope
    assert 'edit' not in created[0]['scopes']
    assert len(calls) == 1 and calls[0][0].startswith('/v1/plans')
