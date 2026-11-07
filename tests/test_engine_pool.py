"""Pool coordination: exclusive ownership, cross-workspace control and recovery."""
from concurrent.futures import ThreadPoolExecutor
import os
import socket
import sys
import threading
import time
from pathlib import Path

import pytest

from biopipe.engine.contracts import BusyError, PoolSpec, ResourceRequest, RunState, UnauthorizedError
from biopipe.engine.coordinator import Coordinator
from biopipe.engine.executor import ExecutionResult, ProcessExecutor
from biopipe.engine.facade import EngineRuntime
from biopipe.engine.recovery import recover
from biopipe.engine.state import StateStore
from biopipe.engine.supervisor import LaunchSpec, ProcessSupervisor


class FakeExecutor:
    capability = 'fake'
    resizable = False

    def __init__(self):
        self.launches = []
        self.cancelled = []
        self.lock = threading.Lock()

    def launch(self, context):
        with self.lock:
            self.launches.append((context.run['id'], context.unit['local_id']))
        return ExecutionResult(state='running')

    def poll(self, context):
        return ExecutionResult(state='succeeded', exit_code=0)

    def cancel(self, context, *, timeout=10.0):
        with self.lock:
            self.cancelled.append((context.run['id'], context.unit['local_id']))
        return ExecutionResult(state='cancelled')

    def reconcile(self, context):
        return ExecutionResult(state='running')


class LongExecutor(FakeExecutor):
    def poll(self, context):
        return ExecutionResult(state='running')


def make(tmp_path, name='ws', *, executor=None, capacity=32 * 1024 * 1024):
    store = StateStore(tmp_path / f'{name}.sqlite3')
    spec = PoolSpec('pool-pool', 'tester', 'host:' + socket.gethostname(),
                    capacity, capacity // 16, 4)
    store.ensure_pool(spec)
    store.register_workspace(name, 'pool-pool', str(tmp_path / name), 'tester')
    root = tmp_path / name
    root.mkdir(exist_ok=True)
    coordinator = Coordinator(store, spec, executor or FakeExecutor(), workspace_id=name,
                              principal='tester', root=root)
    coordinator.claim()
    return store, spec, coordinator, root


def submit(coordinator, *, key='k', run_id='run-1', units=None, workspace='ws', project='p'):
    coordinator.store.register_workspace(workspace, coordinator.pool_id,
                                         str(coordinator.root.parent / workspace), 'tester')
    return coordinator.submit(key=key, digest=key, graph={}, parameters={}, execution={},
                              units=units or [{'unit_id': 'u1', 'node_ids': ['n1'], 'depends_on': [],
                                               'requirement': {'managed_budget_bytes': 1024,
                                                               'process_reservation_bytes': 2048,
                                                               'cpu_threads': 1}}],
                              workspace_id=workspace, project=project, run_id=run_id)


def test_pool_has_one_live_coordinator(tmp_path):
    store, spec, coordinator, root = make(tmp_path)
    second = Coordinator(store, spec, FakeExecutor(), workspace_id='ws', principal='tester', root=root)
    with pytest.raises(BusyError):
        second.claim()
    coordinator.stop()
    # After the first owner detaches, a new coordinator can take over.
    third = Coordinator(store, spec, FakeExecutor(), workspace_id='ws', principal='tester', root=root)
    assert third.claim() > coordinator.epoch
    third.stop()


def test_authorized_control_reaches_a_run_from_another_workspace(tmp_path):
    store, spec, coordinator, root = make(tmp_path, executor=LongExecutor())
    submit(coordinator, key='other', run_id='run-other', workspace='ws-b')
    coordinator.run_once()
    assert coordinator.details('run-other')['status'] == RunState.RUNNING.value
    acknowledged = coordinator.cancel('run-other', reason='authorized control')
    assert acknowledged['cancel_requested']
    for _ in range(5):
        coordinator.run_once()
    run = store.run('run-other')
    assert run['status'] == RunState.CANCELLED.value
    attempts = store.attempts('run-other')
    assert attempts and store.lease(attempts[0]['id'])['state'] == 'released'
    coordinator.stop()


def test_ready_units_with_dependencies_never_start_before_their_join(tmp_path):
    executor = FakeExecutor()
    store, spec, coordinator, root = make(tmp_path, executor=executor)
    submit(coordinator, units=[
        {'unit_id': 'a', 'node_ids': ['a'], 'depends_on': [],
         'requirement': {'managed_budget_bytes': 1024, 'process_reservation_bytes': 2048, 'cpu_threads': 1}},
        {'unit_id': 'b', 'node_ids': ['b'], 'depends_on': [],
         'requirement': {'managed_budget_bytes': 1024, 'process_reservation_bytes': 2048, 'cpu_threads': 1}},
        {'unit_id': 'c', 'node_ids': ['c'], 'depends_on': ['a', 'b'],
         'requirement': {'managed_budget_bytes': 1024, 'process_reservation_bytes': 2048, 'cpu_threads': 1}},
    ])
    coordinator.run_once()
    first = [unit for _, unit in executor.launches]
    assert sorted(first) == ['a', 'b']
    coordinator.run_once()
    second = [unit for _, unit in executor.launches]
    assert sorted(second) == ['a', 'b', 'c']
    coordinator.stop()


def test_restart_adopts_the_live_worker_and_never_duplicates_it(tmp_path):
    root = tmp_path / 'ws'
    root.mkdir()
    store = StateStore(tmp_path / 'state.sqlite3')
    spec = PoolSpec('pool-restart', 'tester', 'host', 64 * 1024 * 1024, 1024 * 1024, 2)
    store.ensure_pool(spec)
    store.register_workspace('ws', 'pool-restart', str(root), 'tester')

    def command(context):
        script = root / 'sleeper.py'
        script.write_text('import time; time.sleep(30)\n', encoding='utf-8')
        return LaunchSpec(argv=(sys.executable, str(script)), cwd=str(root),
                          environment=dict(os.environ), stdout_path='')

    first = Coordinator(store, spec, ProcessExecutor(root, command_builder=command),
                        workspace_id='ws', principal='tester', root=root)
    first.claim()
    first.submit(key='k', digest='d', graph={}, parameters={}, execution={},
                 units=[{'unit_id': 'u1', 'node_ids': ['n1'], 'depends_on': [],
                         'requirement': {'managed_budget_bytes': 1024,
                                         'process_reservation_bytes': 2048, 'cpu_threads': 1}}])
    first.run_once()
    run = store.list_runs()[0]
    attempt = store.attempts(run['id'])[0]
    assert attempt['state'] in ('starting', 'running')
    first.stop()  # detach only; the worker keeps its lease and process

    restarted_executor = ProcessExecutor(root, command_builder=command)
    second = Coordinator(store, spec, restarted_executor, workspace_id='ws', principal='tester', root=root)
    second.claim()
    adopted = store.attempt(attempt['id'])
    assert adopted['state'] in ('running', 'admitted', 'starting')
    assert len(store.attempts(run['id'])) == 1
    assert restarted_executor.supervisor.read_receipt(attempt['id']) is not None
    second.cancel(run['id'], reason='test cleanup')
    for _ in range(20):
        second.run_once()
        if store.run(run['id'])['status'] == 'cancelled':
            break
        time.sleep(0.05)
    assert store.run(run['id'])['status'] == 'cancelled'
    second.stop()


def test_different_principal_cannot_control_a_run_by_guessing_its_id(tmp_path):
    store, spec, coordinator, root = make(tmp_path)
    store.register_workspace('ws-other', 'pool-pool', str(root / 'other'), 'intruder')
    store.claim_submission(principal='intruder', key='foreign', digest='d', operation='run',
                           run={'id': 'run-foreign', 'workspace_id': 'ws-other', 'project': 'p',
                                'plan_key': 'p', 'plan_digest': 'd', 'plan': {}},
                           units=[{'unit_id': 'u', 'node_ids': ['n'], 'depends_on': [],
                                   'target': {'kind': 'local'}, 'requirement': {}}])
    with pytest.raises(UnauthorizedError):
        coordinator.details('run-foreign')
    with pytest.raises(UnauthorizedError):
        coordinator.cancel('run-foreign')
    with pytest.raises(UnauthorizedError):
        coordinator.submit(key='foreign-submit', digest='d', graph={}, parameters={},
                           execution={}, units=[], principal='intruder')
    coordinator.stop()


def test_unknown_live_ownership_is_quarantined_with_its_lease_charged(tmp_path):
    store, spec, coordinator, root = make(tmp_path)
    submit(coordinator)
    unit = store.units('run-1')[0]
    attempt = store.create_attempt(unit['id'], epoch=coordinator.epoch)
    store.transition_attempt(attempt['id'], 'running', expected_revision=attempt['revision'])
    coordinator.resources.admit(attempt_id=attempt['id'],
                                request=ResourceRequest(managed_budget_bytes=1024,
                                                        process_reservation_bytes=2048,
                                                        cpu_threads=1),
                                owner={})
    coordinator.stop()
    # No launch receipt exists for this attempt: ownership is unknown.
    report = recover(EngineRuntime(store, spec, workspace_root=root, mode='coordinator',
                                   principal='tester', workspace='ws'))
    assert report.quarantined >= 1
    assert store.attempt(attempt['id'])['state'] == 'recovery_required'
    assert store.lease(attempt['id'])['state'] != 'released'
def test_standalone_pool_snapshot_respects_container_memory_and_cpu(tmp_path, monkeypatch):
    from biopipe.engine.facade import pool_from_host
    from src.task.memory.config import AUTO_BUDGET_FRACTION
    monkeypatch.setattr('src.task.memory.system.available_memory', lambda: 128 * 1024**2)
    monkeypatch.setattr('src.web.admission.cpu_capacity', lambda: 2)
    spec = pool_from_host(root=tmp_path)
    assert spec.ceiling_bytes == int(128 * 1024**2 * AUTO_BUDGET_FRACTION)
    assert spec.cpu_threads == 2
