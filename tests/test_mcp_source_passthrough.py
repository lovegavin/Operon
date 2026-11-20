"""Regression tests for the known MCP/HTTP remote-source parity gap.

Two independent losses make `operon_remote_source` availability-only:

1. `operon/mcp_server.py:1111-1118` accepts only `profile_id` and always posts `{}`.
2. `operon/control_api.py:855-858` accepts no body and calls `source` without params.

The desktop route `src/web/remote_api.py:159-161` already forwards the payload.
Both tests are xfail (non-strict) because the audit must not modify product code;
remove the markers when the two-line pass-through is applied.
"""
import asyncio

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from operon import control_api
from operon.mcp_server import create_server


class Remotes:
    def __init__(self):
        self.calls = []

    def call(self, key, method, params=None):
        self.calls.append((key, method, params))
        return {"available": True}


class Bridge:
    id = "test-instance"

    def actor(self, request, scope="context"):
        return "user"


class Client:
    def __init__(self):
        self.calls = []

    def request(self, path, payload=None):
        self.calls.append((path, payload))
        return {"available": True}


@pytest.mark.xfail(reason="known gap: /api/v1/remotes/{key}/source ignores request body", strict=True)
def test_v1_remote_source_forwards_payload(monkeypatch):
    # mount_control also mounts viewer/storage/plan APIs; those are unrelated
    # to this route and need a full Application, so stub their mounters.
    import operon.viewer_api
    import operon.storage_api
    import operon.plan_api

    monkeypatch.setattr(operon.viewer_api, "mount_viewers", lambda *a, **k: None)
    monkeypatch.setattr(operon.storage_api, "mount_storage", lambda *a, **k: None)
    monkeypatch.setattr(operon.plan_api, "mount_plans", lambda *a, **k: None)

    remotes = Remotes()

    class Service:
        pass

    service = Service()
    service.remotes = remotes

    class Application:
        pass

    application = Application()
    application.service = service

    app = FastAPI()
    control_api.mount_control(app, application, Bridge())
    client = TestClient(app)

    payload = {"path": "reads/a.fastq", "reader": "fastq"}
    response = client.post("/api/v1/remotes/r1/source", json=payload)

    assert response.status_code == 200
    assert remotes.calls == [("r1", "source", payload)]


@pytest.mark.xfail(reason="known gap: operon_remote_source accepts only profile_id", strict=True)
def test_mcp_remote_source_sends_payload():
    client = Client()
    server = create_server(client)
    asyncio.run(server.call_tool(
        "operon_remote_source",
        {"profile_id": "r1", "path": "reads/a.fastq", "reader": "fastq"},
    ))
    assert client.calls == [
        ("/v1/remotes/r1/source", {"path": "reads/a.fastq", "reader": "fastq"}),
    ]