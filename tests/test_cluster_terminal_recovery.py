"""Coordinator proof-routing fixtures; no real process-exit claim is made here."""
import pytest

from operon.engine.contracts import ProcessIdentity
from operon.engine.executor import ExecutionResult
from test_engine_pool import LongExecutor, make, submit


@pytest.mark.parametrize('terminal', ['succeeded', 'cancelled', 'failed'])
def test_verified_terminal_recovery_uses_normal_finalizer_without_relaunch(tmp_path, terminal):
    executor = LongExecutor()
    store, _, coordinator, _ = make(tmp_path, executor=executor)
    publications = []
    coordinator.artifact_committer = lambda payload, result: (publications.append(payload['id']) or {'artifact_id': 'fixture-proof'})
    try:
        submit(coordinator)
        coordinator.run_once()
        attempt, = store.attempts('run-1')
        store.transition_attempt(attempt['id'], 'recovery_required')
        executor.reconcile = lambda context: ExecutionResult(state=terminal, exit_code=0 if terminal == 'succeeded' else 1,
            identity=ProcessIdentity(pid=999999, created=1.0), tree_alive=False, detail='verified fixture exit')
        report = coordinator.recover()
        assert report['completed'] == 1
        assert store.attempt(attempt['id'])['state'] == terminal
        assert store.lease(attempt['id'])['state'] == 'released'
        assert len(executor.launches) == 1
        if terminal == 'succeeded':
            assert publications == [attempt['id']]
            assert store.attempt(attempt['id'])['receipt']['artifact_id'] == 'fixture-proof'
        else:
            assert not publications
    finally:
        coordinator.stop()
        store.close()


@pytest.mark.parametrize('identity,alive', [(None, False), (ProcessIdentity(pid=999999, created=1.0), True)])
def test_terminal_label_without_exit_proof_keeps_lease_quarantined(tmp_path, identity, alive):
    executor = LongExecutor()
    store, _, coordinator, _ = make(tmp_path, executor=executor)
    try:
        submit(coordinator)
        coordinator.run_once()
        attempt, = store.attempts('run-1')
        executor.reconcile = lambda context: ExecutionResult(state='succeeded', exit_code=0,
                                                               identity=identity, tree_alive=alive)
        report = coordinator.recover()
        assert report['quarantined'] == 1
        assert store.attempt(attempt['id'])['state'] == 'recovery_required'
        assert store.lease(attempt['id'])['state'] != 'released'
        assert len(executor.launches) == 1
    finally:
        coordinator.stop()
        store.close()
