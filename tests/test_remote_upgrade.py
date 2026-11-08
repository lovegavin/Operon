"""Explicit upgrades retire only idle servers; ordinary clients reuse installs."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace
import sys
import threading

import pytest

from biopipe.remote.server import RemoteService
from biopipe.documents import CommandError
from src.web.admission import HostAdmission, AdmissionConflict, process_identity


def daemon(*, jobs=(), busy=False):
    value = RemoteService.__new__(RemoteService)
    value._lifecycle = threading.RLock()
    value._active_requests = 0
    value._draining = False
    value.stop_requested = threading.Event()
    value.service = SimpleNamespace(history=lambda: jobs)
    value.alive = lambda: busy
    value._dispatch = lambda method, params: {'accepted': True}
    return value


@pytest.mark.parametrize('status', ['queued', 'preparing', 'running', 'recovery_required'])
def test_upgrade_preserves_pending_and_running_jobs(status):
    service = daemon(jobs=[{'status': status}])
    assert not service.dispatch('retire_if_idle', {})['retired']
    assert not service.stop_requested.is_set()
    assert service.dispatch('history', {})['accepted']


def test_upgrade_preserves_transfers_maintenance_and_inflight_requests():
    service = daemon(busy=True)
    assert not service.retire_if_idle()['retired']
    service = daemon()
    started, finish = threading.Event(), threading.Event()
    def request(*args):
        started.set()
        assert finish.wait(5)
    service._dispatch = request
    with ThreadPoolExecutor() as pool:
        pending = pool.submit(service.dispatch, 'run', {})
        assert started.wait(5)
        assert not service.retire_if_idle()['retired']
        finish.set()
        pending.result()
    assert service.retire_if_idle()['retired']
    with pytest.raises(CommandError) as error:
        service.dispatch('run', {})
    assert error.value.code == 'server_draining'


def test_idle_upgrade_retires_without_cancelling_any_jobs():
    service = daemon(jobs=[{'status': 'complete', 'logs_complete': True}])
    assert service.retire_if_idle() == {'retired': True}
    assert service.stop_requested.is_set()
    assert service.retire_if_idle() == {'retired': True}


def test_conflict_names_live_processes_and_does_not_discard_the_ledger(tmp_path):
    from src.web.storage import atomic_json
    admission = HostAdmission(tmp_path / 'admission', available_bytes=1024**3, cpu_threads=2)
    identity = process_identity()
    owner = {**identity, 'pid': identity['pid'] + 1000000, 'service_id': 'test-coordinator'}
    before = admission.path.read_bytes()
    try:
        with pytest.raises(AdmissionConflict) as error:
            admission.claim_coordinator(owner)
        assert error.value.code == 'legacy_launchers_active'
        assert error.value.details['clients'] == [identity]
        assert str(identity['pid']) in str(error.value)
        assert admission.path.read_bytes() == before
    finally:
        admission.close()


@pytest.mark.parametrize('allowed', [True, False])
def test_explicit_upgrade_restarts_only_after_daemon_acknowledges_idle(tmp_path, monkeypatch, allowed):
    import biopipe.remote.server as module
    from biopipe import __version__
    address = tmp_path / 'daemon.sock'
    address.touch()
    monkeypatch.setitem(sys.modules, 'fcntl', SimpleNamespace(LOCK_EX=1, flock=lambda *a: None))
    monkeypatch.setattr(module, 'socket_path', lambda workspace: address)
    monkeypatch.setattr('biopipe.remote.handshake.validate_daemon_response', lambda result: result['value'])
    calls, launches = [], []
    def rpc(workspace, request):
        calls.append(request['method'])
        if request['method'] == 'retire_if_idle':
            if allowed:
                address.unlink()
            return {'ok': True, 'value': {'retired': allowed, 'reason': 'Tasks are still active'}}
        return {'ok': True, 'value': {'version': 'old-version', 'python': sys.executable,
                                     'code_root': str(Path(module.__file__).resolve().parents[2])}}
    monkeypatch.setattr(module, 'rpc', rpc)
    monkeypatch.setattr(module.subprocess, 'Popen', lambda *a, **k: launches.append(a))
    workspace = tmp_path / 'workspace'
    if allowed:
        module.ensure_daemon(workspace, upgrade=True)
        assert len(launches) == 1
    else:
        with pytest.raises(RuntimeError, match='Tasks are still active'):
            module.ensure_daemon(workspace, upgrade=True)
        assert not launches and address.exists()
    assert calls[:2] == ['handshake', 'retire_if_idle']


def test_ordinary_connection_reuses_other_compatible_installation(tmp_path, monkeypatch):
    import biopipe.remote.server as module
    monkeypatch.setitem(sys.modules, 'fcntl', SimpleNamespace(LOCK_EX=1, flock=lambda *a: None))
    monkeypatch.setattr(module, 'socket_path', lambda workspace: tmp_path / 'daemon.sock')
    monkeypatch.setattr('biopipe.remote.handshake.validate_daemon_response', lambda value: value)
    calls = []
    monkeypatch.setattr(module, 'rpc', lambda workspace, request: calls.append(request['method']) or {})
    module.ensure_daemon(tmp_path)
    assert calls == ['handshake']


def test_new_pool_waits_for_previous_idle_owner_before_spawning(tmp_path, monkeypatch):
    from biopipe import managed_pool as module
    import json
    root=tmp_path/'managed';root.mkdir()
    old={'implementation':'previous','owner':{'pid':1}}
    new={'implementation':'current','owner':{'pid':2}}
    (root/'instance.json').write_text(json.dumps(old))
    monkeypatch.setattr(module,'locations',lambda settings:(tmp_path/'admission',root))
    monkeypatch.setattr(module,'implementation',lambda root:'current')
    seen=[]
    def alive(record):
        if record == old:
            seen.append('old')
            return len(seen)<3
        return record==new
    monkeypatch.setattr(module,'_alive',alive)
    def spawn(*args):
        assert len(seen)>=3
        (root/'instance.json').write_text(json.dumps(new))
    monkeypatch.setattr(module,'_spawn',spawn)
    assert module.ensure_pool(None)[0]==new
