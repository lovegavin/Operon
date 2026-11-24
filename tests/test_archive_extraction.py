"""A repacked archive may list the same member twice."""

import io
import tarfile
import zipfile

import pytest

from operon.contracts.base import ContractError
from operon.environment_store import builders


def write_zip(path, entries):
    with zipfile.ZipFile(path, 'w') as archive:
        for name, payload in entries:
            archive.writestr(name, payload)


def write_tar(path, entries):
    with tarfile.open(path, 'w') as archive:
        for name, payload in entries:
            info = tarfile.TarInfo(name)
            data = payload.encode()
            info.size = len(data)
            archive.addfile(info, io.BytesIO(data))


def test_an_identical_zip_member_may_repeat(tmp_path):
    archive = tmp_path / 'vendor.zip'
    write_zip(archive, [('pkg/data.txt', 'one'), ('pkg/data.txt', 'one')])

    destination = tmp_path / 'out'
    builders.extract_locked(archive, destination, format='zip', maximum=1024)

    assert (destination / 'pkg/data.txt').read_text() == 'one'


def test_a_conflicting_zip_member_overwrites_the_earlier_one(tmp_path):
    archive = tmp_path / 'conflict.zip'
    with zipfile.ZipFile(archive, 'w') as handle:
        handle.writestr('tool/config.json', '{"first": true}')
        handle.writestr('tool/config.json', '{"second": true}')
    destination = tmp_path / 'tree'
    builders.extract_locked(archive, destination, format='zip', maximum=1 << 20)
    assert (destination / 'tool' / 'config.json').read_text() == '{"second": true}'


def test_an_identical_tar_member_may_repeat(tmp_path):
    archive = tmp_path / 'vendor.tar'
    write_tar(archive, [('pkg/data.txt', 'one'), ('pkg/data.txt', 'one')])

    destination = tmp_path / 'out'
    builders.extract_locked(archive, destination, format='tar', maximum=1024)

    assert (destination / 'pkg/data.txt').read_text() == 'one'


def test_a_tar_link_replaces_a_regular_member_with_the_same_name(tmp_path):
    """Conda packs ``libpython3.11.so`` both as a file and as a link."""
    archive = tmp_path / 'closure.tar'
    with tarfile.open(archive, 'w') as handle:
        payload = b'first'
        info = tarfile.TarInfo('lib/libpython3.11.so')
        info.size = len(payload)
        handle.addfile(info, io.BytesIO(payload))
        link = tarfile.TarInfo('lib/libpython3.11.so')
        link.type = tarfile.SYMTYPE
        link.linkname = 'libpython3.11.so.1.0'
        handle.addfile(link)

    destination = tmp_path / 'tree'
    builders.extract_locked(archive, destination, format='tar', maximum=1 << 20)

    assert (destination / 'lib' / 'libpython3.11.so').is_symlink()
    assert (destination / 'lib' / 'libpython3.11.so').readlink().as_posix() == 'libpython3.11.so.1.0'


def test_a_tar_file_replaces_a_link_with_the_same_name(tmp_path):
    archive = tmp_path / 'closure2.tar'
    with tarfile.open(archive, 'w') as handle:
        link = tarfile.TarInfo('lib/libpython3.11.so')
        link.type = tarfile.SYMTYPE
        link.linkname = 'libpython3.11.so.1.0'
        handle.addfile(link)
        payload = b'owned'
        info = tarfile.TarInfo('lib/libpython3.11.so')
        info.size = len(payload)
        handle.addfile(info, io.BytesIO(payload))

    destination = tmp_path / 'tree'
    builders.extract_locked(archive, destination, format='tar', maximum=1 << 20)

    assert not (destination / 'lib' / 'libpython3.11.so').is_symlink()
    assert (destination / 'lib' / 'libpython3.11.so').read_bytes() == b'owned'
