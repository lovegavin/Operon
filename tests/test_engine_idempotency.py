"""Atomic request claims: duplicates, conflicts, crash replay and outbox identity."""
from concurrent.futures import ThreadPoolExecutor
import threading

import pytest

from biopipe.engine.contracts import IdempotencyConflictError, ResourceRequest
from biopipe.engine.coordinator import Coordinator
from biopipe.engine.executor import ExecutionResult
from biopipe.engine.facade import EngineRuntime
from biopipe.engine.state import StateStore


class FakeExecutor:
    capability = 'fake'
    resizable = False

    def __init__(self):
        self.launches = []
        self.lock = threading.Lock()

    def launch(self, context):
        with self.lock:
            self.launches.append(context.attempt['id'])
        return ExecutionResult(state='running')

    def poll(self, context):
        return ExecutionResult(state='running')

    def cancel(self, context, *, timeout=10.0):
        return ExecutionResult(state='cancelled')

    def reconcile(self, context):
        return ExecutionResult(state='running')


def runtime(tmp_path, *, mode='coordinator', capacity=1024 * 1024):
    return EngineRuntime.open(data_dir=tmp_path / '.studio', workspace_root=tmp_path,
                              mode=mode, principal='tester', ceiling_bytes=capacity,
                              cpu_threads=4)


def submit(runtime, key='request-1', digest='digest-1', unit='u1'):
    return runtime.facade.submit(
        key=key, digest=digest, graph={'nodes': []}, parameters={'x': 1},
        execution={'engine': 'test'},
        units=[{'unit_id': unit, 'node_ids': ['n1'], 'depends_on': [],
                'requirement': {'managed_budget_bytes': 1024, 'process_reservation_bytes': 2048,
                                'cpu_threads': 1}}])


def test_one_hundred_identical_requests_create_one_run(tmp_path):
    engine = runtime(tmp_path)
    executor = FakeExecutor()
    engine.coordinator(executor)
    barrier = threading.Barrier(100)

    def call(_):
        barrier.wait()
        return submit(engine)

    with ThreadPoolExecutor(max_workers=100) as pool:
        results = list(pool.map(call, range(100)))

    assert len({item['run_id'] for item in results}) == 1
    assert sum(1 for item in results if item['created']) == 1
    assert len(engine.store.list_runs()) == 1
    assert len(engine.store.pending_outbox(limit=1000)) == 1
    engine.close()


def test_same_key_with_different_content_is_a_conflict(tmp_path):
    engine = runtime(tmp_path)
    engine.coordinator(FakeExecutor())
    submit(engine, digest='first')
    with pytest.raises(IdempotencyConflictError):
        submit(engine, digest='second')
    assert len(engine.store.list_runs()) == 1
    engine.close()


def test_distinct_keys_are_distinct_runs_and_outbox_identities(tmp_path):
    engine = runtime(tmp_path, capacity=512 * 1024 * 1024)
    engine.coordinator(FakeExecutor())
    results = [submit(engine, key=f'request-{index}', digest=f'digest-{index}', unit=f'u{index}')
               for index in range(50)]
    assert len({item['run_id'] for item in results}) == 50
    assert len(engine.store.list_runs()) == 50
    assert len({item['id'] for item in engine.store.pending_outbox(limit=1000)}) == 50
    engine.close()


def test_crash_after_commit_before_reply_returns_the_same_receipt(tmp_path):
    engine = runtime(tmp_path)
    engine.coordinator(FakeExecutor())
    first = submit(engine)
    engine.store.close()
    reopened = StateStore(tmp_path / '.studio' / 'engine' / 'state.sqlite3')
    try:
        record = reopened.request('tester', 'request-1')
        assert record['run_id'] == first['run_id']
        # A retry after the crash sees the committed run, never a second one.
        retry = reopened.claim_submission(
            principal='tester', key='request-1', digest='digest-1', operation='run',
            run={'id': 'ignored', 'workspace_id': 'ws', 'project': 'p', 'plan_key': 'p',
                 'plan_digest': 'd', 'plan': {}}, units=[])
        assert retry.reused and retry.record['run_id'] == first['run_id']
    finally:
        reopened.close()


def test_coordinator_dispatches_one_attempt_for_a_replayed_submission(tmp_path):
    engine = runtime(tmp_path)
    executor = FakeExecutor()
    facade = engine.coordinator(executor)
    submit(engine, key='replay', digest='replay')
    for _ in range(5):
        facade.coordinator.run_once()
    assert len(executor.launches) == 1
    assert len(engine.store.attempts(engine.store.list_runs()[0]['id'])) == 1
    engine.close()
