"""Tests for linking an existing external copy as a library resource."""

from __future__ import annotations

import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from src.task.step.steps import _resources_common as common
from src.task.step.steps import resource_link
from src.task.step.steps.resource_link import link, unlink

EXPECTED = "esm2_t6_8M_UR50D.pt"
POSIX_ONLY = pytest.mark.skipif(
    os.name == "nt", reason="POSIX symlink and junction behaviour differs on Windows"
)


def _resource(
    root: Path,
    *,
    files: tuple[str, ...] = (EXPECTED,),
    expected: tuple[str, ...] = (),
    link_roots: tuple[str, ...] = (),
    env: str = "",
) -> common.Resource:
    return common.Resource(
        id="esm2",
        title="ESM-2 checkpoint",
        kind="weights",
        url="",
        install="",
        env=env,
        roots=(str(root),),
        files=tuple(files),
        downloads=(),
        link_roots=tuple(link_roots),
        expected_files=tuple(expected),
    )


def _source(tmp_path: Path, payload: bytes = b"weights") -> Path:
    source = tmp_path / "external" / "esm2"
    source.mkdir(parents=True)
    (source / EXPECTED).write_bytes(payload)
    return source


@POSIX_ONLY
def test_check_resource_reports_every_declared_file(tmp_path: Path) -> None:
    resource = common.Resource(
        id='demo',
        title='Demo',
        kind='weights',
        url='',
        install='',
        env='OPERON_DEMO',
        roots=(str(tmp_path),),
        files=('weights/a.pt',),
        expected_files=('weights/a.pt', 'weights/b.pt'),
    )
    (tmp_path / 'weights').mkdir()
    (tmp_path / 'weights' / 'a.pt').write_bytes(b'1')
    result = common.check_resource(resource)
    assert set(result['files']) == {'weights/a.pt', 'weights/b.pt'}
    assert result['files']['weights/a.pt']['present'] is True
    assert result['files']['weights/b.pt']['present'] is False
    assert result['status'] == 'partial'


def test_link_directory_records_receipt(tmp_path):
    source = _source(tmp_path)
    root = tmp_path / "resources" / "esm2"
    resource = _resource(root)

    result = link(resource, source, allowed_roots=[str(tmp_path / "external")])

    assert result["status"] == "linked"
    assert result["mode"] == "symlink"
    assert result["target"] == str(root)
    assert Path(root).is_symlink()
    assert os.readlink(root) == str(source)
    assert (root / EXPECTED).read_bytes() == b"weights"
    assert sorted(entry.name for entry in source.iterdir()) == [EXPECTED]

    receipt_file = root.parent / ".receipts" / f"receipt-{resource.id}.json"
    assert receipt_file.is_file()
    assert not (root / f"receipt-{resource.id}.json").exists()
    receipt = json.loads(receipt_file.read_text(encoding="utf-8"))
    assert receipt["kind"] == "linked"
    assert receipt["id"] == "esm2"
    assert receipt["source"] == str(source)
    assert receipt["target"] == str(root)
    assert receipt["mode"] == "symlink"
    assert receipt["probe"] == EXPECTED
    assert receipt["probe_bytes"] == len(b"weights")
    assert receipt["created_by"] == "resource_link"
    assert receipt["created_at"].endswith("Z")

    check = common.check_resource(resource)
    assert check["present"] is True
    assert check["linked"] is True
    assert check["source"] == str(source)
    assert check["receipt"] == str(receipt_file)

    state = common.link_state(resource)
    assert state["linked"] is True
    assert state["source"] == str(source)
    assert state["mode"] == "symlink"
    assert state["created_at"] == receipt["created_at"]
    assert state["probe"] == EXPECTED
    assert state["present"] is True
    assert state["state"] == "linked"
    assert state["root_linked"] is True
    assert state["root_target"] == str(source)
    units = state["units"]
    assert [unit["name"] for unit in units] == ["tree"]
    assert units[0]["state"] == "linked"
    assert units[0]["receipt"] is True
    assert units[0]["source"] == str(source)


def test_link_directory_uses_a_junction_on_windows(tmp_path, monkeypatch):
    source = _source(tmp_path)
    root = tmp_path / "resources" / "esm2"
    resource = _resource(root)
    commands = []

    def fake_run(command, **kwargs):
        commands.append(command)
        # Stand-in for the NTFS junction: the probe has to resolve through it.
        os.symlink(source, root, target_is_directory=True)
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(resource_link, "_on_windows", lambda: True)
    monkeypatch.setattr(resource_link.subprocess, "run", fake_run)

    result = link(resource, source, allowed_roots=[str(tmp_path / "external")])

    assert result["mode"] == "junction"
    assert commands == [["cmd", "/c", "mklink", "/J", str(root), str(source)]]
    assert (root / EXPECTED).read_bytes() == b"weights"


@POSIX_ONLY
def test_link_is_idempotent(tmp_path):
    source = _source(tmp_path)
    root = tmp_path / "resources" / "esm2"
    resource = _resource(root)
    allowed = [str(tmp_path / "external")]

    first = link(resource, source, allowed_roots=allowed)
    second = link(resource, source, allowed_roots=allowed)

    assert first["status"] == "linked"
    assert second["status"] == "already_linked"
    assert second["source"] == str(source)
    assert second["mode"] == "symlink"
    assert second["target"] == str(root)


def test_link_conflict_without_replace(tmp_path):
    source = _source(tmp_path)
    root = tmp_path / "resources" / "esm2"
    root.mkdir(parents=True)
    sentinel = root / "keep.txt"
    sentinel.write_text("mine", encoding="utf-8")

    with pytest.raises(ValueError, match="already exists"):
        link(_resource(root), source, allowed_roots=[str(tmp_path / "external")])

    assert sentinel.read_text(encoding="utf-8") == "mine"
    assert not root.is_symlink()


@POSIX_ONLY
@POSIX_ONLY
def test_link_replace_removes_only_the_link(tmp_path):
    source = _source(tmp_path)
    old = tmp_path / "external" / "esm2-old"
    old.mkdir(parents=True)
    (old / EXPECTED).write_bytes(b"old")
    root = tmp_path / "resources" / "esm2"
    resource = _resource(root)
    link(resource, old, allowed_roots=[str(tmp_path / "external")])

    result = link(
        resource,
        source,
        replace=True,
        allowed_roots=[str(tmp_path / "external")],
    )

    assert result["status"] == "linked"
    assert root.is_symlink()
    assert Path(os.readlink(root)) == source
    assert (old / EXPECTED).read_bytes() == b"old"
    assert (source / EXPECTED).read_bytes() == b"weights"


def test_link_rejects_relative_and_dotted_sources(tmp_path):
    source = _source(tmp_path)
    resource = _resource(tmp_path / "resources" / "esm2")
    allowed = [str(tmp_path / "external")]

    with pytest.raises(ValueError, match="absolute"):
        link(resource, "relative/esm2", allowed_roots=allowed)
    with pytest.raises(ValueError, match="must not contain"):
        link(resource, source.parent / ".." / "external" / "esm2", allowed_roots=allowed)


def test_link_rejects_sources_outside_the_allowed_roots(tmp_path):
    source = _source(tmp_path)
    allowed = tmp_path / "allowed"
    allowed.mkdir()

    with pytest.raises(ValueError, match="outside the allowed link roots"):
        link(_resource(tmp_path / "resources" / "esm2"), source, allowed_roots=[str(allowed)])


def test_link_rejects_a_source_inside_the_resource_root(tmp_path):
    root = tmp_path / "resources" / "esm2"
    inner = root / "inner"
    inner.mkdir(parents=True)
    (inner / EXPECTED).write_bytes(b"weights")

    with pytest.raises(ValueError, match="resource root"):
        link(_resource(root), inner, allowed_roots=[str(root)])
    with pytest.raises(ValueError, match="resource root"):
        link(_resource(root), root, allowed_roots=[str(root)])


@POSIX_ONLY
def test_unlink_removes_the_link_but_not_the_source(tmp_path):
    source = _source(tmp_path)
    root = tmp_path / "resources" / "esm2"
    resource = _resource(root)
    link(resource, source, allowed_roots=[str(tmp_path / "external")])

    result = unlink(resource)

    assert result == {
        "status": "unlinked",
        "name": "esm2",
        "target": str(root),
        "root": str(root),
        "mode": "symlink",
        "unit": "tree",
    }
    assert not root.exists()
    assert not root.is_symlink()
    assert (source / EXPECTED).read_bytes() == b"weights"
    assert sorted(entry.name for entry in source.iterdir()) == [EXPECTED]
    assert not (source / f"receipt-{resource.id}.json").exists()
    assert not (root.parent / ".receipts" / f"receipt-{resource.id}.json").exists()
    assert common.read_receipt(resource) is None


@POSIX_ONLY
def test_probe_failure_removes_the_link(tmp_path):
    source = tmp_path / "external" / "esm2"
    source.mkdir(parents=True)
    root = tmp_path / "resources" / "esm2"

    with pytest.raises(ValueError, match="expected file"):
        link(_resource(root), source, allowed_roots=[str(tmp_path / "external")])

    assert not root.exists()
    assert not root.is_symlink()
    assert source.is_dir()


@POSIX_ONLY
def test_expected_files_override_files_for_the_probe(tmp_path):
    source = _source(tmp_path)
    (source / "other.bin").write_bytes(b"probe")
    resource = _resource(
        tmp_path / "resources" / "esm2",
        files=("missing.pt",),
        expected=("other.bin",),
    )
    assert common.expected_files(resource) == ("other.bin",)

    result = link(resource, source, allowed_roots=[str(tmp_path / "external")])

    assert result["probe"] == "other.bin"
    assert result["probe_bytes"] == len(b"probe")


def test_link_single_file_uses_a_hardlink(tmp_path):
    source = tmp_path / "external" / "esm2" / EXPECTED
    source.parent.mkdir(parents=True)
    source.write_bytes(b"weights")
    root = tmp_path / "resources" / "esm2"
    resource = _resource(root)

    result = link(resource, source, allowed_roots=[str(tmp_path / "external")])

    assert result["status"] == "linked"
    assert result["mode"] == "hardlink"
    assert result["target"] == str(root / EXPECTED)
    assert os.path.samefile(root / EXPECTED, source)

    check = common.check_resource(resource)
    assert check["present"] is True
    assert check["linked"] is True

    unlink(resource)
    assert not (root / EXPECTED).exists()
    assert source.read_bytes() == b"weights"


def test_link_single_file_falls_back_to_a_symlink(tmp_path, monkeypatch):
    source = tmp_path / "external" / "esm2" / EXPECTED
    source.parent.mkdir(parents=True)
    source.write_bytes(b"weights")
    root = tmp_path / "resources" / "esm2"
    resource = _resource(root)

    def cross_device(link_source, link_target):
        raise OSError("cross-device link")

    monkeypatch.setattr(resource_link.os, "link", cross_device)

    result = link(resource, source, allowed_roots=[str(tmp_path / "external")])

    assert result["mode"] == "symlink"
    assert (root / EXPECTED).read_bytes() == b"weights"


def test_single_file_link_never_copies_on_windows(tmp_path, monkeypatch):
    source = tmp_path / "external" / "esm2" / EXPECTED
    source.parent.mkdir(parents=True)
    source.write_bytes(b"weights")
    root = tmp_path / "resources" / "esm2"

    def denied(*args, **kwargs):
        raise OSError("denied")

    monkeypatch.setattr(resource_link, "_on_windows", lambda: True)
    monkeypatch.setattr(resource_link.os, "link", denied)
    monkeypatch.setattr(resource_link.os, "symlink", denied)

    with pytest.raises(ValueError, match="copy the file into place"):
        link(_resource(root), source, allowed_roots=[str(tmp_path / "external")])

    assert not (root / EXPECTED).exists()


def test_unlink_refuses_a_real_directory(tmp_path):
    root = tmp_path / "resources" / "esm2"
    root.mkdir(parents=True)
    (root / EXPECTED).write_bytes(b"weights")

    with pytest.raises(ValueError, match="not a link"):
        unlink(_resource(root))

    assert (root / EXPECTED).exists()


def test_check_resource_reports_presence_without_a_link(tmp_path):
    root = tmp_path / "resources" / "esm2"
    root.mkdir(parents=True)
    (root / EXPECTED).write_bytes(b"weights")

    check = common.check_resource(_resource(root))

    assert check["present"] is True
    assert check["linked"] is False
    assert check["source"] is None
    assert check["receipt"] == ""


def test_manifest_declares_link_roots_and_expected_files():
    resources = common.load_resources()

    roots = common.link_roots(resources["esm2"])
    assert "/public/home/lihj/operon-resources" in roots
    assert os.path.expanduser("~/.cache/huggingface") in roots
    assert os.path.expanduser("~/.cache/torch") in roots
    assert os.path.expanduser("~/.local/share/operon/external") in roots
    assert os.path.expanduser("~/operon-resources") in roots
    assert resources["esm2"].expected_files == (EXPECTED,)
    assert common.expected_files(resources["esm2"]) == (EXPECTED,)


def test_link_roots_unions_manifest_and_per_resource_roots(tmp_path):
    resource = _resource(tmp_path / "resources" / "esm2", link_roots=[str(tmp_path / "extra")])

    roots = common.link_roots(resource)

    assert str(tmp_path / "extra") in roots
    assert os.path.expanduser("~/.cache/huggingface") in roots


def test_write_and_read_receipt_round_trip(tmp_path):
    root = tmp_path / "resources" / "esm2"
    root.mkdir(parents=True)
    resource = _resource(root)

    path = common.write_receipt(resource, {"kind": "linked", "source": "/tmp/external"})

    assert path == root.parent / ".receipts" / "receipt-esm2.json"
    assert common.read_receipt(resource) == {
        "kind": "linked",
        "source": "/tmp/external",
    }


@POSIX_ONLY
def test_link_and_unlink_never_write_into_the_source(tmp_path):
    source = _source(tmp_path)
    before = sorted(entry.name for entry in source.iterdir())
    root = tmp_path / "resources" / "esm2"
    resource = _resource(root)

    link(resource, source, allowed_roots=[str(tmp_path / "external")])
    assert sorted(entry.name for entry in source.iterdir()) == before
    assert not (source / f"receipt-{resource.id}.json").exists()

    unlink(resource)
    assert sorted(entry.name for entry in source.iterdir()) == before
    assert (source / EXPECTED).read_bytes() == b"weights"


@POSIX_ONLY
def test_link_succeeds_with_a_read_only_source(tmp_path):
    source = _source(tmp_path)
    (source / EXPECTED).chmod(0o444)
    source.chmod(0o555)
    root = tmp_path / "resources" / "esm2"
    resource = _resource(root)
    try:
        result = link(resource, source, allowed_roots=[str(tmp_path / "external")])
        assert result["status"] == "linked"
        assert common.check_resource(resource)["linked"] is True
        unlink(resource)
    finally:
        source.chmod(0o755)
        (source / EXPECTED).chmod(0o644)
    assert (source / EXPECTED).read_bytes() == b"weights"


def test_single_file_probe_reports_the_linked_file_name(tmp_path):
    source = tmp_path / "external" / "weights" / "b.pt"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"probe")
    root = tmp_path / "resources" / "esm2"
    resource = _resource(root, files=("a.pt", "b.pt"), expected=("a.pt", "b.pt"))

    result = link(resource, source, allowed_roots=[str(tmp_path / "external")])

    assert result["probe"] == "b.pt"
    assert result["target"] == str(root / "b.pt")
    unlink(resource)


def test_replace_refuses_to_delete_an_unmanaged_directory(tmp_path):
    source = _source(tmp_path)
    root = tmp_path / "resources" / "esm2"
    root.mkdir(parents=True)
    (root / "keep.txt").write_text("user data", encoding="utf-8")

    with pytest.raises(ValueError, match="holds existing data"):
        link(
            _resource(root),
            source,
            replace=True,
            allowed_roots=[str(tmp_path / "external")],
        )

    assert (root / "keep.txt").read_text(encoding="utf-8") == "user data"

def test_junction_detection_without_path_is_junction(monkeypatch):
    """Python 3.11 ships no ``Path.is_junction``; the lstat fallback must work."""

    monkeypatch.setattr(resource_link.os, "name", "nt")
    monkeypatch.setattr(
        resource_link.os,
        "lstat",
        lambda path: SimpleNamespace(st_reparse_tag=0xA0000003),
    )
    assert resource_link._is_junction(object()) is True

    monkeypatch.setattr(
        resource_link.os,
        "lstat",
        lambda path: SimpleNamespace(st_reparse_tag=0xA000000C),
    )
    assert resource_link._is_junction(object()) is False

    monkeypatch.setattr(
        resource_link.os,
        "lstat",
        lambda path: SimpleNamespace(st_file_attributes=0x410),
    )
    assert resource_link._is_junction(object()) is True

    def missing(path):
        raise OSError("not a reparse point")

    monkeypatch.setattr(resource_link.os, "lstat", missing)
    assert resource_link._is_junction(object()) is False


def test_readlink_strips_windows_device_prefix(monkeypatch):
    prefix = "\\\\?\\"
    monkeypatch.setattr(
        resource_link.os, "readlink", lambda path: prefix + "C:\\Users\\dev\\esm2"
    )
    assert str(resource_link._readlink(Path("C:/tmp"))) == "C:\\Users\\dev\\esm2"

    monkeypatch.setattr(
        resource_link.os, "readlink", lambda path: "\\??\\C:\\Users\\dev\\esm2"
    )
    assert str(resource_link._readlink(Path("C:/tmp"))) == "C:\\Users\\dev\\esm2"

    monkeypatch.setattr(
        resource_link.os,
        "readlink",
        lambda path: "\\\\?\\UNC\\server\\share\\esm2",
    )
    assert str(resource_link._readlink(Path("C:/tmp"))) == "\\\\server\\share\\esm2"

    def missing(path):
        raise OSError("not a link")

    monkeypatch.setattr(resource_link.os, "readlink", missing)
    assert resource_link._readlink(Path("C:/tmp")) is None


def test_link_is_idempotent_when_the_root_is_a_junction(tmp_path, monkeypatch):
    """A linked root must report ``already_linked`` instead of a root conflict."""

    source = _source(tmp_path)
    root = tmp_path / "resources" / "esm2"
    root.mkdir(parents=True)
    (root / EXPECTED).write_bytes(b"weights")
    resource = _resource(root)

    real_is_junction = resource_link._is_junction
    monkeypatch.setattr(
        resource_link,
        "_is_junction",
        lambda path: Path(path) == root or real_is_junction(Path(path)),
    )
    real_readlink = resource_link._readlink
    monkeypatch.setattr(
        resource_link,
        "_readlink",
        lambda path: source if Path(path) == root else real_readlink(Path(path)),
    )

    result = link(resource, source, allowed_roots=[str(tmp_path / "external")])

    assert result["status"] == "already_linked"
    assert result["mode"] == "junction"
    assert result["source"] == str(source)
    assert (source / EXPECTED).read_bytes() == b"weights"


@pytest.mark.skipif(os.name != "nt", reason="directory junctions are Windows-only")
def test_junction_round_trip_on_windows(tmp_path):
    source = _source(tmp_path)
    root = tmp_path / "resources" / "esm2"
    resource = _resource(root)
    allowed = [str(tmp_path / "external")]

    first = link(resource, source, allowed_roots=allowed)
    assert first["status"] == "linked"
    assert first["mode"] == "junction"
    assert (root / EXPECTED).read_bytes() == b"weights"

    second = link(resource, source, allowed_roots=allowed)
    assert second["status"] == "already_linked"
    assert second["mode"] == "junction"

    removed = unlink(resource)
    assert removed["status"] == "unlinked"
    assert not root.exists()
    assert (source / EXPECTED).read_bytes() == b"weights"
    assert unlink(resource)["status"] == "unlinked"
