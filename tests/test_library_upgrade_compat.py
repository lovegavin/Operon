"""Upgrades from 4.0.x source trees and cross-platform provider wheel checks."""
import hashlib
import json
import shutil
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def legacy_digest(root):
    """The 4.0.x fingerprint: source directories plus declarations only."""
    from operon.dropins import snapshot
    from operon.source_library import SOURCE_DIRS
    digest = hashlib.sha256()
    for relative in [*SOURCE_DIRS.values(), 'operon/builtin_packages.json']:
        digest.update(relative.encode() + snapshot(root / relative, None).encode())
    return digest.hexdigest()


def test_legacy_tree_without_environment_manifest_keeps_its_digest(tmp_path):
    from operon.source_library import snapshot_sources
    legacy = tmp_path / 'legacy'
    shutil.copytree(ROOT / 'library/seed', legacy)
    (legacy / 'operon/environments.json').unlink()
    # The import path fingerprints the live tree before unpacking; this used to
    # raise FileNotFoundError on every 4.0.x installation.
    assert snapshot_sources(legacy) == legacy_digest(legacy)
    full = tmp_path / 'full'
    shutil.copytree(ROOT / 'library/seed', full)
    assert snapshot_sources(full) != legacy_digest(full)


def test_wheel_identity_ignores_zip_container_metadata(tmp_path):
    from operon.library_bundle import sha256, wheel_contents
    first = tmp_path / 'first.whl'
    with zipfile.ZipFile(first, 'w') as archive:
        archive.writestr('pkg/__init__.py', 'value = 1\n')
        archive.writestr('pkg/METADATA', 'Name: demo\n')
    data = bytearray(first.read_bytes())
    offset = 0
    while True:
        offset = data.find(b'PK\x01\x02', offset)
        if offset < 0:
            break
        data[offset + 5] = 0  # "version made by": Windows instead of Unix
        offset += 4
    second = tmp_path / 'second.whl'
    second.write_bytes(bytes(data))
    assert sha256(first) != sha256(second)
    assert wheel_contents(first) == wheel_contents(second)


def test_explicit_library_root_does_not_fall_back_to_the_seed(tmp_path):
    from operon.environments import load, manifest_path
    assert manifest_path(tmp_path) == tmp_path / 'operon/environments.json'
    assert load(tmp_path) == {}


def test_prepare_without_manifest_is_explicit(tmp_path):
    from operon import environment_install
    (tmp_path / 'library').mkdir()
    with pytest.raises(FileNotFoundError, match='does not declare isolated environments'):
        environment_install.prepare('openmm81', root=tmp_path / 'env', source=tmp_path / 'library')


def test_wheel_identity_ignores_record_row_order(tmp_path):
    from operon.library_bundle import sha256, wheel_contents
    rows = ['pkg/__init__.py,sha256=aaa,1\r\n', 'pkg/METADATA,sha256=bbb,2\r\n']
    first = tmp_path / 'first-record.whl'
    second = tmp_path / 'second-record.whl'
    for path, order in ((first, rows), (second, list(reversed(rows)))):
        with zipfile.ZipFile(path, 'w') as archive:
            archive.writestr('pkg/__init__.py', 'value = 1\n')
            archive.writestr('pkg/METADATA', 'Name: demo\n')
            archive.writestr('pkg-1.0.dist-info/RECORD', ''.join(order))
    assert sha256(first) != sha256(second)
    assert wheel_contents(first) == wheel_contents(second)
