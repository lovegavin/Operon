"""Library discovery never imports science; selected code uses real transport/install."""
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import time

import pytest

from operon.plugins import PluginManager
from operon.remote.library import compare, inventory, export_provider, install_selected
from operon.remote.transfers import TransferStore
from src.web.transfers import TransferClient
from src.web.remote_service import RemoteManager
from extension_fixtures import write_extension
from test_remote_handshake import remote, forbidden


def state(ids=('test.new',), *, name='sample', enabled=True, kind='operator'):
    return {'packages': [{'name': name, 'version': '1.0.0', 'enabled': enabled, 'origin': 'wheel', 'sha256': 'a'}],
            'descriptors': [{'distribution': name, 'id': i, 'kind': kind, 'title': i, 'code_sha': 'a', 'declaration_sha': 'b'} for i in ids]}


def test_comparison_is_kind_aware_and_disabled_local_is_ignored():
    local = inventory(state())
    same = inventory(state(kind='reader'))
    assert compare(local, same)['missing_count'] == 1
    assert compare(inventory(state(enabled=False)), same)['packages'] == []
    assert compare(local, local)['missing_count'] == 0


@pytest.mark.parametrize('existing,reason', [
    (state(('old',), enabled=False), 'remote_package_disabled'),
    (state(('old', 'server-only')), 'remote_only_entries'),
    (state(('old',), name='different'), 'different_provider'),
])
def test_never_overwrite_disabled_custom_or_other_provider(existing, reason):
    result = compare(inventory(state(('old', 'new'))), inventory(existing))
    assert result['packages'][0]['reason'] == reason
    assert not result['packages'][0]['selectable']


def test_same_provider_supplement_discloses_whole_package_update_and_aliases():
    result = compare(inventory(state(('old', 'new'), name='operon-core')),
                     inventory(state(('old',), name='operon-core')))
    assert result['packages'][0]['selectable']
    assert result['packages'][0]['replaces'] == 1
    assert [d['id'] for d in result['packages'][0]['missing']] == ['new']


@pytest.fixture
def wheel(tmp_path):
    from operon.dropins import single_file_wheel
    source = tmp_path/'addition.py'
    write_extension(source, '''OPERON_PLUGIN = {'name': 'remote-library-example'}
from operon_sdk import Step
raise AssertionError('Registration must never import provider code')
class Addition(Step):
    name = 'test.remote_addition'
    input_contracts = []
    output_contract = {'mode': 'report'}
    parameters_schema = {'type': 'object'}
    dependencies = ['never-install-this-scientific-package>=999']
    def run(self, ctx, inputs):
        raise AssertionError('Not a workflow execution')
''')
    return single_file_wheel(source, tmp_path/'wheels')


def upload(wheel, tmp_path):
    transfers = TransferStore(tmp_path/'transfers', chunk_bytes=1024, scan_bytes=2048)
    client = TransferClient(transfers.dispatch, tmp_path/'client', chunk_bytes=1024)
    reference = client.upload(wheel)
    assert client.upload(wheel)['reused']  # identical files reuse the verified object
    return transfers, {'filename': wheel.name, 'reference': reference}


def test_real_upload_static_install_and_stale_revision_rollback(tmp_path, wheel, monkeypatch):
    manager = PluginManager(tmp_path/'remote', source_root=None)
    previous = manager.state()
    transfers, item = upload(wheel, tmp_path)
    monkeypatch.setattr('operon.targets.TargetBuilder.prepare', forbidden)
    payload = {'files': [item], 'remote_revision': inventory(previous)['revision']}
    install_selected(manager, transfers, payload)
    installed = manager.state()
    assert 'test.remote_addition' in {d['id'] for d in installed['descriptors']}
    assert not installed.get('shared_paths')
    receipt = manager.registry.read_bytes()
    with pytest.raises(ValueError, match='changed'):
        install_selected(manager, transfers, payload)
    assert manager.registry.read_bytes() == receipt
    local_wheel = export_provider(manager, installed, 'remote-library-example', tmp_path/'export')
    assert local_wheel.read_bytes() == wheel.read_bytes()


def test_corrupt_or_unverified_transfer_cannot_change_registry(tmp_path, wheel):
    manager = PluginManager(tmp_path/'remote', source_root=None)
    revision = inventory(manager.state())['revision']
    before = manager.registry.read_bytes()
    transfers, item = upload(wheel, tmp_path)
    item['reference']['sha256'] = '0'*64
    with pytest.raises((ValueError, FileNotFoundError)):
        install_selected(manager, transfers, {'files': [item], 'remote_revision': revision})
    assert manager.registry.read_bytes() == before


def test_bundled_provider_export_uses_registered_source_without_import(tmp_path):
    from operon.install_targets import wheel_entries
    manager = PluginManager(tmp_path/'local')
    original = manager.state()
    name = original['packages'][0]['name']
    wheel = export_provider(manager, original, name, tmp_path/'export')
    entries = wheel_entries(wheel)
    assert {e['expected']['id'] for e in entries} == {d['id'] for d in original['descriptors'] if d['distribution'] == name}


def test_connection_checks_once_and_explicit_selected_install_closes_loop(remote, tmp_path, wheel, monkeypatch):
    local = PluginManager(tmp_path/'local')
    local.install(wheel)
    calls = []
    class Connection:
        connected = True
        def __init__(self, *_):
            self.info = remote.dispatch('bootstrap', {})
        def call(self, method, params=None):
            calls.append(method)
            return remote.dispatch(method, params or {})
        def close(self): self.connected = False
    # No separate local allocator is needed for this in-process transport test.
    admission = SimpleNamespace(reserve=lambda *a: True, release=lambda *a: None)
    manager = RemoteManager(SimpleNamespace(directory=tmp_path, plugins=local, admission=admission), Connection)
    key = manager.save({'name': 'test', 'host': 'example.org', 'username': 'tester',
                        'app_dir': '/app', 'workspace': '/work'})['id']
    try:
        connected = manager.connect(key, {})
        checked = connected['library_check']
        assert checked['missing_count'] == 1
        assert calls == ['library_manifest']
        assert not remote.handshake.maintenance_running
        monkeypatch.setattr('operon.targets.TargetBuilder.prepare', forbidden)
        manager.start_library_install(key, {**checked, 'packages': ['remote-library-example']})
        deadline = time.monotonic()+90
        while manager.library_status(key)['status'] == 'running' and time.monotonic() < deadline:
            time.sleep(.1)
        result = manager.library_status(key)
        assert result['status'] == 'complete', result
        assert result['result']['missing_count'] == 0
        assert 'library_install' in calls and 'transfer_chunk' in calls
        assert not remote.handshake.maintenance_running
        # The registered operator's unsatisfied science dependency remains
        # unchecked: installing code must not run pip repair or operator imports.
        entry = remote.service.dependencies.entries['test.remote_addition']
        assert entry['status'] == 'unchecked'
    finally:
        manager.close()


def test_old_server_check_has_upgrade_guidance_without_install(tmp_path):
    local = SimpleNamespace(state=lambda: state())
    manager = RemoteManager(SimpleNamespace(directory=tmp_path, plugins=local))
    key = manager.save({'name': 'test', 'host': 'example.org', 'username': 'tester', 'app_dir': '/app', 'workspace': '/work'})['id']
    manager.connections[key] = SimpleNamespace(connected=True, info={'catalog': {'operators': [], 'readers': []}}, call=forbidden)
    result = manager.check_library(key)
    assert result['supported'] is False and result['missing_count'] == 1
    assert result['packages'][0]['reason'] == 'server_upgrade_required'


def test_server_install_rejects_active_environment_maintenance(remote, tmp_path, wheel):
    transfers, item = upload(wheel, tmp_path)
    before = remote.service.plugins.registry.read_bytes()
    guard = remote.service.execution_environment_guard()
    environment = remote.service.environment_identity()
    token = guard.begin(owner=remote.service.owner, kind='test-maintenance', environment=environment)
    try:
        revision = inventory(remote.service.plugins.state())['revision']
        remote.handshake.install_library({'files': [item], 'remote_revision': revision}, transfers, maintenance_factory=lambda: None)
        remote.handshake.maintenance_thread.join(30)
        assert not remote.handshake.maintenance_running
        assert 'already active' in remote.handshake.maintenance['error']
        assert remote.service.plugins.registry.read_bytes() == before
        assert guard.status()['maintenances'][environment]['id'] == token.id
    finally:
        guard.end(token)


def test_missing_library_capability_does_not_make_ssh_connect_fail(tmp_path):
    class Connection:
        connected = True
        def __init__(self, *_):
            self.info = {'catalog': {'operators': [], 'readers': []}, 'dependencies': {'entries': [{'status': 'unchecked'}]}}
        call = staticmethod(forbidden)
        def close(self): self.connected = False
    manager = RemoteManager(SimpleNamespace(directory=tmp_path, plugins=SimpleNamespace(state=lambda: state())), Connection)
    key = manager.save({'name': 'test', 'host': 'example.org', 'username': 'tester', 'app_dir': '/app', 'workspace': '/work'})['id']
    result = manager.connect(key, {})
    assert manager.status()[0]['connected']
    assert not result['library_check']['supported']
    manager.close()


def test_library_endpoints_share_manager_without_implicit_installs():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    calls = []
    manager = SimpleNamespace(check_library=lambda key: calls.append(('check', key)) or {'missing_count': 1},
                              start_library_install=lambda key, payload: calls.append(('install', key, payload)) or {'status': 'running'},
                              library_status=lambda key: {'status': 'complete'})
    from src.web.remote_api import mount_remote
    app = FastAPI()
    mount_remote(app, SimpleNamespace(remotes=manager))
    with TestClient(app) as client:
        assert client.post('/api/remote/example/library/check').json() == {'missing_count': 1}
        assert calls == [('check', 'example')]
        selection = {'packages': ['sample'], 'local_revision': 'local', 'remote_revision': 'remote'}
        assert client.post('/api/remote/example/library/install', json=selection).json()['status'] == 'running'
        assert calls[-1] == ('install', 'example', selection)
        assert client.get('/api/remote/example/library/status').json()['status'] == 'complete'
