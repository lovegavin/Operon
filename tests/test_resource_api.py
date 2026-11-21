"""Focused tests for the large-resource API helpers (5.4.0).

The download path is exercised through a stub opener so the tests never touch
the network; they pin the safety rules (https only, no traversal), progress
accounting and the operation registry.
"""
from __future__ import annotations

import os
import pathlib
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
    assert not (target / ".git").exists()
    assert any(line.startswith("GIT ") for line in lines)


class _StubFetch:
    def __init__(self, declared: pathlib.Path) -> None:
        self.declared = declared

    def _target_root(self, resource, root):
        return self.declared


def test_writable_root_keeps_a_writable_declaration(tmp_path: pathlib.Path) -> None:
    declared = tmp_path / "declared"
    seen: list[str] = []
    root = resource_api._writable_root(_StubFetch(declared), Resource([]), None, seen.append)
    assert root == declared
    assert seen == []


def test_writable_root_falls_back_when_the_declaration_is_read_only(
        monkeypatch, tmp_path: pathlib.Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(pathlib.Path, "home", classmethod(lambda cls: home))
    seen: list[str] = []
    resource = Resource([])
    resource.id = "esm2"
    root = resource_api._writable_root(
        _StubFetch(pathlib.Path("/proc/definitely-not-writable")), resource, None, seen.append)
    assert root == home / ".local" / "share" / "operon" / "resources" / "esm2"
    assert root.is_dir()
    assert seen and seen[0].startswith("ROOT ")


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

def test_git_fetch_refreshes_a_read_only_file(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "weights.bin").write_bytes(b"new")
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "init")
    target = tmp_path / "target"
    target.mkdir()
    stale = target / "weights.bin"
    stale.write_bytes(b"old")
    stale.chmod(0o444)

    result = resource_api._git_fetch({"url": repo.as_uri()}, target,
                                     event=threading.Event(), job={}, emit=lambda line: None)

    assert result["status"] == "cloned"
    assert stale.read_bytes() == b"new"
    assert os.access(stale, os.W_OK)


def _make_tarball(path: Path, files: dict[str, bytes]) -> Path:
    import io
    import tarfile

    with tarfile.open(path, "w:gz") as archive:
        for name, payload in files.items():
            info = tarfile.TarInfo(name)
            info.size = len(payload)
            archive.addfile(info, io.BytesIO(payload))
    return path


def test_extract_member_unpacks_a_whole_archive_below_the_target(tmp_path: Path) -> None:
    bundle = _make_tarball(tmp_path / "bfd.tar.gz", {
        "bfd/bfd_a3m.ffdata": b"a3m",
        "bfd/bfd_a3m.ffindex": b"index",
        "pdb70/pdb70_clu.tsv": b"cluster",
    })
    target = tmp_path / "tree"
    job: dict = {}

    written = resource_api._extract_member(bundle, target, "", threading.Event(), job)

    assert written == 3 + 5 + 7
    assert (target / "bfd" / "bfd_a3m.ffdata").read_bytes() == b"a3m"
    assert (target / "bfd" / "bfd_a3m.ffindex").read_bytes() == b"index"
    assert (target / "pdb70" / "pdb70_clu.tsv").read_bytes() == b"cluster"
    assert job["files"] == 3


def test_extract_member_rejects_a_member_that_escapes_the_target(tmp_path: Path) -> None:
    bundle = _make_tarball(tmp_path / "evil.tar.gz", {"../escape.txt": b"nope"})

    with pytest.raises(ValueError, match="escapes the target"):
        resource_api._extract_member(bundle, tmp_path / "tree", "", threading.Event(), {})
    assert not (tmp_path / "escape.txt").exists()


def test_expected_files_follow_the_released_unit_layout() -> None:
    from src.task.step.steps import _resources_common as common

    resource = common.load_resources()["alphafold2"]
    names = common.expected_files(resource)
    assert len(names) == 18
    assert "pdb_seqres/pdb_seqres.txt" in names
    assert "pdb_seqres/pdb_seqres_2022_09_28.fasta" not in names
    assert set(common.check_resource(resource)["files"]) == set(names)


def test_expected_files_prefer_unit_files_over_the_legacy_declaration() -> None:
    from src.task.step.steps import _resources_common as common

    entry = {
        "id": "demo", "title": "demo", "files": ["old.bin"],
        "expected_files": ["old.bin"],
        "units": [{"name": "demo", "files": ["new/a.bin", "new/b.bin"]}],
    }
    assert common.expected_files(common.Resource.from_entry(entry)) == (
        "new/a.bin", "new/b.bin",
    )


def test_expected_files_fall_back_when_units_declare_no_files() -> None:
    from src.task.step.steps import _resources_common as common

    entry = {
        "id": "demo", "title": "demo", "files": ["old.bin"],
        "expected_files": ["declared.bin"],
        "units": [{"name": "demo", "files": []}],
    }
    assert common.expected_files(common.Resource.from_entry(entry)) == ("declared.bin",)


def test_planned_bytes_requires_a_size_for_every_file() -> None:
    assert resource_api._planned_bytes([{"bytes": 10}, {"bytes": 5}]) == 15
    assert resource_api._planned_bytes([{"bytes": 10}, {"bytes": 0}]) == 0
    assert resource_api._planned_bytes([]) == 0


def test_planned_bytes_falls_back_to_unit_declared_file_sizes() -> None:
    resource = _CardResource([_Unit('afdb', ())])
    resource.components = ({
        'name': 'afdb',
        'files': [
            {'path': 'pdb_seqres/pdb_seqres.txt', 'bytes': 68_464_969},
            {'path': 'params/params_model_1_ptm.npz', 'size_bytes': 373_103_340},
        ],
    },)
    planned = [
        {'path': 'pdb_seqres/pdb_seqres.txt'},
        {'path': 'params/params_model_1_ptm.npz'},
    ]
    assert resource_api._planned_bytes(planned, resource, 'afdb') == 441_568_309
    # One file without any known size keeps the total indeterminate.
    assert resource_api._planned_bytes(planned + [{'path': 'unknown.bin'}],
                                       resource, 'afdb') == 0


def test_operation_reports_percent_only_with_a_planned_total(monkeypatch) -> None:
    monkeypatch.setattr(resource_api, '_jobs', {
        'job': {'id': 'job', 'status': 'running', 'completed_bytes': 50,
                'bytes': 75, 'planned_bytes': 200},
        'unknown': {'id': 'unknown', 'status': 'running', 'completed_bytes': 1,
                    'bytes': 1, 'planned_bytes': 0},
    })
    assert resource_api.operation('job')['percent'] == 37
    assert resource_api.operation('unknown')['percent'] == 0


def test_an_explicit_old_file_alias_counts_as_present(tmp_path: Path) -> None:
    from src.task.step.steps import _resources_common as common

    root = tmp_path / 'afdb'
    (root / 'pdb_seqres').mkdir(parents=True)
    (root / 'pdb_seqres' / 'pdb_seqres_2022_09_28.fasta').write_bytes(b'old')

    assert common.file_exists(root, 'pdb_seqres/pdb_seqres.txt') is True
    assert resource_api._split_presence(
        root, ['pdb_seqres/pdb_seqres.txt'], common,
    ) == (['pdb_seqres/pdb_seqres.txt'], [])
    entry = common.check_resource(
        common.load_resources()['alphafold2'], root,
    )['files']['pdb_seqres/pdb_seqres.txt']
    assert entry['present'] is True


def test_resource_from_entry_keeps_unit_file_sizes_for_planned_bytes() -> None:
    from src.task.step.steps import _resources_common as common

    entry = {
        'id': 'demo', 'title': 'demo', 'kind': 'model', 'url': '', 'install': '',
        'env': 'OPERON_DEMO_PATH', 'roots': ['.'], 'files': ['a.bin'],
        'downloads': [{'url': 'https://example.com/a.bin', 'path': 'a.bin'}],
        'units': [{'name': 'afdb', 'files': [
            {'path': 'a.bin', 'bytes': 10},
            {'name': 'b.bin', 'size_bytes': 5},
        ]}],
    }
    resource = common.Resource.from_entry(entry)
    unit = resource.components[0]
    assert unit['files'] == ('a.bin', 'b.bin')
    assert unit['file_sizes'] == {'a.bin': 10, 'b.bin': 5}
    assert resource_api._planned_bytes(
        [{'path': 'a.bin'}, {'path': 'b.bin'}], resource, 'afdb',
    ) == 15
