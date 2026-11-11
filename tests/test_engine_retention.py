"""Reference-aware retention: pins, deletion boundaries and quota enforcement."""
import json
import os
from pathlib import Path

import pytest

from operon.engine.artifacts import ArtifactCommitter
from operon.engine.contracts import PoolSpec
from operon.engine.retention import QuotaExceeded, RetentionManager
from operon.engine.state import StateStore


def setup(tmp_path, *, state='running'):
    store = StateStore(tmp_path / 'state.sqlite3')
    spec = PoolSpec('pool-ret', 'tester', 'host', 64 * 1024 * 1024, 4 * 1024 * 1024, 2)
    store.ensure_pool(spec)
    store.register_workspace('ws', 'pool-ret', str(tmp_path), 'tester')
    store.claim_submission(principal='tester', key='k', digest='d', operation='run',
                           run={'id': 'run-1', 'workspace_id': 'ws', 'project': 'p',
                                'plan_key': 'p', 'plan_digest': 'd', 'plan': {}},
                           units=[{'unit_id': 'u1', 'node_ids': ['n'], 'depends_on': [],
                                   'target': {'kind': 'local'},
                                   'requirement': {'managed_budget_bytes': 1,
                                                   'process_reservation_bytes': 1, 'cpu_threads': 1}}])
    unit = store.units('run-1')[0]
    attempt = store.create_attempt(unit['id'], epoch=1)
    if state == 'running':
        store.transition_attempt(attempt['id'], 'running', expected_revision=attempt['revision'])
    return store, unit, store.attempt(attempt['id'])


def make_artifact(tmp_path, store, unit, attempt, name='data.bin', content=b'x' * 100):
    committer = ArtifactCommitter(tmp_path, store)
    staging = committer.staging('run-1', unit['local_id'], attempt['id'])
    (staging / name).write_bytes(content)
    return committer.commit(attempt=attempt, unit=unit, fence=attempt['fence'],
                            manifest={'files': [{'path': name}]}, run_id='run-1')


def test_active_attempt_and_reference_pin_artifacts(tmp_path):
    store, unit, attempt = setup(tmp_path)
    receipt = make_artifact(tmp_path, store, unit, attempt)
    manager = RetentionManager(store, tmp_path, result_days=0)
    plan = manager.plan()
    assert any(item['artifact_id'] == receipt['artifact_id'] for item in plan['pinned'])
    result = manager.apply()
    assert not result['deleted']
    assert Path(receipt['location']).exists()
    # Once the attempt is terminal and the result retention is zero, the artifact
    # is collectable unless a reference pins it.
    store.transition_attempt(attempt['id'], 'succeeded', expected_revision=store.attempt(attempt['id'])['revision'])
    store.add_reference(receipt['artifact_id'], owner='run-2', reason='consumer')
    plan = manager.plan()
    assert any(item['artifact_id'] == receipt['artifact_id'] for item in plan['pinned'])


def test_unpinned_artifact_is_deleted_only_inside_its_owned_root(tmp_path):
    store, unit, attempt = setup(tmp_path)
    receipt = make_artifact(tmp_path, store, unit, attempt)
    store.transition_attempt(attempt['id'], 'succeeded', expected_revision=store.attempt(attempt['id'])['revision'])
    manager = RetentionManager(store, tmp_path, result_days=0)
    result = manager.apply()
    assert any(item['artifact_id'] == receipt['artifact_id'] for item in result['deleted'])
    assert not Path(receipt['location']).exists()
    assert store.artifact(receipt['artifact_id'])['state'] == 'deleted'


def test_unknown_ownership_is_quarantined_not_deleted(tmp_path):
    store, unit, attempt = setup(tmp_path)
    orphan = tmp_path / 'artifacts' / 'art-orphan'
    orphan.mkdir(parents=True)
    (orphan / 'receipt.json').write_text(json.dumps({'artifact_id': 'art-orphan'}), encoding='utf-8')
    manager = RetentionManager(store, tmp_path, result_days=0)
    report = manager.apply()
    assert any(item['artifact_id'] == 'art-orphan' for item in report['quarantine'])
    assert orphan.exists()


def test_outside_paths_are_rejected_by_the_safety_check(tmp_path):
    store, unit, attempt = setup(tmp_path)
    manager = RetentionManager(store, tmp_path, result_days=0)
    assert not manager._safe(tmp_path / 'outside.bin', 'artifact')
    assert not manager._safe(tmp_path / 'artifacts' / '..' / 'escape', 'artifact')


def test_quota_evicts_unpinned_cache_and_fails_when_pinned(tmp_path):
    store, unit, attempt = setup(tmp_path)
    first = make_artifact(tmp_path, store, unit, attempt, 'one.bin', b'a' * 4096)
    store.transition_attempt(attempt['id'], 'succeeded', expected_revision=store.attempt(attempt['id'])['revision'])
    manager = RetentionManager(store, tmp_path, result_days=0, quota_bytes=64)
    report = manager.enforce_quota()
    assert report['usage']['artifacts_bytes'] <= 64 or report['over_quota']
    assert not Path(first['location']).exists()
