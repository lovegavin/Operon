"""Focused tests for the large-resource API helpers (5.4.0).

The download path is exercised through a stub opener so the tests never touch
the network; they pin the safety rules (https only, no traversal), progress
accounting and the operation registry.
"""
from __future__ import annotations

import os
import subprocess
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


def test_download_accepts_http_and_ftp(tmp_path: Path) -> None:
    for scheme in ("http", "ftp"):
        entry = {"url": f"{scheme}://example.com/{scheme}.bin", "path": f"{scheme}.bin"}
        result = resource_api._download(entry, tmp_path, overwrite=False,
                                        event=threading.Event(), job={},
                                        opener=lambda url, token: _Response(b"payload"))
        assert result["status"] == "downloaded"
        assert (tmp_path / f"{scheme}.bin").read_bytes() == b"payload"


def test_download_rejects_an_unknown_scheme(tmp_path: Path) -> None:
    entry = {"url": "git://example.com/repo.git", "path": "repo"}
    with pytest.raises(ValueError, match="unsupported download scheme"):
        resource_api._download(entry, tmp_path, overwrite=False,
                               event=threading.Event(), job={}, opener=lambda url, token: None)


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True,
                   env={**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.com",
                        "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.com"})


def test_git_fetch_copies_one_subdirectory(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    (repo / "sub").mkdir(parents=True)
    (repo / "sub" / "weights.bin").write_bytes(b"w" * 8)
    (repo / "README").write_text("x", encoding="utf-8")
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "init")
    target = tmp_path / "target"
    lines: list[str] = []
    result = resource_api._git_fetch({"url": repo.as_uri(), "subdir": "sub"}, target,
                                     event=threading.Event(), job={}, emit=lines.append)
    assert result["status"] == "cloned"
    assert (target / "weights.bin").read_bytes() == b"w" * 8
    assert not (target / "README").exists()
    assert any(line.startswith("GIT ") for line in lines)


def test_git_fetch_reports_a_missing_git(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.delenv("OPERON_GIT", raising=False)
    monkeypatch.setattr(resource_api.shutil, "which", lambda name: None)
    with pytest.raises(RuntimeError, match="git 不可用"):
        resource_api._git_fetch({"url": "https://example.com/x.git"}, tmp_path / "t",
                                event=threading.Event(), job={}, emit=lambda line: None)


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


def test_used_by_combines_the_environment_variable_and_the_resource_id(monkeypatch, tmp_path: Path) -> None:
    common = _StubCommon()
    monkeypatch.setattr(resource_api, '_modules', lambda service: (tmp_path, common, None, None))
    monkeypatch.setattr(resource_api, '_manifest', lambda root: root / 'resources.json')
    monkeypatch.setattr(resource_api, '_used_by_map',
                        lambda root, release, probes: {'OPERON_OPENFOLD_PATH': ['openfold_predict'],
                                                       'openfold': ['openfold_reader']})
    monkeypatch.setattr(resource_api, '_link_roots', lambda common: [])
    monkeypatch.setattr(resource_api, '_expected_files', lambda common, resource: [])
    monkeypatch.setattr(resource_api, '_link_state',
                        lambda common, resource: {'linked': False, 'source': '', 'mode': None})
    monkeypatch.setattr(resource_api, '_size_bytes', lambda root, names: 0)
    item = resource_api.snapshot(_StubService())['resources'][0]
    assert item['used_by'] == ['openfold_predict', 'openfold_reader']


def test_a_resource_whose_id_is_an_environment_belongs_to_it(monkeypatch, tmp_path: Path) -> None:
    common = _StubCommon()
    monkeypatch.setattr(resource_api, '_modules', lambda service: (tmp_path, common, None, None))
    monkeypatch.setattr(resource_api, '_manifest', lambda root: root / 'resources.json')
    monkeypatch.setattr(resource_api, '_used_by_map', lambda root, release, probes: {})
    monkeypatch.setattr(resource_api, '_environment_map', lambda service: {})
    monkeypatch.setattr(resource_api, '_declared_environments', lambda: {'openfold', 'esm3'})
    monkeypatch.setattr(resource_api, '_link_roots', lambda common: [])
    monkeypatch.setattr(resource_api, '_expected_files', lambda common, resource: [])
    monkeypatch.setattr(resource_api, '_link_state',
                        lambda common, resource: {'linked': False, 'source': '', 'mode': None})
    monkeypatch.setattr(resource_api, '_size_bytes', lambda root, names: 0)
    item = resource_api.snapshot(_StubService())['resources'][0]
    assert item['used_by'] == []
    assert item['environments'] == ['openfold']


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


class _Unit:
    def __init__(self, name, files):
        self.name = name
        self.files = files


class _CardResource:
    """Minimal stand-in for the library's resource object."""

    def __init__(self, units, expected=(), files=()):
        # The library hands snapshot() plain dicts for ``units``.
        self.components = tuple({'name': unit.name, 'files': unit.files} for unit in units)
        self.expected_files = tuple(expected)
        self.files = tuple(files)


def test_unit_declared_files_falls_back_to_the_resource_list() -> None:
    resource = _CardResource([_Unit('prodigal', ())],
                             expected=({'path': 'prodigal', 'required': True},))
    assert resource_api.unit_declared_files(resource, 'prodigal') == ['prodigal']


def test_unit_declared_files_never_guesses_for_a_multi_unit_resource() -> None:
    resource = _CardResource([_Unit('left', ('a.bin',)), _Unit('right', ())],
                             expected=('shared.bin',))
    assert resource_api.unit_declared_files(resource, 'left') == ['a.bin']
    assert resource_api.unit_declared_files(resource, 'right') == []


def test_split_presence_reads_a_missing_root_as_everything_missing(tmp_path: Path) -> None:
    assert resource_api._split_presence(None, ['a.bin']) == ([], ['a.bin'])
    (tmp_path / 'a.bin').write_text('x', encoding='utf-8')
    assert resource_api._split_presence(tmp_path, ['a.bin', 'b.bin']) == (['a.bin'], ['b.bin'])


def test_merge_missing_prefers_the_card_verdict() -> None:
    units = [{'name': 'afdb', 'files_missing': []}]
    # The library still lists pdb_mmcif/mmcif_files, a directory it cannot see.
    assert resource_api._merge_missing(units, ['pdb_mmcif/mmcif_files']) == []
    assert resource_api._merge_missing([], ['pdb_mmcif/mmcif_files']) == ['pdb_mmcif/mmcif_files']


def test_mirror_components_publishes_the_fields_without_a_unit_row() -> None:
    components = [{'name': 'right', 'state': 'unknown',
                   'files': [{'name': 'b.bin', 'present': False}]}]
    resource_api._mirror_components(components, [], None, [{'path': 'b.bin'}])
    card = components[0]
    for field in ('downloadable', 'undownloadable', 'download_supported', 'rsync',
                  'files_present', 'files_missing', 'state', 'source'):
        assert field in card, field
    assert card['missing'] == ['b.bin']
    assert card['files_missing'] == ['b.bin']
    assert card['downloadable'] == ['b.bin']
    assert card['download_supported'] is True


def test_card_ready_matches_the_card_fields() -> None:
    assert resource_api.card_ready({'state': 'linked', 'files_missing': []})
    assert not resource_api.card_ready({'state': 'linked', 'files_missing': ['a']})
    assert resource_api.card_ready({'state': 'present',
                                    'files': [{'name': 'a', 'present': True}]})
    assert not resource_api.card_ready({'state': 'unknown', 'files': []})
