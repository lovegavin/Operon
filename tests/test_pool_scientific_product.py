"""Installed v3 declarations and real workers through ordinary pooled workflows."""
import ast
import json
from pathlib import Path
import time

import numpy as np
import pytest

from operon.application import Application
from operon.developer import scaffold, build
from operon.pool_service import PoolService, PoolControlServer
from src.web.models import Graph
from src.web.service import Settings

ROOT = Path(__file__).resolve().parents[1]
CACHE = {'deterministic': True, 'stochastic': False, 'side_effects': 'none'}


def cached_package(root, name, reader=False):
    project = root / name
    scaffold(project, template='reader' if reader else 'operator')
    source = project / name / '__init__.py'
    tree = ast.parse(source.read_text(encoding='utf-8'))
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef))
    declaration = next(n for n in cls.body if isinstance(n, ast.Assign)
                       and any(isinstance(t, ast.Name) and t.id == 'definition' for t in n.targets))
    value = ast.literal_eval(declaration.value)
    value['resources']['cache'] = CACHE
    declaration.value = ast.parse(repr(value), mode='eval').body
    source.write_text(ast.unparse(tree), encoding='utf-8')
    return build(project)['wheels'][0]


def finish(app, key, timeout=90):
    until = time.monotonic() + timeout
    while time.monotonic() < until:
        result = app.jobs.details(key)
        if result['status'] in ('complete', 'failed', 'cancelled'):
            assert result['status'] == 'complete', result.get('error') or result
            return result
        time.sleep(.1)
    pytest.fail(f'Workflow did not finish: {key}')


@pytest.mark.parametrize('publication_failure', [False, True])
def test_installed_contract_real_pool_workflow_and_cache(tmp_path, monkeypatch, publication_failure):
    monkeypatch.setenv('OPERON_ENVIRONMENT_GATE', str(tmp_path / 'gate.json'))
    workspace = tmp_path / 'workspace'; workspace.mkdir()
    data = np.array([[1., 2.], [3., 4.]])
    np.save(workspace / 'input.npy', data)
    pool = PoolService(root=tmp_path / 'pool', admission_dir=tmp_path / 'admission',
                       workspaces=[{'root': workspace, 'principal': 'test'}], code_root=ROOT,
                       capacity_bytes=2 * 1024**3, cpu_threads=4)
    server = PoolControlServer(pool, token='test-only', port=0).start()
    app = None
    try:
        service = pool.resolve(workspace)
        for name, reader in [('cache_reader', True), ('cache_scale', False)]:
            service.plugins.install(cached_package(tmp_path, name, reader))
        service.refresh_catalog()
        if publication_failure:
            from operon.engine.artifacts import ArtifactError
            def fail_publish(*args):
                raise ArtifactError('injected publication failure')
            monkeypatch.setattr(service, '_commit_job_artifacts', fail_publish)
        # Reload through the normal registry, never inject into the catalog.
        from operon.plugins import PluginManager
        state = PluginManager(workspace / '.studio').state()
        for entry in state['descriptors']:
            if entry['id'] in ('example.cache_reader', 'example.cache_scale'):
                assert entry['resources']['cache'] == CACHE
        app = Application(Settings(workspace, workspace / '.studio', ROOT / 'frontend/dist',
                                   code_root=ROOT, testing=True,
                                   pool_address=f'127.0.0.1:{server.address[1]}',
                                   pool_token='test-only', pool_principal='test'))
        graph = Graph.model_validate({
            'schema_version': 2, 'name': 'actual pooled scale',
            'memory': {'enabled': True, 'budget_mb': 32, 'process_limit_mb': 512},
            'runtime': {'execution': {'mode': 'manual', 'cache': 'verified'}},
            'nodes': [
                {'id': 'input', 'kind': 'source', 'position': {'x': 0, 'y': 0},
                 'source': {'path': str(workspace / 'input.npy'), 'reader': 'example.cache_reader',
                            'dims': ['sample', 'feature'], 'labels': {}}},
                {'id': 'scale', 'kind': 'operator', 'operator': 'example.cache_scale',
                 'position': {'x': 1, 'y': 1}, 'params': {'factor': 3, 'output': 'scaled'}}],
            'edges': [{'id': 'e', 'source': 'input', 'target': 'scale'}]})
        first = app.jobs.submit({'graph': graph.model_dump(mode='json'), 'request_id': 'science-1'})
        assert first['id'].startswith('exec-')  # orchestration was not bypassed
        if publication_failure:
            deadline = time.monotonic() + 60
            while time.monotonic() < deadline:
                failed = app.jobs.details(first['id'])
                if failed['status'] not in ('queued', 'preparing', 'running'):
                    break
                time.sleep(.1)
            assert failed['status'] == 'failed', failed
            assert 'publication failure' in failed['error']
            assert not failed.get('completed_units')
            return
        done = finish(app, first['id'])
        assert app.service.admission is None
        assert app.service.resources()['capacity_bytes'] == pool.engine.resources.snapshot().capacity
        assert len(service.jobs) == 1
        child = done['children'][0]['id']
        report = service.details(child)
        assert report['summary']['steps']
        # Exported exchange is a safe array packet produced by the actual worker.
        from operon.bytecode import io_path
        arrays = list(io_path(service.jobs_dir / child / 'output').rglob('*.npy'))
        assert arrays, list((service.jobs_dir / child / 'output').rglob('*'))
        assert any(np.array_equal(np.load(p, allow_pickle=False), data * 3) for p in arrays)
        reused = finish(app, app.jobs.submit({'graph': graph.model_dump(mode='json'), 'request_id': 'science-2'})['id'])
        assert reused.get('cache_hits') == 1, reused.get('cache_decisions')
        assert len(service.jobs) == 1
        np.save(workspace / 'input.npy', data + 1)
        changed = finish(app, app.jobs.submit({'graph': graph.model_dump(mode='json'), 'request_id': 'science-3'})['id'])
        assert not changed.get('cache_hits')
        assert len(service.jobs) == 2
    finally:
        if app:
            app.shutdown()
        server.close()
        pool.shutdown()


def test_cache_declaration_is_strict_and_optional():
    from operon_sdk.protocol import CacheContract
    with pytest.raises(ValueError):
        CacheContract.model_validate({**CACHE, 'deterministic': 'yes'})
    with pytest.raises(ValueError):
        CacheContract.model_validate({**CACHE, 'stochastic': True})


@pytest.mark.parametrize('resource', [{'external_tools': ['bwa']}, {'r': {}}, {'environment': 'other'}])
def test_external_environments_are_not_assumed_cache_verified(resource):
    from types import SimpleNamespace
    from operon.engine.cache_environment import fingerprint
    state = {'descriptors': [{'id': 'op', 'resources': resource}]}
    service = SimpleNamespace(pool_remote=False, plugins=SimpleNamespace(snapshot=lambda graph: state))
    result = fingerprint(service, SimpleNamespace(plugin_lock={'op': {}}))
    assert result == {'verified': False, 'error': 'isolated-or-external-environment-unverified'}


def test_studio_bootstrap_uses_pool_capacity(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from src.web.api import create_app
    monkeypatch.setenv('OPERON_ENVIRONMENT_GATE', str(tmp_path / 'gate.json'))
    workspace = tmp_path / 'workspace'
    pool = PoolService(root=tmp_path / 'pool', admission_dir=tmp_path / 'admission',
                       workspaces=[{'root': workspace, 'principal': 'test'}], code_root=ROOT,
                       capacity_bytes=1024**3, cpu_threads=2)
    server = PoolControlServer(pool, token='test-only', port=0).start()
    try:
        app = create_app(Settings(workspace, workspace / '.studio', ROOT / 'frontend/dist',
                                  code_root=ROOT, testing=True,
                                  pool_address=f'127.0.0.1:{server.address[1]}',
                                  pool_token='test-only', pool_principal='test'))
        with TestClient(app) as client:
            data = client.get('/api/bootstrap').json()
            assert data['automatic_memory_budget_bytes'] == pool.engine.resources.snapshot().capacity
            assert app.state.service.admission is None
    finally:
        server.close()
        pool.shutdown()


def test_transfer_bytes_share_the_worker_pool(tmp_path):
    from operon.engine.transport import transport_admission
    pool = PoolService(root=tmp_path / 'pool', admission_dir=tmp_path / 'admission',
                       workspaces=[{'root': tmp_path / 'workspace', 'principal': 'test'}],
                       code_root=ROOT, capacity_bytes=1024**3, cpu_threads=2)
    try:
        service = pool.resolve(tmp_path / 'workspace')
        transport = transport_admission(service)
        before = pool.coordinator.resources.snapshot()
        amount = 6 * 1024**2
        allocation = {'kind': 'transport', 'cpu_threads': 0, 'reserved_bytes': amount}
        assert transport.reserve('upload-a', allocation)
        assert transport.reserve('upload-a', allocation)  # same request is not charged twice
        held = pool.coordinator.resources.snapshot()
        assert held.used.ram - before.used.ram == amount
        assert held.transport - before.transport == amount
        transport.release('upload-a')
        transport.release('upload-a')
        assert pool.coordinator.resources.snapshot().used.ram == before.used.ram
    finally:
        pool.shutdown()
