"""A graph aimed at a dropped key profile reconnects it before planning."""
from types import SimpleNamespace

from src.web.execution import ExecutionService


class Remotes:
    def __init__(self, connected):
        self.connected = connected
        self.calls = []

    def status(self):
        return [{'profile': {'id': 'p'}, 'connected': self.connected}]

    def ensure(self, key):
        self.calls.append(key)
        self.connected = True
        return {'connected': True, 'profile_id': key}


def service(remotes):
    instance = object.__new__(ExecutionService)
    instance.service = SimpleNamespace(remotes=remotes)
    return instance


def graph(kind='ssh', profile_id='p'):
    execution = {'kind': kind} if kind == 'local' else {'kind': 'ssh', 'profile_id': profile_id}
    return SimpleNamespace(runtime={'execution': execution})


def test_a_dropped_key_profile_is_reconnected_before_planning():
    remotes = Remotes(connected=False)
    service(remotes)._ensure_target(graph())
    assert remotes.calls == ['p']


def test_a_connected_profile_is_not_touched():
    remotes = Remotes(connected=True)
    service(remotes)._ensure_target(graph())
    assert remotes.calls == []


def test_a_local_graph_never_connects_anything():
    remotes = Remotes(connected=False)
    service(remotes)._ensure_target(graph(kind='local'))
    assert remotes.calls == []


def test_a_graph_without_execution_settings_is_left_alone():
    remotes = Remotes(connected=False)
    service(remotes)._ensure_target(SimpleNamespace(runtime={}))
    assert remotes.calls == []
