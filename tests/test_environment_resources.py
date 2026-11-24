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
    from operon import environments as environments_module

    monkeypatch.setattr(environment_install_module, 'dependency_status',
                        lambda entry, location: (1, 1, [{'kind': 'requirements', 'name': 'numpy', 'installed': True}]))
    # Only a resource the environment declares in its own manifest can downgrade
    # it; one that merely lists the environment among its consumers stays a
    # warning.  The manifest entry therefore has to declare the resource for this
    # scenario to exist at all.
    monkeypatch.setattr(environments_module, 'load', lambda: {
        'alphafold2': {'resources': ['alphafold2']},
    })
    monkeypatch.setattr(remote_server, '_resource_catalogue', lambda service: {
        'alphafold2': {'official_root': 'afdb', 'state': 'partial',
                       'units': [{'name': 'afdb', 'files': [{'path': 'a', 'present': False}]}]},
    })

    snapshot = remote_server.environment_snapshot(object())
    item = snapshot['environments']['alphafold2']
    assert item['resources_total'] == 1
    assert item['resources_ready'] == 0
    assert item['resources_declared_total'] == 1
    assert item['resources_declared_ready'] == 0
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

def test_a_shared_resource_gap_is_only_a_warning(monkeypatch):
    monkeypatch.setattr(remote_server, '_environment_plan', lambda service: (
        '/root', '/source',
        {'boltz': {'status': 'ready', 'error': '', 'location': '/tmp/boltz'}},
    ))
    from operon import environment_install as environment_install_module

    monkeypatch.setattr(environment_install_module, 'dependency_status',
                        lambda entry, location: (1, 1, [{'kind': 'requirements', 'name': 'numpy', 'installed': True}]))
    monkeypatch.setattr(environment_install_module, 'dependency_counts',
                        lambda rows: {'dependency_total': 1, 'dependency_installed': 1,
                                      'missing_dependencies': []})
    # The environment declares nothing of its own; the catalogue entry only names
    # it among several consumers, exactly like colabfold_msa does.
    monkeypatch.setattr(remote_server, '_resource_catalogue', lambda service: {
        'colabfold_msa': {'state': 'partial', 'environments': ['boltz', 'colabfold'],
                          'components': [{'name': 'uniref30_2302', 'files': [{'path': 'a', 'present': False}]}]},
    })

    snapshot = remote_server.environment_snapshot(object())
    item = snapshot['environments']['boltz']
    assert item['status'] == 'ready'
    assert item['resources_warning']


def test_declared_resources_gate_only_touches_a_ready_environment():
    assert remote_server.declared_resources_gate(0, 9, 'ready') is True
    assert remote_server.declared_resources_gate(9, 9, 'ready') is False
    assert remote_server.declared_resources_gate(0, 9, 'installing') is False
    assert remote_server.declared_resources_gate(0, 0, 'ready') is False


def test_snapshot_clears_a_stale_resource_reason(monkeypatch):
    """A ready environment keeps no reason from an earlier, incomplete snapshot."""
    monkeypatch.setattr(remote_server, '_environment_plan', lambda service: (
        '/root', '/source',
        {'alphafold2': {'status': 'ready',
                        'error': '资源未齐备（8/9）：pdb_mmcif',
                        'location': '/tmp/af2'}},
    ))
    from operon import environment_install as environment_install_module
    from operon import environments as environments_module

    monkeypatch.setattr(environment_install_module, 'dependency_status',
                        lambda entry, location: (1, 1, [{'kind': 'requirements', 'name': 'numpy', 'installed': True}]))
    monkeypatch.setattr(environments_module, 'load', lambda: {
        'alphafold2': {'resources': ['alphafold2']},
    })
    monkeypatch.setattr(remote_server, '_resource_catalogue', lambda service: {
        'alphafold2': {'official_root': 'afdb', 'state': 'present',
                       'units': [{'name': 'afdb', 'files': [{'path': 'a', 'present': True}]}]},
    })

    snapshot = remote_server.environment_snapshot(object())
    item = snapshot['environments']['alphafold2']
    assert item['resources_ready'] == item['resources_total'] == 1
    assert item['error'] == ''
    assert item['status'] == 'ready'
