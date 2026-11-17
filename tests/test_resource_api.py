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
