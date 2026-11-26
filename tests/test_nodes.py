from types import SimpleNamespace

import pytest

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


def _batch(name, state='idle', cpus=8, idle=8, memory=1000, free=800, gpus=0, ready=True):
    return {'name': name, 'state': state, 'cpus': cpus, 'cpus_idle': idle,
            'memory_mb': memory, 'memory_free_mb': free, 'gpus': gpus, 'env_ready': ready}


def test_capacity_counts_idle_cpu_and_free_memory():
    roomy = _batch('roomy', cpus=64, idle=64, memory=1000, free=1000)
    busy = _batch('busy', state='mix', cpus=64, idle=4, memory=1000, free=100)
    assert nodes.capacity(roomy) > nodes.capacity(busy)
    assert nodes.capacity(busy) >= 0.0


def test_readiness_lives_in_the_score():
    ready = nodes.readiness_score(_batch('ready', ready=True))
    waiting = nodes.readiness_score(_batch('waiting', ready=False))
    assert 0.5 <= ready <= 1.0
    assert 0.0 <= waiting < 0.5
    assert waiting < ready


def test_ready_small_node_ranks_above_unready_big_node():
    ranked = nodes.rank_compute([
        _batch('big', cpus=96, idle=96, memory=510000, free=500000, gpus=1, ready=False),
        _batch('small', cpus=8, idle=8, memory=8000, free=4000, ready=True)])
    assert [item['name'] for item in ranked] == ['small', 'big']
    assert ranked[0]['rank'] == 1 and ranked[1]['rank'] == 2
    assert ranked[1]['reason'] == '环境未就绪'


def test_all_unready_nodes_keep_relative_capacity_order():
    ranked = nodes.rank_compute([
        _batch('busy', state='mix', cpus=64, idle=8, memory=1000, free=200, ready=False),
        _batch('idle', cpus=64, idle=64, memory=1000, free=900, ready=False)])
    assert [item['name'] for item in ranked] == ['idle', 'busy']
    assert ranked[0]['score'] > ranked[1]['score']


def test_slurm_parser_uses_cpu_states_and_free_memory(monkeypatch):
    class _Done:
        stdout = 'node80|all*|up|mix|16/80/0/96|510000|410000|gpu:1\n'

    monkeypatch.setattr(nodes.shutil, 'which', lambda name: '/usr/bin/' + name)
    monkeypatch.setattr(nodes.subprocess, 'run', lambda *args, **kwargs: _Done())
    monkeypatch.setattr(nodes, '_node_ready', lambda name, marker: name != 'node80')
    value = nodes._slurm_nodes(ready_marker='/tmp/python')
    node = value['nodes'][0]
    assert node['cpus'] == 96 and node['cpus_idle'] == 80
    assert node['memory_mb'] == 510000 and node['memory_free_mb'] == 410000
    assert node['gpus'] == 1 and node['env_ready'] is False
    assert node['score'] < 0.5


def test_execution_node_reads_the_runtime_request():
    assert nodes.execution_node({'runtime': {'execution': {'node': ' node79 '}}}) == 'node79'
    assert nodes.execution_node({'runtime': {'execution': {'node': 3}}}) == ''
    assert nodes.execution_node({}) == ''


def test_srun_command_wraps_the_worker(monkeypatch):
    monkeypatch.setattr(nodes.shutil, 'which', lambda name: '/usr/bin/srun' if name == 'srun' else None)
    command = nodes.srun_command(['/envs/core/bin/python', '-m', 'operon.worker', 'd'], 'node79', 8)
    assert command[:9] == ['/usr/bin/srun', '-N', '1', '-n', '1', '--nodelist', 'node79', '-c', '8']
    assert command[9:11] == ['--time', '1440']
    assert command[11:] == ['--export=ALL', '/envs/core/bin/python', '-m', 'operon.worker', 'd']
    assert nodes.srun_command(['python', 'x'], '', 4) == ['python', 'x']


def test_srun_command_rejects_bad_names_and_missing_slurm(monkeypatch):
    monkeypatch.setattr(nodes.shutil, 'which', lambda name: '/usr/bin/srun')
    with pytest.raises(RuntimeError, match='invalid compute node name'):
        nodes.srun_command(['python'], 'bad node', 1)
    monkeypatch.setattr(nodes.shutil, 'which', lambda name: None)
    with pytest.raises(RuntimeError, match='slurm'):
        nodes.srun_command(['python'], 'node79', 1)
