"""Remote large-resource links use the same authenticated RPC channel."""
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.web.remote_api import mount_remote


class Manager:
    def __init__(self):
        self.calls = []

    def call(self, key, method, params=None):
        self.calls.append((key, method, params))
        return {'method': method, 'ok': True}


def client():
    manager = Manager()
    app = FastAPI()
    mount_remote(app, SimpleNamespace(remotes=manager))
    return TestClient(app), manager


def test_list_remote_resources_uses_the_agent_method():
    http, manager = client()
    body = http.get('/api/remote/srv/resources').json()
    assert body == {'method': 'resources', 'ok': True}
    assert manager.calls == [('srv', 'resources', None)]


def test_link_remote_resource_forwards_source_and_replace():
    http, manager = client()
    response = http.post('/api/remote/srv/resources/esm2/link',
                         json={'source': '/srv/data/esm2', 'replace': True})
    assert response.status_code == 200
    assert manager.calls == [('srv', 'resources_link',
                              {'name': 'esm2', 'source': '/srv/data/esm2', 'replace': True})]


def test_link_without_a_body_still_forwards_an_empty_source():
    http, manager = client()
    assert http.post('/api/remote/srv/resources/esm2/link').status_code == 200
    assert manager.calls == [('srv', 'resources_link',
                              {'name': 'esm2', 'source': '', 'replace': False})]


def test_unlink_remote_resource_forwards_the_name():
    http, manager = client()
    assert http.delete('/api/remote/srv/resources/esm2/link').status_code == 200
    assert manager.calls == [('srv', 'resources_unlink', {'name': 'esm2'})]


def test_remote_agent_dispatches_resource_methods_to_the_local_api(monkeypatch):
    from operon.remote.server import RemoteService
    from src.web import resource_api

    seen = []
    monkeypatch.setattr(resource_api, 'snapshot', lambda service: {'resources': []})
    monkeypatch.setattr(resource_api, 'link',
                        lambda service, name, source, replace=False: seen.append(
                            (name, source, replace)) or {'status': 'linked'})
    monkeypatch.setattr(resource_api, 'unlink',
                        lambda service, name: seen.append((name,)) or {'status': 'unlinked'})

    agent = RemoteService.__new__(RemoteService)
    agent.service = SimpleNamespace()
    agent.transport_leases = {}
    assert agent._dispatch('resources', None) == {'resources': []}
    assert agent._dispatch('resources_link',
                           {'name': 'esm2', 'source': '/data/esm2', 'replace': True}) == {
        'status': 'linked'}
    assert agent._dispatch('resources_unlink', {'name': 'esm2'}) == {'status': 'unlinked'}
    assert seen == [('esm2', '/data/esm2', True), ('esm2',)]
