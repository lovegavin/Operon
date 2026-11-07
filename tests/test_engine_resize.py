"""Elastic budget protocol at step boundaries; process credits stay charged."""
import json
from pathlib import Path

import pytest

from biopipe.engine.budget import (
    ResizeCommand, ResizeController, read_ack, step_boundary_resize, write_command,
)
from biopipe.engine.contracts import PoolSpec, ResourceRequest
from biopipe.engine.policy import water_fill
from biopipe.engine.resources import PoolResources
from biopipe.engine.state import StateStore


class FakeMemory:
    def __init__(self, budget):
        self.config = type('Config', (), {'budget_bytes': budget})()
        self.calls = []

    def update_budget(self, value):
        self.calls.append(value)
        self.config.budget_bytes = value


class RejectingMemory(FakeMemory):
    def update_budget(self, value):
        self.calls.append(value)
        raise RuntimeError('safe eviction failed')


def test_worker_applies_resize_once_and_duplicate_commands_are_idempotent(tmp_path):
    memory = FakeMemory(1024 * 1024)
    command = ResizeCommand('lease-1', 'attempt-1', 7, 'resize-1', 2, 512 * 1024, 1024 * 1024)
    write_command(tmp_path, command)
    first = step_boundary_resize(tmp_path, memory)
    assert first['state'] == 'acknowledged' and memory.calls == [512 * 1024]
    second = step_boundary_resize(tmp_path, memory)
    assert second == first and memory.calls == [512 * 1024]
    assert read_ack(tmp_path)['resize_id'] == 'resize-1'


def test_failed_managed_shrink_keeps_the_previous_budget_and_reports_failure(tmp_path):
    memory = RejectingMemory(1024 * 1024)
    write_command(tmp_path, ResizeCommand('lease-1', 'attempt-1', 1, 'resize-bad', 2,
                                          256 * 1024, 1024 * 1024))
    ack = step_boundary_resize(tmp_path, memory)
    assert ack['state'] == 'failed' and 'safe eviction failed' in ack['error']
    assert memory.config.budget_bytes == 1024 * 1024
    assert ack['acknowledged_process_release'] == 0


def test_delayed_old_command_cannot_override_a_newer_applied_budget(tmp_path):
    memory = FakeMemory(1024 * 1024)
    write_command(tmp_path, ResizeCommand('lease-1', 'attempt-1', 1, 'resize-new', 5,
                                          512 * 1024, 1024 * 1024))
    step_boundary_resize(tmp_path, memory)
    write_command(tmp_path, ResizeCommand('lease-1', 'attempt-1', 1, 'resize-old', 4,
                                          256 * 1024, 1024 * 1024))
    ack = step_boundary_resize(tmp_path, memory)
    assert ack['stale_command'] is True
    assert memory.config.budget_bytes == 512 * 1024


def pool_setup(tmp_path, capacity=56, reserve=0):
    store = StateStore(tmp_path / 'state.sqlite3')
    spec = PoolSpec('pool-resize', 'tester', 'host', capacity, reserve, 8)
    store.ensure_pool(spec)
    store.register_workspace('ws', 'pool-resize', str(tmp_path), 'tester')
    return store, spec


def add_run(store, index, *, managed, process, cpu=1, capability='cooperative-resize-step'):
    run_id = f'run-{index}'
    store.claim_submission(principal='tester', key=f'k{index}', digest='d', operation='run',
                           run={'id': run_id, 'workspace_id': 'ws', 'project': 'p',
                                'plan_key': 'p', 'plan_digest': 'd', 'plan': {}},
                           units=[{'unit_id': f'u{index}', 'node_ids': [f'n{index}'],
                                   'depends_on': [], 'target': {'kind': 'local'},
                                   'capability': capability,
                                   'requirement': {'managed_budget_bytes': managed,
                                                   'process_reservation_bytes': process,
                                                   'cpu_threads': cpu}}])
    unit = store.units(run_id)[0]
    attempt = store.create_attempt(unit['id'], epoch=1)
    store.transition_attempt(attempt['id'], 'running', expected_revision=attempt['revision'])
    return store.unit(unit['id']), store.attempt(attempt['id'])


def test_device_leases_cannot_overlap(tmp_path):
    from biopipe.engine.contracts import InfeasibleResourcesError
    store, spec = pool_setup(tmp_path)
    resources = PoolResources(store, *store.pool('pool-resize'))
    a = add_run(store, 1, managed=8, process=8)[1]
    b = add_run(store, 2, managed=8, process=8)[1]
    first = resources.admit(attempt_id=a['id'], request=ResourceRequest(
        process_reservation_bytes=8, cpu_threads=1, devices=('gpu:0',)), owner={})
    with pytest.raises(InfeasibleResourcesError, match='already leased'):
        resources.admit(attempt_id=b['id'], request=ResourceRequest(
            process_reservation_bytes=8, cpu_threads=1, devices=('gpu:0',)), owner={})
    second = resources.admit(attempt_id=b['id'], request=ResourceRequest(
        process_reservation_bytes=8, cpu_threads=1, devices=('gpu:1',)), owner={})
    assert first['id'] != second['id']
    store.close()


def test_managed_shrink_does_not_return_process_credits_without_verification(tmp_path):
    store, spec = pool_setup(tmp_path)
    unit, attempt = add_run(store, 1, managed=24, process=24)
    resources = PoolResources(store, *store.pool('pool-resize'))
    lease = resources.admit(attempt_id=attempt['id'], request=ResourceRequest(
        managed_budget_bytes=24, process_reservation_bytes=24, cpu_threads=1), owner={})
    controller = ResizeController(resources, store)
    proposal = controller.propose(attempt['id'], managed_budget_bytes=16, release_process_bytes=8)
    ack = {'resize_id': proposal['resize']['resize_id'], 'revision': proposal['revision'],
           'state': 'acknowledged', 'managed_budget_bytes': 16}
    updated = controller.acknowledge(attempt['id'], ack)
    assert updated['committed'].managed_budget_bytes == 16
    # The process reservation stays charged: no second worker can spend it.
    assert updated['committed'].process_reservation_bytes == 24
    with pytest.raises(Exception):
        resources.admit(attempt_id=add_run(store, 2, managed=40, process=40)[1]['id'],
                        request=ResourceRequest(managed_budget_bytes=40,
                                                process_reservation_bytes=40, cpu_threads=1), owner={})


def test_verified_process_release_returns_credits_only_once(tmp_path):
    store, spec = pool_setup(tmp_path)
    unit, attempt = add_run(store, 1, managed=24, process=24)
    resources = PoolResources(store, *store.pool('pool-resize'))
    resources.admit(attempt_id=attempt['id'], request=ResourceRequest(
        managed_budget_bytes=24, process_reservation_bytes=24, cpu_threads=1), owner={})
    controller = ResizeController(resources, store,
                                  process_release_verifier=lambda *args: True)
    proposal = controller.propose(attempt['id'], managed_budget_bytes=20, release_process_bytes=4)
    ack = {'resize_id': proposal['resize']['resize_id'], 'revision': proposal['revision'],
           'state': 'acknowledged'}
    first = controller.acknowledge(attempt['id'], ack)
    assert first['committed'].process_reservation_bytes == 20
    second = controller.acknowledge(attempt['id'], ack)
    assert second['committed'].process_reservation_bytes == 20
    # A duplicate ACK must not free another four bytes.
    assert resources.snapshot().used.ram == 20


def test_worked_water_fill_example_scaled():
    targets = water_fill([
        {'key': 'A', 'minimum': 16, 'preferred': 32},
        {'key': 'B', 'minimum': 8, 'preferred': 16},
        {'key': 'C', 'minimum': 8, 'preferred': 16},
        {'key': 'D', 'minimum': 8, 'preferred': 16},
    ], 56)
    assert targets == {'A': 20, 'B': 12, 'C': 12, 'D': 12}
    with pytest.raises(Exception):
        water_fill([{'key': 'A', 'minimum': 60, 'preferred': 70}], 56)


def test_growth_reserves_capacity_before_the_ack(tmp_path):
    store, spec = pool_setup(tmp_path, capacity=10, reserve=0)
    unit, attempt = add_run(store, 1, managed=6, process=6)
    resources = PoolResources(store, *store.pool('pool-resize'))
    resources.admit(attempt_id=attempt['id'], request=ResourceRequest(
        managed_budget_bytes=6, process_reservation_bytes=6, cpu_threads=1), owner={})
    controller = ResizeController(resources, store)
    proposal = controller.propose(attempt['id'], managed_budget_bytes=6,
                                  process_reservation_bytes=9, resize_id='grow-1')
    # The pending growth consumes capacity even before the worker acknowledges.
    with pytest.raises(Exception):
        resources.admit(attempt_id=add_run(store, 2, managed=4, process=4)[1]['id'],
                        request=ResourceRequest(managed_budget_bytes=4,
                                                process_reservation_bytes=4, cpu_threads=1), owner={})
    ack = {'resize_id': 'grow-1', 'revision': proposal['revision'], 'state': 'acknowledged'}
    updated = controller.acknowledge(attempt['id'], ack)
    assert updated['committed'].process_reservation_bytes == 9
    # After the acknowledgment only one byte remains; the pending growth was
    # not double-counted.
    assert resources.snapshot().used.ram == 9


def test_resize_is_rejected_for_fixed_workers_and_non_running_attempts(tmp_path):
    store, spec = pool_setup(tmp_path)
    unit, attempt = add_run(store, 1, managed=8, process=8, capability='legacy-sequential')
    resources = PoolResources(store, *store.pool('pool-resize'))
    controller = ResizeController(resources, store)
    with pytest.raises(Exception):
        controller.propose(attempt['id'], managed_budget_bytes=4)
