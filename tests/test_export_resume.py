"""Resume state/file contract tests with synthetic process evidence, not E2E."""
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from operon.contracts.base import ContractError
from operon.engine.artifacts import ArtifactCommitter
from operon.engine.contracts import BusyError, StaleRevisionError
from operon.engine.executor import ExecutionResult
from operon.engine.fs import atomic_json
from operon.engine.retention import RetentionManager
from operon.execution.codecs import file_reference
from operon.export.resume import attach_verified_resume
from test_engine_pool import FakeExecutor, make


class FailingSecond(FakeExecutor):
    def poll(self, context):
        return ExecutionResult(state='succeeded' if context.unit['local_id'] == 'a' else 'failed',
                               exit_code=0 if context.unit['local_id'] == 'a' else 1)


@pytest.fixture
def lineage(tmp_path):
    store, _, coordinator, root = make(tmp_path, executor=FailingSecond())
    environment_store = SimpleNamespace(root=root / 'environments')
    units = [{'unit_id': name, 'node_ids': [name], 'depends_on': [] if name == 'a' else ['a'],
              'requirement': {'managed_budget_bytes': 1024, 'process_reservation_bytes': 2048, 'cpu_threads': 1}}
             for name in ('a', 'b')]
    graph = {'units': [{'unit_id': name, 'output_contracts': [
        {'name': 'value', 'representation': 'file', 'required': True}]} for name in ('a', 'b')]}
    committer = ArtifactCommitter(root, store)

    def publish(attempt, result):
        path = root / 'runs' / attempt['run']['id'] / 'nodes' / attempt['unit']['local_id'] / 'attempts' / attempt['id'] / 'outputs'
        path.mkdir(parents=True)
        (path / 'value.txt').write_text('verified scientific result', encoding='utf-8')
        receipt = committer.commit_existing(attempt=attempt, unit=attempt['unit'], fence=attempt['fence'],
            source_root=path, files=['value.txt'], run_id=attempt['run']['id'])
        atomic_json(root / 'runs' / attempt['run']['id'] / 'published' / (attempt['unit']['local_id'] + '.json'),
                    {'receipt': receipt, 'outputs': {'value': file_reference(path / 'value.txt')}})
        return receipt

    coordinator.artifact_committer = publish

    def submit(run_id):
        return coordinator.submit(key=run_id, digest='exact-plan-input-environment', graph=graph,
            parameters={}, execution={'standalone': True}, units=units, run_id=run_id, workspace_id='ws')

    submit('parent')
    for _ in range(5):
        coordinator.run_once()
    assert store.run('parent')['status'] == 'failed'
    successful = next(a for a in store.attempts('parent') if a['state'] == 'succeeded')
    # Deliberately synthetic OS evidence. These tests exercise validation and
    # state transactions, not actual supervisor containment or process exit.
    supervisor = root / 'supervisor'
    proof = {'attempt_id': successful['id'], 'fence': successful['fence'], 'tree_exited': True, 'method': 'linux-subreaper'}
    atomic_json(supervisor / (successful['id'] + '.tree-exit.json'), proof)
    atomic_json(supervisor / (successful['id'] + '.launch.json'), {
        'attempt_id': successful['id'], 'fence': successful['fence'], 'pid': 999999999, 'created': 1.0, 'state': 'exited'})
    atomic_json(environment_store.root / 'leases' / (successful['id'] + '.json'), {
        'attempt_id': successful['id'], 'fence': successful['fence'], 'state': 'released',
        'supervisor_directory': str(supervisor.resolve()), 'proof': proof})
    submit('child')
    def attach(**overrides):
        return attach_verified_resume(store, root=root, parent_run_id='parent', run_id='child',
            run_identity=overrides.pop('run_identity', 'exact-plan-input-environment'), request_id='attach-child',
            principal='tester', environment_store=environment_store, **overrides)
    try:
        yield SimpleNamespace(store=store, coordinator=coordinator, root=root, env=environment_store,
                              successful=successful, attach=attach, submit=submit, committer=committer)
    finally:
        coordinator.stop()
        store.close()


def test_resume_attaches_zero_attempt_success_and_only_executes_failed_unit(lineage):
    value = lineage
    before = value.store.run('parent')
    receipt = value.attach()
    assert receipt['reused_units'] == ['a']
    a, b = value.store.units('child')
    assert (a['state'], a['attempts'], b['state']) == ('succeeded', 0, 'ready')
    assert value.store.attempts('child') == []
    assert value.store.run('parent') == before
    assert value.store.run('child')['plan']['execution']['resume_parent_run_id'] == 'parent'
    attached, = value.store.resume_attachments('child')
    assert any(ref['owner'] == 'run:child' for ref in value.store.references(attached['artifact_id']))
    value.coordinator.run_once()
    assert ('child', 'a') not in value.coordinator.executor.launches
    assert ('child', 'b') in value.coordinator.executor.launches


def test_resume_replay_repairs_interrupted_published_descriptor_write(lineage):
    value = lineage
    expected = value.attach()
    published = value.root / 'runs' / 'child' / 'published' / 'a.json'
    published.unlink()
    assert value.attach() == expected
    assert published.is_file()
    assert len(value.store.resume_attachments('child')) == 1
    assert value.store.attempts('child') == []


def test_resume_rejects_changed_identity_and_corrupt_payload(lineage):
    value = lineage
    with pytest.raises(ContractError, match='identity changed'):
        value.attach(run_identity='changed-environment')
    published = json.loads((value.root / 'runs' / 'parent' / 'published' / 'a.json').read_text())
    Path(published['outputs']['value']['path']).write_text('tampered', encoding='utf-8')
    with pytest.raises(ContractError, match='contents changed'):
        value.attach()
    assert value.store.resume_attachments('child') == []
    assert value.store.units('child')[0]['state'] == 'ready'


def test_resume_rejects_output_reference_outside_verified_artifact(lineage):
    value = lineage
    path = value.root / 'runs' / 'parent' / 'published' / 'a.json'
    published = json.loads(path.read_text())
    other = value.root / 'unowned.txt'
    other.write_text('different valid payload', encoding='utf-8')
    published['outputs']['value'] = file_reference(other)
    atomic_json(path, published)
    with pytest.raises(ContractError, match='escapes'):
        value.attach()


@pytest.mark.parametrize('state', ['acquired', 'spawning'])
def test_resume_refuses_active_or_uncertain_environment_lease(lineage, state):
    value = lineage
    path = value.env.root / 'leases' / (value.successful['id'] + '.json')
    lease = json.loads(path.read_text())
    lease['state'] = state
    atomic_json(path, lease)
    with pytest.raises(ContractError, match='lease is active or uncertain'):
        value.attach()


def test_resume_final_transaction_checks_resource_lease_and_revision(lineage, monkeypatch):
    value = lineage
    original = ArtifactCommitter.verify_existing
    def change_revision(self, *args, **kwargs):
        result = original(self, *args, **kwargs)
        value.store.transition_run('parent', 'failed', reason='concurrent audit')
        return result
    monkeypatch.setattr(ArtifactCommitter, 'verify_existing', change_revision)
    with pytest.raises(StaleRevisionError):
        value.attach()
    assert value.store.resume_attachments('child') == []
    monkeypatch.setattr(ArtifactCommitter, 'verify_existing', original)
    with value.store.transaction():
        value.store.connection.execute("UPDATE leases SET state='granted' WHERE attempt_id=?", (value.successful['id'],))
    with pytest.raises(BusyError, match='resource lease'):
        value.attach()


def test_repeated_failed_resume_can_inherit_earlier_verified_attachment(lineage):
    value = lineage
    value.attach()
    for _ in range(3):
        value.coordinator.run_once()
    assert value.store.run('child')['status'] == 'failed'
    value.submit('grandchild')
    receipt = attach_verified_resume(value.store, root=value.root, parent_run_id='child', run_id='grandchild',
        run_identity='exact-plan-input-environment', request_id='attach-grandchild', principal='tester', environment_store=value.env)
    assert receipt['reused_units'] == ['a']
    assert value.store.units('grandchild')[0]['attempts'] == 0


def test_pinned_resume_payload_is_excluded_from_attempt_scratch_cleanup(lineage):
    value = lineage
    value.attach()
    plan = RetentionManager(value.store, value.root, result_days=0, failed_days=0).plan(now=10**12)
    assert all(Path(item['path']).name != value.successful['id'] for item in plan['scratch'])


def test_equal_payloads_keep_distinct_fenced_publication_identity(tmp_path):
    committer = ArtifactCommitter(tmp_path)
    receipts = []
    for index in (1, 2):
        folder = tmp_path / str(index)
        folder.mkdir()
        (folder / 'x').write_text('same content', encoding='utf-8')
        receipts.append(committer.commit_existing(attempt={'id': f'a-{index}', 'fence': index},
            unit={'id': f'u-{index}'}, fence=index, source_root=folder, files=['x']))
    assert receipts[0]['digest'] == receipts[1]['digest']
    assert receipts[0]['artifact_id'] != receipts[1]['artifact_id']
    assert all(committer.verify_existing(receipt)['valid'] for receipt in receipts)
