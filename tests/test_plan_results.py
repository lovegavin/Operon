"""Real durable read/ownership tests; adapter fixtures are not execution proof."""
import asyncio
import base64
import errno
import json
import os
from pathlib import Path
from types import SimpleNamespace
import threading
from urllib.parse import parse_qs, urlsplit

from fastapi.testclient import TestClient
import pytest

from operon.contracts.base import ContractError
from operon.bytecode import io_path
from operon.contracts.plan_operations import PlanEventsQuery, PlanLogsQuery, PlanPageQuery
from operon.engine.admission_limits import PrincipalLimiter
from operon.engine.contracts import CursorExpiredError, EngineError, PoolSpec
from operon.engine.control import ControlError
from operon.engine.state import StateStore
from operon.plan_service import PlanService
from operon.pool_service import PoolAuthError, PoolControlServer, PoolService


@pytest.fixture
def owned(tmp_path):
    store = StateStore(tmp_path / 'state.sqlite3')
    spec = PoolSpec(pool_id='pool-test', principal='owner', capacity_domain='host:test',
                    ceiling_bytes=1000, management_reserve_bytes=100, cpu_threads=2)
    store.ensure_pool(spec)
    services = {}
    for workspace in ('a', 'b'):
        root = tmp_path / workspace
        directory = root / '.studio'
        directory.mkdir(parents=True)
        store.register_workspace(workspace, spec.pool_id, str(root), 'owner')
        services[workspace] = SimpleNamespace(root=root, directory=directory, _pool_principal='owner',
            engine=SimpleNamespace(workspace_id=workspace, principal='owner'))
    pool = PoolService.__new__(PoolService)
    pool.engine = SimpleNamespace(store=store)
    pool.services = services
    pool.workspaces = {str(service.root): service for service in services.values()}
    pool.sessions = {}
    pool._state_lock = threading.RLock()
    # No coordinator/executor is constructed: read paths must not need one.
    for run_id, workspace in (('run-a', 'a'), ('run-other', 'a'), ('run-b', 'b')):
        store.claim_submission(principal='owner', key=run_id, digest=run_id, operation='run-plan',
            run={'id': run_id, 'workspace_id': workspace, 'project': 'test', 'plan_key': run_id,
                 'plan_digest': run_id, 'plan': {'graph': {}, 'execution': {'invocation_binding': {'test': True}}}},
            units=[{'unit_id': unit, 'node_ids': [unit], 'requirement': {'process_reservation_bytes': 10},
                    'capability': 'invocation-v1'} for unit in ('one', 'two')])
    attempts = {run: [store.create_attempt(unit['id'], epoch=1) for unit in store.units(run)]
                for run in ('run-a', 'run-other', 'run-b')}
    app = SimpleNamespace(service=SimpleNamespace(root=services['a'].root, pool_remote=False,
        pool=pool, _pool_principal='owner', engine=services['a'].engine))
    try:
        yield SimpleNamespace(store=store, pool=pool, services=services, attempts=attempts,
                              plans=PlanService(app), app=app)
    finally:
        store.close()


def log_path(owned, *, legacy=False):
    attempt = owned.attempts['run-a'][0]
    root = owned.services['a'].directory / 'invocations' / 'runs' / 'run-a'
    if legacy:
        root = root / 'nodes' / 'one'
    return root / 'attempts' / attempt['id'] / 'logs' / 'worker.log'


def test_events_keep_real_null_workspace_attempt_events_bounded_and_private(owned):
    for index in range(20):
        owned.store.append_event('progress', principal='owner', workspace_id='a', run_id='run-a',
                                 payload={'secret_path': 'private/' * 10000, 'sequence': index})
    owned.store.append_event('wrong-workspace', principal='owner', workspace_id='b', run_id='run-a')
    owned.store.append_event('wrong-principal', principal='other', workspace_id='a', run_id='run-a')
    before = owned.store.connection.total_changes
    page = owned.plans.events('run-a', limit=200, max_bytes=2048)
    assert page['has_more'] and len(json.dumps(page).encode()) <= 2048
    assert 'attempt_admitted' in {item['kind'] for item in page['events']}
    events = list(page['events'])
    while page['has_more']:
        page = owned.plans.events('run-a', after=page['next_cursor'], max_bytes=2048)
        assert len(json.dumps(page).encode()) <= 2048
        events.extend(page['events'])
    assert len({item['cursor'] for item in events}) == len(events)
    assert {item['kind'] for item in events} == {'run_submitted', 'attempt_admitted', 'progress'}
    assert all('payload' not in item and 'principal' not in item and 'workspace_id' not in item for item in events)
    assert owned.store.connection.total_changes == before


def test_event_retention_returns_floor_and_can_resume(owned):
    owned.store.prune_events(keep=3)
    with pytest.raises(CursorExpiredError) as error:
        owned.pool.plan_events('a', 'run-a', principal='owner')
    floor = error.value.details['floor']
    assert floor >= owned.store.event_bounds()[0] - 1
    with pytest.raises(CursorExpiredError):
        owned.pool.plan_events('a', 'run-a', after=floor - 1)
    page = owned.pool.plan_events('a', 'run-a', principal='owner', after=floor)
    assert page['floor'] == floor and page['next_cursor'] >= floor


@pytest.mark.parametrize('operation,query', [('events', {}), ('attempts', {}), ('artifacts', {}),
                                           ('logs', {'attempt_id': 'does-not-matter'})])
def test_all_reads_authorize_workspace_principal_and_session(owned, operation, query):
    method = getattr(owned.pool, 'plan_' + operation)
    for workspace, run_id, principal in [('a', 'run-b', 'owner'), ('b', 'run-a', 'owner'),
                                          ('a', 'run-a', 'other')]:
        with pytest.raises(PoolAuthError):
            method(workspace, run_id, principal=principal, **query)
    session = owned.pool.open_session('b', principal='owner')['session_id']
    with pytest.raises(PoolAuthError):
        method('a', 'run-a', principal='owner', session_id=session, **query)
    with pytest.raises(EngineError) as error:
        method('a', 'missing-run', principal='owner', **query)
    assert error.value.code == 'plan_not_found'


def test_attempt_page_discovers_retry_ids_without_private_process_records(owned):
    before = owned.store.connection.total_changes
    first = owned.plans.attempts('run-a', limit=1)
    second = owned.plans.attempts('run-a', after=first['next_cursor'], limit=1)
    assert first['has_more'] and not second['has_more']
    assert {item['attempt_id'] for item in first['attempts'] + second['attempts']} == {
        attempt['id'] for attempt in owned.attempts['run-a']}
    assert all('process' not in item and 'receipt' not in item and 'error' not in item
               for item in first['attempts'] + second['attempts'])
    assert owned.store.connection.total_changes == before


def test_artifact_listing_only_committed_owned_metadata_and_explicit_reuse(owned):
    for run_id in ('run-a', 'run-other', 'run-b'):
        for index, attempt in enumerate(owned.attempts[run_id]):
            owned.store.record_artifact(artifact_id=f'artifact-{run_id}-{index}', attempt_id=attempt['id'],
                fence=attempt['fence'], manifest={'files': [{'path': '/never/open/private'}]}, digest='a' * 64,
                size_bytes=12, state='committed' if index == 0 else 'staging', location='/never/open/private')
    # A resume's durable reference is authoritative even though the original
    # attempt belongs to its source run. No mutable published index is consulted.
    unit = owned.store.units('run-a')[1]
    source_unit = owned.store.units('run-other')[0]
    with owned.store.transaction():
        owned.store.connection.execute(
            'INSERT INTO unit_reuses(unit_id,source_run_id,source_unit_id,artifact_id,published_json,created_at) '
            'VALUES(?,?,?,?,?,?)', (unit['id'], 'run-other', source_unit['id'], 'artifact-run-other-0', '{}', 'test'))
    before = owned.store.connection.total_changes
    first = owned.plans.artifacts('run-a', limit=1)
    second = owned.plans.artifacts('run-a', after=first['next_cursor'], limit=1)
    assert first['has_more'] and not second['has_more']
    items = first['artifacts'] + second['artifacts']
    assert {item['artifact_id'] for item in items} == {'artifact-run-a-0', 'artifact-run-other-0'}
    assert sum(item['reused'] for item in items) == 1
    assert all(item['size_bytes'] == 12 and item['sha256'] == 'a' * 64 for item in items)
    assert '/never' not in json.dumps(items) and all('manifest' not in item and 'location' not in item for item in items)
    assert owned.store.connection.total_changes == before


@pytest.mark.parametrize('legacy', [False, True])
def test_logs_are_owned_byte_pages_and_never_follow_receipt_paths(owned, legacy):
    attempt = owned.attempts['run-a'][0]
    path = log_path(owned, legacy=legacy)
    path.parent.mkdir(parents=True)
    data = 'α first\nβ last\n'.encode()
    path.write_bytes(data)
    before = owned.store.connection.total_changes
    first = owned.plans.logs('run-a', attempt_id=attempt['id'], max_bytes=3, encoding='base64')
    assert base64.b64decode(first['data']) == data[:3] and first['next_offset'] == 3
    assert first['available'] and not first['eof'] and first['bytes_read'] == 3
    second = owned.plans.logs('run-a', attempt_id=attempt['id'], offset=3, encoding='base64')
    assert base64.b64decode(second['data']) == data[3:] and second['eof']
    assert second['next_offset'] == len(data) and 'path' not in second
    with pytest.raises(ContractError) as error:
        owned.plans.logs('run-a', attempt_id=attempt['id'], offset=len(data) + 1)
    assert error.value.code == 'plan_log_offset'
    with pytest.raises(EngineError) as error:
        owned.pool.plan_logs('a', 'run-a', attempt_id=owned.attempts['run-other'][0]['id'])
    assert error.value.code == 'plan_attempt_not_found'
    assert owned.store.connection.total_changes == before


def test_log_not_yet_created_is_explicit_not_a_completion_claim(owned):
    value = owned.plans.logs('run-a', attempt_id=owned.attempts['run-a'][0]['id'])
    assert value['available'] is False and value['bytes_read'] == 0 and value['state'] == 'admitted'
    assert 'complete' not in value


@pytest.mark.parametrize('link_kind', ['symlink', 'hardlink', 'ancestor'])
def test_log_links_cannot_read_an_outside_file(owned, tmp_path, link_kind):
    path = log_path(owned)
    path.parent.mkdir(parents=True)
    outside = tmp_path / 'private'
    outside.mkdir()
    secret = outside / 'worker.log'
    secret.write_bytes(b'not authorized')
    try:
        if link_kind == 'hardlink':
            os.link(io_path(secret), io_path(path))
        elif link_kind == 'symlink':
            io_path(path).symlink_to(io_path(secret))
        else:
            path.parent.rmdir()
            io_path(path.parent).symlink_to(io_path(outside), target_is_directory=True)
    except OSError as exc:
        if getattr(exc, 'winerror', None) in (5, 1314) or exc.errno in (errno.EACCES, errno.EPERM, errno.ENOTSUP):
            pytest.skip(f'This filesystem cannot create {link_kind}: {exc}')
        raise
    with pytest.raises(ContractError) as error:
        owned.plans.logs('run-a', attempt_id=owned.attempts['run-a'][0]['id'])
    assert error.value.code == 'plan_log_unavailable' and 'not authorized' not in str(error.value)


@pytest.mark.parametrize('model,values', [
    (PlanEventsQuery, {'after': -1}), (PlanEventsQuery, {'limit': True}),
    (PlanEventsQuery, {'limit': 201}), (PlanPageQuery, {'max_bytes': 65537}),
    (PlanPageQuery, {'max_bytes': 1}), (PlanPageQuery, {'after': '../unsafe?'}),
    (PlanLogsQuery, {'attempt_id': '../outside'}), (PlanLogsQuery, {'attempt_id': 'a', 'offset': -1}),
    (PlanLogsQuery, {'attempt_id': 'a', 'max_bytes': True}),
    (PlanLogsQuery, {'attempt_id': 'a', 'path': '/private'}),
])
def test_strict_read_contracts_reject_unbounded_or_path_selectors(model, values):
    with pytest.raises(ValueError):
        model.model_validate(values)


def test_pool_rpc_strict_read_delegation_and_normal_lane_only(owned):
    server = PoolControlServer.__new__(PoolControlServer)
    server.pool, server.token = owned.pool, 'test-token'
    server.principal_limiter = PrincipalLimiter(rate=100, burst=100, concurrent=4)
    params = {'_token': 'test-token', 'workspace': 'a', 'run_id': 'run-a', 'principal': 'owner', 'limit': 1}
    page = server.dispatch('plan.attempts', params)
    assert len(page['attempts']) == 1
    with pytest.raises(ControlError):
        server.dispatch_lifecycle('plan.attempts', params)
    with pytest.raises(ValueError):
        server.dispatch('plan.artifacts', {**params, 'path': '/private'})
    with pytest.raises(PoolAuthError):
        server.dispatch('plan.events', {**params, 'principal': 'other'})


def test_remote_reads_preserve_current_pool_session_and_query(owned):
    service, calls = owned.app.service, []
    service.pool_remote = True
    service.pool_principal, service.pool_session_id = 'owner', 'session'
    service._ensure_pool_session = lambda: None
    service.pool_client = SimpleNamespace(request=lambda method, payload: calls.append((method, payload)) or {})
    owned.plans.events('run-a', after=7, limit=2)
    owned.plans.attempts('run-a', limit=1)
    owned.plans.artifacts('run-a', max_bytes=2048)
    owned.plans.logs('run-a', attempt_id='attempt-a', offset=5, max_bytes=12)
    assert [call[0] for call in calls] == ['plan.events', 'plan.attempts', 'plan.artifacts', 'plan.logs']
    assert all(value['principal'] == 'owner' and value['session_id'] == 'session'
               and value['workspace'] == str(owned.services['a'].root) for _, value in calls)
    assert calls[0][1]['after'] == 7 and calls[-1][1]['offset'] == 5


def test_read_api_requires_context_and_rejects_extra_paths_and_large_pages(owned, tmp_path):
    from operon.headless import create_headless_app
    from src.web.service import Settings
    root = Path(__file__).resolve().parents[1]
    (tmp_path / 'http').mkdir()
    app = create_headless_app(Settings(tmp_path / 'http', tmp_path / 'http/.studio', tmp_path / 'no-ui',
                                       testing=True, code_root=root))
    app.state.application.plans = owned.plans
    attempt = owned.attempts['run-a'][0]['id']
    with TestClient(app, base_url='http://127.0.0.1') as client:
        assert client.get('/api/v1/plans/run-a/events').status_code == 403
        token = client.post('/api/agent/connect', headers={'X-Operon-Bridge': app.state.bridge.secret},
                            json={'name': 'Plan reads', 'scopes': ['context']}).json()['token']
        client.headers['Authorization'] = 'Bearer ' + token
        for operation in ('events', 'attempts', 'artifacts'):
            response = client.get(f'/api/v1/plans/run-a/{operation}?limit=1&max_bytes=2048')
            assert response.status_code == 200 and response.json()['run_id'] == 'run-a'
            assert client.get(f'/api/v1/plans/run-a/{operation}?limit=201').status_code == 422
            assert client.get(f'/api/v1/plans/run-a/{operation}?path=private').status_code == 422
        assert client.get(f'/api/v1/plans/run-a/logs?attempt_id={attempt}').status_code == 200
        assert client.get(f'/api/v1/plans/run-a/logs?attempt_id={attempt}&max_bytes=65537').status_code == 422
        assert client.get('/api/v1/plans/run-a/logs?attempt_id=../private').status_code == 422
        assert client.get('/api/v1/plans/run-b/artifacts').status_code == 403
        assert client.post('/api/v1/plans/run-a/cancel', json={}).status_code == 403


@pytest.mark.parametrize('operation', ['events', 'attempts', 'artifacts', 'logs'])
def test_cli_read_operations_only_request_context_and_forward_bounds(tmp_path, monkeypatch, operation):
    from operon import cli
    created, calls = [], []
    class Client:
        def __init__(self, *args, **kwargs): created.append(kwargs)
        def request(self, path, payload=None): calls.append((path, payload)); return {'ok': True}
        def close(self): pass
    monkeypatch.setattr(cli, 'Client', Client)
    argv = ['--workspace', str(tmp_path), 'plan', operation, 'run-a', '--max-bytes', '2048']
    argv += ['--attempt-id', 'attempt-a', '--offset', '3'] if operation == 'logs' else ['--limit', '2']
    cli.execute(cli.parser().parse_args(argv))
    assert 'context' in created[0]['scopes'] and not {'run', 'edit', 'plugins'} & set(created[0]['scopes'])
    assert len(calls) == 1 and calls[0][1] is None
    assert urlsplit(calls[0][0]).path == '/v1/plans/run-a/' + operation
    assert parse_qs(urlsplit(calls[0][0]).query)['max_bytes'] == ['2048']


def test_mcp_reads_forward_to_the_same_bounded_endpoints():
    pytest.importorskip('mcp')
    from operon.mcp_server import create_server
    calls = []
    server = create_server(SimpleNamespace(request=lambda path, payload=None: calls.append(path) or {}))
    async def run():
        for operation in ('events', 'attempts', 'artifacts', 'logs'):
            parameters = {'run_id': 'run-a', 'max_bytes': 2048}
            if operation == 'logs': parameters.update(attempt_id='attempt-a', offset=4)
            await server.call_tool('operon_plan_' + operation, parameters)
    asyncio.run(run())
    assert [urlsplit(path).path for path in calls] == ['/v1/plans/run-a/' + operation
                                                     for operation in ('events', 'attempts', 'artifacts', 'logs')]
