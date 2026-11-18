from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from operon.bridge import Bridge


class FakeRemotes:
    def __init__(self):
        self.calls = []

    def call(self, key, method, params=None):
        self.calls.append((key, method, params))
        return {"key": key, "method": method, "params": params}


def _client(tmp_path):
    app = FastAPI()
    remotes = FakeRemotes()
    service = SimpleNamespace(remotes=remotes, directory=tmp_path)
    bridge = Bridge(app, service, "studio-token")
    client = TestClient(app)
    response = client.post("/api/agent/connect", headers={"x-operon-bridge": bridge.secret},
                           json={"scopes": ["context", "edit", "run"], "name": "test"})
    assert response.status_code == 200
    return client, remotes, {"authorization": "Bearer " + response.json()["token"]}


def test_bridge_forwards_remote_resource_reads(tmp_path):
    client, remotes, headers = _client(tmp_path)
    response = client.get("/api/agent/remote/srv/resources", headers=headers)
    assert response.status_code == 200
    assert remotes.calls[-1] == ("srv", "resources", None)


def test_bridge_forwards_remote_resource_link_and_unlink(tmp_path):
    client, remotes, headers = _client(tmp_path)
    linked = client.post("/api/agent/remote/srv/resources/esm2/link", headers=headers,
                         json={"source": "D:\\msa-data", "replace": True})
    assert linked.status_code == 200
    assert remotes.calls[-1] == ("srv", "resources_link",
                                 {"name": "esm2", "source": "D:\\msa-data", "replace": True})
    unlinked = client.delete("/api/agent/remote/srv/resources/esm2/link", headers=headers)
    assert unlinked.status_code == 200
    assert remotes.calls[-1] == ("srv", "resources_unlink", {"name": "esm2"})
