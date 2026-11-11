"""Real detached default pool lifecycle, through ordinary product entry points."""
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import subprocess
import sys
import time

import psutil
import pytest

from operon.application import Application
from operon.managed_pool import inspect_pool, locations
from operon.pool_service import PoolClientError
from src.web.admission import HostAdmission, process_alive
from src.web.models import Graph
from src.web.service import Settings

ROOT = Path(__file__).resolve().parents[1]


def wait(check, timeout=30):
    until = time.monotonic() + timeout
    while time.monotonic() < until:
        value = check()
        if value:
            return value
        time.sleep(.05)
    pytest.fail('Managed pool lifecycle did not reach its expected state')


@pytest.fixture
def managed(tmp_path, monkeypatch):
    for key in ('OPERON_POOL_ADDRESS', 'OPERON_POOL_TOKEN', 'OPERON_ENGINE_MODE',
                'OPERON_ENGINE_PRINCIPAL', 'OPERON_POOL_PRINCIPAL'):
        monkeypatch.delenv(key, raising=False)
    code = tmp_path / 'code'; (code / 'scripts').mkdir(parents=True)
    (code / 'scripts/run.py').write_text('''import json, os, sys, time
from pathlib import Path
task=Path(sys.argv[1]);output=task/'output';output.mkdir(exist_ok=True)
(output/'started.json').write_text(json.dumps({'pid':os.getpid(),'python':sys.executable}))
while not (task/'finish').exists():
    if (task/'cancel.requested').exists():sys.exit(2)
    time.sleep(.03)
(output/'run_summary.json').write_text(json.dumps({'status':'complete'}))
''', encoding='utf-8')
    apps = []
    def create(name='alpha', **options):
        root = tmp_path / name; root.mkdir(exist_ok=True)
        (root / 'input.csv').write_text('a,b\n1,2\n3,4\n', encoding='utf-8')
        # testing=False is intentional: exercise the shipping default with no
        # pool address, token, engine mode or pre-registered workspace.
        app = Application(Settings(root, root / '.studio', root / 'ui',
                                   code_root=options.pop('code_root', code), **options))
        apps.append(app)
        return app
    yield create
    for app in apps:
        try:
            for job in app.service.history():
                if job.get('status') in ('queued', 'preparing', 'running'):
                    app.service.cancel(job['id'])
        except Exception:
            pass
        app.shutdown()
    _, directory = locations()
    # Preserve the actual launcher failure in CI instead of only a path to a
    # temporary runner file. This contains startup diagnostics, not pool tokens.
    log = directory / 'pool.log'
    if log.is_file():
        output = log.read_text(encoding='utf-8', errors='replace')
        if 'Traceback' in output:
            print('Managed pool startup log:\n' + output[-6000:])
    path = directory / 'instance.json'
    if path.exists():
        record = json.loads(path.read_text(encoding='utf-8'))
        wait(lambda: not process_alive(record['owner']), timeout=35)


def graph(app):
    return Graph.model_validate({
        'schema_version': 2, 'name': 'automatic pool', 'base_dir': str(app.service.root),
        'memory': {'enabled': True, 'auto_spill': True, 'budget_mb': 16, 'process_limit_mb': 64},
        'nodes': [{'id': 'input', 'kind': 'source', 'position': {'x': 0, 'y': 0},
                   'source': {'path': 'input.csv', 'dims': ['sample', 'feature'],
                              'labels': {'sample': 'auto', 'feature': 'builtin'}}},
                  {'id': 'summary', 'kind': 'operator', 'operator': 'describe',
                   'position': {'x': 1, 'y': 0}, 'params': {}}],
        'edges': [{'id': 'e1', 'source': 'input', 'target': 'summary'}]})


def start(app, request='stable'):
    job = app.service.launch(graph(app), request_id=request)
    def started():
        current = app.service.details(job['id'])
        assert current['status'] not in ('failed', 'cancelled'), current.get('error')
        return (app.service.jobs_dir / job['id'] / 'output/started.json').exists()
    wait(started)
    return job


def finish(app, job):
    (app.service.jobs_dir / job['id'] / 'finish').touch()
    return wait(lambda: (value if (value := app.service.details(job['id'])).get(
        'lifecycle', {}).get('resources_released') else None))


def test_default_two_workspaces_start_one_pool_and_close_independently(managed):
    alpha, beta = managed('alpha'), managed('beta')
    with ThreadPoolExecutor(max_workers=2) as threads:
        states = list(threads.map(lambda app: app.engine_status(), (alpha, beta)))
    assert all(state['available'] and state['mode'] == 'pool' for state in states)
    assert states[0]['pool']['owner'] == states[1]['pool']['owner']
    assert len(inspect_pool()['workspaces']) == 2
    assert alpha.service.admission is beta.service.admission is None
    assert alpha.service.scheduler is beta.service.scheduler is None
    assert alpha.service.execution_environment_guard().path == beta.service.execution_environment_guard().path
    job_a, job_b = start(alpha, 'alpha-1'), start(beta, 'beta-1')
    repeated = alpha.service.launch(graph(alpha), request_id='alpha-1')
    assert repeated['id'] == job_a['id'] and repeated['reused'] is True
    changed = graph(alpha); changed.name = 'different request content'
    with pytest.raises(ValueError) as conflict:
        alpha.service.launch(changed, request_id='alpha-1')
    assert conflict.value.code == 'idempotency_conflict'
    alpha.shutdown()
    assert beta.service.details(job_b['id'])['status'] == 'running'
    # Closing a client leaves its accepted worker running too.
    reopened = managed('alpha')
    assert reopened.service.details(job_a['id'])['status'] == 'running'
    reopened.service.cancel(job_a['id'])
    wait(lambda: reopened.service.details(job_a['id'])['status'] == 'cancelled')
    assert finish(beta, job_b)['status'] == 'complete'
    assert inspect_pool()['owner'] == states[0]['pool']['owner']


def test_default_pool_restarts_and_adopts_worker_without_launching_again(managed):
    app = managed()
    job = start(app)
    before = app.service.details(job['id'])
    ceiling = inspect_pool()['pool']['ceiling_bytes']
    owner = app.service.pool_client.record['owner']
    daemon = psutil.Process(owner['pid'])
    assert daemon.create_time() == owner['created']
    daemon.kill(); daemon.wait(timeout=10)
    # The default client detects the dead owner, restores durable workspace
    # bindings and automatically subscribes to the replacement daemon.
    recovered = app.service.details(job['id'])
    assert recovered['worker'] == before['worker']
    assert recovered['pool']['attempt']['id'] == before['pool']['attempt']['id']
    assert app.service.pool_client.record['owner']['pid'] != owner['pid']
    assert inspect_pool()['pool']['ceiling_bytes'] == ceiling
    assert app.service.launch(graph(app), request_id='stable')['id'] == job['id']
    assert finish(app, job)['status'] == 'complete'


def test_automatic_pool_refuses_live_legacy_authority_without_fallback(managed, monkeypatch):
    # A separate account-local launcher is a real upgrade/drain conflict.
    app = managed()
    admission = HostAdmission()
    try:
        state = app.engine_status()
        assert not state['available']
        assert app.service.scheduler is None and app.service.admission is None
        with pytest.raises(ValueError, match='shared pool|Shared pool'):
            app.service.launch(graph(app), request_id='must-not-launch')
        assert not list(app.service.jobs_dir.glob('*/job.json'))
    finally:
        admission.close()
    # No configuration edits: retry once the old authority has drained.
    assert app.engine_status()['available']


def test_shared_workspace_rejects_conflicting_data_directory(managed):
    app = managed()
    assert app.engine_status()['available']
    _, root = locations()
    from operon.managed_pool import _client
    record = app.service.pool_client.record
    client = _client(record, root)
    with pytest.raises(PoolClientError, match='another data directory'):
        client.request('workspace.register', {
            'root': str(app.service.root), 'data_dir': str(app.service.root / '.other'),
            'code_root': str(app.service.settings.code_root),
            'principal': app.service.pool_principal, 'implementation': record['implementation']})
    assert inspect_pool()['owner'] == record['owner']


def test_pool_status_does_not_start_an_unused_daemon(tmp_path):
    assert inspect_pool()['running'] is False
    assert not locations()[1].exists()


def test_default_worker_uses_its_workspace_interpreter(managed, tmp_path):
    target = tmp_path / 'target'
    subprocess.run([sys.executable, '-m', 'venv', '--without-pip', '--system-site-packages', str(target)],
                   check=True, timeout=60)
    python = target / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
    alpha, beta = managed(), managed('beta', worker_python=str(python))
    assert alpha.engine_status()['available']  # first client starts the control service
    job = start(beta)
    observed = json.loads((beta.service.jobs_dir / job['id'] / 'output/started.json').read_text())
    assert Path(observed['python']).absolute() == python.absolute()
    assert finish(beta, job)['status'] == 'complete'


def test_default_scientific_workflow_reaches_committed_results(managed):
    app = managed(code_root=ROOT)
    workflow = graph(app)
    workflow.memory['process_limit_mb'] = 512
    job = app.jobs.submit({'graph': workflow.model_dump(mode='json'), 'request_id': 'science'})
    job_id = job['id']
    value = wait(lambda: (v if (v := app.service.details(job_id))['status'] in ('failed', 'complete')
                          and v.get('lifecycle', {}).get('resources_released') else None), timeout=90)
    assert value['status'] == 'complete', value.get('error')
    assert value['lifecycle']['artifact_committed']
    assert list((app.service.jobs_dir / job_id / 'output').iterdir())


def test_dead_client_does_not_stop_pool_worker(managed, tmp_path):
    app = managed()
    request = tmp_path / 'graph.json'; request.write_text(graph(app).model_dump_json(), encoding='utf-8')
    reply = tmp_path / 'child.json'
    script = '''import json, os, sys
from pathlib import Path
from operon.application import Application
from src.web.models import Graph
from src.web.service import Settings
root=Path(sys.argv[1])
app=Application(Settings(root,root/'.studio',root/'ui',code_root=Path(sys.argv[2])))
job=app.service.launch(Graph.model_validate_json(Path(sys.argv[3]).read_text()),request_id='child')
Path(sys.argv[4]).write_text(json.dumps({'id':job['id']}))
os._exit(0)
'''
    subprocess.run([sys.executable, '-c', script, str(app.service.root), str(app.service.settings.code_root),
                    str(request), str(reply)], check=True, timeout=90)
    job = json.loads(reply.read_text())
    wait(lambda: app.service.details(job['id'])['status'] == 'running')
    assert finish(app, job)['status'] == 'complete'


def test_live_different_pool_version_is_replaced_when_idle(managed):
    app = managed()
    assert app.engine_status()['available']
    _, root = locations()
    path = root / 'instance.json'
    record = json.loads(path.read_text())
    try:
        path.write_text(json.dumps({**record, 'implementation': 'another-release'}), encoding='utf-8')
        other = managed('other')
        state = other.engine_status()
        assert state['available']
        new_record = json.loads(path.read_text())
        assert new_record['implementation'] != 'another-release'
        assert new_record['owner'] != record['owner']
    finally:
        path.write_text(json.dumps(record), encoding='utf-8')


def test_legacy_is_explicit_only(managed, monkeypatch):
    monkeypatch.setenv('OPERON_ENGINE_MODE', 'legacy')
    app = managed()
    assert not app.service.pool_remote
    assert app.service.admission is not None
    assert not locations()[1].exists()


def test_remote_entry_automatically_shares_pool_and_durable_events(managed):
    from operon.remote.server import RemoteService
    alpha, beta = (managed(code_root=ROOT, manifest_only_registry=True),
                   managed('beta', code_root=ROOT, manifest_only_registry=True))
    remotes = [RemoteService(app.service.root, input_roots=[app.service.root]) for app in (alpha, beta)]
    try:
        owners = [remote.service.pool_client.record['owner'] for remote in remotes]
        assert owners[0] == owners[1]
        workflow = graph(beta); workflow.memory['process_limit_mb'] = 512
        payload = {'graph': workflow.model_dump(mode='json'), 'request_id': 'e' * 32}
        first = remotes[1].dispatch('run', payload)
        repeated = remotes[1].dispatch('run', payload)
        assert first['id'] == repeated['id']
        remotes[0].close()
        value = wait(lambda: (v if (v := remotes[1].service.details(first['id']))['status'] in ('complete', 'failed')
                              and v.get('lifecycle', {}).get('resources_released') else None), timeout=90)
        assert value['status'] == 'complete', value.get('error')
        page = remotes[1].dispatch('events', {'after': 0, 'run_id': first['id']})
        assert page['available'] and any(e.get('run_id') == first['id'] for e in page['events'])
        assert inspect_pool()['owner'] == owners[0]
    finally:
        for remote in remotes:
            remote.close()


@pytest.mark.parametrize('status', [psutil.STATUS_ZOMBIE, psutil.STATUS_DEAD])
def test_exited_process_is_not_a_live_pool_owner(monkeypatch, status):
    from types import SimpleNamespace
    from operon.engine.supervisor import identity_alive
    monkeypatch.setattr(psutil, 'Process', lambda pid: SimpleNamespace(
        create_time=lambda: 123.0, status=lambda: status))
    assert not process_alive({'pid': 42, 'created': 123.0})
    assert not identity_alive({'pid': 42, 'created': 123.0})


@pytest.mark.skipif(os.name != 'nt', reason='Windows desktop Job Object lifecycle')
@pytest.mark.parametrize('job_flags', [0x2800, 0x3000, 0x2000],
                         ids=['desktop-breakaway', 'silent-breakaway', 'external-host-contained'])
def test_pool_and_other_client_work_survive_desktop_job_object_close(managed, tmp_path, job_flags):
    """A desktop closes its job; an enclosing service/CI job outlives clients."""
    import ctypes
    from ctypes import wintypes
    class Basic(ctypes.Structure):
        _fields_ = [('times', ctypes.c_int64 * 2), ('flags', wintypes.DWORD),
                    ('minimum', ctypes.c_size_t), ('maximum', ctypes.c_size_t),
                    ('active', wintypes.DWORD), ('affinity', ctypes.c_size_t),
                    ('priority', wintypes.DWORD), ('scheduling', wintypes.DWORD)]
    class Limits(ctypes.Structure):
        _fields_ = [('basic', Basic), ('io', ctypes.c_uint64 * 6), ('memory', ctypes.c_size_t * 4)]
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.CreateJobObjectW.restype = wintypes.HANDLE
    kernel.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
    kernel.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    handle = kernel.CreateJobObjectW(None, None)
    limits = Limits(); limits.basic.flags = job_flags
    assert kernel.SetInformationJobObject(handle, 9, ctypes.byref(limits), ctypes.sizeof(limits)), ctypes.get_last_error()
    app = managed()
    request = tmp_path / 'request.json'; request.write_text(graph(app).model_dump_json(), encoding='utf-8')
    reply = tmp_path / 'host-ready.json'
    script = '''import json, sys, time
from pathlib import Path
from operon.application import Application
from src.web.models import Graph
from src.web.service import Settings
sys.stdin.readline()
root=Path(sys.argv[1])
app=Application(Settings(root,root/'.studio',root/'ui',code_root=Path(sys.argv[2])))
job=app.jobs.launch(Graph.model_validate_json(Path(sys.argv[3]).read_text()))
Path(sys.argv[4]).write_text(json.dumps({'id':job['id'],'owner':app.service.pool_client.record['owner']}))
time.sleep(120)
'''
    host = subprocess.Popen([sys.executable, '-c', script, str(app.service.root),
                             str(app.service.settings.code_root), str(request), str(reply)],
                            stdin=subprocess.PIPE, cwd=ROOT)
    try:
        assert kernel.AssignProcessToJobObject(handle, int(host._handle)), ctypes.get_last_error()
        host.stdin.write(b'start\n'); host.stdin.flush()
        wait(reply.exists)
        value = json.loads(reply.read_text())
        wait(lambda: (app.service.jobs_dir / value['id'] / 'output/started.json').exists())
        # A second real client observes the SAME pool before the owning host dies.
        before = app.service.details(value['id'])
        assert app.service.pool_client.record['owner'] == value['owner']
        if job_flags & (0x800 | 0x1000):
            kernel.CloseHandle(handle); handle = None
        else:
            # A host that forbids breakaway (CI / container) owns the job for
            # its whole lifetime. Ending one submitting client must not kill
            # its peer's work; the outer host retains cleanup authority.
            host.kill()
        host.wait(timeout=10)
        time.sleep(.3)
        assert process_alive(value['owner']), 'Desktop Job Object killed the shared pool'
        after = app.service.details(value['id'])
        assert after['worker'] == before['worker']
        assert app.service.pool_client.record['owner'] == value['owner'], 'Pool was restarted instead of surviving'
        assert finish(app, value)['status'] == 'complete'
    finally:
        if handle: kernel.CloseHandle(handle)
        if host.poll() is None: host.kill()
        host.wait(timeout=10)
