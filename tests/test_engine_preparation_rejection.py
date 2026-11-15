"""Real journals and resource grants; injected pre-launch faults, not process E2E."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import json
import os
import sys
import threading
from types import SimpleNamespace

import pytest

from operon.cluster.host import HostControllerEndpoint, stopped_attempt_proof
from operon.contracts.base import ContractError
from operon.engine import supervisor as supervisor_module
from operon.engine.executor import ExecutionContext, ProcessExecutor
from operon.engine.fs import atomic_json
from operon.engine.supervisor import (LaunchSpec, PreparationRejectedError, ProcessSupervisor,
                                      SupervisorError, identity_alive)
from operon.environment_store import EnvironmentStore
from test_engine_pool import make, submit


def _spec(root):
    return LaunchSpec((sys.executable, '-c', 'import time; time.sleep(30)'), str(root),
                      dict(os.environ), str(root / 'worker.log'))


@pytest.mark.parametrize('stage', ['command', 'environment'])
def test_preparation_rejection_is_final_failed_without_process_or_generation_lease(tmp_path, stage):
    root = tmp_path / 'ws'
    environments = EnvironmentStore(tmp_path / 'environments')
    def reject(_):
        raise ContractError('Frozen script differs', code='implementation_unavailable')
    executor = ProcessExecutor(root / 'invocations', command_builder=reject if stage == 'command'
        else lambda _: _spec(root), environment_builder=reject if stage == 'environment' else None,
        environment_store=environments)
    store, spec, coordinator, _ = make(tmp_path, executor=executor)
    try:
        submit(coordinator, units=[{'unit_id': 'u1', 'node_ids': ['n1'], 'depends_on': [],
            'retry_limit': 2, 'requirement': {'managed_budget_bytes': 1024,
                'process_reservation_bytes': 2048, 'cpu_threads': 1}}])
        coordinator.run_once()
        coordinator.run_once()
        attempt, = store.attempts('run-1')
        assert store.run('run-1')['status'] == attempt['state'] == 'failed'
        assert not attempt['process']
        assert store.lease(attempt['id'])['state'] == 'released'
        assert not list((environments.root / 'leases').glob('*.json'))
        assert not executor.supervisor._processes
        assert stopped_attempt_proof(root / 'invocations', attempt)
        pool = SimpleNamespace(engine=SimpleNamespace(store=store, spec=spec), plan_details=lambda *a, **k: None)
        endpoint = HostControllerEndpoint(pool, authenticated_controller_id='controller')
        workspace = SimpleNamespace(root=root, directory=root, engine=SimpleNamespace(workspace_id='ws'))
        receipt = endpoint._plan_receipt({'host_run_id': 'run-1'}, {}, workspace, 'tester')
        assert receipt['state'] == 'failed' and receipt['tree_exited'] and receipt['resources_released']
        assert not receipt['artifact_committed']
    finally:
        coordinator.stop()
        store.close()


@pytest.mark.parametrize('marker', ['launching', 'corrupt', 'other_fence', 'environment',
                                     'lease', 'containment', 'ready', 'start', 'tree-exit'])
def test_conflicting_preparation_history_quarantines_and_retains_grants(tmp_path, marker):
    environments = EnvironmentStore(tmp_path / 'environments')
    executor = None
    def reject(context):
        directory = executor.supervisor.directory
        attempt, fence = context.attempt_id, context.fence
        if marker in ('launching', 'other_fence'):
            atomic_json(directory / (attempt + '.launch.json'), {'attempt_id': attempt,
                'fence': fence + (marker == 'other_fence'), 'state': 'launching', 'pid': None})
        elif marker == 'corrupt':
            (directory / (attempt + '.launch.json')).write_bytes(b'{broken')
        elif marker == 'lease':
            atomic_json(environments.root / 'leases' / (attempt + '.json'), {'state': 'spawning', 'fence': fence})
        else:
            suffix = '.start' if marker == 'start' else '.' + marker + '.json'
            atomic_json(directory / (attempt + suffix), {'fence': fence})
        raise ContractError('Preparation rejected')
    executor = ProcessExecutor(tmp_path / 'ws/invocations', command_builder=reject, environment_store=environments)
    store, _, coordinator, _ = make(tmp_path, executor=executor)
    try:
        submit(coordinator)
        coordinator.run_once()
        attempt, = store.attempts('run-1')
        assert attempt['state'] == 'recovery_required'
        assert store.lease(attempt['id'])['state'] != 'released'
        coordinator.cancel('run-1')
        coordinator.run_once()
        assert store.lease(attempt['id'])['state'] != 'released'
        assert not executor.supervisor.preparation_rejected(attempt['id'], fence=attempt['fence'])
    finally:
        coordinator.stop()
        store.close()


def test_concurrent_rejections_have_one_atomic_outcome_and_quarantine_replay(tmp_path):
    owners = [ProcessSupervisor(tmp_path / 'super') for _ in range(2)]
    barrier = threading.Barrier(2)
    def reject(owner):
        barrier.wait()
        try:
            return owner.record_preparation_rejection('attempt', fence=7, error='bad input').state
        except SupervisorError as exc:
            return exc.code
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(reject, owners)) == ['failed', 'recovery_required']
    raw = owners[0].receipt_path('attempt').read_bytes()
    for fence in (7, 8):
        with pytest.raises(SupervisorError) as caught:
            owners[1].record_preparation_rejection('attempt', fence=fence, error='different')
        assert caught.value.code == 'recovery_required'
        assert owners[0].receipt_path('attempt').read_bytes() == raw
        with pytest.raises(SupervisorError) as caught:
            owners[1].launch('attempt', fence=fence, spec=_spec(tmp_path))
        assert caught.value.code == 'recovery_required'


def test_preparation_failure_cannot_replace_a_live_owned_process(tmp_path):
    first = ProcessSupervisor(tmp_path / 'super')
    receipt = first.launch('attempt', fence=3, spec=_spec(tmp_path))
    second = ProcessSupervisor(tmp_path / 'super')
    before = first.receipt_path('attempt').read_bytes()
    try:
        with pytest.raises(SupervisorError) as caught:
            second.record_preparation_rejection('attempt', fence=3, error='bad input')
        assert caught.value.code == 'recovery_required'
        assert first.receipt_path('attempt').read_bytes() == before
        assert identity_alive(receipt.identity)
    finally:
        assert first.stop('attempt', fence=3).confirmed


def test_negative_receipt_write_failure_is_quarantined(tmp_path, monkeypatch):
    owner = ProcessSupervisor(tmp_path / 'super')
    def unavailable(*args, **kwargs):
        raise OSError('simulated full disk')
    monkeypatch.setattr(supervisor_module, 'atomic_json', unavailable)
    with pytest.raises(SupervisorError) as caught:
        owner.record_preparation_rejection('attempt', fence=3, error='bad input')
    assert caught.value.code == 'recovery_required'
    assert not owner.receipt_path('attempt').exists()


def test_existing_generation_lease_without_receipt_blocks_launch(tmp_path):
    environments = EnvironmentStore(tmp_path / 'env')
    owner = ProcessSupervisor(tmp_path / 'super', environment_store=environments)
    lease = environments.root / 'leases/attempt.json'
    atomic_json(lease, {'attempt_id': 'attempt', 'fence': 3, 'state': 'spawning'})
    before = lease.read_bytes()
    with pytest.raises(SupervisorError) as caught:
        owner.launch('attempt', fence=3, spec=replace(_spec(tmp_path), generation_id='a' * 64))
    assert caught.value.code == 'recovery_required'
    assert lease.read_bytes() == before and not owner.receipt_path('attempt').exists()


def test_exception_from_supervisor_boundary_never_creates_preparation_proof(tmp_path, monkeypatch):
    executor = ProcessExecutor(tmp_path, command_builder=lambda _: _spec(tmp_path))
    context = ExecutionContext(run={'id': 'run'}, unit={'local_id': 'unit'},
        attempt={'id': 'attempt', 'fence': 3}, directory=tmp_path, environment={}, plan={})
    def uncertain(*args, **kwargs):
        raise SupervisorError('Spawn response lost', code='recovery_required')
    monkeypatch.setattr(executor.supervisor, 'launch', uncertain)
    with pytest.raises(SupervisorError) as caught:
        executor.launch(context)
    assert caught.value.code == 'recovery_required'
    assert not executor.supervisor.receipt_path('attempt').exists()


@pytest.mark.parametrize('failure', ['timeout', 'open', 'release'])
def test_launch_lock_failure_quarantines_and_retains_resource_grant(tmp_path, monkeypatch, failure):
    root = tmp_path / 'ws'
    executor = ProcessExecutor(root / 'invocations', command_builder=lambda _: _spec(root))
    class FaultedLock:
        def __enter__(self):
            if failure == 'timeout':
                raise TimeoutError('Another supervisor owns the launch')
            if failure == 'open':
                raise OSError('Lock file cannot be opened')
            return self

        def __exit__(self, *exc):
            raise OSError('Lock handle close failed after launch')
    monkeypatch.setattr(executor.supervisor, '_launch_lock', lambda _: FaultedLock())
    store, _, coordinator, _ = make(tmp_path, executor=executor)
    attempt = None
    try:
        submit(coordinator)
        coordinator.run_once()
        attempt, = store.attempts('run-1')
        assert attempt['state'] == 'recovery_required'
        assert store.lease(attempt['id'])['state'] != 'released'
        assert not executor.supervisor.preparation_rejected(attempt['id'], fence=attempt['fence'])
        receipt = executor.supervisor.read_receipt(attempt['id'])
        if failure == 'release':
            assert receipt is not None and identity_alive(receipt.identity)
        else:
            assert receipt is None and not executor.supervisor._processes
    finally:
        if attempt is not None:
            receipt = executor.supervisor.read_receipt(attempt['id'])
            if receipt is not None and receipt.identity is not None:
                assert executor.supervisor.stop(attempt['id'], fence=attempt['fence']).confirmed
        coordinator.stop()
        store.close()


def test_missing_linux_containment_helper_rejects_before_lease_or_spawn(tmp_path, monkeypatch):
    # Platform fault injection verifies ordering; this is not a Linux runtime gate.
    owner = ProcessSupervisor(tmp_path / 'super', environment_store=EnvironmentStore(tmp_path / 'env'))
    monkeypatch.setattr(supervisor_module, 'os', SimpleNamespace(**{**vars(os), 'name': 'posix'}))
    monkeypatch.setattr(supervisor_module.sys, 'platform', 'linux')
    monkeypatch.setattr(supervisor_module, '__file__', str(tmp_path / 'missing/engine/supervisor.py'))
    with pytest.raises(PreparationRejectedError, match='helper is unavailable'):
        owner.launch('attempt', fence=3, spec=replace(_spec(tmp_path), generation_id='a' * 64))
    assert owner.preparation_rejected('attempt', fence=3)
    assert not list((owner.environment_store.root / 'leases').glob('*.json'))
    assert not owner._processes and not owner._generation_jobs


@pytest.mark.parametrize('state', ['missing', 'launching', 'failed', 'malformed'])
def test_absent_or_ambiguous_no_identity_receipt_cannot_confirm_stop(tmp_path, state):
    owner = ProcessSupervisor(tmp_path / 'super')
    if state == 'malformed':
        owner.receipt_path('attempt').write_bytes(b'bad json')
    elif state != 'missing':
        atomic_json(owner.receipt_path('attempt'), {'attempt_id': 'attempt', 'fence': 3, 'state': state,
                                                  'pid': None, 'created': None})
    with pytest.raises(SupervisorError):
        owner.stop('attempt', fence=3)
