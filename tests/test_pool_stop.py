"""4.1.8: shared-pool stop/force-clear behaviour on the desktop, bridge and remote."""
from __future__ import annotations

import asyncio
import json
import threading
from pathlib import Path

import pytest

from operon import managed_pool
from operon.remote import server as remote_server
from src.web import remote_service


def pool_root(tmp_path: Path) -> Path:
    root = tmp_path / 'managed-pool'
    root.mkdir(parents=True, exist_ok=True)
    return root


def instance(root: Path, pid: int = 4242) -> None:
    (root / 'instance.json').write_text(json.dumps({
        'owner': {'pid': pid, 'created': 0},
        'version': '4.1.7',
        'implementation': 'x',
        'address': [127, 0, 0, 1, 1],
    }), encoding='utf-8')


@pytest.fixture()
def pool(monkeypatch, tmp_path):
    root = pool_root(tmp_path)
    monkeypatch.setattr(managed_pool, 'locations', lambda settings=None: (tmp_path / 'admission', root))
    return root


def test_stop_pool_without_running_owner_clears_stale_state(pool):
    instance(pool, pid=999999)
    result = managed_pool.stop_pool()
    assert result['stopped'] is True
    assert result['forced'] is False
    assert not pool.exists()


def test_stop_pool_busy_raises_unless_forced(pool, monkeypatch):
    instance(pool)
    monkeypatch.setattr(managed_pool, '_alive', lambda record: True)

    class Client:
        def request(self, method):
            raise managed_pool.PoolClientError('tasks active', code='pool_busy')

    monkeypatch.setattr(managed_pool, '_client', lambda record, root: Client())
    with pytest.raises(managed_pool.PoolClientError):
        managed_pool.stop_pool()
    result = managed_pool.stop_pool(force=True)
    assert result['stopped'] is True and result['forced'] is True
    assert result['active_tasks_cancelled'] is True
    assert not pool.exists()


def test_remote_pool_stop_reports_busy_and_success(monkeypatch):
    class Service:
        pass

    monkeypatch.setattr(managed_pool, 'stop_pool',
                        lambda force=False: (_ for _ in ()).throw(
                            managed_pool.PoolClientError('active', code='pool_busy')))
    busy = remote_server.pool_stop(Service(), {'force': False})
    assert busy['stopped'] is False and busy['busy'] is True and 'active' in busy['error']

    monkeypatch.setattr(managed_pool, 'stop_pool',
                        lambda force=False: {'stopped': True, 'forced': bool(force)})
    ok = remote_server.pool_stop(Service(), {'force': True})
    assert ok == {'stopped': True, 'forced': True}


def test_remote_manager_pool_stop_clears_cache():
    manager = object.__new__(remote_service.RemoteManager)
    manager.lock = threading.RLock()
    manager.pools = {'srv': (0.0, {'available': True})}
    calls = []
    manager.call = lambda key, method, params=None: calls.append((key, method, params)) or {'stopped': True}
    assert manager.pool_stop('srv', force=True) == {'stopped': True}
    assert calls == [('srv', 'pool_stop', {'force': True})]
    assert manager.pools == {}


def test_mcp_exposes_pool_tools():
    from operon import mcp_server
    tools = asyncio.run(mcp_server.create_server(object()).list_tools())
    names = {tool.name for tool in tools}
    assert {'operon_pool_status', 'operon_pool_stop', 'operon_remote_pool_stop'} <= names
