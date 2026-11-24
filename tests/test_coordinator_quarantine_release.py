"""A quarantined attempt must not charge pool capacity forever."""
from operon.engine.contracts import AttemptState
from test_engine_pool import LongExecutor, make, submit


def quarantine(store, attempt_id, *, pid=999999):
    store.transition_attempt(attempt_id, AttemptState.RECOVERY_REQUIRED,
                             process={'pid': pid, 'created': 1.0},
                             error='worker descendants are still alive',
                             error_code='recovery_required')


def test_a_dead_quarantined_worker_releases_its_lease(tmp_path, monkeypatch):
    monkeypatch.setattr('operon.engine.coordinator.ABANDON_AFTER_SECONDS', 0.0)
    executor = LongExecutor()
    store, _, coordinator, _ = make(tmp_path, executor=executor)
    try:
        submit(coordinator)
        coordinator.run_once()
        attempt, = store.attempts('run-1')
        quarantine(store, attempt['id'])
        assert store.lease(attempt['id'])['state'] != 'released'
        report = coordinator.run_once()
        assert report['abandoned'] == 1
        quarantined = store.attempt(attempt['id'])
        assert quarantined['state'] == 'failed'
        assert quarantined['error_code'] == 'recovery_abandoned'
        assert store.lease(attempt['id'])['state'] == 'released'
    finally:
        coordinator.stop()
        store.close()


def test_a_live_quarantined_worker_keeps_its_lease(tmp_path, monkeypatch):
    monkeypatch.setattr('operon.engine.coordinator.ABANDON_AFTER_SECONDS', 0.0)
    monkeypatch.setattr('operon.engine.coordinator.identity_alive', lambda process: True)
    executor = LongExecutor()
    store, _, coordinator, _ = make(tmp_path, executor=executor)
    try:
        submit(coordinator)
        coordinator.run_once()
        attempt, = store.attempts('run-1')
        quarantine(store, attempt['id'])
        report = coordinator.run_once()
        assert report['abandoned'] == 0
        assert store.attempt(attempt['id'])['state'] == 'recovery_required'
        assert store.lease(attempt['id'])['state'] != 'released'
    finally:
        coordinator.stop()
        store.close()
