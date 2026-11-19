"""Unit and per-file download behaviour for large resources."""

from __future__ import annotations

import io
import tarfile
import threading
from pathlib import Path
from types import SimpleNamespace

import pytest

from src.web import resource_api


def _resource(**overrides):
    values = {
        'id': 'payloads',
        'downloads': (),
        'components': (
            {'name': 'bundle', 'url': 'https://example.invalid/project', 'files': ['params/model.npz']},
        ),
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_unit_downloads_uses_declared_file_sources():
    entry = {
        'path': 'params/model.npz',
        'url': 'https://example.invalid/models.tar',
        'archive': 'tar',
        'member': 'params/model.npz',
        'bytes': 4,
        'unit': 'bundle',
    }
    resource = _resource(downloads=(entry,))
    downloads, allowed = resource_api.unit_downloads('payloads', resource, 'bundle')
    assert downloads == [entry]
    assert allowed == {'params/model.npz'}


def test_unit_downloads_rejects_a_project_page():
    resource = _resource()
    with pytest.raises(ValueError) as error:
        resource_api.unit_downloads('payloads', resource, 'bundle')
    assert 'only documents a project page' in str(error.value)


def test_download_extracts_one_archive_member(tmp_path):
    payload = b'model-bytes'
    bundle = io.BytesIO()
    with tarfile.open(fileobj=bundle, mode='w:gz') as archive:
        info = tarfile.TarInfo('params/model.npz')
        info.size = len(payload)
        archive.addfile(info, io.BytesIO(payload))
    raw = bundle.getvalue()

    entry = {
        'path': 'params/model.npz',
        'url': 'https://example.invalid/models.tar',
        'archive': 'tar',
        'member': 'params/model.npz',
        'bytes': len(payload),
    }
    job: dict = {'completed_bytes': 0, 'bytes': 0}

    def opener(url, token):
        assert url == entry['url']
        return io.BytesIO(raw)

    result = resource_api._download(entry, tmp_path, overwrite=False, event=threading.Event(), job=job, opener=opener)
    assert result['status'] == 'extracted'
    assert (tmp_path / 'params/model.npz').read_bytes() == payload
    assert not (tmp_path / 'params/model.npz.part').exists()
    assert job['bytes'] == len(raw)


def test_download_keeps_an_existing_file(tmp_path):
    target = tmp_path / 'params/model.npz'
    target.parent.mkdir(parents=True)
    target.write_bytes(b'model-bytes')
    entry = {'path': 'params/model.npz', 'url': 'https://example.invalid/models.tar', 'bytes': 11}
    job: dict = {'completed_bytes': 0, 'bytes': 0}
    result = resource_api._download(
        entry, tmp_path, overwrite=False, event=threading.Event(), job=job,
        opener=lambda url, token: pytest.fail('an existing file must not be downloaded again'),
    )
    assert result['status'] == 'existing'