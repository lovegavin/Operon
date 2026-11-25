from types import SimpleNamespace

from operon import nodes


def _capacity(available=50, total=100, cpu=8, load=1.0, disk_free=50, disk_total=100, gpus=0):
    return {'cpu_count': cpu, 'load': load,
            'memory': {'total_bytes': total, 'available_bytes': available},
            'disk': {'total_bytes': disk_total, 'free_bytes': disk_free},
            'gpus': gpus, 'slurm': {'available': False, 'nodes': [], 'idle': 0}}


def test_snapshot_reports_host_facts(tmp_path):
    value = nodes.snapshot(tmp_path)
    assert set(value) >= {'cpu_count', 'memory', 'disk', 'gpus', 'slurm', 'host', 'platform'}
    assert value['cpu_count'] >= 1
    assert value['memory']['total_bytes'] >= 0
    assert value['disk']['total_bytes'] >= 0
    assert isinstance(value['slurm'], dict)


def test_score_ranks_free_capacity():
    roomy = _capacity(available=90)
    busy = _capacity(available=5, load=8.0)
    assert nodes.score(roomy) > nodes.score(busy)
    assert 0.0 <= nodes.score(busy) <= 1.5


def test_order_prefers_available_then_score():
    items = [{'target': 'down', 'available': False, 'score': 0.99},
             {'target': 'small', 'available': True, 'score': 0.2},
             {'target': 'big', 'available': True, 'score': 0.8}]
    assert nodes.order(items) == ['big', 'small', 'down']


class _Remotes:
    def __init__(self, connected=True):
        self.connected = connected
        self.calls = 0

    def status(self):
        return [{'profile': {'id': 'k1', 'name': 'node1', 'host': '10.0.0.1'},
                 'connected': self.connected}]

    def call(self, key, method, params=None):
        assert key == 'k1' and method == 'host_capacity'
        self.calls += 1
        return {**_capacity(available=64), 'host': 'node1', 'platform': 'linux-x86_64'}


def test_inventory_merges_local_and_remote_and_caches(tmp_path):
    remotes = _Remotes()
    service = SimpleNamespace(root=tmp_path, remotes=remotes)
    first = nodes.inventory(service)
    assert [item['target'] for item in first] == ['local', 'k1']
    assert first[0]['kind'] == 'local' and first[1]['kind'] == 'ssh'
    assert first[1]['available'] is True and first[1]['score'] > 0
    nodes.inventory(service)
    assert remotes.calls == 1
    nodes.inventory(service, refresh=True)
    assert remotes.calls == 2


def test_disconnected_remote_stays_listed(tmp_path):
    remotes = _Remotes(connected=False)
    service = SimpleNamespace(root=tmp_path, remotes=remotes)
    items = nodes.inventory(service, refresh=True)
    assert items[1]['available'] is False
    assert items[1]['error'] == '服务器未连接'
    assert items[1]['score'] == 0.0
    assert remotes.calls == 0
