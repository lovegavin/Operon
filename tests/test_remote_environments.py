"""Remote environment RPC: snapshot, idempotent preparation, logs, dependency repair."""
import json
import threading
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

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


def test_force_prepare_rebuilds_a_ready_environment(tmp_path, monkeypatch):
    """A ready environment still installs newly declared optional bindings on request."""
    fake, external = make_service(tmp_path, monkeypatch)
    entry = environments.load(fake.plugins.source_root)['demo']
    python = external / 'demo' / 'bin' / 'python'
    python.parent.mkdir(parents=True)
    python.write_text('#!/bin/sh\n', encoding='utf-8')
    python.chmod(0o755)
    (external / 'demo' / 'receipt.json').write_text(
        json.dumps({'spec_sha256': environment_install.spec_sha256(entry)}), encoding='utf-8')
    started = []
    release = threading.Event()

    def fake_prepare(name, root, source=None):
        started.append(name)
        release.wait(5)

    monkeypatch.setattr(environment_install, 'prepare', fake_prepare)
    result = server.environment_prepare(fake, {'names': ['demo'], 'force': True})
    assert result['started'] == ['demo']
    release.set()
    deadline = time.time() + 5
    while 'demo' in server.environment_snapshot(fake)['running'] and time.time() < deadline:
        time.sleep(0.01)
    assert started == ['demo']


def test_retry_asks_for_a_forced_prepare(tmp_path, monkeypatch):
    fake, _ = make_service(tmp_path, monkeypatch)
    calls = []
    monkeypatch.setattr(server, 'environment_prepare',
                        lambda service, payload=None: calls.append(payload) or {})
    server.environment_retry(fake, {'name': 'demo'})
    assert calls == [{'names': ['demo'], 'force': True}]


def test_prepare_can_repair_dependencies(tmp_path, monkeypatch):
    fake, _ = make_service(tmp_path, monkeypatch)
    monkeypatch.setattr(environment_install, 'prepare', lambda *a, **k: None)
    result = server.environment_prepare(fake, {'names': ['demo'], 'dependencies': True})
    assert result['dependencies'] is True
    deadline = time.time() + 5
    while not fake.dependencies.calls and time.time() < deadline:
        time.sleep(0.01)
    assert fake.dependencies.calls == [{'repair': True, 'repair_r': True, 'ids': ['alpha']}]


def test_environment_log_returns_tail(tmp_path):
    directory = tmp_path / 'studio'
    (directory / 'environments').mkdir(parents=True)
    (directory / 'environments' / 'demo.log').write_text(
        '\n'.join(f'line {index}' for index in range(10)), encoding='utf-8')
    service = SimpleNamespace(directory=directory)
    result = server.environment_log(service, 'demo', 3)
    assert result['text'].splitlines() == ['line 7', 'line 8', 'line 9']
    assert server.environment_log(service, 'absent')['text'] == ''


def test_environment_log_reads_the_log_the_installer_writes(tmp_path):
    directory = tmp_path / 'studio'
    logs = directory / 'environments' / '.operon-environment-logs'
    logs.mkdir(parents=True)
    (logs / 'demo.log').write_text('one\ntwo\nthree', encoding='utf-8')
    service = SimpleNamespace(directory=directory)
    result = server.environment_log(service, 'demo', 2)
    assert result['text'].splitlines() == ['two', 'three']
    assert result['path'].endswith('.operon-environment-logs/demo.log')


def test_manager_wrappers_route_remote_methods():
    from src.web.remote_service import RemoteManager
    manager = RemoteManager.__new__(RemoteManager)
    seen = []
    manager.call = lambda key, method, params=None: seen.append((key, method, params)) or {'ok': True}
    assert manager.environments('srv') == {'ok': True}
    manager.prepare_environments('srv', ['demo'], True)
    manager.environment_log('srv', 'demo', 5)
    assert [item[1] for item in seen] == ['environments', 'environments_prepare', 'environments_log']
    assert seen[1][2] == {'names': ['demo'], 'dependencies': True, 'force': False}
    assert seen[2][2] == {'name': 'demo', 'limit': 5}


def test_remote_manager_forwards_environment_cancel() -> None:
    from src.web.remote_service import RemoteManager

    calls = []

    class Connection:
        connected = True

        def call(self, method, params=None):
            calls.append((method, params))
            return {'cancelled': True}

    manager = RemoteManager.__new__(RemoteManager)
    manager.state = {'profiles': {'srv': {}}}
    manager.connections = {'srv': Connection()}
    result = manager.cancel_environment('srv', 'esm3')
    assert result == {'cancelled': True}
    assert calls == [('environments_cancel', {'name': 'esm3'})]


def test_remote_manager_forwards_dependency_install() -> None:
    from src.web.remote_service import RemoteManager

    calls = []

    class Connection:
        connected = True

        def call(self, method, params=None):
            calls.append((method, params))
            return {'installed': {}}

    manager = RemoteManager.__new__(RemoteManager)
    manager.state = {'profiles': {'srv': {}}}
    manager.connections = {'srv': Connection()}
    assert manager.install_dependency('srv', 'esm3', {'kind': 'import', 'name': 'torch'}) == {'installed': {}}
    assert calls == [('environments_dependency', {'name': 'esm3', 'kind': 'import', 'requirement': 'torch'})]


def test_remote_manager_forwards_environment_repair() -> None:
    from src.web.remote_service import RemoteManager

    calls = []

    class Connection:
        connected = True

        def call(self, method, params=None):
            calls.append((method, params))
            return {'repair': {'name': 'demo', 'rewritten': 0}}

    manager = RemoteManager.__new__(RemoteManager)
    manager.state = {'profiles': {'srv': {}}}
    manager.connections = {'srv': Connection()}
    assert manager.environment_repair('srv', 'demo') == {
        'repair': {'name': 'demo', 'rewritten': 0}}
    assert calls == [('environments_repair', {'name': 'demo'})]


def test_server_environment_repair_requires_an_installed_environment(tmp_path, monkeypatch):
    from operon.documents import CommandError

    fake, external = make_service(tmp_path, monkeypatch)
    with pytest.raises(CommandError) as failure:
        server.environment_repair(fake, {'name': 'demo'})
    assert failure.value.code == 'unknown_environment'
    (external / 'demo').mkdir(parents=True, exist_ok=True)
    result = server.environment_repair(fake, {'name': 'demo'})
    assert result['repair'] == {'name': 'demo',
                                'directory': str(external / 'demo'), 'rewritten': 0}


def test_prepare_uses_needs_preparation_for_incomplete_status(tmp_path, monkeypatch):
    """An environment whose resources are incomplete must still be prepared."""
    fake, external = make_service(tmp_path, monkeypatch)
    monkeypatch.setattr(environment_install, 'plan', lambda *a, **k: {
        'demo': {'status': 'incomplete', 'used_by': ['alpha'],
                 'location': str(external / 'demo')}})
    started, release = [], threading.Event()

    def fake_prepare(name, root, source=None):
        started.append(name)
        release.wait(5)

    monkeypatch.setattr(environment_install, 'prepare', fake_prepare)
    result = server.environment_prepare(fake, {'names': ['demo']})
    assert result['started'] == ['demo']
    release.set()
    deadline = time.time() + 5
    while 'demo' in server.environment_snapshot(fake)['running'] and time.time() < deadline:
        time.sleep(0.01)
