"""Focused tests for the large-resource API helpers (5.4.0).

The download path is exercised through a stub opener so the tests never touch
the network; they pin the safety rules (https only, no traversal), progress
accounting and the operation registry.
"""
from __future__ import annotations

import threading
from pathlib import Path

import pytest

from src.web import resource_api


class Entry(dict):
    pass


class Resource:
    def __init__(self, downloads, name="esm2"):
        self.name = name
        self.downloads = [Entry(item) for item in downloads]


def test_download_rejects_plain_http(tmp_path: Path) -> None:
    resource = Resource([{"url": "http://example.com/a.pt", "path": "a.pt"}])
    with pytest.raises(ValueError, match="https"):
        resource_api._download(resource.downloads[0], tmp_path, overwrite=False,
                               event=threading.Event(), job={}, opener=lambda url, token: None)


@pytest.mark.parametrize("relative", ["../escape.bin", "/abs/path.bin", ""])
def test_download_rejects_unsafe_paths(tmp_path: Path, relative: str) -> None:
    entry = {"url": "https://example.com/x.bin", "path": relative}
    with pytest.raises(ValueError):
        resource_api._download(entry, tmp_path, overwrite=False,
                               event=threading.Event(), job={}, opener=lambda url, token: None)


class _Response:
    def __init__(self, payload: bytes):
        self.payload = payload
        self.offset = 0

    def read(self, size: int) -> bytes:
        chunk = self.payload[self.offset:self.offset + size]
        self.offset += len(chunk)
        return chunk

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def test_download_writes_and_verifies(tmp_path: Path) -> None:
    payload = b"weights" * 100
    entry = {"url": "https://example.com/w.bin", "path": "sub/w.bin", "bytes": len(payload)}
    job = {"completed_bytes": 0}
    result = resource_api._download(entry, tmp_path, overwrite=False, event=threading.Event(),
                                    job=job, opener=lambda url, token: _Response(payload))
    assert result["status"] == "downloaded"
    assert (tmp_path / "sub/w.bin").read_bytes() == payload
    assert job["bytes"] == len(payload)


def test_download_rejects_size_mismatch(tmp_path: Path) -> None:
    entry = {"url": "https://example.com/w.bin", "path": "w.bin", "bytes": 999}
    with pytest.raises(ValueError, match="size mismatch"):
        resource_api._download(entry, tmp_path, overwrite=False, event=threading.Event(),
                               job={}, opener=lambda url, token: _Response(b"short"))
    assert not (tmp_path / "w.bin").exists()


def test_download_honours_cancellation(tmp_path: Path) -> None:
    event = threading.Event()
    event.set()
    entry = {"url": "https://example.com/w.bin", "path": "w.bin"}
    with pytest.raises(resource_api._Cancelled):
        resource_api._download(entry, tmp_path, overwrite=False, event=event,
                               job={}, opener=lambda url, token: _Response(b"data"))
    assert not (tmp_path / "w.bin.part").exists()


def test_part_bytes_counts_partials(tmp_path: Path) -> None:
    resource = Resource([{"url": "https://example.com/a", "path": "a.bin"},
                         {"url": "https://example.com/b", "path": "nested/b.bin"}])
    (tmp_path / "a.bin.part").write_bytes(b"x" * 10)
    (tmp_path / "nested").mkdir()
    (tmp_path / "nested/b.bin.part").write_bytes(b"y" * 5)
    assert resource_api._part_bytes(tmp_path, resource) == 15


def test_operation_registry_roundtrip() -> None:
    key = "unit-test-operation"
    resource_api._jobs[key] = {"id": key, "status": "running"}
    try:
        assert resource_api.operation(key)["status"] == "running"
        assert resource_api.operation("missing") is None
    finally:
        resource_api._jobs.pop(key, None)

class _StubResource:
    id = 'openfold'
    env = 'OPERON_OPENFOLD_PATH'
    downloads: list = []


class _StubCommon:
    def load_resources(self, manifest):
        return {'openfold': _StubResource()}

    def check_resource(self, resource):
        return {'id': resource.id, 'present': False, 'status': 'missing', 'root': '/nowhere'}


class _StubPlugins:
    directory = '/library'

    def state(self):
        return {'library_release': {'version': '0.1.29'}}


class _StubService:
    plugins = _StubPlugins()
    catalog = {
        'operators': [
            {'id': 'openfold_predict', 'resources': {'environment': 'openfold'}},
            {'id': 'openfold_score', 'resources': {'environment': 'openfold'}},
            {'id': 'plain_operator', 'resources': {}},
            {'id': 'no_resources_at_all'},
        ],
        'readers': [{'id': 'openfold_reader', 'resources': {'environment': 'openfold'}}],
    }


def test_environment_map_follows_descriptor_resources() -> None:
    found = resource_api._environment_map(_StubService())
    assert found == {
        'openfold_predict': 'openfold',
        'openfold_score': 'openfold',
        'openfold_reader': 'openfold',
    }


def test_environment_map_tolerates_a_service_without_a_catalog() -> None:
    assert resource_api._environment_map(object()) == {}


def test_snapshot_attaches_environments(monkeypatch, tmp_path: Path) -> None:
    common = _StubCommon()
    monkeypatch.setattr(resource_api, '_modules', lambda service: (tmp_path, common, None, None))
    monkeypatch.setattr(resource_api, '_manifest', lambda root: root / 'resources.json')
    monkeypatch.setattr(resource_api, '_used_by_map',
                        lambda root, release, probes: {'OPERON_OPENFOLD_PATH': ['openfold_predict', 'plain_operator']})
    monkeypatch.setattr(resource_api, '_link_roots', lambda common: ['/data/links'])
    monkeypatch.setattr(resource_api, '_expected_files', lambda common, resource: ['openfold'])
    monkeypatch.setattr(resource_api, '_link_state',
                        lambda common, resource: {'linked': False, 'source': '', 'mode': None})
    monkeypatch.setattr(resource_api, '_size_bytes', lambda root, names: 0)
    snapshot = resource_api.snapshot(_StubService())
    item = snapshot['resources'][0]
    assert item['used_by'] == ['openfold_predict', 'plain_operator']
    assert item['environments'] == ['openfold']
    assert item['link_roots'] == ['/data/links']
