"""Route collections become removable units once installed."""

import json
import sys
from pathlib import Path

ROOT = Path("/home/gavin/Operon-540")
sys.path.insert(0, str(ROOT))

from operon import library_install  # noqa: E402


class FakeRoutes:
    def __init__(self, directory):
        self.directory = directory
        self.deleted = []

    def manage_item(self, key, action):
        if action != "delete":
            raise AssertionError(action)
        self.deleted.append(key)
        if key not in {"route_a", "route_b"}:
            raise KeyError(key)


class FakeService:
    def __init__(self, directory):
        self.routes = FakeRoutes(directory)


def _write(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def test_collections_are_listed_after_import(tmp_path):
    routes = tmp_path / "routes"
    _write(routes / "collections" / "bundle-0.1.0.json", {
        "name": "bundle-0.1.0",
        "imported_at": "2026-11-17T12:00:00+00:00",
        "routes": [{"key": "route_a", "name": "A"}, {"key": "route_b", "name": "B"}],
    })
    service = FakeService(routes)
    listed = library_install.route_collections(service)
    assert listed["count"] == 1
    assert listed["collections"][0]["slug"] == "bundle-0.1.0"
    assert listed["collections"][0]["count"] == 2


def test_uninstall_removes_routes_records_and_parameters(tmp_path):
    routes = tmp_path / "routes"
    _write(routes / "collections" / "bundle.json", {
        "name": "bundle",
        "imported_at": "2026-11-17T12:00:00+00:00",
        "routes": [
            {"key": "route_a", "name": "A", "workflow_id": "route_aaa"},
            {"key": "route_b", "name": "B", "workflow_id": "route_bbb"},
        ],
    })
    _write(routes / "route_aaa.json", {
        "id": "route_aaa",
        "parameters_file": "parameters/route_aaa.json",
        "execution_file": "execution/route_aaa.json",
    })
    _write(routes / "route_bbb.json", {"id": "route_bbb"})
    _write(routes / "parameters" / "route_aaa.json", {"values": {}})
    _write(routes / "execution" / "route_aaa.json", {"settings": {}})
    service = FakeService(routes)

    result = library_install.uninstall_routes_collection(service, "bundle")

    assert result["removed"] == 2
    assert service.routes.deleted == ["route_a", "route_b"]
    assert not (routes / "route_aaa.json").exists()
    assert not (routes / "route_bbb.json").exists()
    assert not (routes / "parameters" / "route_aaa.json").exists()
    assert not (routes / "execution" / "route_aaa.json").exists()
    assert not (routes / "collections" / "bundle.json").exists()
    assert library_install.route_collections(service)["count"] == 0


def test_uninstall_rejects_unknown_collection(tmp_path):
    service = FakeService(tmp_path / "routes")
    try:
        library_install.uninstall_routes_collection(service, "missing")
    except ValueError as error:
        assert "not imported" in str(error)
    else:
        raise AssertionError("unknown collection must raise")


def test_slug_is_filesystem_safe():
    assert library_install._collection_slug("Routes 0.1.0 / final") == "routes-0.1.0-final"
    assert library_install._collection_slug("") == "collection"
