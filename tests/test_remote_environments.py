"""Remote environment RPC: snapshot, idempotent preparation, logs, dependency repair."""
import json
import threading
import time
from pathlib import Path
from types import SimpleNamespace

from operon import environment_install, environments
from operon.remote import server


def manifest(root: Path) -> Path:
    (root / 'operon').mkdir(parents=True, exist_ok=True)
    (root / 'operon' / 'environments.json').write_text(
        json.dumps({'version': 1, 'environments': {
            'demo': {'python': '3.11', 'imports': []},
            'other': {'python': '3.11', 'imports': []},
        }}), encoding='utf-8')
    return root


class FakeService:
    def __init__(self, directory, source, descriptors=None):
        self.directory = directory
        self.plugins = SimpleNamespace(source_root=source)
        self.dependencies = SimpleNamespace(calls=[], check=self._check)
        self._descriptors = descriptors or [{'id': 'alpha', 'resources': {'environment': 'demo'}}]
        self.catalog = {'operators': list(self._descriptors), 'readers': []}

    def _check(self, **kwargs):
        self.dependencies.calls.append(kwargs)
        return {'entries': []}

    def state(self):
        return {'descriptors': self._descriptors}


def make_service(tmp_path, monkeypatch):
    source = manifest(tmp_path / 'source')
    external = tmp_path / 'external'
    monkeypatch.setattr(environments, 'root', lambda: external)
    for name in list(server._ENVIRONMENT_JOBS):
        server._ENVIRONMENT_JOBS.pop(name, None)
    return FakeService(tmp_path / 'studio', source), external


def test_snapshot_reports_plan_for_every_environment(tmp_path, monkeypatch):
    fake, external = make_service(tmp_path, monkeypatch)
    snapshot = server.environment_snapshot(fake)
    assert 'error' not in snapshot
    assert Path(snapshot['root']) == external
    assert set(snapshot['environments']) == {'demo', 'other'}
    demo = snapshot['environments']['demo']
    assert demo['status'] == 'missing'
    assert demo['used_by'] == ['alpha']
    assert snapshot['running'] == {}


def test_snapshot_reports_plan_failure_without_raising(tmp_path, monkeypatch):
    fake, _ = make_service(tmp_path, monkeypatch)

    def boom(*args, **kwargs):
        raise RuntimeError('manifest exploded')

    monkeypatch.setattr(environment_install, 'plan', boom)
    snapshot = server.environment_snapshot(fake)
    assert snapshot['environments'] == {}
    assert 'manifest exploded' in snapshot['error']
    prepared = server.environment_prepare(fake, {'names': ['demo']})
    assert 'manifest exploded' in prepared['error']


def test_prepare_starts_only_requested_missing_environment(tmp_path, monkeypatch):
    fake, external = make_service(tmp_path, monkeypatch)
    started, release = [], threading.Event()

    def fake_prepare(name, root, source=None):
        started.append(name)
        assert Path(root) == external
        release.wait(5)

    monkeypatch.setattr(environment_install, 'prepare', fake_prepare)
    first = server.environment_prepare(fake, {'names': ['demo']})
    assert first['started'] == ['demo']
    deadline = time.time() + 5
    while 'demo' not in started and time.time() < deadline:
        time.sleep(0.01)
    assert started == ['demo']
    second = server.environment_prepare(fake, {'names': ['demo']})
    assert second['started'] == [], 'a running environment must not be started twice'
    release.set()
    deadline = time.time() + 5
    while 'demo' in server.environment_snapshot(fake)['running'] and time.time() < deadline:
        time.sleep(0.01)
    assert server.environment_snapshot(fake)['running'] == {}


def test_prepare_skips_ready_environment(tmp_path, monkeypatch):
    fake, external = make_service(tmp_path, monkeypatch)
    entry = environments.load(fake.plugins.source_root)['demo']
    python = external / 'demo' / 'bin' / 'python'
    python.parent.mkdir(parents=True)
    python.write_text('#!/bin/sh\n', encoding='utf-8')
    python.chmod(0o755)
    (external / 'demo' / 'receipt.json').write_text(
        json.dumps({'spec_sha256': environment_install.spec_sha256(entry)}), encoding='utf-8')
    called = []
    monkeypatch.setattr(environment_install, 'prepare', lambda *a, **k: called.append(a))
    result = server.environment_prepare(fake, {'names': ['demo']})
    assert result['environments']['demo']['status'] == 'ready'
    assert result['started'] == []
    assert called == []


def test_prepare_can_repair_dependencies(tmp_path, monkeypatch):
    fake, _ = make_service(tmp_path, monkeypatch)
    monkeypatch.setattr(environment_install, 'prepare', lambda *a, **k: None)
    result = server.environment_prepare(fake, {'names': ['demo'], 'dependencies': True})
    assert result['dependencies'] is True
    deadline = time.time() + 5
    while not fake.dependencies.calls and time.time() < deadline:
        time.sleep(0.01)
    assert fake.dependencies.calls == [{'repair': True, 'repair_r': True}]


def test_environment_log_returns_tail(tmp_path):
    directory = tmp_path / 'studio'
    (directory / 'environments').mkdir(parents=True)
    (directory / 'environments' / 'demo.log').write_text(
        '\n'.join(f'line {index}' for index in range(10)), encoding='utf-8')
    service = SimpleNamespace(directory=directory)
    result = server.environment_log(service, 'demo', 3)
    assert result['text'].splitlines() == ['line 7', 'line 8', 'line 9']
    assert server.environment_log(service, 'absent')['text'] == ''


def test_manager_wrappers_route_remote_methods():
    from src.web.remote_service import RemoteManager
    manager = RemoteManager.__new__(RemoteManager)
    seen = []
    manager.call = lambda key, method, params=None: seen.append((key, method, params)) or {'ok': True}
    assert manager.environments('srv') == {'ok': True}
    manager.prepare_environments('srv', ['demo'], True)
    manager.environment_log('srv', 'demo', 5)
    assert [item[1] for item in seen] == ['environments', 'environments_prepare', 'environments_log']
    assert seen[1][2] == {'names': ['demo'], 'dependencies': True}
    assert seen[2][2] == {'name': 'demo', 'limit': 5}
