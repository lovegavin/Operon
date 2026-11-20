"""Resource readiness must feed the environment status shown by the agent."""

from __future__ import annotations

import pytest

from operon.remote import server as remote_server


@pytest.fixture(autouse=True)
def _clean_state():
    remote_server._SNAPSHOT_SERVICE.clear()
    remote_server._RESOURCE_CACHE['items'] = {}
    remote_server._RESOURCE_CACHE['at'] = 0.0
    yield
    remote_server._SNAPSHOT_SERVICE.clear()
    remote_server._RESOURCE_CACHE['items'] = {}
    remote_server._RESOURCE_CACHE['at'] = 0.0


def test_resource_readiness_counts_units(monkeypatch):
    catalogue = {
        'alphafold2': {
            'official_root': 'afdb',
            'state': 'partial',
            'units': [
                {
                    'name': 'afdb',
                    'files': [
                        {'path': 'params/params_model_1_ptm.npz', 'present': True},
                        {'path': 'uniref90/uniref90.fasta', 'present': False},
                    ],
                }
            ],
        }
    }
    monkeypatch.setattr(remote_server, '_resource_catalogue', lambda service: catalogue)
    remote_server._SNAPSHOT_SERVICE['service'] = object()

    ready, total, missing = remote_server.resource_readiness(['alphafold2'])
    assert (ready, total) == (0, 1)
    assert missing == ['afdb']


def test_resource_readiness_ready_unit(monkeypatch):
    catalogue = {
        'esm2': {
            'state': 'downloaded',
            'units': [
                {'name': 'esm2_t6_8M_UR50D.pt', 'files': [{'path': 'esm2_t6_8M_UR50D.pt', 'present': True}]}
            ],
        }
    }
    monkeypatch.setattr(remote_server, '_resource_catalogue', lambda service: catalogue)
    remote_server._SNAPSHOT_SERVICE['service'] = object()

    assert remote_server.resource_readiness(['esm2']) == (1, 1, [])


def test_snapshot_downgrades_ready_environment_with_missing_resources(monkeypatch):
    monkeypatch.setattr(remote_server, '_environment_plan', lambda service: (
        '/root', '/source',
        {'alphafold2': {'status': 'ready', 'error': '', 'location': '/tmp/af2'}},
    ))
    from operon import environment_install as environment_install_module

    monkeypatch.setattr(environment_install_module, 'dependency_status',
                        lambda entry, location: (1, 1, [{'kind': 'requirements', 'name': 'numpy', 'installed': True}]))
    monkeypatch.setattr(remote_server, '_resource_catalogue', lambda service: {
        'alphafold2': {'official_root': 'afdb', 'state': 'partial',
                       'units': [{'name': 'afdb', 'files': [{'path': 'a', 'present': False}]}]},
    })

    snapshot = remote_server.environment_snapshot(object())
    item = snapshot['environments']['alphafold2']
    assert item['resources_total'] == 1
    assert item['resources_ready'] == 0
    assert item['status'] == 'incomplete'
    assert '资源未齐备（0/1）' in item['error']

def test_unit_downloads_falls_back_to_a_declared_rsync_source() -> None:
    from types import SimpleNamespace

    from src.web import resource_api

    resource = SimpleNamespace(
        id='pdb_mmcif',
        downloads=(),
        rsync={'url': 'rsync://example.invalid/pdb/mmCIF/', 'note': 'rsync only'},
        components=(),
    )

    downloads, allowed = resource_api.unit_downloads('pdb_mmcif', resource, None)

    assert allowed is None
    assert downloads == [{'path': '', 'rsync': {'url': 'rsync://example.invalid/pdb/mmCIF/', 'note': 'rsync only'}}]


def test_rsync_only_unit_still_reports_download_support() -> None:
    from types import SimpleNamespace

    from src.web import resource_api

    resource = SimpleNamespace(
        id='pdb_mmcif',
        downloads=(),
        rsync={'url': 'rsync://example.invalid/pdb/mmCIF/'},
        components=(),
    )

    downloads, allowed = resource_api.unit_downloads('pdb_mmcif', resource, None)
    assert downloads and allowed is None

