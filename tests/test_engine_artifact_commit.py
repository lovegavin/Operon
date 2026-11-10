"""Artifact staging, fenced publication and crash reconciliation."""
import json
from pathlib import Path

import pytest

from operon.engine.artifacts import ArtifactCommitter, ArtifactError, CommitInterrupted
from operon.engine.contracts import PoolSpec, ResourceRequest, RunState, StaleAttemptError
from operon.engine.state import StateStore


def setup(tmp_path, *, state='running'):
    store = StateStore(tmp_path / 'state.sqlite3')
    spec = PoolSpec('pool-art', 'tester', 'host', 64 * 1024 * 1024, 4 * 1024 * 1024, 2)
    store.ensure_pool(spec)
    store.register_workspace('ws', 'pool-art', str(tmp_path), 'tester')
    store.claim_submission(principal='tester', key='k', digest='d', operation='run',
                           run={'id': 'run-1', 'workspace_id': 'ws', 'project': 'p',
                                'plan_key': 'plan', 'plan_digest': 'pd', 'plan': {}},
                           units=[{'unit_id': 'u1', 'node_ids': ['n1'], 'depends_on': [],
                                   'target': {'kind': 'local'},
                                   'requirement': {'managed_budget_bytes': 1024,
                                                   'process_reservation_bytes': 2048,
                                                   'cpu_threads': 1}}])
    unit = store.units('run-1')[0]
    attempt = store.create_attempt(unit['id'], epoch=1)
    store.transition_attempt(attempt['id'], 'running', expected_revision=attempt['revision'])
    return store, unit, store.attempt(attempt['id'])


def commit(committer, store, unit, attempt, *, files=None, fence=None, manifest=None):
    staging = committer.staging('run-1', unit['local_id'], attempt['id'])
    for name, content in (files or {'data.npy': b'payload-1', 'info.json': b'{"x":1}'}).items():
        path = staging / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    manifest = manifest or {'kind': 'form', 'form': 'matrix', 'labels': {'rows': ['a']},
                            'files': [{'path': name} for name in (files or
                                      {'data.npy': 0, 'info.json': 0})]}
    return committer.commit(attempt=attempt, unit=unit, fence=fence or attempt['fence'],
                            manifest=manifest, run_id='run-1', unit_label=unit['local_id'])


def test_commit_publishes_verified_immutable_digests(tmp_path):
    store, unit, attempt = setup(tmp_path)
    committer = ArtifactCommitter(tmp_path, store)
    receipt = commit(committer, store, unit, attempt)
    assert receipt['state'] == 'committed' and receipt['fence'] == attempt['fence']
    location = Path(receipt['location'])
    assert (location / 'data.npy').read_bytes() == b'payload-1'
    record = store.artifact(receipt['artifact_id'])
    assert record['state'] == 'committed'
    assert record['manifest']['files'][0]['sha256']
    results = json.loads((tmp_path / 'runs/run-1/results/manifest.json').read_text())
    assert results['artifacts'][0]['artifact_id'] == receipt['artifact_id']
    # Replay is idempotent and does not duplicate the results entry.
    replay = commit(committer, store, unit, attempt)
    assert replay['artifact_id'] == receipt['artifact_id']
    results = json.loads((tmp_path / 'runs/run-1/results/manifest.json').read_text())
    assert len(results['artifacts']) == 1


def test_stale_fence_cannot_publish(tmp_path):
    store, unit, attempt = setup(tmp_path)
    committer = ArtifactCommitter(tmp_path, store)
    with pytest.raises(StaleAttemptError):
        commit(committer, store, unit, attempt, fence=attempt['fence'] + 99)


def test_tampered_staging_or_path_escape_is_rejected(tmp_path):
    store, unit, attempt = setup(tmp_path)
    committer = ArtifactCommitter(tmp_path, store)
    staging = committer.staging('run-1', unit['local_id'], attempt['id'])
    (staging / 'data.npy').write_bytes(b'payload')
    with pytest.raises(ArtifactError):
        committer.commit(attempt=attempt, unit=unit, fence=attempt['fence'],
                         manifest={'files': [{'path': 'data.npy', 'sha256': '0' * 64}]},
                         run_id='run-1')
    with pytest.raises(ArtifactError):
        committer.commit(attempt=attempt, unit=unit, fence=attempt['fence'],
                         manifest={'files': [{'path': '../escape.txt'}]}, run_id='run-1')
    with pytest.raises(ArtifactError):
        committer.commit(attempt=attempt, unit=unit, fence=attempt['fence'],
                         manifest={'files': [{'path': 'C:/absolute.txt'}]}, run_id='run-1')


def test_crash_after_staged_leaves_no_committed_artifact_and_retry_succeeds(tmp_path):
    store, unit, attempt = setup(tmp_path)

    def crash(phase):
        if phase == 'staged':
            raise CommitInterrupted('crash after staging')

    first = ArtifactCommitter(tmp_path, store, crash_point=crash)
    with pytest.raises(CommitInterrupted):
        commit(first, store, unit, attempt)
    assert store.artifact('art-' + '0' * 32) is None
    success = ArtifactCommitter(tmp_path, store)
    receipt = commit(success, store, unit, attempt)
    assert store.artifact(receipt['artifact_id'])['state'] == 'committed'


def test_crash_after_rename_or_receipt_is_reconciled(tmp_path):
    for phase in ('renamed', 'receipt', 'database'):
        root = tmp_path / phase
        root.mkdir()
        store, unit, attempt = setup(root)

        def crash(value, phase=phase):
            if value == phase:
                raise CommitInterrupted(value)

        committer = ArtifactCommitter(root, store, crash_point=crash)
        with pytest.raises(CommitInterrupted):
            commit(committer, store, unit, attempt)
        recovery = ArtifactCommitter(root, store).reconcile()
        committed = [store.artifact(row['id']) for row in
                     store.connection.execute("SELECT id FROM artifacts WHERE state='committed'")]
        assert committed, (phase, recovery)
        assert all(item['digest'] for item in committed)


def test_damaged_output_is_never_served_as_committed(tmp_path):
    store, unit, attempt = setup(tmp_path)
    committer = ArtifactCommitter(tmp_path, store)
    receipt = commit(committer, store, unit, attempt)
    (Path(receipt['location']) / 'data.npy').write_bytes(b'payload-2')
    from operon.engine.resume import verify_artifact
    ok, problems = verify_artifact(store.artifact(receipt['artifact_id']), tmp_path)
    assert not ok and any('digest' in item for item in problems)
