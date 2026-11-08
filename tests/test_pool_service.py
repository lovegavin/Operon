"""Product-level multi-workspace pool service with real workers and clients."""
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import time

import pytest

from biopipe.engine.environment import EnvironmentBusy
from biopipe.pool_service import PoolClient, PoolControlServer, PoolService
from src.web.models import Graph

ROOT = Path(__file__).resolve().parents[1]
MIB = 1024 ** 2


def wait_until(check, timeout=40):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        value = check()
        if value:
            return value
        time.sleep(.05)
    pytest.fail('Timed out waiting for pool state')


def make_workspace(root):
    root.mkdir(parents=True)
    (root / 'input.csv').write_text('a,b,c\n1,2,4\n2,5,7\n3,8,1\n7,2,9\n4,6,3\n',
                                    encoding='utf-8')
    return root


def graph_for(root, *, budget=8, process_limit=16):
    return Graph.model_validate({
        'schema_version': 2, 'name': str(root.name), 'base_dir': str(root),
        'memory': {'enabled': True, 'auto_spill': True, 'budget_mb': budget,
                   'process_limit_mb': process_limit, 'chunk_mb': .01},
        'runtime': {'execution': {'mode': 'manual', 'max_parallel_tasks': 2}},
        'nodes': [
            {'id': 'input', 'kind': 'source', 'position': {'x': 0, 'y': 0},
             'source': {'path': 'input.csv', 'dims': ['sample', 'feature'],
                        'labels': {'sample': 'auto', 'feature': 'builtin'}}},
            {'id': 'summary', 'kind': 'operator', 'operator': 'describe',
             'position': {'x': 1, 'y': 0}, 'params': {}}],
        'edges': [{'id': 'e1', 'source': 'input', 'target': 'summary'}]})


@pytest.fixture
def pool(tmp_path):
    code = tmp_path / 'code'
    (code / 'scripts').mkdir(parents=True)
    (code / 'scripts/run.py').write_text('''import json, os, sys, time
from pathlib import Path
task = Path(sys.argv[1]); output = task / 'output'; output.mkdir(parents=True, exist_ok=True)
(output / 'started.json').write_text(json.dumps({'pid': os.getpid(), 'cwd': os.getcwd()}))
(output / 'cwd.txt').write_text(os.getcwd())
while not (task / 'finish').exists():
    if (task / 'cancel.requested').exists():
        sys.exit(2)
    time.sleep(.03)
(output / 'run_summary.json').write_text(json.dumps({'status': 'complete'}))
''', encoding='utf-8')
    wsa = make_workspace(tmp_path / 'alpha')
    wsb = make_workspace(tmp_path / 'beta')
    service = PoolService(
        root=tmp_path / 'pool-state', admission_dir=tmp_path / 'admission',
        workspaces=[{'root': wsa, 'principal': 'alice'},
                    {'root': wsb, 'principal': 'bob'}],
        code_root=code, capacity_bytes=256 * MIB, cpu_threads=4)
    server = PoolControlServer(service, token='test-token', port=0).start()
    try:
        yield service, server, wsa, wsb
    finally:
        server.close()
        service.shutdown()


def finish(service, workspace, job_id):
    (service.resolve(workspace).jobs_dir / job_id / 'finish').touch()


def test_two_workspaces_parallel_clients_respect_budget(pool):
    service, server, wsa, wsb = pool
    client_a = PoolClient(server.address, 'test-token')
    client_b = PoolClient(server.address, 'test-token')
    with ThreadPoolExecutor(max_workers=2) as pool_threads:
        a = pool_threads.submit(client_a.submit, wsa, graph_for(wsa).model_dump(mode='json'),
                                request_id='alpha-1', principal='alice').result(timeout=15)
        b = pool_threads.submit(client_b.submit, wsb, graph_for(wsb).model_dump(mode='json'),
                                request_id='beta-1', principal='bob').result(timeout=15)
    assert a['id'] != b['id']
    wait_until(lambda: (service.resolve(wsa).jobs_dir / a['id'] / 'output/started.json').exists())
    wait_until(lambda: (service.resolve(wsb).jobs_dir / b['id'] / 'output/started.json').exists())
    jobs = [service.details(wsa, a['id'], principal='alice'),
            service.details(wsb, b['id'], principal='bob')]
    assert all(job['pool']['workspace'] == str(service.resolve(job['pool']['workspace']).root)
               for job in jobs)
    assert (service.resolve(wsa).jobs_dir / a['id'] / 'output/cwd.txt').read_text() == str(wsa)
    assert (service.resolve(wsb).jobs_dir / b['id'] / 'output/cwd.txt').read_text() == str(wsb)
    leases = [service.details(wsa, a['id'], principal='alice')['pool']['lease'],
              service.details(wsb, b['id'], principal='bob')['pool']['lease']]
    assert len(service.engine.store.lease_details(service.engine.spec.pool_id)) == 2
    used = sum(item['committed']['process_reservation_bytes'] for item in leases)
    assert used <= service.engine.resources.snapshot().capacity
    assert service.admission.resources()['reservations'] == {}
    finish(service, wsa, a['id']); finish(service, wsb, b['id'])
    wait_until(lambda: service.details(wsa, a['id'], principal='alice')['status'] == 'complete')
    wait_until(lambda: service.details(wsb, b['id'], principal='bob')['status'] == 'complete')
    wait_until(lambda: service.engine.store.run(a['id'])['status'] == 'complete' and
               service.engine.store.run(b['id'])['status'] == 'complete')
    for workspace, principal, job in ((wsa, 'alice', a), (wsb, 'bob', b)):
        details = service.details(workspace, job['id'], principal=principal)
        assert details['lifecycle'] == {
            'compute_complete': True, 'artifact_committed': True, 'tree_exited': True,
            'resources_released': True, 'lease_state': 'released',
            'resource_authority': 'coordinator'}
        assert details['artifact_id']


def test_duplicate_request_and_disconnect_do_not_launch_twice(pool):
    service, server, wsa, _ = pool
    first = PoolClient(server.address, 'test-token')
    job = first.submit(wsa, graph_for(wsa).model_dump(mode='json'),
                       request_id='disconnect-1', principal='alice')
    # A transport/session connection is not the pool lifetime; reconnect with
    # a fresh client and retry the same durable request.
    second = PoolClient(server.address, 'test-token')
    duplicate = second.submit(wsa, graph_for(wsa).model_dump(mode='json'),
                              request_id='disconnect-1', principal='alice')
    assert duplicate['id'] == job['id']
    wait_until(lambda: (service.resolve(wsa).jobs_dir / job['id'] / 'output/started.json').exists())
    assert len(service.engine.store.attempts(job['id'])) == 1
    finish(service, wsa, job['id'])
    wait_until(lambda: service.details(wsa, job['id'], principal='alice')['status'] == 'complete')
    wait_until(lambda: service.engine.store.run(job['id'])['status'] == 'complete')
    assert len(service.engine.store.attempts(job['id'])) == 1


def test_cancel_one_workspace_does_not_cancel_other(pool):
    service, server, wsa, wsb = pool
    client = PoolClient(server.address, 'test-token')
    a = client.submit(wsa, graph_for(wsa).model_dump(mode='json'),
                      request_id='cancel-a', principal='alice')
    b = client.submit(wsb, graph_for(wsb).model_dump(mode='json'),
                      request_id='cancel-b', principal='bob')
    wait_until(lambda: (service.resolve(wsa).jobs_dir / a['id'] / 'output/started.json').exists())
    wait_until(lambda: (service.resolve(wsb).jobs_dir / b['id'] / 'output/started.json').exists())
    cancelled = client.cancel(wsa, a['id'], principal='alice')
    assert cancelled['id'] == a['id']
    wait_until(lambda: service.details(wsa, a['id'], principal='alice')['status'] == 'cancelled')
    wait_until(lambda: service.engine.store.lease(
        service.engine.store.attempts(a['id'])[0]['id'])['state'] == 'released')
    assert service.details(wsb, b['id'], principal='bob')['status'] in ('running', 'preparing')
    finish(service, wsb, b['id'])
    wait_until(lambda: service.details(wsb, b['id'], principal='bob')['status'] == 'complete')
    wait_until(lambda: service.engine.store.run(b['id'])['status'] == 'complete')


def test_environment_repair_is_shared_across_workspaces(pool):
    service, server, wsa, wsb = pool
    alpha = service.resolve(wsa)
    beta = service.resolve(wsb)
    job = service.launch(wsa, graph_for(wsa), request_id='env-alpha', principal='alice')
    wait_until(lambda: (alpha.jobs_dir / job['id'] / 'output/started.json').exists())
    assert alpha.environment_identity() == beta.environment_identity()
    with pytest.raises(EnvironmentBusy):
        beta.environment_guard.begin(owner=beta.owner, kind='repair',
                                     environment=beta.environment_identity())
    finish(service, wsa, job['id'])
    wait_until(lambda: service.details(wsa, job['id'], principal='alice')['status'] == 'complete')
    wait_until(lambda: service.engine.store.lease(
        service.engine.store.attempts(job['id'])[0]['id'])['state'] == 'released')
    token = beta.environment_guard.begin(owner=beta.owner, kind='repair',
                                         environment=beta.environment_identity())
    assert beta.environment_guard.end(token)


def test_pool_restart_adopts_live_worker_without_duplicate(pool, tmp_path):
    service, server, wsa, _ = pool
    job = service.launch(wsa, graph_for(wsa), request_id='restart-1', principal='alice')
    wait_until(lambda: (service.resolve(wsa).jobs_dir / job['id'] / 'output/started.json').exists())
    attempts = service.engine.store.attempts(job['id'])
    assert len(attempts) == 1
    old = service
    old.restart()
    replacement = PoolService(
        root=tmp_path / 'pool-state', admission_dir=tmp_path / 'admission',
        workspaces=[{'root': wsa, 'principal': 'alice'},
                    {'root': tmp_path / 'beta', 'principal': 'bob'}],
        code_root=tmp_path / 'code', capacity_bytes=256 * MIB, cpu_threads=4)
    try:
        wait_until(lambda: replacement.coordinator is not None)
        finish(replacement, wsa, job['id'])
        wait_until(lambda: replacement.details(wsa, job['id'], principal='alice')['status'] == 'complete')
        wait_until(lambda: replacement.engine.store.run(job['id'])['status'] == 'complete')
        assert len(replacement.engine.store.attempts(job['id'])) == 1
        # Resource release follows the terminal compute commit; verify the
        # release phase explicitly instead of sampling in that commit gap.
        wait_until(lambda: replacement.engine.store.lease(attempts[0]['id'])['state'] == 'released')
    finally:
        replacement.shutdown()

def test_connections_do_not_multiply_physical_capacity(pool):
    service, server, wsa, wsb = pool
    client_a1 = PoolClient(server.address, 'test-token')
    client_a2 = PoolClient(server.address, 'test-token')
    client_b = PoolClient(server.address, 'test-token')
    a1 = client_a1.submit(wsa, graph_for(wsa, budget=100, process_limit=110).model_dump(mode='json'),
                          request_id='fair-a1', principal='alice')
    a2 = client_a2.submit(wsa, graph_for(wsa, budget=100, process_limit=110).model_dump(mode='json'),
                          request_id='fair-a2', principal='alice')
    b = client_b.submit(wsb, graph_for(wsb, budget=30, process_limit=40).model_dump(mode='json'),
                        request_id='fair-b', principal='bob')
    wait_until(lambda: service.details(wsa, a1['id'], principal='alice')['status'] in ('running', 'complete'))
    wait_until(lambda: service.details(wsb, b['id'], principal='bob')['status'] in ('running', 'complete'))
    # Alice's second connection cannot manufacture capacity; Bob's independent
    # small request still runs while Alice's second request waits.
    assert service.details(wsa, a2['id'], principal='alice')['status'] == 'queued'
    finish(service, wsa, a1['id']); finish(service, wsb, b['id'])
    wait_until(lambda: service.details(wsa, a1['id'], principal='alice')['status'] == 'complete')
    wait_until(lambda: service.details(wsb, b['id'], principal='bob')['status'] == 'complete')
    wait_until(lambda: service.details(wsa, a2['id'], principal='alice')['status'] in ('running', 'complete'))
    finish(service, wsa, a2['id'])
    wait_until(lambda: service.details(wsa, a2['id'], principal='alice')['status'] == 'complete')

def test_closing_workspace_session_does_not_cancel_pool_work(pool):
    service, server, wsa, wsb = pool
    client = PoolClient(server.address, 'test-token')
    session = client.open_session(wsa, principal='alice')
    job = client.submit(wsa, graph_for(wsa).model_dump(mode='json'),
                        request_id='session-close', principal='alice')
    wait_until(lambda: (service.resolve(wsa).jobs_dir / job['id'] / 'output/started.json').exists())
    closed = client.close_session(session['session_id'])
    assert closed['pool_closed'] is False and closed['closed'] is True
    assert service.details(wsa, job['id'], principal='alice')['status'] in ('running', 'preparing')
    finish(service, wsa, job['id'])
    reconnect = PoolClient(server.address, 'test-token')
    wait_until(lambda: reconnect.details(wsa, job['id'], principal='alice')['status'] == 'complete')
    wait_until(lambda: service.engine.store.run(job['id'])['status'] == 'complete')


def test_two_sessions_same_workspace_are_independent(pool):
    service, server, wsa, _ = pool
    alpha = PoolClient(server.address, 'test-token')
    beta = PoolClient(server.address, 'test-token')
    alpha.open_session(wsa, principal='alice', name='alpha')
    beta.open_session(wsa, principal='alice', name='beta')
    a = alpha.submit(wsa, graph_for(wsa).model_dump(mode='json'),
                     request_id='session-a', principal='alice')
    b = beta.submit(wsa, graph_for(wsa).model_dump(mode='json'),
                    request_id='session-b', principal='alice')
    wait_until(lambda: (service.resolve(wsa).jobs_dir / a['id'] / 'output/started.json').exists())
    wait_until(lambda: (service.resolve(wsa).jobs_dir / b['id'] / 'output/started.json').exists())
    alpha.close_session()
    # B's session remains usable for submit/query/cancel; A's running job is not affected.
    assert beta.details(wsa, b['id'])['id'] == b['id']
    c = beta.submit(wsa, graph_for(wsa).model_dump(mode='json'),
                    request_id='session-c', principal='alice')
    wait_until(lambda: (service.resolve(wsa).jobs_dir / c['id'] / 'output/started.json').exists())
    assert beta.cancel(wsa, b['id'])['id'] == b['id']
    wait_until(lambda: service.details(wsa, b['id'], principal='alice')['status'] == 'cancelled')
    assert service.details(wsa, a['id'], principal='alice')['status'] in ('running', 'preparing')
    # A can reconnect and observe its historical/running work.
    again = PoolClient(server.address, 'test-token')
    again.open_session(wsa, principal='alice', name='alpha-reconnect')
    assert again.details(wsa, a['id'])['id'] == a['id']
    finish(service, wsa, a['id']); finish(service, wsa, c['id'])
    wait_until(lambda: service.details(wsa, a['id'], principal='alice')['status'] == 'complete')
    wait_until(lambda: service.details(wsa, c['id'], principal='alice')['status'] == 'complete')

def test_pool_submission_failure_is_visible_and_pool_recovers(pool, monkeypatch):
    from biopipe.engine.contracts import UnavailableStateError
    from biopipe.pool_service import PoolClientError
    service, server, wsa, _ = pool
    client = PoolClient(server.address, 'test-token')
    original = service.coordinator.submit
    def unavailable(**kwargs):
        raise UnavailableStateError('injected durable-store failure')
    monkeypatch.setattr(service.coordinator, 'submit', unavailable)
    with pytest.raises(PoolClientError) as error:
        client.submit(wsa, graph_for(wsa).model_dump(mode='json'),
                      request_id='db-failure', principal='alice')
    assert error.value.code in ('engine_unavailable', 'state_unavailable', 'unavailable')
    failed = [job for job in service.resolve(wsa).jobs.values()
              if job.get('request_id') == 'db-failure']
    assert failed and failed[0]['status'] == 'failed'
    assert not service.resolve(wsa).processes
    assert not service.engine.store.list_runs()
    monkeypatch.setattr(service.coordinator, 'submit', original)
    job = client.submit(wsa, graph_for(wsa).model_dump(mode='json'),
                        request_id='db-recovered', principal='alice')
    wait_until(lambda: (service.resolve(wsa).jobs_dir / job['id'] / 'output/started.json').exists())
    finish(service, wsa, job['id'])
    wait_until(lambda: service.details(wsa, job['id'], principal='alice')['status'] == 'complete')

def test_artifact_publication_failure_is_distinct_from_compute_success(pool, monkeypatch):
    from biopipe.engine.artifacts import ArtifactError
    service, server, wsa, _ = pool
    alpha = service.resolve(wsa)
    def fail(_payload, _result):
        raise ArtifactError('injected staging disk failure')
    monkeypatch.setattr(alpha, '_commit_job_artifacts', fail)
    job = service.launch(wsa, graph_for(wsa), request_id='artifact-fail', principal='alice')
    wait_until(lambda: (alpha.jobs_dir / job['id'] / 'output/started.json').exists())
    finish(service, wsa, job['id'])
    wait_until(lambda: service.engine.store.run(job['id'])['status'] == 'failed')
    result = service.details(wsa, job['id'], principal='alice')
    assert result['status'] == 'complete'  # scientific computation itself completed
    assert result['lifecycle']['compute_complete'] is True
    assert result['lifecycle']['tree_exited'] is True
    assert result['lifecycle']['artifact_committed'] is False
    assert result['lifecycle']['resources_released'] is True
    assert result.get('artifact_committed') is False

def test_client_reopens_lost_subscription_without_relaunch(pool):
    service, server, wsa, _ = pool
    client = PoolClient(server.address, 'test-token')
    old = client.open_session(wsa, principal='alice')['session_id']
    graph = graph_for(wsa).model_dump(mode='json')
    job = client.submit(wsa, graph, request_id='subscription-recovery', principal='alice')
    service.sessions.clear()  # volatile state after a pool restart
    assert client.details(wsa, job['id'])['id'] == job['id']
    assert client.session_id != old
    assert client.submit(wsa, graph, request_id='subscription-recovery')['id'] == job['id']
    assert len(service.resolve(wsa).jobs) == 1
    client.cancel(wsa, job['id'])


def test_workspace_stop_is_explicit_and_does_not_cancel_running_work(pool):
    from biopipe.pool_service import PoolClientError
    service, server, wsa, _ = pool
    client = PoolClient(server.address, 'test-token')
    session = client.open_session(wsa, principal='alice')
    job = client.submit(wsa, graph_for(wsa).model_dump(mode='json'),
                        request_id='workspace-stop', principal='alice')
    wait_until(lambda: (service.resolve(wsa).jobs_dir / job['id'] / 'output/started.json').exists())
    stopped = client.stop_workspace(wsa, principal='alice')
    assert stopped['accepting'] is False and stopped['pool_closed'] is False
    with pytest.raises(PoolClientError):
        client.submit(wsa, graph_for(wsa).model_dump(mode='json'),
                      request_id='workspace-stop-2', principal='alice')
    assert service.details(wsa, job['id'], principal='alice')['status'] in ('running', 'preparing')
    finish(service, wsa, job['id'])
    wait_until(lambda: service.details(wsa, job['id'], principal='alice')['status'] == 'complete')
