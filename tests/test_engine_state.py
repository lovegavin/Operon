"""Durable engine state: pool freeze, transitions, leases, events and recovery."""
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import sqlite3
import threading

import pytest

from operon.engine.contracts import (
    AttemptState, InfeasibleResourcesError, PoolSpec, ResourceRequest, RunState, StaleRevisionError,
    UnavailableStateError,
)
from operon.engine.events import EventStream
from operon.engine.resources import PoolResources
from operon.engine.state import StateStore


def spec(**values):
    base = dict(pool_id='pool-test', principal='tester', capacity_domain='host:test',
                ceiling_bytes=1000, management_reserve_bytes=100, cpu_threads=4)
    base.update(values)
    return PoolSpec(**base)


def store_at(tmp_path, **values):
    store = StateStore(tmp_path / 'engine.sqlite3')
    store.ensure_pool(spec(**values))
    store.register_workspace('ws-a', store.pool('pool-test')[0].pool_id, str(tmp_path), 'tester')
    return store


def submission(store, key='k1', run_id='run-1', digest='digest-1', unit='u1',
               dependencies=(), requirement=None):
    requirement = requirement or {'managed_budget_bytes': 100, 'process_reservation_bytes': 200,
                                  'cpu_threads': 1}
    run = {'id': run_id, 'workspace_id': 'ws-a', 'project': 'p', 'plan_key': 'plan',
           'plan_digest': 'plan-digest', 'plan': {'graph': {}}}
    units = [{'unit_id': unit, 'node_ids': ['n1'], 'depends_on': list(dependencies),
              'target': {'kind': 'local'}, 'requirement': requirement}]
    return store.claim_submission(principal='tester', key=key, digest=digest, operation='run',
                                  run=run, units=units)


def test_pool_snapshot_is_frozen_and_persisted(tmp_path):
    store = store_at(tmp_path)
    first, epoch = store.ensure_pool(spec())
    assert (first.ceiling_bytes, epoch) == (1000, 1)
    assert first.schedulable_bytes == 900
    submission(store)
    attempt = store.create_attempt(store.units('run-1')[0]['id'], epoch=1)
    resources = PoolResources(store, first, epoch)
    resources.admit(attempt_id=attempt['id'], request=ResourceRequest(
        managed_budget_bytes=50, process_reservation_bytes=100, cpu_threads=1), owner={})
    with pytest.raises(UnavailableStateError):
        store.ensure_pool(spec(ceiling_bytes=2000))
    store.release_lease(store.lease(attempt['id'])['id'])
    updated, next_epoch = store.ensure_pool(spec(ceiling_bytes=2000))
    assert updated.ceiling_bytes == 2000 and next_epoch == epoch + 1


def test_attempt_transition_table_rejects_illegal_moves(tmp_path):
    store = store_at(tmp_path)
    submission(store)
    attempt = store.create_attempt(store.units('run-1')[0]['id'], epoch=1)
    store.transition_attempt(attempt['id'], AttemptState.RUNNING, expected_revision=1)
    with pytest.raises(Exception):
        store.transition_attempt(attempt['id'], AttemptState.ADMITTED, expected_revision=2)
    store.transition_attempt(attempt['id'], AttemptState.COMMITTING, expected_revision=2)
    store.transition_attempt(attempt['id'], AttemptState.SUCCEEDED, expected_revision=3, exit_code=0)
    assert store.run('run-1')['status'] == RunState.COMPLETE.value


def test_cancel_uses_revision_and_completion_race_never_rewrites_success(tmp_path):
    store = store_at(tmp_path)
    submission(store)
    run = store.request_cancel('run-1', expected_revision=1, reason='test')
    assert run['cancel_requested'] and run['revision'] == 2
    with pytest.raises(StaleRevisionError):
        store.request_cancel('run-1', expected_revision=1)
    store.mark_cancel_stopped('run-1')
    assert store.run('run-1')['status'] == RunState.CANCELLED.value
    assert store.run('run-1')['cancel_state'] == 'stopped'


def test_lease_admission_is_atomic_and_all_or_nothing(tmp_path):
    store = store_at(tmp_path)
    requirements = {'managed_budget_bytes': 8, 'process_reservation_bytes': 9, 'cpu_threads': 1}
    for index in range(20):
        submission(store, key=f'k{index}', run_id=f'run-{index}', digest=f'g{index}', unit=f'u{index}',
                   requirement=requirements)
    results = []
    barrier = threading.Barrier(20)

    def admit(index):
        attempt = store.create_attempt(next(u['id'] for u in store.units(f'run-{index}')), epoch=1)
        barrier.wait()
        try:
            lease = store.acquire_lease(attempt_id=attempt['id'], pool_id='pool-test', owner={},
                                        request=ResourceRequest.from_json(requirements))
            results.append(('granted', lease['id']))
        except InfeasibleResourcesError:
            results.append(('rejected', None))

    with ThreadPoolExecutor(max_workers=20) as pool:
        list(pool.map(admit, range(20)))
    granted = [item for item in results if item[0] == 'granted']
    # 900 bytes / 9 bytes per lease = exactly 100 possible; the CPU limit of 4
    # is the binding constraint here, so four leases are admitted atomically.
    assert len(granted) == 4
    snapshot = PoolResources(store, *store.pool('pool-test')).snapshot()
    assert snapshot.used.ram == 36 and snapshot.used.cpu == 4


def test_transaction_commits_state_event_and_outbox_together(tmp_path):
    store = store_at(tmp_path)
    result = submission(store)
    assert result.created
    assert store.unit(store.units('run-1')[0]['id'])['state'] == AttemptState.READY.value
    page = EventStream(store).page(0)
    assert [event['kind'] for event in page.events] == ['pool_registered', 'run_submitted']
    assert [item['command'] for item in store.pending_outbox()] == ['dispatch']
    # Replaying the same request does not create a second run or outbox row.
    replay = submission(store)
    assert replay.reused and replay.record['run_id'] == 'run-1'
    assert len(store.list_runs()) == 1
    assert len(store.pending_outbox()) == 1


def test_injected_crash_inside_transaction_leaves_no_partial_record(tmp_path):
    store = store_at(tmp_path)
    run = {'id': 'run-crash', 'workspace_id': 'ws-a', 'project': 'p', 'plan_key': 'p',
           'plan_digest': 'd', 'plan': {}}
    units = [{'unit_id': 'u1', 'node_ids': ['n'], 'depends_on': [], 'target': {'kind': 'local'},
              'requirement': {}}]
    try:
        with store.transaction():
            store.claim_submission(principal='tester', key='crash', digest='x', operation='run',
                                   run=run, units=units)
            raise RuntimeError('injected crash before commit')
    except RuntimeError:
        pass
    assert store.request('tester', 'crash') is None
    assert store.list_runs() == []


def test_corrupt_or_newer_state_is_reported_not_recreated(tmp_path):
    path = tmp_path / 'bad.sqlite3'
    path.write_bytes(b'not a sqlite database')
    with pytest.raises(UnavailableStateError):
        StateStore(path)
    assert path.read_bytes() == b'not a sqlite database'
    good = StateStore(tmp_path / 'future.sqlite3')
    with good.transaction():
        good.connection.execute("UPDATE schema_meta SET value='99' WHERE key='schema_version'")
    good.close()
    with pytest.raises(UnavailableStateError):
        StateStore(tmp_path / 'future.sqlite3')


def test_backup_can_be_opened_and_has_the_durable_queue(tmp_path):
    store = store_at(tmp_path)
    submission(store)
    backup = store.backup(tmp_path / 'backup.sqlite3')
    restored = StateStore(backup)
    try:
        assert restored.run('run-1')['status'] == RunState.QUEUED.value
        assert restored.request('tester', 'k1')['run_id'] == 'run-1'
    finally:
        restored.close()


def test_event_retention_expires_a_cursor_explicitly(tmp_path):
    store = store_at(tmp_path)
    for index in range(30):
        store.append_event('progress', principal='tester', run_id='run-1', payload={'i': index})
    pruned = store.prune_events(keep=5)
    assert pruned['deleted'] > 0
    page = EventStream(store).page(0)
    assert page.snapshot_required and not page.events
    latest = store.event_bounds()[1]
    fresh = EventStream(store).page(latest - 1)
    assert fresh.events and not fresh.snapshot_required
