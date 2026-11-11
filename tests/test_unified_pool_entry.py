"""Ordinary application entry routes into the dedicated shared pool."""
import json
from pathlib import Path
import time

import pytest

from operon.application import Application
from operon.pool_service import PoolClient, PoolControlServer, PoolService
from src.web.models import Graph
from src.web.operator_catalog import catalog_from_descriptors
from src.web.service import Settings

ROOT = Path(__file__).resolve().parents[1]
MIB = 1024 ** 2


def wait_until(check, timeout=40):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        value = check()
        if value:
            return value
        time.sleep(.05)
    pytest.fail('Timed out waiting for unified pool entry')


def graph(root):
    return Graph.model_validate({
        'schema_version': 2, 'name': 'unified entry', 'base_dir': str(root),
        'memory': {'enabled': True, 'auto_spill': True, 'budget_mb': 16,
                   'process_limit_mb': 64},
        'nodes': [{'id': 'input', 'kind': 'source', 'position': {'x': 0, 'y': 0},
                   'source': {'path': 'input.csv', 'dims': ['sample', 'feature'],
                              'labels': {'sample': 'auto', 'feature': 'builtin'}}},
                  {'id': 'summary', 'kind': 'operator', 'operator': 'describe',
                   'position': {'x': 1, 'y': 0}, 'params': {}}],
        'edges': [{'id': 'e1', 'source': 'input', 'target': 'summary'}]})


def test_application_task_entry_uses_pool_and_has_no_local_allocator(tmp_path, monkeypatch):
    workspace = tmp_path / 'workspace'; workspace.mkdir()
    (workspace / 'input.csv').write_text('a,b\n1,2\n3,4\n', encoding='utf-8')
    code = tmp_path / 'code'; (code / 'scripts').mkdir(parents=True)
    (code / 'scripts/run.py').write_text('''import json, sys, time
from pathlib import Path
task = Path(sys.argv[1]); output = task / 'output'; output.mkdir(parents=True)
(output / 'started.json').write_text(json.dumps({'pid': __import__('os').getpid()}))
while not (task / 'finish').exists():
    if (task / 'cancel.requested').exists():
        sys.exit(2)
    time.sleep(.03)
(output / 'run_summary.json').write_text(json.dumps({'status': 'complete'}))
''', encoding='utf-8')
    gate = tmp_path / 'environment-gate.json'
    monkeypatch.setenv('OPERON_ENVIRONMENT_GATE', str(gate))
    pool = PoolService(root=tmp_path / 'pool', admission_dir=tmp_path / 'admission',
                       workspaces=[{'root': workspace, 'principal': 'alice'}],
                       code_root=code, capacity_bytes=256 * MIB, cpu_threads=4,
                       environment_gate=gate)
    server = PoolControlServer(pool, token='unified-token', port=0).start()
    app = None
    try:
        settings = Settings(workspace, workspace / '.studio', workspace / 'frontend',
                            testing=True, code_root=code,
                            pool_address=f'127.0.0.1:{server.address[1]}',
                            pool_token='unified-token', pool_principal='alice')
        app = Application(settings, catalog_from_descriptors())
        assert app.service.admission is None
        assert app.service.engine is None
        assert app.service.scheduler is None
        # The ordinary click/API entry is public; this local test bypasses only
        # dependency readiness probes whose subprocess stdio is sandboxed.
        monkeypatch.setattr(app.readiness, 'require_ready', lambda value: None)
        job = app.jobs.launch(graph(workspace))
        wait_until(lambda: (workspace / '.studio/jobs' / job['id'] / 'output/started.json').exists())
        assert app.service.resources()['engine']['mode'] == 'pool'
        assert app.service.resources()['pool']['coordinator']['active_attempts'] >= 1
        assert app.jobs.details(job['id'])['id'] == job['id']
        events = app.events(0, limit=50)
        assert events['available'] is True
        assert any(event.get('run_id') == job['id'] for event in events['events'])
        # Cancel through the ordinary TaskService, not a dedicated pool command.
        app.jobs.cancel(job['id'])
        wait_until(lambda: app.jobs.details(job['id'])['status'] == 'cancelled')
        wait_until(lambda: pool.engine.store.run(job['id'])['status'] == 'cancelled')
        # Stable request IDs through the ordinary submit entry deduplicate at
        # the pool authority; a second call cannot create a second run.
        payload = {'graph': graph(workspace).model_dump(mode='json'),
                   'request_id': 'unified-stable-request'}
        first = app.jobs.submit(payload)
        again = app.jobs.submit(payload)
        assert first['id'] == again['id']
        assert len([run for run in pool.engine.store.list_runs()
                    if run['id'] == first['id']]) == 1
        app.jobs.cancel(first['id'])
        wait_until(lambda: app.jobs.details(first['id'])['status'] == 'cancelled')
    finally:
        if app is not None:
            app.shutdown()
        server.close()
        pool.shutdown()

def test_unavailable_pool_returns_explicit_error_without_local_job(tmp_path):
    from operon.documents import CommandError
    workspace = tmp_path / 'workspace'; workspace.mkdir()
    (workspace / 'input.csv').write_text('a,b\n1,2\n', encoding='utf-8')
    code = tmp_path / 'code'; (code / 'scripts').mkdir(parents=True)
    (code / 'scripts/run.py').write_text('print("should not run")\n', encoding='utf-8')
    app = Application(Settings(workspace, workspace / '.studio', workspace / 'frontend',
                               testing=True, code_root=code,
                               pool_address='127.0.0.1:1', pool_token='missing',
                               pool_principal='alice'),
                      catalog_from_descriptors())
    try:
        prepared = app.prepare(graph(workspace))
        with pytest.raises(CommandError) as error:
            app.jobs._launch(prepared, validated=True)
        assert error.value.code == 'engine_unavailable'
        assert app.service.jobs == {}
        assert list((workspace / '.studio/jobs').glob('*/job.json')) == []
    finally:
        app.shutdown()
