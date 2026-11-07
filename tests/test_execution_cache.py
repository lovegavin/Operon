"""Cross-run stage cache through the real ExecutionService/JobService paths."""
from pathlib import Path
import time

import pytest

from src.web.execution import ExecutionService
from src.web.models import Graph
from src.web.operator_catalog import catalog_from_descriptors
from src.web.service import JobService, Settings

ROOT = Path(__file__).resolve().parents[1]


def wait(executions, key, timeout=30):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        value = executions.details(key)
        if value['status'] in ('complete', 'failed', 'cancelled'):
            return value
        time.sleep(.05)
    pytest.fail('execution did not finish')


def graph(root, method='total', cache='verified'):
    return Graph.model_validate({
        'schema_version': 2, 'name': 'cache pipeline', 'base_dir': str(root),
        'memory': {'enabled': True, 'auto_spill': True, 'budget_mb': 16,
                   'process_limit_mb': 64, 'chunk_mb': .01},
        'runtime': {'execution': {'mode': 'manual', 'max_parallel_tasks': 1,
                                  'cache': cache}},
        'nodes': [
            {'id': 'input', 'kind': 'source', 'position': {'x': 0, 'y': 0},
             'source': {'path': 'input.csv', 'dims': ['sample', 'feature'],
                        'labels': {'sample': 'auto', 'feature': 'builtin'}}},
            {'id': 'norm', 'kind': 'operator', 'operator': 'normalize',
             'position': {'x': 1, 'y': 0},
             'params': {'dim': 'sample', 'method': method, 'output': 'normalized'}},
            {'id': 'summary', 'kind': 'operator', 'operator': 'describe',
             'position': {'x': 2, 'y': 0}, 'params': {}}],
        'edges': [{'id': 'e1', 'source': 'input', 'target': 'norm'},
                  {'id': 'e2', 'source': 'norm', 'target': 'summary'}]})


@pytest.fixture
def executions(tmp_path, monkeypatch):
    code = tmp_path / 'code'
    (code / 'scripts').mkdir(parents=True)
    (code / 'scripts/run.py').write_text('''import json, sys
from pathlib import Path
task = Path(sys.argv[1]); output = task / 'output'; output.mkdir(parents=True)
(output / 'run_summary.json').write_text(json.dumps({'status': 'complete'}))
''', encoding='utf-8')
    source = tmp_path / 'input.csv'
    source.write_text('a,b\n1,2\n3,4\n', encoding='utf-8')
    service = JobService(Settings(tmp_path, tmp_path / '.studio', tmp_path / 'none',
                                  testing=True, code_root=code),
                         catalog_from_descriptors())
    declare_cache_contract(service)
    result = ExecutionService(service)
    try:
        yield result, service, source
    finally:
        result.shutdown()
        service.shutdown()


def declare_cache_contract(service, *, side_effects='none', stochastic=False,
                           randomness=None):
    for field in ('operators', 'readers'):
        for spec in service.catalog.get(field, []):
            if spec.get('id') in ('CsvReader', 'normalize', 'describe'):
                spec.setdefault('resources', {})['cache'] = {'deterministic': True, 'side_effects': side_effects,
                                 'stochastic': stochastic,
                                 **({'seed_parameters': randomness['parameters']} if randomness else {})}


def cache_decision(executor, run_id):
    return executor.details(run_id)['cache_decisions']['stage_1']


def test_verified_stage_cache_hit_and_invalidation(executions):
    executor, service, source = executions
    first = wait(executor, executor.launch(graph(executor.service.root))['id'])
    assert first['status'] == 'complete', first.get('error') or first.get('console')
    assert len(service.jobs) == 1
    assert first.get('cache_hits', 0) == 0
    second = wait(executor, executor.launch(graph(executor.service.root))['id'])
    assert second['status'] == 'complete'
    assert second.get('cache_hits') == 1
    assert len(service.jobs) == 1
    assert second['children'][0]['cache_hit'] is True

    # A changed parameter must miss the cache and create a new worker job.
    changed_param = wait(executor, executor.launch(graph(executor.service.root, method='zscore'))['id'])
    assert changed_param['status'] == 'complete'
    assert changed_param.get('cache_hits', 0) == 0
    assert len(service.jobs) == 2

    # Changed input content must also miss.
    source.write_text('a,b\n9,8\n7,6\n', encoding='utf-8')
    changed_input = wait(executor, executor.launch(graph(executor.service.root, method='zscore'))['id'])
    assert changed_input['status'] == 'complete'
    assert changed_input.get('cache_hits', 0) == 0
    assert len(service.jobs) == 3

    # Damage the previously cached output: the next matching request must not
    # reuse the artifact and must run a new worker.
    cached_child = changed_input['children'][0]['id']
    output = service.jobs_dir / cached_child / 'output'
    (output / 'run_summary.json').write_text('{"status":"damaged"}', encoding='utf-8')
    repaired = wait(executor, executor.launch(graph(executor.service.root, method='zscore'))['id'])
    assert repaired['status'] == 'complete'
    assert repaired.get('cache_hits', 0) == 0
    assert len(service.jobs) == 4


def test_cache_requires_explicit_opt_in(executions):
    executor, service, _ = executions
    value = wait(executor, executor.launch(graph(executor.service.root, cache=False))['id'])
    assert value['status'] == 'complete'
    value = wait(executor, executor.launch(graph(executor.service.root, cache=False))['id'])
    assert value['status'] == 'complete'
    assert value.get('cache_hits', 0) == 0
    assert len(service.jobs) == 2

def test_external_side_effects_and_unbound_randomness_are_refused(executions):
    executor, service, _ = executions
    for spec in service.catalog['operators']:
        if spec['id'] == 'normalize':
            spec.setdefault('resources', {})['cache'] = {'deterministic': True, 'side_effects': 'external-write',
                             'stochastic': False}
    first = wait(executor, executor.launch(graph(executor.service.root))['id'])
    assert first['status'] == 'complete'
    decision = first['cache_decisions']['stage_1']
    assert decision['eligible'] is False
    assert any('side-effects-not-none' in reason for reason in decision['reasons'])
    second = wait(executor, executor.launch(graph(executor.service.root))['id'])
    assert second['status'] == 'complete'
    assert second.get('cache_hits', 0) == 0
    assert len(service.jobs) == 2

    for spec in service.catalog['operators']:
        if spec['id'] == 'normalize':
            spec.setdefault('resources', {})['cache'] = {'deterministic': True, 'side_effects': 'none',
                             'stochastic': True,
                             'seed_parameters': ['not_bound_seed']}
    third = wait(executor, executor.launch(graph(executor.service.root))['id'])
    assert third['status'] == 'complete'
    decision = third['cache_decisions']['stage_1']
    assert decision['eligible'] is False
    assert any('randomness-not-bound' in reason for reason in decision['reasons'])


def test_environment_content_change_and_unverified_environment_refuse_cache(executions, monkeypatch):
    executor, service, _ = executions
    first = wait(executor, executor.launch(graph(executor.service.root))['id'])
    assert first['status'] == 'complete'
    assert first['cache_decisions']['stage_1']['eligible'] is True
    # Add a real distribution-metadata entry to the import path.  The cache
    # fingerprint is derived from the actual installed metadata, so this is a
    # dependency-content change rather than a mocked digest.
    fake = executor.service.directory / 'fake-site' / 'fake_dep-1.0.dist-info'
    fake.mkdir(parents=True, exist_ok=True)
    (fake / 'METADATA').write_text('Metadata-Version: 2.1\nName: fake-dep\nVersion: 1.0\n',
                                   encoding='utf-8')
    import os
    monkeypatch.setenv('PYTHONPATH', str(fake.parent) + os.pathsep + os.environ.get('PYTHONPATH', ''))
    changed = wait(executor, executor.launch(graph(executor.service.root))['id'])
    assert changed['status'] == 'complete'
    assert changed.get('cache_hits', 0) == 0
    assert len(service.jobs) == 2
    monkeypatch.setattr(
        executor, '_environment_content_fingerprint',
        lambda stage: {'verified': False, 'error': 'injected verification failure'})
    unverified = wait(executor, executor.launch(graph(executor.service.root))['id'])
    assert unverified['status'] == 'complete'
    decision = unverified['cache_decisions']['stage_1']
    assert decision['eligible'] is False
    assert any('environment-unverified' in reason for reason in decision['reasons'])

def test_declared_random_operator_without_bound_seed_is_refused(executions):
    executor, service, _ = executions
    target = next(spec for spec in service.catalog['operators'] if spec['id'] == 'bootstrap_ci')
    target.setdefault('resources', {})['cache'] = {'deterministic': True, 'side_effects': 'none',
                       'stochastic': True,
                       'seed_parameters': ['seed']}
    graph_value = graph(executor.service.root).model_dump(mode='json')
    graph_value['nodes'][1].update({'operator': 'bootstrap_ci', 'params': {}})
    result = wait(executor, executor.launch(Graph.model_validate(graph_value))['id'])
    assert result['status'] == 'complete', result.get('error') or result.get('console')
    decision = result['cache_decisions']['stage_1']
    assert decision['eligible'] is False
    assert any('randomness-not-bound:bootstrap_ci:seed' in reason
               for reason in decision['reasons'])
    second = wait(executor, executor.launch(Graph.model_validate(graph_value))['id'])
    assert second.get('cache_hits', 0) == 0

def test_undeclared_operators_are_not_cached(executions):
    executor, service, _ = executions
    for field in ('operators', 'readers'):
        for spec in service.catalog.get(field, []):
            spec.get('resources', {}).pop('cache', None)
            spec.pop('cache_contract', None)
    first = wait(executor, executor.launch(graph(executor.service.root))['id'])
    assert first['status'] == 'complete'
    decision = first['cache_decisions']['stage_1']
    assert decision['eligible'] is False
    assert any('missing-cache-contract' in reason for reason in decision['reasons'])
    second = wait(executor, executor.launch(graph(executor.service.root))['id'])
    assert second.get('cache_hits', 0) == 0
