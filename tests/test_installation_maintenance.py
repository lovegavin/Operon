import json
import os
from pathlib import Path
import subprocess
import sys
import time
import uuid

import pytest

from operon.installation_maintenance import InstallationBusy, mutex_name, start_guard, maintenance_active


@pytest.mark.skipif(os.name != 'nt', reason='Windows installer mutex contract')
def test_live_installer_blocks_pool_restart_and_crash_releases_gate(tmp_path):
    (tmp_path / 'operon-install.json').write_text(json.dumps({'profile_id': uuid.uuid4().hex}))
    # Separate process: Windows mutexes are reentrant on the owning thread.
    code = '''import sys,time
from operon.installation_maintenance import start_guard
with start_guard(sys.argv[1]):
 print('held',flush=True)
 time.sleep(60)
'''
    child = subprocess.Popen([sys.executable, '-c', code, str(tmp_path)], stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, text=True)
    try:
        assert child.stdout.readline().strip() == 'held'
        with pytest.raises(InstallationBusy):
            with start_guard(tmp_path): pass
        # A normal startup guard is not an installer drain signal.
        assert not maintenance_active(tmp_path)
    finally:
        child.terminate(); child.communicate(timeout=10)
    with start_guard(tmp_path): pass


def test_uninstalled_source_tree_needs_no_installation_marker(tmp_path):
    assert mutex_name(tmp_path) is None
    with start_guard(tmp_path): pass
    assert not maintenance_active(tmp_path)


def test_installed_identity_is_not_derived_from_machine_paths(tmp_path):
    value = uuid.uuid4().hex
    for name in ('first', 'renamed'):
        path = tmp_path / name; path.mkdir()
        (path / 'operon-install.json').write_text(json.dumps({'profile_id': value}))
        assert mutex_name(path) == 'Local\\OperonMaintenance-' + value


@pytest.mark.skipif(os.name != 'nt', reason='Windows native installer integration')
def test_real_setup_gate_prevents_managed_pool_respawn(tmp_path, monkeypatch):
    from operon import managed_pool
    exe = Path(__file__).parent / 'native_setup/bin/Release/net8.0-windows/SetupTests.exe'
    if not exe.is_file():
        pytest.skip('Build tests/native_setup first for cross-language acceptance')
    root = tmp_path / 'installed'; (root / 'operon').mkdir(parents=True)
    (root / 'operon-install.json').write_text(json.dumps({'profile_id': uuid.uuid4().hex}))
    ready, stop = tmp_path / 'ready', tmp_path / 'stop'
    child = subprocess.Popen([str(exe), '--maintenance-gate', str(root), str(ready), str(stop)],
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                             creationflags=subprocess.CREATE_NO_WINDOW)
    try:
        deadline = time.monotonic() + 15
        while not ready.exists() and child.poll() is None and time.monotonic() < deadline:
            time.sleep(.03)
        assert ready.exists(), 'Native Setup failed to acquire its maintenance gate'
        assert maintenance_active(root)
        monkeypatch.setattr(managed_pool, '__file__', str(root / 'operon/managed_pool.py'))
        monkeypatch.setattr(managed_pool, '_spawn', lambda *args: pytest.fail('Pool respawned during uninstall'))
        with pytest.raises(InstallationBusy):
            managed_pool.ensure_pool(None)
    finally:
        stop.touch()
        try:
            child.communicate(timeout=10)
        except subprocess.TimeoutExpired:
            child.kill(); child.communicate(timeout=5)
    assert child.returncode == 0
    assert not maintenance_active(root)
    with start_guard(root): pass
