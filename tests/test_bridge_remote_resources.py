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

    def environment_repair(self, key, name):
        self.calls.append((key, "environments_repair", {"name": name}))
        return {"key": key, "method": "environments_repair", "params": {"name": name}}


def _client(tmp_path):
    app = FastAPI()
    remotes = FakeRemotes()
    service = SimpleNamespace(remotes=remotes, directory=tmp_path)
    bridge = Bridge(app, service, "studio-token")
    client = TestClient(app)
    response = client.post("/api/agent/connect", headers={"x-operon-bridge": bridge.secret},
                           json={"scopes": ["context", "edit", "run", "plugins"], "name": "test"})
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
                                 {"name": "esm2", "source": "D:\\msa-data", "replace": True,
                                  "unit": ""})
    unlinked = client.delete("/api/agent/remote/srv/resources/esm2/link", headers=headers)
    assert unlinked.status_code == 200
    assert remotes.calls[-1] == ("srv", "resources_unlink", {"name": "esm2", "unit": ""})


def test_bridge_forwards_remote_resource_cancel_and_log(tmp_path):
    client, remotes, headers = _client(tmp_path)
    cancelled = client.post("/api/agent/remote/srv/resources/esm2/cancel", headers=headers)
    assert cancelled.status_code == 200
    assert remotes.calls[-1] == ("srv", "resources_cancel", {"name": "esm2"})
    log = client.get("/api/agent/remote/srv/resources/esm2/log", headers=headers,
                     params={"limit": 100})
    assert log.status_code == 200
    assert remotes.calls[-1] == ("srv", "resources_log", {"name": "esm2", "limit": 100})


def test_bridge_forwards_remote_environment_repair(tmp_path):
    client, remotes, headers = _client(tmp_path)
    reply = client.post("/api/agent/remote/srv/environments/esm3/repair", headers=headers)
    assert reply.status_code == 200
    assert remotes.calls[-1] == ("srv", "environments_repair", {"name": "esm3"})


def test_bridge_forwards_remote_jobs(tmp_path):
    client, remotes, headers = _client(tmp_path)
    listed = client.get("/api/agent/remote/srv/jobs", headers=headers)
    assert listed.status_code == 200
    assert listed.json() == {"items": {"key": "srv", "method": "history", "params": None}}
    assert remotes.calls[-1] == ("srv", "history", None)
    detail = client.get("/api/agent/remote/srv/jobs/j1", headers=headers)
    assert detail.status_code == 200
    assert remotes.calls[-1] == ("srv", "job", {"job_id": "j1"})
    cancelled = client.post("/api/agent/remote/srv/jobs/j1/cancel", headers=headers)
    assert cancelled.status_code == 200
    assert remotes.calls[-1] == ("srv", "cancel", {"job_id": "j1"})
