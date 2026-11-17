"""Application-side large-resource external links: snapshot, HTTP, capability, MCP."""
from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.web import resource_api

ROOT = Path(__file__).resolve().parents[1]


class Resource:
    """Stand-in for the library's frozen Resource dataclass."""

    def __init__(self, *, env: str | None = "OPERON_ESMFOLD_PATH",
                 files=("model.pt", "tokenizer.json")) -> None:
        self.id = "esmfold"
        self.title = "ESMFold weights"
        self.kind = "directory"
        self.env = env
        self.roots: list = []
        self.files = list(files)
        self.expected_files = list(files)
        self.downloads = [{"url": "https://example.invalid/model.pt", "path": "model.pt"}]


class Common:
    """Minimal _resources_common replacement for one resource."""

    def __init__(self, resource: Resource, *, root: Path, roots=("/data/weights",),
                 state=None, helpers: bool = True) -> None:
        self.resource = resource
        self.root = root
        self.roots = list(roots)
        self.state = dict(state or {"linked": False, "source": None, "mode": None})
        if not helpers:
            for name in ("expected_files", "link_roots", "link_state"):
                setattr(self, name, None)

    def load_resources(self, path=None):
        return {self.resource.id: self.resource}

    def check_resource(self, resource, root=None):
        present = Path(self.root, "model.pt").is_file()
        return {"id": resource.id, "title": resource.title, "kind": resource.kind,
                "env": resource.env, "root": str(self.root),
                "present": present, "status": "ok" if present else "missing",
                "missing": [] if present else ["model.pt"], "files": list(resource.files),
                "receipt": None}

    def expected_files(self, resource):
        return list(resource.expected_files)

    def link_roots(self):
        return list(self.roots)

    def link_state(self, resource):
        return dict(self.state)


class LinkModule:
    """Records link/unlink calls and can raise like the real module."""

    def __init__(self) -> None:
        self.calls: list[dict] = []
        self.error: Exception | None = None
        self.existing = "/data/weights/other"
        self.unlinked: list = []

    def link(self, resource, source, *, replace=False, allowed_roots=None):
        self.calls.append({"source": source, "replace": replace,
                           "allowed_roots": list(allowed_roots or [])})
        if self.error is not None:
            raise self.error
        if not replace and self.existing and source != self.existing:
            raise ValueError(f"{self.existing} already linked; pass replace=True to replace it")
        return {"id": resource.id, "status": "linked", "mode": "symlink",
                "source": source, "root": "/data/weights/esmfold",
                "files": ["model.pt"], "probe": "ok"}

    def unlink(self, resource):
        self.unlinked.append(resource.id)
        return {"id": resource.id, "status": "unlinked", "root": "/data/weights/esmfold"}


class Plugins:
    def __init__(self, directory: Path, state: dict) -> None:
        self.directory = directory
        self._state = state

    def state(self):
        return dict(self._state)


class Service:
    def __init__(self, tmp_path: Path, root: Path) -> None:
        self.directory = tmp_path / "state"
        self.directory.mkdir(exist_ok=True)
        self.plugins = Plugins(tmp_path / "plugins", {
            "code_paths": ["code"],
            "library_release": {"version": "9.9.9"},
        })


@pytest.fixture()
def library(tmp_path, monkeypatch):
    """Fake code root plus a monkeypatched _modules (no real library needed)."""
    root = tmp_path / "code"
    root.mkdir()
    (root / "resources.json").write_text("{}\n", encoding="utf-8")
    (root / "esmfold_predict.EsmfoldPredictStep.md").write_text(
        "Set OPERON_ESMFOLD_PATH to the weights directory.\n", encoding="utf-8")
    (root / "unrelated.py").write_text("esmfold = 1\n", encoding="utf-8")
    (root / "resources.json").write_text('{"env": "OPERON_ESMFOLD_PATH"}\n', encoding="utf-8")
    (root / "huge.py").write_text("OPERON_ESMFOLD_PATH\n" + "x" * (300 * 1024), encoding="utf-8")
    (root / "model.pt").write_bytes(b"0123456789")

    resource = Resource()
    common = Common(resource, root=root, state={"linked": True,
                                                "source": "/data/weights/esmfold",
                                                "mode": "symlink"})
    link = LinkModule()
    fetch = SimpleNamespace(_target_root=lambda resource, base=None: root,
                            _open_url=lambda url, token_env: None)
    monkeypatch.setattr(resource_api, "_modules",
                        lambda service: (root, common, fetch, link))
    monkeypatch.setattr(resource_api, "_jobs", {})
    monkeypatch.setattr(resource_api, "_running", {})
    service = Service(tmp_path, root)
    return SimpleNamespace(service=service, root=root, common=common, link=link,
                           resource=resource)


def client_for(service) -> TestClient:
    app = FastAPI()
    resource_api.mount_resources(app, service)
    return TestClient(app)


def test_snapshot_reports_link_state_and_used_by(library):
    snapshot = resource_api.snapshot(library.service)
    assert snapshot["library"]["version"] == "9.9.9"
    item = snapshot["resources"][0]
    assert item["linked"] is True
    assert item["source"] == "/data/weights/esmfold"
    assert item["mode"] == "symlink"
    assert item["link_roots"] == ["/data/weights"]
    assert item["expected_files"] == ["model.pt", "tokenizer.json"]
    assert item["size_bytes"] == 10
    # The operator file mentioning the env variable, not resources.json or the 300 KB file.
    assert item["used_by"] == ["esmfold_predict"]
    assert item["downloads"] == [{"url": "https://example.invalid/model.pt", "path": "model.pt"}]


def test_snapshot_tolerates_library_without_link_module(library, monkeypatch):
    common = Common(library.resource, root=library.root,
                    state={"linked": False, "source": None, "mode": None}, helpers=False)
    monkeypatch.setattr(resource_api, "_modules",
                        lambda service: (library.root, common, SimpleNamespace(), None))
    snapshot = resource_api.snapshot(library.service)
    item = snapshot["resources"][0]
    assert item["linked"] is False
    assert item["link_roots"] == []
    assert item["expected_files"] == ["model.pt", "tokenizer.json"]
    assert item["used_by"] == ["esmfold_predict"]


def test_snapshot_without_env_falls_back_to_resource_id(tmp_path, monkeypatch):
    root = tmp_path / "code"
    root.mkdir()
    (root / "resources.json").write_text("{}\n", encoding="utf-8")
    (root / "esmfold_runner.py").write_text("resource_id = 'esmfold'\n", encoding="utf-8")
    resource = Resource(env=None)
    common = Common(resource, root=root, helpers=False)
    monkeypatch.setattr(resource_api, "_modules",
                        lambda service: (root, common, SimpleNamespace(), None))
    monkeypatch.setattr(resource_api, "_jobs", {})
    snapshot = resource_api.snapshot(Service(tmp_path, root))
    assert snapshot["resources"][0]["used_by"] == ["esmfold_runner"]


def test_post_link_passes_allowed_roots_and_records_operation(library):
    client = client_for(library.service)
    response = client.post("/api/resources/esmfold/link",
                           json={"source": "/data/weights/other"})
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "linked"
    assert body["mode"] == "symlink"
    assert body["operation"]
    assert library.link.calls == [{"source": "/data/weights/other", "replace": False,
                                   "allowed_roots": ["/data/weights"]}]
    job = client.get(f"/api/resources/operations/{body['operation']}").json()
    assert job["kind"] == "link"
    assert job["status"] == "linked"
    assert job["mode"] == "symlink"
    assert job["source"] == "/data/weights/other"


def test_link_conflict_returns_409_then_replace_succeeds(library):
    client = client_for(library.service)
    conflict = client.post("/api/resources/esmfold/link", json={"source": "/data/weights/new"})
    assert conflict.status_code == 409
    assert "replace=True" in conflict.json()["detail"]
    replaced = client.post("/api/resources/esmfold/link",
                           json={"source": "/data/weights/new", "replace": True})
    assert replaced.status_code == 200
    assert library.link.calls[-1]["replace"] is True


def test_link_rejection_returns_409(library):
    library.link.existing = None
    library.link.error = ValueError("source is outside the allowed link roots")
    response = client_for(library.service).post(
        "/api/resources/esmfold/link", json={"source": "/etc/passwd"})
    assert response.status_code == 409
    assert "allowed link roots" in response.json()["detail"]


def test_delete_unlinks_and_records_operation(library):
    client = client_for(library.service)
    response = client.delete("/api/resources/esmfold/link")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "unlinked"
    assert library.link.unlinked == ["esmfold"]
    job = client.get(f"/api/resources/operations/{body['operation']}").json()
    assert job["kind"] == "link"
    assert job["status"] == "unlinked"


def test_unknown_resource_is_404(library):
    client = client_for(library.service)
    assert client.post("/api/resources/nope/link",
                       json={"source": "/data/weights/x"}).status_code == 404
    assert client.delete("/api/resources/nope/link").status_code == 404
    assert client.post("/api/resources/nope/link",
                       json={"source": "/data/weights/x"}).json()["detail"] == "unknown resource: nope"


def test_link_unsupported_is_501(library, monkeypatch):
    common = Common(library.resource, root=library.root, helpers=False)
    monkeypatch.setattr(resource_api, "_modules",
                        lambda service: (library.root, common, SimpleNamespace(), None))
    client = client_for(library.service)
    assert client.post("/api/resources/esmfold/link",
                       json={"source": "/data/weights/x"}).status_code == 501
    assert client.delete("/api/resources/esmfold/link").status_code == 501


def test_capabilities_include_large_resource_link(tmp_path):
    from src.web.api import create_app
    from src.web.service import Settings

    settings = Settings(root=tmp_path, data_dir=tmp_path / ".studio",
                        dist_dir=ROOT / "frontend/dist", testing=True, code_root=ROOT)
    client = TestClient(create_app(settings))
    token = client.get("/api/bootstrap").json()["token"]
    client.headers["X-Studio-Token"] = token
    response = client.get("/api/v1/capabilities")
    assert response.status_code == 200
    capabilities = response.json()["capabilities"]
    assert "large-resource-link" in capabilities
    assert "large-resource-download" in capabilities
    paths = client.app.openapi()["paths"]
    link_route = paths["/api/v1/large-resources/{name}/link"]
    assert "post" in link_route and "delete" in link_route


def test_mcp_registers_link_tools():
    from operon.mcp_server import create_server

    server = create_server(SimpleNamespace())
    names = {tool.name for tool in asyncio.run(server.list_tools())}
    assert {"operon_resource_link", "operon_resource_unlink"} <= names


def test_link_and_unlink_payloads_are_normalized(library):
    """A library payload that says name/target still yields id/root for clients."""
    library.link.link = lambda resource, source, *, replace=False, allowed_roots=None: {
        "name": resource.id, "status": "linked", "mode": "symlink", "source": source}
    response = client_for(library.service).post(
        "/api/resources/esmfold/link", json={"source": "/data/weights/esmfold"})
    assert response.status_code == 200
    assert response.json()["id"] == "esmfold"

    library.link.unlink = lambda resource: {"name": resource.id, "status": "unlinked"}
    response = client_for(library.service).delete("/api/resources/esmfold/link")
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == "esmfold"
    assert "root" in body
