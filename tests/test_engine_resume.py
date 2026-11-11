"""Verified resume keys, invalidation and closed cache eligibility."""
import json
from pathlib import Path

import pytest

from operon.engine.artifacts import ArtifactCommitter
from operon.engine.contracts import PoolSpec
from operon.engine.resume import (
    ResumePlanner, cache_key, eligibility, execution_graph, execution_identity, file_identity,
    implementation_identity,
)
from operon.engine.state import StateStore


def setup(tmp_path):
    store = StateStore(tmp_path / 'state.sqlite3')
    spec = PoolSpec('pool-resume', 'tester', 'host', 64 * 1024 * 1024, 4 * 1024 * 1024, 2)
    store.ensure_pool(spec)
    store.register_workspace('ws', 'pool-resume', str(tmp_path), 'tester')
    store.claim_submission(principal='tester', key='k', digest='d', operation='run',
                           run={'id': 'run-1', 'workspace_id': 'ws', 'project': 'p',
                                'plan_key': 'p', 'plan_digest': 'd', 'plan': {}},
                           units=[{'unit_id': 'u1', 'node_ids': ['n'], 'depends_on': [],
                                   'target': {'kind': 'local'},
                                   'requirement': {'managed_budget_bytes': 1,
                                                   'process_reservation_bytes': 1, 'cpu_threads': 1}}])
    unit = store.units('run-1')[0]
    attempt = store.create_attempt(unit['id'], epoch=1)
    store.transition_attempt(attempt['id'], 'running', expected_revision=attempt['revision'])
    return store, unit, store.attempt(attempt['id'])


def prior_run(tmp_path, store, unit, attempt, key):
    committer = ArtifactCommitter(tmp_path, store)
    staging = committer.staging('run-1', unit['local_id'], attempt['id'])
    (staging / 'out.bin').write_bytes(b'result')
    receipt = committer.commit(attempt=attempt, unit=unit, fence=attempt['fence'],
                               manifest={'files': [{'path': 'out.bin'}]}, run_id='run-1')
    store.transition_attempt(attempt['id'], 'succeeded',
                             expected_revision=store.attempt(attempt['id'])['revision'],
                             receipt={'cache_key': key})
    return receipt


def target(key, *, unit_id='u1', depends=(), env_verified=True):
    identity = execution_identity(
        graph={'name': 'title', 'nodes': [{'id': 'n', 'operator': 'x'}]},
        parameters={'k': 1}, implementation=implementation_identity(operator='x', version='1',
                                                                    entry_point='x:run', code_sha='abc'),
        environment={'python': '3.12', 'verified': env_verified},
        converters={'port': 'v1'})
    return {'unit_id': unit_id, 'depends_on': list(depends), 'cache_key': key,
            'execution_identity': identity, 'inputs': [{'sha256': 'abc', 'size': 1}],
            'environment_verified': env_verified}


def test_verified_artifact_is_reused_for_the_same_key(tmp_path):
    store, unit, attempt = setup(tmp_path)
    receipt = prior_run(tmp_path, store, unit, attempt, 'same-key')
    planner = ResumePlanner(store, tmp_path)
    decisions = planner.plan('run-1', [target('same-key')])
    assert decisions[0].reuse and decisions[0].artifact_ids == (receipt['artifact_id'],)


def test_changed_parameters_or_inputs_invalidate_the_unit(tmp_path):
    store, unit, attempt = setup(tmp_path)
    prior_run(tmp_path, store, unit, attempt, 'old-key')
    planner = ResumePlanner(store, tmp_path)
    decisions = planner.plan('run-1', [target('new-key')])
    assert not decisions[0].reuse and decisions[0].reason == 'cache-key-changed'


def test_dependency_rerun_invalidates_descendants_even_with_matching_key(tmp_path):
    store, unit, attempt = setup(tmp_path)
    prior_run(tmp_path, store, unit, attempt, 'base')
    planner = ResumePlanner(store, tmp_path)
    decisions = planner.plan('run-1', [target('changed', unit_id='u1', depends=['upstream']),
                                       target('same', unit_id='u2', depends=['u1'])])
    assert decisions[0].reuse is False
    assert not decisions[1].reuse and decisions[1].reason.startswith('dependency-rerun')


def test_damaged_artifact_is_not_reused(tmp_path):
    store, unit, attempt = setup(tmp_path)
    receipt = prior_run(tmp_path, store, unit, attempt, 'same')
    (Path(receipt['location']) / 'out.bin').write_bytes(b'damaged')
    planner = ResumePlanner(store, tmp_path)
    decisions = planner.plan('run-1', [target('same')])
    assert not decisions[0].reuse and decisions[0].reason == 'damaged-artifact'


def test_presentation_only_changes_do_not_alter_execution_identity():
    graph = {'name': 'old title', 'nodes': [{'id': 'n', 'operator': 'x', 'title': 'Old',
                                             'position': {'x': 1, 'y': 2}, 'params': {'a': 1}}]}
    changed = {'name': 'new title', 'nodes': [{'id': 'n', 'operator': 'x', 'title': 'New',
                                               'position': {'x': 90, 'y': 3}, 'params': {'a': 1}}]}
    assert execution_graph(graph) == execution_graph(changed)
    assert cache_key(identity=execution_identity(graph=graph, parameters={'a': 1})) == \
        cache_key(identity=execution_identity(graph=changed, parameters={'a': 1}))


def test_cache_eligibility_fails_closed_for_unknown_side_effects_or_randomness():
    identity = execution_identity(graph={'nodes': []}, parameters={},
                                  implementation={'operator': 'x'}, environment={'python': '3'})
    assert eligibility(identity=identity).eligible
    assert not eligibility(identity=identity, side_effects='unknown').eligible
    assert not eligibility(identity=identity, stochastic=True).eligible
    assert not eligibility(identity=identity, environment_verified=False).eligible


def test_file_identity_is_incremental_and_detects_content_changes(tmp_path):
    path = tmp_path / 'input.bin'
    path.write_bytes(b'a' * (2 * 1024 * 1024))
    first = file_identity(path)
    path.write_bytes(b'a' * (2 * 1024 * 1024 - 1) + b'b')
    second = file_identity(path)
    assert first['size'] == second['size'] == 2 * 1024 * 1024
    assert first['sha256'] != second['sha256']
