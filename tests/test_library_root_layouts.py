from pathlib import Path

from operon.installation import library_root


def _installed(root: Path) -> Path:
    library = root / "library"
    library.mkdir(parents=True)
    (library / "registry.json").write_text("{}", encoding="utf-8")
    return library


def test_desktop_versions_layout(tmp_path):
    version = tmp_path / "versions" / "5.1.9-abc"
    library = _installed(version)
    assert library_root(version) == library


def test_managed_remote_layout(tmp_path):
    code = tmp_path / "managed-v1" / "code-1234"
    library = _installed(code)
    assert library_root(code) == library
