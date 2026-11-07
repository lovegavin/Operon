"""Independent-branch planning and real DAG overlap under the pool coordinator."""
import os
import sys
import threading
import time
from pathlib import Path

import pytest

from biopipe.engine.contracts import PoolSpec
from biopipe.engine.coordinator import Coordinator
from biopipe.engine.dag import decide_branches, parallel_estimate, split_chains
from biopipe.engine.executor import ExecutionResult, ProcessExecutor
from biopipe.engine.state import StateStore
from biopipe.engine.supervisor import LaunchSpec


class InstantExecutor:
    capability = 'fake'
    resizable = False

    def __init__(self):
        self.launches = []

    def launch(self, context):
        self.launches.append(context.unit['local_id'])
        return ExecutionResult(state='running')

    def poll(self, context):
        return ExecutionResult(state='succeeded', exit_code=0)

    def cancel(self, context, *, timeout=10.0):
        return ExecutionResult(state='cancelled')

    def reconcile(self, context):
        return ExecutionResult(state='running')


def test_linear_chain_is_not_split_but_independent_branches_are():
    nodes = ['a', 'b', 'c', 'd']
    edges = [('a', 'b'), ('a', 'c'), ('b', 'd'), ('c', 'd')]
    assigned = {node: 'local' for node in nodes}
    chains = split_chains(nodes, edges, assigned)
    assert [chain['node_ids'] for chain in chains] == [['a'], ['b'], ['c'], ['d']]
    assert chains[3]['depends_on'] == ['stage_2', 'stage_3']
    linear = split_chains(['a', 'b', 'c'], [('a', 'b'), ('b', 'c')], assigned)
    assert [chain['node_ids'] for chain in linear] == [['a', 'b', 'c']]
    assert decide_branches(parallel_estimate(chains), max_parallel=2, enabled=True)[0].run
    assert not decide_branches(parallel_estimate(chains), max_parallel=1, enabled=True)[0].run


def test_engine_coordinator_waits_for_a_join(tmp_path):
    store = StateStore(tmp_path / 'state.sqlite3')
    spec = PoolSpec('pool-dag', 'tester', 'host', 64 * 1024 * 1024, 1024 * 1024, 4)
    store.ensure_pool(spec)
    store.register_workspace('ws', 'pool-dag', str(tmp_path), 'tester')
    executor = InstantExecutor()
    coordinator = Coordinator(store, spec, executor, workspace_id='ws', principal='tester', root=tmp_path)
    coordinator.claim()
    coordinator.submit(key='k', digest='d', graph={}, parameters={}, execution={},
                       units=[
                           {'unit_id': 'a', 'node_ids': ['a'], 'depends_on': [],
                            'requirement': {'managed_budget_bytes': 1024,
                                            'process_reservation_bytes': 2048, 'cpu_threads': 1}},
                           {'unit_id': 'b', 'node_ids': ['b'], 'depends_on': [],
                            'requirement': {'managed_budget_bytes': 1024,
                                            'process_reservation_bytes': 2048, 'cpu_threads': 1}},
                           {'unit_id': 'c', 'node_ids': ['c'], 'depends_on': ['a', 'b'],
                            'requirement': {'managed_budget_bytes': 1024,
                                            'process_reservation_bytes': 2048, 'cpu_threads': 1}},
                       ])
    coordinator.run_once()
    assert sorted(executor.launches) == ['a', 'b']
    coordinator.run_once()
    assert executor.launches[-1] == 'c'
    assert sorted(executor.launches) == ['a', 'b', 'c']
    coordinator.stop()


def test_two_branches_overlap_in_real_processes_and_join_waits(tmp_path):
    store = StateStore(tmp_path / 'state.sqlite3')
    spec = PoolSpec('pool-real-dag', 'tester', 'host', 128 * 1024 * 1024, 1024 * 1024, 4)
    store.ensure_pool(spec)
    store.register_workspace('ws', 'pool-real-dag', str(tmp_path), 'tester')

    def command(context):
        label = context.unit['local_id']
        marker = tmp_path / f'{label}.start'
        code = (f"import pathlib, time\n"
                f"pathlib.Path({str(marker)!r}).write_text(str(time.time()))\n"
                f"time.sleep(0.9)\n")
        script = tmp_path / f'{label}.py'
        script.write_text(code, encoding='utf-8')
        return LaunchSpec(argv=(sys.executable, str(script)), cwd=str(tmp_path),
                          environment=dict(os.environ), stdout_path=str(tmp_path / f'{label}.log'))

    executor = ProcessExecutor(tmp_path, command_builder=command)
    coordinator = Coordinator(store, spec, executor, workspace_id='ws', principal='tester', root=tmp_path)
    coordinator.claim()
    coordinator.submit(key='k', digest='d', graph={}, parameters={}, execution={},
                       units=[
                           {'unit_id': 'left', 'node_ids': ['left'], 'depends_on': [],
                            'requirement': {'managed_budget_bytes': 1024,
                                            'process_reservation_bytes': 2048, 'cpu_threads': 1}},
                           {'unit_id': 'right', 'node_ids': ['right'], 'depends_on': [],
                            'requirement': {'managed_budget_bytes': 1024,
                                            'process_reservation_bytes': 2048, 'cpu_threads': 1}},
                           {'unit_id': 'join', 'node_ids': ['join'], 'depends_on': ['left', 'right'],
                            'requirement': {'managed_budget_bytes': 1024,
                                            'process_reservation_bytes': 2048, 'cpu_threads': 1}},
                       ])
    started = time.perf_counter()
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        coordinator.run_once()
        if store.list_runs()[0]['status'] == 'complete':
            break
        time.sleep(0.05)
    elapsed = time.perf_counter() - started
    run = store.list_runs()[0]
    assert run['status'] == 'complete'
    left = float((tmp_path / 'left.start').read_text())
    right = float((tmp_path / 'right.start').read_text())
    # Both real workers were live before either finished; the join did not
    # start while either branch was pending.
    assert abs(left - right) < 0.6
    assert elapsed < 2.6, elapsed
    coordinator.stop()
