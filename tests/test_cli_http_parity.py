"""CLI/HTTP parity for environment repair, install-all and resource verbs."""
import pytest

from operon import cli


class FakeClient:
    def __init__(self, *args, **kwargs):
        self.scopes = list(kwargs.get('scopes') or [])
        self.calls = []

    def request(self, path, payload=None, *, method=None):
        self.calls.append((path, payload, method))
        return {'ok': True}

    def close(self):
        pass


@pytest.fixture
def clients(monkeypatch):
    created = []

    def factory(*args, **kwargs):
        client = FakeClient(*args, **kwargs)
        created.append(client)
        return client

    monkeypatch.setattr(cli, 'Client', factory)
    return created


def run(clients, tmp_path, *argv):
    cli.execute(cli.parser().parse_args(['--workspace', str(tmp_path), *argv]))
    return clients[-1]


def test_install_without_names_prepares_everything(clients, tmp_path):
    client = run(clients, tmp_path, 'environment', 'install')
    assert client.calls == [('/v1/environments/prepare', {}, None)]
    assert 'plugins' in client.scopes and 'run' not in client.scopes


def test_install_with_names_keeps_the_explicit_list(clients, tmp_path):
    client = run(clients, tmp_path, 'environment', 'install', 'demo', 'other')
    assert client.calls == [('/v1/environments/prepare', {'names': ['demo', 'other']}, None)]


def test_repair_uses_the_authenticated_v1_route(clients, tmp_path):
    client = run(clients, tmp_path, 'environment', 'repair', 'demo')
    assert client.calls == [('/v1/environments/demo/repair', {}, None)]
    assert 'plugins' in client.scopes and 'run' not in client.scopes


def test_remote_repair_targets_the_bridge(clients, tmp_path):
    client = run(clients, tmp_path, 'environment', 'repair', 'demo', '--profile', 'srv')
    assert client.calls == [('/remote/srv/environments/demo/repair', {}, None)]
    assert 'plugins' in client.scopes


def test_remote_cancel_keeps_the_profile(clients, tmp_path):
    client = run(clients, tmp_path, 'environment', 'cancel', 'demo', '--profile', 'srv')
    assert client.calls == [('/remote/srv/environments/demo/cancel', {}, None)]
    assert {'plugins', 'run'} <= set(client.scopes)


def test_unlink_sends_delete(clients, tmp_path):
    client = run(clients, tmp_path, 'resources', 'unlink', 'esm2')
    path, payload, method = client.calls[0]
    assert method == 'DELETE' and payload == {}
    assert path == '/v1/large-resources/esm2/link?unit=tree'


def test_local_resource_cancel_is_run_scoped(clients, tmp_path):
    client = run(clients, tmp_path, 'resources', 'cancel', 'esm2')
    assert client.calls[0][0] == '/v1/large-resources/esm2/cancel'
    assert 'run' in client.scopes


def test_remote_resource_download_is_run_scoped(clients, tmp_path):
    client = run(clients, tmp_path, 'resources', 'download', 'esm2', '--profile', 'srv')
    assert client.calls[0][0] == '/remote/srv/resources/esm2/download'
    assert 'run' in client.scopes and 'plugins' not in client.scopes


def test_resource_log_honours_limit(clients, tmp_path):
    client = run(clients, tmp_path, 'resources', 'log', 'esm2', '--limit', '7')
    assert client.calls[0][0] == '/v1/large-resources/esm2/log?limit=7'
