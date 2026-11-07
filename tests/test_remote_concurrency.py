"""Remote server request idempotency and durable events over the engine journal."""
from concurrent.futures import ThreadPoolExecutor
import json
import threading
import time
from pathlib import Path

import pytest

from biopipe.remote.server import RemoteService


def graph_payload():
    return {'schema_version': 2, 'name': 'remote-idempotency', 'base_dir': '.',
            'memory': {'enabled': True},
            'nodes': [], 'edges': []}


def readiness(service, ids, *, graph=None, scripts=None, repair=False):
    return {'entries': {}, 'scripts': {}, 'checked_at': 'fixture'}


@pytest.fixture
def remote(tmp_path, monkeypatch):
    root = tmp_path / 'server'
    root.mkdir()
    monkeypatch.setenv('BIOPIPE_ADMISSION_DIR', str(tmp_path / 'admission'))
    monkeypatch.setenv('BIOPIPE_ENGINE_DIR', str(tmp_path / 'engine'))
    service = RemoteService(str(root))
    monkeypatch.setattr('biopipe.readiness.inspect_declared_environment', readiness)
    calls = []
    lock = threading.Lock()

    def launch(graph):
        with lock:
            calls.append(graph)
            job = {'id': f'job-{len(calls)}', 'name': 'fixture', 'status': 'queued',
                   'created_at': '2026-01-01T00:00:00+00:00', 'finished_at': None, 'error': None,
                   'graph': graph.model_dump(mode='json'), 'order': [], 'allocation': {},
                   'progress': {'completed': 0, 'total': 0, 'percent': 0}}
            folder = service.service.jobs_dir / job['id']
            folder.mkdir(parents=True)
            (folder / 'job.json').write_text(json.dumps(job), encoding='utf-8')
        return job

    monkeypatch.setattr(service.service, 'launch', launch)
    yield service, calls, root


def test_concurrent_identical_remote_runs_launch_once(remote):
    service, calls, root = remote
    payload = {'graph': graph_payload(), 'request_id': 'a' * 32}
    with ThreadPoolExecutor(max_workers=16) as pool:
        results = list(pool.map(lambda _: service.dispatch('run', payload), range(20)))
    assert len(calls) == 1
    assert len({item['id'] for item in results}) == 1
    record = service._journal().request(payload['request_id'])
    assert record['state'] == 'submitted' and record['run_id'] == results[0]['id']
    page = service.dispatch('events', {'after': 0})
    assert page['available'] and any(event['kind'] == 'request_claimed' for event in page['events'])
    service.close()


def test_same_remote_identity_with_different_content_is_rejected(remote):
    service, calls, root = remote
    first = service.dispatch('run', {'graph': graph_payload(), 'request_id': 'b' * 32})
    changed = graph_payload()
    changed['name'] = 'different graph'
    with pytest.raises(ValueError, match='different graph'):
        service.dispatch('run', {'graph': changed, 'request_id': 'b' * 32})
    assert len(calls) == 1
    service.close()


def test_interrupted_remote_submission_is_recovered_not_relaunched(remote, monkeypatch):
    service, calls, root = remote
    original = service.service.launch

    def lost_response(graph):
        original(graph)
        raise OSError('response publication interrupted')

    monkeypatch.setattr(service.service, 'launch', lost_response)
    first = service.dispatch('run', {'graph': graph_payload(), 'request_id': 'c' * 32})
    # The graph runtime recorded the request identity; a retry returns it.
    second = service.dispatch('run', {'graph': graph_payload(), 'request_id': 'c' * 32})
    assert first['id'] == second['id']
    assert len(calls) == 1
    service.close()


def test_daemon_liveness_includes_transfers_leases_and_maintenance():
    from types import SimpleNamespace
    service = RemoteService.__new__(RemoteService)
    service.service = SimpleNamespace(processes={}, threads={})
    service.transport_leases = {}
    service.transport_active = {}
    service.handshake = SimpleNamespace(maintenance_running=False)
    service.transfers = SimpleNamespace(tokens={})
    assert service.alive() is False
    service.transfers.tokens['t'] = {}
    assert service.alive() is True
    service.transfers.tokens.clear()
    service.transport_leases['transfer-' + 'a' * 32] = 1e18
    assert service.alive() is True
    service.transport_leases.clear()
    service.handshake.maintenance_running = True
    assert service.alive() is True


def test_remote_claim_failure_never_falls_back_to_launch(remote, monkeypatch):
    import sqlite3
    service, calls, _ = remote
    monkeypatch.setattr(service._journal(), 'claim', lambda *a, **k: (_ for _ in ()).throw(
        sqlite3.OperationalError('store unavailable')))
    with pytest.raises(ValueError) as error:
        service.dispatch('run', {'graph': graph_payload(), 'request_id': 'e' * 32})
    assert error.value.code == 'engine_unavailable'
    assert calls == []
    service.close()


def test_remote_unknown_commit_never_falls_back_to_launch(remote, monkeypatch):
    from biopipe.engine.contracts import CommitOutcomeUnknown
    service, calls, _ = remote
    journal = service._journal()
    original = journal.claim
    def uncertain(*args, **kwargs):
        original(*args, **kwargs)
        raise CommitOutcomeUnknown('lost commit acknowledgement')
    monkeypatch.setattr(journal, 'claim', uncertain)
    with pytest.raises(ValueError) as error:
        service.dispatch('run', {'graph': graph_payload(), 'request_id': 'f' * 32})
    assert error.value.code == 'submission_uncertain'
    assert calls == []
    service.close()


def test_events_cursor_is_resumable_across_restart(remote):
    service, calls, root = remote
    started = service.dispatch('run', {'graph': graph_payload(), 'request_id': 'd' * 32})
    page = service.dispatch('events', {'after': 0})
    cursor = page['cursor']
    assert cursor > 0
    service.close()
    reopened = RemoteService(str(root))
    try:
        later = reopened.dispatch('events', {'after': cursor})
        assert later['available']
        # A restart may re-freeze the pool when its startup snapshot changed;
        # no business event is replayed and the cursor never moves backward.
        assert all(event['kind'].startswith('pool_') for event in later['events'])
        assert later['cursor'] >= cursor
        snapshot = reopened.dispatch('engine_status', {})
        assert snapshot['journal']['active_leases'] >= 0
    finally:
        reopened.close()
