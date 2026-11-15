"""Real host journal/artifact checks with synthetic process evidence, not E2E."""
import json
from types import SimpleNamespace

import pytest

from operon.cluster import host
from operon.cluster.host import HostControllerEndpoint, stopped_attempt_proof
from operon.engine.artifacts import ArtifactCommitter
from operon.engine.fs import atomic_json
from operon.engine.supervisor import ProcessSupervisor
from test_engine_pool import LongExecutor, make, submit


@pytest.fixture
def receipt_case(tmp_path):
    store, spec, coordinator, root = make(tmp_path, executor=LongExecutor())
    submit(coordinator, units=[{'unit_id': 'u1', 'node_ids': ['n1'], 'depends_on': [], 'retry_limit': 2,
        'requirement': {'managed_budget_bytes': 1024, 'process_reservation_bytes': 2048, 'cpu_threads': 1}}])
    coordinator.run_once()
    attempt, = store.attempts('run-1')
    unit = store.unit(attempt['unit_id'])
    workspace = SimpleNamespace(root=root, directory=root, engine=SimpleNamespace(workspace_id='ws'))
    pool = SimpleNamespace(engine=SimpleNamespace(store=store, spec=spec),
                           plan_details=lambda *a, **k: None)
    endpoint = HostControllerEndpoint(pool, authenticated_controller_id='controller')
    record = {'host_run_id': 'run-1', 'state': 'dispatching', 'envelope': {'submission_kind': 'plan'}}
    response = {'submission_kind': 'plan'}
    identity = {'pid': 999999999, 'created': 1.0, 'boot_id': 'fixture-boot', 'host': None}
    invocation = root / 'invocations'
    proof_path = invocation / 'supervisor' / (attempt['id'] + '.tree-exit.json')
    launch_path = invocation / 'supervisor' / (attempt['id'] + '.launch.json')

    def finish(state='succeeded', *, terminal_run=True, never_spawned=False):
        process = {} if never_spawned else identity
        receipt = {}
        if state == 'succeeded':
            output = invocation / 'runs' / 'run-1' / 'output'
            output.mkdir(parents=True)
            (output / 'value.json').write_text('{"value":1}', encoding='utf-8')
            receipt = ArtifactCommitter(invocation, store).commit_existing(attempt=attempt, unit=unit,
                fence=attempt['fence'], source_root=output, files=['value.json'], run_id='run-1')
        store.transition_attempt(attempt['id'], 'committing', process=process)
        store.transition_attempt(attempt['id'], state, exit_code=0 if state == 'succeeded' else 1, receipt=receipt)
        lease = store.lease(attempt['id'])
        store.release_lease(lease['id'])
        if state == 'failed' and terminal_run:
            store.transition_run('run-1', 'failed')
        proof = {'attempt_id': attempt['id'], 'fence': attempt['fence'], 'tree_exited': True,
                 'method': 'never-spawned' if never_spawned else 'linux-subreaper'}
        if not never_spawned:
            proof['identity'] = identity
        atomic_json(proof_path, proof)
        atomic_json(launch_path, {'attempt_id': attempt['id'], 'fence': attempt['fence'],
            'state': 'failed' if never_spawned else 'exited',
            **({'pid': None, 'created': None} if never_spawned else identity)})

    def read():
        return endpoint._receipt(record, response, workspace, 'tester')
    try:
        yield SimpleNamespace(store=store, coordinator=coordinator, attempt=attempt, unit=unit,
            invocation=invocation, proof_path=proof_path, launch_path=launch_path, finish=finish, read=read)
    finally:
        coordinator.stop()
        store.close()


def test_terminal_success_requires_owned_artifact_and_matching_process_proof(receipt_case):
    case = receipt_case
    case.finish()
    value = case.read()
    assert value['state'] == 'succeeded'
    assert value['host_unit_id'] == case.unit['id']
    assert value['artifact']['artifact_id'] == case.store.attempt(case.attempt['id'])['receipt']['artifact_id']
    assert value['artifact_committed'] and value['tree_exited'] and value['logs_complete']
    attempt = case.store.attempt(case.attempt['id'])
    assert stopped_attempt_proof(case.invocation, attempt) is True


@pytest.mark.parametrize('change', ['proof_identity', 'launch_identity', 'attempt_identity', 'proof_fence', 'proof_attempt'])
def test_identity_or_fence_mismatch_never_reports_success_or_complete_logs(receipt_case, change):
    case = receipt_case
    case.finish()
    if change == 'attempt_identity':
        process = {**case.store.attempt(case.attempt['id'])['process'], 'created': 2.0}
        case.store.transition_attempt(case.attempt['id'], 'succeeded', process=process)
    else:
        path = case.launch_path if change == 'launch_identity' else case.proof_path
        value = json.loads(path.read_text())
        if change == 'proof_identity': value['identity']['created'] = 2.0
        elif change == 'launch_identity': value['created'] = 2.0
        elif change == 'proof_fence': value['fence'] += 1
        else: value['attempt_id'] = 'other-attempt'
        atomic_json(path, value)
    result = case.read()
    assert result['state'] == 'recovery_required' and result['phase'] == 'host_stop_unproven'
    assert not result['tree_exited'] and not result['logs_complete'] and not result['artifact_committed']


def test_never_spawned_cannot_certify_success(receipt_case):
    case = receipt_case
    case.finish(never_spawned=True)
    result = case.read()
    assert result['state'] == 'recovery_required'
    assert not result['compute_complete'] and not result['logs_complete']


def test_owned_never_spawned_failure_can_release_terminal_receipt(receipt_case):
    case = receipt_case
    case.finish('failed', never_spawned=True)
    result = case.read()
    assert result['state'] == 'failed' and result['tree_exited'] and result['resources_released']
    assert not result['artifact_committed']


def test_retry_ready_unit_keeps_old_failed_attempt_nonterminal(receipt_case):
    case = receipt_case
    case.finish('failed', terminal_run=False)
    case.store.update_unit(case.unit['id'], state='ready')
    result = case.read()
    assert result['state'] == 'recovery_required' and result['phase'] == 'host_run_active'
    assert not result['tree_exited'] and not result['resources_released'] and not result['logs_complete']


def test_selected_attempt_changing_during_proof_read_discards_old_evidence(receipt_case, monkeypatch):
    case = receipt_case
    case.finish('failed', terminal_run=False)
    original = host._read_evidence
    replacement = []
    def read_and_retry(path):
        value = original(path)
        if not replacement:
            case.store.update_unit(case.unit['id'], state='ready')
            replacement.append(case.store.create_attempt(case.unit['id'], epoch=case.coordinator.epoch))
        return value
    monkeypatch.setattr(host, '_read_evidence', read_and_retry)
    result = case.read()
    assert result['state'] == 'recovery_required' and result['phase'] == 'host_receipt_changed'
    assert result['host_attempt_id'] == replacement[0]['id']
    assert result['host_fence'] == replacement[0]['fence']
    assert not result['tree_exited'] and not result['logs_complete'] and not result['artifact_committed']


def test_artifact_receipt_from_another_run_is_not_success(receipt_case):
    case = receipt_case
    case.finish()
    attempt = case.store.attempt(case.attempt['id'])
    case.store.transition_attempt(attempt['id'], 'succeeded', receipt={**attempt['receipt'], 'run_id': 'other-run'})
    result = case.read()
    assert result['state'] == 'recovery_required' and result['phase'] == 'host_artifact_unproven'
    assert not result['artifact_committed']


@pytest.mark.parametrize('change', ['none', 'missing_proof', 'missing_launch', 'wrong_fence',
    'wrong_proof_fence', 'wrong_attempt', 'identity', 'acquired_lease', 'contradictory_marker',
    'contradictory_ready', 'success'])
def test_atomic_preparation_rejection_requires_exact_negative_proof(receipt_case, change):
    case = receipt_case
    case.finish('succeeded' if change == 'success' else 'failed', never_spawned=True)
    case.launch_path.unlink()
    case.proof_path.unlink()
    owner = ProcessSupervisor(case.invocation / 'supervisor')
    owner.record_preparation_rejection(case.attempt['id'], fence=case.attempt['fence'], error='invalid script')
    value = json.loads(case.launch_path.read_text())
    if change == 'missing_launch': case.launch_path.unlink()
    elif change in ('contradictory_marker', 'contradictory_ready'):
        suffix = '.ready.json' if change == 'contradictory_ready' else '.environment.json'
        atomic_json(case.launch_path.with_name(case.attempt['id'] + suffix), {'fence': case.attempt['fence']})
    elif change not in ('none', 'success'):
        if change == 'missing_proof': value.pop('no_spawn_proof')
        elif change == 'wrong_fence': value['fence'] += 1
        elif change == 'wrong_proof_fence': value['no_spawn_proof']['fence'] += 1
        elif change == 'wrong_attempt': value['no_spawn_proof']['attempt_id'] = 'other'
        elif change == 'identity': value['no_spawn_proof']['identity'] = {'pid': 123}
        elif change == 'acquired_lease': value['no_spawn_proof']['environment_lease_acquired'] = True
        atomic_json(case.launch_path, value)
    result = case.read()
    if change == 'none':
        assert result['state'] == 'failed' and result['tree_exited'] and result['resources_released']
    else:
        assert result['state'] == 'recovery_required' and not result['tree_exited']
        assert not result['logs_complete'] and not result['artifact_committed']
