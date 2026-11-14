from __future__ import annotations

import io
import hashlib
from pathlib import Path

import pytest

from src.core.errors import StepError
from src.task.step.steps._resources_common import Resource
from src.task.step.steps.resource_fetch import _download_one, _safe_destination


class _Response(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
        return False


def test_manifest_rejects_plain_http():
    with pytest.raises(StepError, match="https"):
        Resource.from_entry({
            "id": "demo",
            "files": ["x.pt"],
            "downloads": [{"url": "http://example.com/x.pt", "path": "x.pt"}],
        })


def test_manifest_rejects_unsafe_path():
    with pytest.raises(StepError, match="safe relative"):
        Resource.from_entry({
            "id": "demo",
            "files": ["x.pt"],
            "downloads": [{"url": "https://example.com/x.pt", "path": "../x.pt"}],
        })


def test_safe_destination_stays_inside_root(tmp_path: Path):
    root = tmp_path / "weights"
    root.mkdir()
    assert _safe_destination(root, "nested/x.pt") == (root / "nested/x.pt").resolve()
    with pytest.raises(StepError, match="safe relative"):
        _safe_destination(root, "../escape.pt")


def test_download_verifies_and_moves_atomically(tmp_path: Path):
    payload = b"weights-data"

    def opener(url, token_env=""):
        assert url == "https://example.com/x.pt"
        return _Response(payload)

    result = _download_one(
        {
            "url": "https://example.com/x.pt",
            "path": "x.pt",
            "bytes": len(payload),
            "sha256": hashlib.sha256(payload).hexdigest(),
        },
        tmp_path,
        overwrite=False,
        opener=opener,
    )
    assert result["downloaded"] is True
    assert (tmp_path / "x.pt").read_bytes() == payload
    assert not (tmp_path / "x.pt.part").exists()


def test_download_keeps_partial_on_checksum_failure(tmp_path: Path):
    payload = b"weights-data"

    def opener(url, token_env=""):
        return _Response(payload)

    with pytest.raises(StepError, match="sha256 mismatch"):
        _download_one(
            {
                "url": "https://example.com/x.pt",
                "path": "x.pt",
                "sha256": "0" * 64,
            },
            tmp_path,
            overwrite=False,
            opener=opener,
        )
    assert not (tmp_path / "x.pt").exists()
    assert (tmp_path / "x.pt.part").read_bytes() == payload


def test_existing_file_is_skipped_when_metadata_matches(tmp_path: Path):
    payload = b"weights-data"
    (tmp_path / "x.pt").write_bytes(payload)

    def opener(url, token_env=""):
        raise AssertionError("must not download an existing verified file")

    result = _download_one(
        {
            "url": "https://example.com/x.pt",
            "path": "x.pt",
            "bytes": len(payload),
            "sha256": hashlib.sha256(payload).hexdigest(),
        },
        tmp_path,
        overwrite=False,
        opener=opener,
    )
    assert result["status"] == "existing"


def test_manifest_accepts_mapping_downloads():
    resource = Resource.from_entry({
        "id": "demo",
        "files": ["a.pt"],
        "downloads": {"a.pt": "https://example.com/a.pt"},
        "sha256": {"a.pt": "a" * 64},
        "sizes": {"a.pt": 3},
    })
    assert resource.downloads == ({
        "url": "https://example.com/a.pt",
        "path": "a.pt",
        "sha256": "a" * 64,
        "bytes": 3,
        "license": "",
        "requires_token": False,
    },)
