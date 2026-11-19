from copy import deepcopy
from types import SimpleNamespace
import time

from src.web.remote_service import RemoteManager


def stub_manager(tmp_path, manifest, checked, calls):
    local = SimpleNamespace(state=lambda: {'packages': [{'name': 'operon-core', 'version': '1.0.0',
                                                         'enabled': True, 'origin': 'wheel', 'sha256': 'a'}],
                                           'descriptors': []})
    manager = RemoteManager(SimpleNamespace(directory=tmp_path, plugins=local))
    key = manager.save({'name': 'test', 'host': 'example.org', 'username': 'tester',
                        'app_dir': '/app', 'workspace': '/work'})['id']

    class Connection:
        connected = True
        info = {'handshake': {'library_capabilities': ['library_sync_v1', 'library_remove_v1']}}

        def call(self, method, params=None):
            calls.append((method, params))
            if method == 'library_manifest':
                return manifest
            if method == 'library_remove':
                return {'removed': (params or {}).get('name')}
            if method == 'refresh_registry':
                return {'started': True}
            if method == 'refresh_status':
                return {'registry_refresh': {'running': False, 'error': None}}
            raise AssertionError(method)

    manager.connections[key] = Connection()
    manager.check_library = lambda target: deepcopy(checked)
    return manager, key


def test_plan_adds_missing_and_removes_remote_only_packages(tmp_path):
    calls = []
    checked = {'local_revision': 'l1', 'remote_revision': 'r1',
               'packages': [{'name': 'operon-core', 'selectable': True, 'reason': None},
                            {'name': 'operon-extra', 'selectable': False, 'reason': 'different_provider'}]}
    manifest = {'packages': [{'name': 'operon-core'}, {'name': 'operon-legacy'}]}
    manager, key = stub_manager(tmp_path, manifest, checked, calls)
    plan = manager.library_plan(key)
    assert plan['install'] == ['operon-core']
    assert plan['remove'] == ['operon-legacy']
    assert plan['blocked'] == [{'name': 'operon-extra', 'reason': 'different_provider'}]
    assert plan['removal_supported'] is True


def test_sync_removes_extra_packages_and_reports_complete(tmp_path):
    calls = []
    checked = {'local_revision': 'l1', 'remote_revision': 'r1', 'packages': []}
    manifest = {'packages': [{'name': 'operon-legacy'}, {'name': 'operon-second'}]}
    manager, key = stub_manager(tmp_path, manifest, checked, calls)
    manager.start_library_sync(key)
    deadline = time.monotonic() + 10
    while manager.library_status(key).get('status') == 'running' and time.monotonic() < deadline:
        time.sleep(.05)
    status = manager.library_status(key)
    assert status['status'] == 'complete', status
    assert status['removed'] == ['operon-legacy', 'operon-second']
    removed = [params['name'] for method, params in calls if method == 'library_remove']
    assert removed == ['operon-legacy', 'operon-second']
    assert any(method == 'refresh_registry' for method, _ in calls)