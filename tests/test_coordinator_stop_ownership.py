"""A shutdown deadline is not evidence that a live scheduler surrendered ownership."""
from types import SimpleNamespace
import threading

import pytest

from operon.engine.contracts import BusyError
from operon.engine.coordinator import Coordinator
from operon.pool_service import PoolService
from test_engine_pool import FakeExecutor, make, submit


def test_slow_launch_keeps_owner_and_thread_until_stop_can_finish(tmp_path):
    entered, release = threading.Event(), threading.Event()

    class SlowExecutor(FakeExecutor):
        def launch(self, context):
            entered.set()
            assert release.wait(10), 'Test did not release its controlled launch'
            return super().launch(context)

    executor = SlowExecutor()
    store, spec, first, root = make(tmp_path, executor=executor)
    second = Coordinator(store, spec, FakeExecutor(), workspace_id='ws', principal='tester', root=root)
    try:
        submit(first)
        first.start()
        assert entered.wait(5)
        thread = first.thread
        with pytest.raises(BusyError, match='ownership was retained'):
            first.stop(timeout=.02)
        assert first.thread is thread and thread.is_alive()
        assert store.coordinator(spec.pool_id)['owner_id'] == first.owner_id
        with pytest.raises(BusyError):
            second.claim()
        release.set()
        first.stop(timeout=5)
        assert first.thread is None
        assert second.claim() > first.epoch
        assert len(executor.launches) == 1
    finally:
        release.set()
        first.stop(timeout=5)
        second.stop(timeout=5)
        store.close()


def test_pool_shutdown_timeout_retains_handles_and_can_be_retried():
    calls = []

    class ControlledCoordinator:
        blocked = True

        def stop(self, **kwargs):
            calls.append('stop')
            if self.blocked:
                raise BusyError('Still owns a live launch')

    coordinator = ControlledCoordinator()
    pool = PoolService.__new__(PoolService)
    pool._closed = False
    pool._state_lock = threading.RLock()
    pool.sessions = {'test': {}}
    pool.coordinator = coordinator
    pool.services = {}
    pool._claimed = True
    pool.owner = {'test': True}
    pool.admission = SimpleNamespace(release_coordinator=lambda _: calls.append('release'),
                                     close=lambda: calls.append('admission-close'))
    pool.engine = SimpleNamespace(close=lambda: calls.append('engine-close'))
    with pytest.raises(BusyError):
        pool.shutdown()
    assert pool.coordinator is coordinator and pool._claimed and not pool._closed
    assert calls == ['stop']
    coordinator.blocked = False
    pool.shutdown()
    assert calls == ['stop', 'stop', 'release', 'engine-close', 'admission-close']
    assert pool._closed and pool.coordinator is None
