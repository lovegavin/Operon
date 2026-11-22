"""A stale channel is repaired once before a remote call reports the break."""
from types import SimpleNamespace

import pytest

from operon.remote.client import RemoteError
from src.web.remote_service import RemoteManager


class Connection:
    """Connected until ``fail`` is set; ``calls`` records the RPC methods."""

    instances = []

    def __init__(self, *args, **kwargs):
        self.connected = True
        self.fail = False
        self.calls = []
        Connection.instances.append(self)

    def close(self):
        self.connected = False

    def call(self, method, params=None):
        self.calls.append(method)
        if self.fail:
            raise RemoteError('gone', code='remote_disconnected')
        return {'method': method}


def manager(tmp_path):
    Connection.instances = []
    return RemoteManager(SimpleNamespace(directory=tmp_path), connection_factory=Connection)


def profile(instance, auth='key'):
    return instance.save({'name': 'srv', 'host': '10.0.0.1', 'port': 22, 'username': 'u', 'auth': auth,
                          'key_path': '/k', 'python': 'python3', 'app_dir': '/opt/operon',
                          'workspace': '/work', 'mode': 'exec', 'menu_choice': ''})['id']


def test_a_missing_connection_is_restored_before_the_call(tmp_path):
    instance = manager(tmp_path)
    key = profile(instance)

    def connect(key, credentials, **kwargs):
        instance.connections[key] = Connection()

    instance.connect = connect

    assert instance.call(key, 'environments') == {'method': 'environments'}


def test_a_password_profile_is_reported_instead_of_reconnected(tmp_path):
    instance = manager(tmp_path)
    key = profile(instance, auth='password')
    instance.connect = lambda key, credentials, **kwargs: (_ for _ in ()).throw(AssertionError('no'))

    with pytest.raises(RemoteError) as error:
        instance.call(key, 'environments')

    assert error.value.code == 'remote_disconnected'
    assert '服务器未连接' in str(error.value)


def test_a_stale_channel_is_replaced_once(tmp_path):
    instance = manager(tmp_path)
    key = profile(instance)
    stale = Connection()
    stale.fail = True
    instance.connections[key] = stale

    def connect(key, credentials, **kwargs):
        instance.connections[key] = Connection()

    instance.connect = connect

    assert instance.call(key, 'environments') == {'method': 'environments'}
    assert stale.calls == ['environments']
    assert instance.connections[key] is not stale


def test_a_break_after_the_retry_is_reported(tmp_path):
    instance = manager(tmp_path)
    key = profile(instance)
    instance.connections[key] = Connection()
    instance.connections[key].fail = True

    def connect(key, credentials, **kwargs):
        instance.connections[key] = Connection()
        instance.connections[key].fail = True

    instance.connect = connect

    with pytest.raises(RemoteError) as error:
        instance.call(key, 'environments')

    assert error.value.code == 'remote_disconnected'
