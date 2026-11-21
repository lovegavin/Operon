"""A key profile is restored in place before a launch reports it as offline."""
from types import SimpleNamespace

from src.web.remote_service import RemoteManager


class Connection:
    connected = True

    def __init__(self, *args, **kwargs):
        pass

    def close(self):
        self.connected = False


def manager(tmp_path):
    return RemoteManager(SimpleNamespace(directory=tmp_path), connection_factory=Connection)


def test_a_key_profile_is_reconnected_without_a_secret(tmp_path):
    instance = manager(tmp_path)
    key = instance.save({'name': 'srv', 'host': '10.0.0.1', 'port': 22, 'username': 'u', 'auth': 'key',
                         'key_path': '/k', 'python': 'python3', 'app_dir': '/opt/operon',
                         'workspace': '/work', 'mode': 'exec', 'menu_choice': ''})['id']
    calls = []
    instance.connect = lambda key, credentials, **kwargs: calls.append((key, credentials))

    profile = instance.profile(key)
    instance._reconnect_key_profile(key, profile)

    assert calls == [(key, {})]


def test_a_password_profile_is_left_to_the_user(tmp_path):
    instance = manager(tmp_path)
    key = instance.save({'name': 'srv', 'host': '10.0.0.1', 'port': 22, 'username': 'u', 'auth': 'password',
                         'key_path': '', 'python': 'python3', 'app_dir': '/opt/operon',
                         'workspace': '/work', 'mode': 'exec', 'menu_choice': ''})['id']
    calls = []
    instance.connect = lambda key, credentials, **kwargs: calls.append(key)

    assert instance._reconnect_key_profile(key, instance.profile(key)) is None
    assert calls == []
