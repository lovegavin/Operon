"""The install POST starts the upgrade in the background and reports progress."""
import threading
import time
from types import SimpleNamespace

from operon.remote.client import HostKeyRequired
from src.web.remote_service import RemoteManager


def make(tmp_path):
    return RemoteManager(SimpleNamespace(directory=tmp_path))


def save(manager):
    return manager.save({'name': 'test', 'host': 'example.org', 'username': 'tester',
                         'app_dir': '/app', 'workspace': '/work',
                         'environment': 'managed'})['id']


def test_start_install_returns_immediately_and_tracks_the_worker(tmp_path):
    manager = make(tmp_path)
    key = save(manager)
    entered, release = threading.Event(), threading.Event()

    def connect(target, credentials, *, install=False, force=False):
        assert (target, install, force) == (key, True, True)
        entered.set(); release.wait(10)
        with manager.lock:
            manager.progress[key] = {'running': False, 'lines': ['已连接'], 'error': ''}

    manager.connect = connect
    assert manager.start_install(key, {'password': 'secret'}, force=True) == {'status': 'running', 'started': True}
    assert entered.wait(5)
    assert manager.start_install(key, {}, force=True) == {'status': 'running', 'started': False}
    assert manager.setup_status(key)['running'] is True
    release.set()
    deadline = time.monotonic() + 5
    while manager.installing and time.monotonic() < deadline:
        time.sleep(.01)
    assert not manager.installing
    assert manager.setup_status(key)['running'] is False


def test_install_worker_reports_the_host_key_for_trust(tmp_path):
    manager = make(tmp_path)
    key = save(manager)

    class Key:
        def get_name(self):
            return 'ssh-ed25519'

        def get_base64(self):
            return 'AAAA'

        def asbytes(self):
            return b'key'

    def connect(*args, **kwargs):
        raise HostKeyRequired(Key(), changed=True)

    manager.connect = connect
    assert manager.start_install(key, {})['started'] is True
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        if not manager.setup_status(key)['running'] and manager.setup_status(key).get('error'):
            break
        time.sleep(.01)
    state = manager.setup_status(key)
    assert state['code'] == 'host_key_required'
    assert state['error'] == '需要先核对主机指纹再升级。'
    assert state['fingerprint'].startswith('SHA256:')
    assert state['changed'] is True
    assert manager.pending_keys[key]['fingerprint'] == state['fingerprint']

    class Failing(Exception):
        def __init__(self):
            self.code = 'remote_upgrade_blocked'

        def __str__(self):
            return '旧版服务端仍有任务或无法安全停止，升级已取消。'

    manager.connect = lambda *a, **k: (_ for _ in ()).throw(Failing())
    assert manager.start_install(key, {})['started'] is True
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        if not manager.setup_status(key)['running'] and manager.setup_status(key).get('error'):
            break
        time.sleep(.01)
    state = manager.setup_status(key)
    assert state['code'] == 'remote_upgrade_blocked'
    assert state['error'].startswith('旧版服务端仍有任务')
