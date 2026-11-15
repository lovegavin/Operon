from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import pytest

from operon.engine.admission_limits import PrincipalLimiter, QueueLimits
from operon.engine.contracts import BusyError
from test_engine_state import store_at, submission


def test_queue_capacity_is_atomic_and_replays_survive_full_queue(tmp_path):
    store = store_at(tmp_path)
    store.queue_limits = replace(QueueLimits(), active_runs=3, principal_active_runs=3)
    def submit(i):
        try:
            submission(store, key=f'k{i}', run_id=f'run-{i}')
            return i
        except BusyError as error:
            assert error.code == 'queue_full'
            return None
    try:
        with ThreadPoolExecutor(max_workers=12) as workers:
            accepted = [i for i in workers.map(submit, range(30)) if i is not None]
        assert len(accepted) == 3
        i = accepted[0]
        assert submission(store, key=f'k{i}', run_id=f'run-{i}').reused
        store.request_cancel(f'run-{i}')
        store.mark_cancel_stopped(f'run-{i}')
        assert submission(store, key='next', run_id='next').created
    finally:
        store.close()


def test_retained_receipts_and_state_watermarks_reject_without_partial_writes(tmp_path):
    store = store_at(tmp_path)
    try:
        store.queue_limits = replace(QueueLimits(), retained_requests=1)
        submission(store)
        store.request_cancel('run-1'); store.mark_cancel_stopped('run-1')
        with pytest.raises(BusyError, match='capacity'):
            submission(store, key='new', run_id='new')
        assert store.request('tester', 'new') is None
        store.queue_limits = replace(QueueLimits(), state_bytes=1)
        with pytest.raises(BusyError) as error:
            submission(store, key='new', run_id='new')
        assert error.value.details['resource'] == 'state_bytes'
        assert submission(store).reused
    finally:
        store.close()


def test_principal_control_limits_do_not_multiply_by_connections_or_block_cancel():
    now = [0.0]
    limiter = PrincipalLimiter(rate=1, burst=2, concurrent=1, clock=lambda: now[0])
    with limiter.admit('alice'):
        with pytest.raises(BusyError) as error:
            with limiter.admit('alice'): pass
        assert error.value.code == 'rate_limited'
        with limiter.admit('bob'): pass
        with limiter.admit('alice', lane='lifecycle'): pass
    with limiter.admit('alice'): pass
    with pytest.raises(BusyError):
        with limiter.admit('alice'): pass
    now[0] = 1
    with limiter.admit('alice'): pass


def test_limiter_identity_table_is_bounded():
    limiter = PrincipalLimiter(rate=1, burst=1, max_keys=2, clock=lambda: 0)
    for key in ('a', 'b'):
        with limiter.admit(key): pass
    with pytest.raises(BusyError):
        with limiter.admit('c'): pass
    assert len(limiter.buckets) == 2
    # A full ordinary identity table cannot consume the lifecycle allowance.
    with limiter.admit('a', lane='lifecycle'): pass
    with limiter.admit('b', lane='lifecycle'): pass
    with pytest.raises(BusyError):
        with limiter.admit('c', lane='lifecycle'): pass
    assert len(limiter.buckets) == 4  # two separately bounded lanes


def test_slow_disk_probe_does_not_hold_writer_and_replay_survives_failed_probe(tmp_path, monkeypatch):
    import threading
    from operon.engine.contracts import UnavailableStateError
    store = store_at(tmp_path)
    submission(store)
    entered, release = threading.Event(), threading.Event()
    def pressure():
        entered.set()
        assert release.wait(5)
        return UnavailableStateError('injected disk probe error')
    monkeypatch.setattr(store, '_submission_storage_pressure', pressure)
    try:
        with ThreadPoolExecutor(max_workers=2) as threads:
            future = threads.submit(submission, store)
            assert entered.wait(3)
            # A durable lookup remains available while the external disk blocks.
            assert threads.submit(store.run, 'run-1').result(timeout=1)['id'] == 'run-1'
            release.set()
            assert future.result(timeout=3).reused
        with pytest.raises(UnavailableStateError):
            submission(store, key='new', run_id='new')
        assert store.request('tester', 'new') is None
    finally:
        release.set()
        store.close()


def test_sustained_excess_submissions_do_not_grow_durable_queue(tmp_path):
    store = store_at(tmp_path)
    store.queue_limits = replace(QueueLimits(), active_runs=8, principal_active_runs=8)
    try:
        for i in range(8): submission(store, key=str(i), run_id=str(i))
        before = store.connection.execute('SELECT count(*) FROM events').fetchone()[0]
        for i in range(1000):
            with pytest.raises(BusyError):
                submission(store, key=f'rejected-{i}', run_id=f'rejected-{i}')
        assert len(store.list_runs()) == 8
        assert store.connection.execute('SELECT count(*) FROM requests').fetchone()[0] == 8
        assert store.connection.execute('SELECT count(*) FROM events').fetchone()[0] == before
    finally:
        store.close()


def test_submission_size_and_unit_limits_leave_no_partial_receipts(tmp_path):
    store = store_at(tmp_path)
    try:
        store.queue_limits = replace(QueueLimits(), submission_bytes=1)
        with pytest.raises(BusyError) as error:
            submission(store)
        assert error.value.details['resource'] == 'submission'
        assert not store.list_runs()
        assert store.request('tester', 'k1') is None
        store.queue_limits = replace(QueueLimits(), submission_units=1)
        run = {'id': 'two-units', 'workspace_id': 'ws-a', 'project': 'p',
               'plan_key': 'p', 'plan_digest': 'd', 'plan': {'name': '非 ASCII'}}
        with pytest.raises(BusyError) as error:
            store.claim_submission(principal='tester', key='two', digest='two', operation='run',
                run=run, units=[{'unit_id': 'a'}, {'unit_id': 'b'}])
        assert error.value.details['units'] == 2
        assert store.request('tester', 'two') is None
        store.queue_limits = QueueLimits()
        assert submission(store).created
    finally:
        store.close()
