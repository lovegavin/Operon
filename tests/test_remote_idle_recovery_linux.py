"""Real Linux localhost SSH bridge: same bridge recovers an exited RPC daemon."""
import os
from pathlib import Path
import socket
import sys
import time

import pytest

pytestmark = pytest.mark.skipif(not sys.platform.startswith('linux'),
                                reason='requires a real Linux Unix-socket daemon')


def profile(workspace, port, user, key):
    import paramiko
    transport = paramiko.Transport(('127.0.0.1', int(port)))
    try:
        transport.start_client(timeout=10)
        key_value = transport.get_remote_server_key()
    finally:
        transport.close()
    import base64
    import hashlib
    host_key = {'type': key_value.get_name(), 'base64': key_value.get_base64(),
                'fingerprint': 'SHA256:' + base64.b64encode(
                    hashlib.sha256(key_value.asbytes()).digest()).decode().rstrip('=')}
    return {
        'id': 'localhost-linux', 'name': 'Linux localhost', 'host': '127.0.0.1',
        'port': int(port), 'username': user, 'auth': 'key', 'key_path': str(key),
        'host_key': host_key, 'environment': 'existing', 'mode': 'exec',
        'app_dir': str(Path(__file__).resolve().parents[1]),
        'workspace': str(workspace), 'python': sys.executable,
    }


def connect(value):
    from biopipe.remote.client import SSHConnection
    connection = SSHConnection(value, {'password': ''}, install=False)
    assert connection.connected
    return connection


def wait_socket(path, present, timeout=90):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if Path(path).exists() is present:
            return
        time.sleep(.1)
    pytest.fail(f'socket existence {present} not reached at {path}')


def test_same_bridge_recovers_after_daemon_exit(tmp_path):
    workspace = tmp_path / 'workspace'; workspace.mkdir()
    port = os.environ['OPERON_LOCAL_SSH_PORT']
    user = os.environ['OPERON_LOCAL_SSH_USER']
    key = Path(os.environ['OPERON_LOCAL_SSH_KEY'])
    value = profile(workspace, port, user, key)
    connection = connect(value)
    try:
        assert connection.call('bootstrap', {})['workspace']
        from biopipe.remote.server import socket_path
        path = socket_path(workspace)
        assert path.exists()
        retired = connection.call('retire_if_idle', {})
        assert retired['retired'] is True
        wait_socket(path, False)
        # The SSH bridge is still the same live channel.  A reconnect before
        # this request would hide the defect this test protects.
        assert connection.connected
        recovered = connection.call('bootstrap', {})
        assert recovered['workspace'] == str(workspace)
        assert connection.channel.active
        events = (workspace / '.studio/remote/bridge.events.jsonl').read_text(encoding='utf-8')
        assert 'daemon_missing' in events and 'daemon_recovered' in events
    finally:
        connection.close()


@pytest.mark.skipif(os.environ.get('OPERON_REAL_IDLE') != '1',
                    reason='slow production-timeout smoke; set OPERON_REAL_IDLE=1')
def test_same_bridge_recovers_after_production_idle_timeout(tmp_path):
    workspace = tmp_path / 'workspace'; workspace.mkdir()
    value = profile(workspace, os.environ['OPERON_LOCAL_SSH_PORT'],
                    os.environ['OPERON_LOCAL_SSH_USER'],
                    Path(os.environ['OPERON_LOCAL_SSH_KEY']))
    connection = connect(value)
    try:
        connection.call('bootstrap', {})
        from biopipe.remote.server import socket_path
        path = socket_path(workspace)
        wait_socket(path, False, timeout=330)
        assert connection.connected and connection.channel.active
        assert connection.call('bootstrap', {})['workspace'] == str(workspace)
    finally:
        connection.close()
