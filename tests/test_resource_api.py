import time
from pathlib import Path
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

import src.web.resource_api as resource_api


class FakeResource:
    id = "esm2"
    downloads = ({"path": "esm2_t6_8M_UR50D.pt", "url": "https://example.test/x", "bytes": 5},)


class FakeCommon:
    @staticmethod
    def load_resources(path):
        return {"esm2": FakeResource()}

    @staticmethod
    def check_resource(resource):
        return {"id": resource.id, "present": False, "files": 0, "size_mb": 0.0}

    @staticmethod
    def resolve_root(resource):
        return None


class FakeFetch:
    @staticmethod
    def _download_one(entry, root, overwrite=False):
        target = Path(root) / entry["path"]
        target.write_bytes(b"hello")
        return {"status": "downloaded", "bytes": 5}


def _root(tmp_path):
    root = tmp_path / "code" / "operon_core" / "steps"
    root.mkdir(parents=True)
    (root / "resources.json").write_text("{}")
    return root.parent.parent


def test_snapshot_download_and_log(tmp_path, monkeypatch):
    service = SimpleNamespace(
        directory=tmp_path,
        plugins=SimpleNamespace(
            directory=tmp_path / "library",
            state=lambda: {"code_paths": ["environments/x/code"],
                           "library_release": {"library_version": "0.1.3"}},
        ),
    )
    root = _root(tmp_path)
    monkeypatch.setattr(resource_api, "_modules", lambda svc: (root, FakeCommon, FakeFetch))

    app = FastAPI()
    resource_api.mount_resources(app, service)
    client = TestClient(app)

    listing = client.get("/api/resources")
    assert listing.status_code == 200
    assert listing.json()["resources"][0]["id"] == "esm2"

    started = client.post("/api/resources/esm2/download", json={})
    assert started.status_code == 200
    job_id = started.json()["id"]

    for _ in range(100):
        payload = client.get("/api/resources").json()
        job = next(item for item in payload["operations"] if item["id"] == job_id)
        if job["status"] != "running":
            break
        time.sleep(0.02)
    assert job["status"] == "succeeded"
    assert job["bytes"] == 5

    log = client.get("/api/resources/esm2/log").json()
    assert "OK esm2_t6_8M_UR50D.pt downloaded 5" in log["text"]


def test_unknown_resource_is_404(tmp_path, monkeypatch):
    root = _root(tmp_path)
    monkeypatch.setattr(resource_api, "_modules", lambda svc: (root, FakeCommon, FakeFetch))
    service = SimpleNamespace(directory=tmp_path, plugins=SimpleNamespace(directory=tmp_path))
    app = FastAPI()
    resource_api.mount_resources(app, service)
    client = TestClient(app, raise_server_exceptions=False)
    assert client.post("/api/resources/nope/download", json={}).status_code == 404
