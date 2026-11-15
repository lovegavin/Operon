"""Real local host-store/pool tests; not the two-compute-host K09 gate."""
import pytest

from operon.engine.state import StateStore
from operon.engine.contracts import StaleAttemptError
from operon.pool_service import PoolClient, PoolClientError, PoolControlServer
from test_pool_service import pool, graph_for, wait_until  # existing real worker fixture


def test_controller_epoch_survives_host_store_restart(tmp_path):
    path = tmp_path / 'host.sqlite3'
    identity = dict(controller_id='configured', principal='alice', request_key='key')
    with StateStore(path) as store:
        assert store.cluster_request(**identity, epoch=7) is None
    with StateStore(path) as store:
        with pytest.raises(StaleAttemptError, match='epoch'):
            store.cluster_request(**identity, epoch=6)
        assert store.cluster_request(**identity, epoch=8) is None


def test_epoch_is_rechecked_at_actual_submit_and_cancel_mutation(tmp_path):
    with StateStore(tmp_path / 'host.sqlite3') as store:
        store.cluster_request(controller_id='configured', epoch=8, principal='alice', request_key='key')
        with store.controller_guard('configured', 7):
            with pytest.raises(StaleAttemptError):
                store.claim_submission(principal='alice', key='key', digest='digest', operation='job',
                    run={'id': 'run', 'plan': {}}, units=[])
        with store.controller_guard('configured', 7, run_id='run', cancel=True):
            with pytest.raises(StaleAttemptError): store.request_cancel('run')


def envelope(workspace, **changes):
    return {'controller_id': 'configured', 'controller_epoch': 4, 'request_key': 'cluster-key',
            'command_id': 'command', 'cluster_run_id': 'cluster-run', 'cluster_unit_id': 'unit',
            'cluster_attempt_id': 'attempt', 'workspace': str(workspace), 'principal': 'alice', **changes}


def test_fenced_real_pool_submission_lookup_and_owned_cancel(pool):
    service, _, workspace, _ = pool
    server = PoolControlServer(service, token='cluster-token', controller_id='configured').start()
    client = PoolClient(server.address, 'cluster-token', capabilities=server.capabilities())
    try:
        assert 'cluster.controller_fence.v1' in client.capabilities
        params = envelope(workspace)
        first = client.request('cluster.submit', {**params, 'graph': graph_for(workspace).model_dump(mode='json')})
        assert first['host_run_id'] and first['host_identity'] == service.engine.spec.pool_id
        # Discarding the first receipt cannot change the key or produce a second run.
        again = client.request('cluster.submit', {**params, 'graph': graph_for(workspace).model_dump(mode='json')})
        assert again['host_run_id'] == first['host_run_id']
        observed = wait_until(lambda: (value if (value := client.request('cluster.lookup', params)).get('host_fence') else None))
        assert observed['host_fence'] != params['controller_epoch']
        cancelled = client.request('cluster.cancel', {**params, 'host_run_id': observed['host_run_id'],
                                                      'host_fence': observed['host_fence']})
        assert cancelled['host_run_id'] == first['host_run_id']
        with pytest.raises(PoolClientError) as error:
            client.request('cluster.lookup', envelope(workspace, controller_epoch=3))
        assert error.value.code == 'stale_controller_epoch'
    finally:
        server.close()


def test_controller_identity_is_bound_to_authenticated_endpoint(pool):
    service, old_server, workspace, _ = pool
    assert 'cluster.controller_fence.v1' not in old_server.capabilities()
    server = PoolControlServer(service, token='cluster-token', controller_id='configured').start()
    try:
        client = PoolClient(server.address, 'cluster-token')
        with pytest.raises(PoolClientError) as error:
            client.request('cluster.lookup', envelope(workspace, controller_id='forged'))
        assert error.value.code == 'unauthorized'
        with pytest.raises(PoolClientError):
            PoolClient(server.address, 'wrong').request('cluster.lookup', envelope(workspace))
    finally:
        server.close()


def test_lookup_missing_key_never_creates_host_request_or_job(pool):
    service, _, workspace, _ = pool
    server = PoolControlServer(service, token='cluster-token', controller_id='configured').start()
    try:
        before = set(service.resolve(workspace).jobs_dir.iterdir())
        client = PoolClient(server.address, 'cluster-token', capabilities=server.capabilities())
        value = client.request('cluster.lookup', envelope(workspace))
        assert value['found'] is False
        assert set(service.resolve(workspace).jobs_dir.iterdir()) == before
        with service.engine.store.lock:
            assert service.engine.store.connection.execute('SELECT COUNT(*) FROM cluster_requests').fetchone()[0] == 0
    finally:
        server.close()
