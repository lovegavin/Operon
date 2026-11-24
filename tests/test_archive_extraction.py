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
