"""4.1.6: the desktop can observe the shared pool that serves a remote workspace."""
from types import SimpleNamespace

import pytest

import operon.managed_pool as managed_pool
from operon.remote.server import pool_snapshot
from src.web.remote_service import RemoteManager


def test_pool_snapshot_reports_owner_and_active_jobs(monkeypatch):
    monkeypatch.setattr(managed_pool, 'inspect_pool', lambda: {
        'available': True, 'managed': True, 'version': '4.0.9',
        'implementation': 'a' * 64, 'owner': {'pid': 195690},
        'closing': False, 'sessions': 1})
    service = SimpleNamespace(history=lambda: [
        {'id': 'req-1', 'status': 'queued', 'title': 'CSV to PCA', 'logs_complete': False},
        {'id': 'req-2', 'status': 'complete', 'title': 'done'},
    ])
    result = pool_snapshot(service)
    assert result['available'] is True
    assert result['version'] == '4.0.9'
    assert result['owner'] == {'pid': 195690}
    assert result['active_count'] == 1
    assert result['active_jobs'][0] == {'id': 'req-1', 'status': 'queued',
                                        'title': 'CSV to PCA', 'updated_at': None}


def test_pool_snapshot_never_fails_a_connection(monkeypatch):
    def broken():
        raise OSError('admission directory is unreadable')
    monkeypatch.setattr(managed_pool, 'inspect_pool', broken)
    service = SimpleNamespace(history=lambda: [])
    result = pool_snapshot(service)
    assert result['available'] is False
    assert 'admission directory is unreadable' in result['error']


def test_remote_status_reports_and_caches_pool_view(tmp_path):
    service = SimpleNamespace(directory=tmp_path)
    manager = RemoteManager(service)
    key = 'a' * 32
    manager.state['profiles'][key] = {'id': key, 'name': 'srv', 'host': 'example.org'}
    calls = []

    def call(method, params):
        calls.append((method, params))
        return {'available': True, 'version': '4.1.5', 'owner': {'pid': 7},
                'active_count': 0, 'active_jobs': []}

    manager.connections[key] = SimpleNamespace(connected=True, call=call, close=lambda: None)
    try:
        first = manager.status()[0]
        assert first['pool']['version'] == '4.1.5'
        assert calls == [('pool_info', {})]
        second = manager.status()[0]
        assert second['pool']['version'] == '4.1.5'
        assert len(calls) == 1  # cached for a few seconds, not one SSH round trip per poll
    finally:
        manager.disconnect(key)


def test_remote_status_survives_an_old_server(tmp_path):
    from operon.remote.client import RemoteError
    service = SimpleNamespace(directory=tmp_path)
    manager = RemoteManager(service)
    key = 'b' * 32
    manager.state['profiles'][key] = {'id': key, 'name': 'old', 'host': 'example.org'}

    def call(method, params):
        raise RemoteError('Unknown remote operation: pool_info', code='unknown_operation')

    manager.connections[key] = SimpleNamespace(connected=True, call=call, close=lambda: None)
    try:
        entry = manager.status()[0]
        assert entry['pool']['available'] is False
        assert entry['pool']['unsupported'] is True
    finally:
        manager.disconnect(key)
