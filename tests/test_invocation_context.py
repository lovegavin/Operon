"""K02 invocation/Context parity and cancellation boundary."""
from __future__ import annotations

import json
from pathlib import Path
import struct
import time
import threading

import numpy as np
import pytest

from operon.application import Application
from operon.contracts import FrozenParameters, WorkflowSpec
from operon.execution import InvocationRunner
from operon.planning import WorkflowCompiler
from operon.planning.legacy import LegacyPlanAdapter
from src.web.operator_catalog import catalog_from_descriptors
from src.web.service import Settings

ROOT = Path(__file__).resolve().parents[1]


def graph(root: Path) -> dict:
    np.save(root / 'input.npy', np.arange(40, dtype=np.float32).reshape(10, 4))
    return {
        'schema_version': 2, 'name': 'k02 parity', 'base_dir': str(root),
        'memory': {'enabled': True, 'auto_spill': True, 'budget_mb': 32,
                   'process_limit_mb': 512},
        'nodes': [
            {'id': 'input', 'kind': 'source', 'position': {'x': 0, 'y': 0},
             'source': {'path': 'input.npy', 'dims': ['sample', 'feature'],
                        'labels': {'sample': 'auto', 'feature': 'builtin'},
                        'reader': 'NpyReader'}},
            {'id': 'pca', 'kind': 'operator', 'operator': 'pca',
             'position': {'x': 1, 'y': 0},
             'params': {'dim': 'feature', 'n_components': 2, 'output': 'pcs'}},
            {'id': 'plot', 'kind': 'operator', 'operator': 'scatter',
             'position': {'x': 2, 'y': -1},
             'params': {'dim': 'component', 'x_label': 'PC1', 'y_label': 'PC2',
                        'filename': 'pca.png'}},
            {'id': 'summary', 'kind': 'operator', 'operator': 'describe',
             'position': {'x': 2, 'y': 1}, 'params': {}},
        ],
        'edges': [
            {'id': 'e1', 'source': 'input', 'target': 'pca',
             'targetHandle': 'in-0', 'sourceHandle': 'out'},
            {'id': 'e2', 'source': 'pca', 'target': 'plot',
             'targetHandle': 'in-0', 'sourceHandle': 'out'},
            {'id': 'e3', 'source': 'pca', 'target': 'summary',
             'targetHandle': 'in-0', 'sourceHandle': 'out'},
        ],
    }


@pytest.fixture()
def app(tmp_path):
    value = Application(Settings(tmp_path, tmp_path / '.studio', tmp_path / 'ui',
                                  testing=True, code_root=ROOT),
                        catalog_from_descriptors())
    try:
        yield value
    finally:
        value.shutdown()


def wait_job(app, key, timeout=120):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        value = app.jobs.details(key)
        if value.get('logs_complete') or value.get('status') in ('complete', 'failed', 'cancelled'):
            return value
        time.sleep(.05)
    raise TimeoutError(key)


def step_value(output: Path, summary: dict, index: int) -> dict:
    return json.loads((output / summary['steps'][index]['export_path']).read_text(encoding='utf-8'))


def png_size(path: str) -> tuple[int, int]:
    data = Path(path).read_bytes()[:24]
    assert data[:8] == b'\x89PNG\r\n\x1a\n' and data[12:16] == b'IHDR'
    return struct.unpack('>II', data[16:24])


def test_branched_native_route_parity(app, tmp_path):
    value = graph(tmp_path)
    job = app.jobs.launch(value)
    app_result = wait_job(app, job['id'])
    assert app_result['status'] == 'complete', app_result
    app_output = Path(app_result['output_dir'])

    plan = app.compile_plan(value)
    receipt = app.run_plan(plan, root=tmp_path / 'backend', run_id='parity', timeout=300)
    assert receipt.status == 'succeeded', receipt
    assert receipt.tree_exited and receipt.resources_released
    repeated = app.run_plan(plan, root=tmp_path / 'backend', run_id='parity', timeout=300)
    assert repeated.job_id == receipt.job_id
    assert repeated.status == 'succeeded'
    new_output = Path(receipt.output_dir)

    app_summary = json.loads((app_output / 'run_summary.json').read_text(encoding='utf-8'))
    new_summary = json.loads((new_output / 'run_summary.json').read_text(encoding='utf-8'))
    assert [step['name'] for step in app_summary['steps']] == [
        step['name'] for step in new_summary['steps']] == ['pca', 'scatter', 'describe']
    app_pca = step_value(app_output, app_summary, 0)
    new_pca = step_value(new_output, new_summary, 0)
    assert np.allclose(app_pca['explained_variance_ratio'],
                       new_pca['explained_variance_ratio'], rtol=1e-6, atol=1e-8)
    app_meta = step_value(app_output, app_summary, 2)
    new_meta = step_value(new_output, new_summary, 2)
    assert app_meta['shape'] == new_meta['shape'] == [10, 2]
    assert app_meta['dims'] == new_meta['dims'] == ['sample', 'component']
    assert app_meta['labels'] == new_meta['labels']
    assert app_meta['info'] == new_meta['info']
    app_fig = app_summary['steps'][1]['figures'][0]
    new_fig = new_summary['steps'][1]['figures'][0]
    assert (app_fig['width_mm'], app_fig['height_mm'], app_fig['dpi']) == (
        new_fig['width_mm'], new_fig['height_mm'], new_fig['dpi'])
    assert png_size(app_fig['path']) == png_size(new_fig['path'])
    assert app_summary.get('managed_peak_bytes', 0) > 0
    assert new_summary.get('managed_peak_bytes', 0) > 0
    assert Path(new_summary['event_log']).is_file()
    assert (Path(receipt.output_dir) / 'run_summary.txt').is_file()
    # Inputs stay external path references; crossing the invocation boundary did
    # not copy the scientific data into the attempt directory.
    directory = app.service.jobs_dir / receipt.job_id
    task_text = (directory / 'task.yaml').read_text(encoding='utf-8')
    import yaml
    input_path = yaml.safe_load(task_text)['sources']['input']['path']
    assert (directory / input_path).resolve() == tmp_path / 'input.npy'
    assert not (directory / 'input.npy').exists()
    assert (directory / 'plugins.lock.json').is_file()
    assert (directory / 'invocation.json').is_file()


def test_worker_refuses_an_unaccepted_exit(tmp_path, app):
    """A zero exit without a complete output manifest is still a failed attempt."""
    value = graph(tmp_path)
    plan = WorkflowCompiler(LegacyPlanAdapter()).compile(
        WorkflowSpec.from_graph(value), FrozenParameters(), app.service.catalog, root=tmp_path)
    runner = InvocationRunner(tmp_path / 'backend-fail')
    unit, prepared = runner.prepare(plan, run_id='fail')
    # Simulate a worker that exits cleanly but produces no summary.  The
    # adapter must validate the declared output, not trust the exit code.
    from operon.execution.adapters.native import NativeInvocationAdapter
    from operon.execution.invocation import ExitReceipt
    output = NativeInvocationAdapter().collect(prepared, ExitReceipt(exit_code=0, state='succeeded'))
    assert output.status == 'failed'
    assert output.run_summary is None


def test_real_script_cancellation_stops_owned_tree(app, tmp_path):
    from operon.script_operators import inspect_source
    script = inspect_source('sleep.py', '# output: out file.txt\n'
                                        'import time\ntime.sleep(8)\n'
                                        'open("out.txt", "w").write("done")\n')
    value = {'schema_version': 2, 'name': 'cancel', 'base_dir': str(tmp_path),
             'memory': {'enabled': True}, 'nodes': [
                 {'id': 'slow', 'kind': 'script', 'script': script,
                  'position': {'x': 0, 'y': 0}, 'params': {}}], 'edges': []}
    plan = app.compile_plan(value)
    runner = InvocationRunner(tmp_path / 'cancel-run', application=app)
    result = {}

    def work():
        try:
            result['receipt'] = runner.execute(plan, run_id='cancel', timeout=60)
        except BaseException as exc:  # noqa: BLE001
            result['error'] = exc

    thread = threading.Thread(target=work)
    thread.start()
    deadline = time.monotonic() + 30
    submission = tmp_path / 'cancel-run' / 'cancel.json'
    key = None
    while time.monotonic() < deadline:
        if 'error' in result:
            raise result['error']
        if submission.exists():
            key = json.loads(submission.read_text(encoding='utf-8'))['receipt']['job_id']
            if app.jobs.details(key)['status'] == 'running':
                break
        time.sleep(.05)
    assert key and app.jobs.details(key)['status'] == 'running', result
    time.sleep(.3)
    app.jobs.cancel(key)
    thread.join(30)
    assert not thread.is_alive(), 'cancellation did not settle'
    assert 'error' not in result, result.get('error')
    receipt = result['receipt']
    assert receipt.status == 'cancelled'
    assert receipt.tree_exited and receipt.resources_released
    assert Path(receipt.log_path).is_file()
    # Do not leave an owned worker behind after the supervisor confirms stop.
    import psutil
    leftovers = []
    for process in psutil.process_iter(['pid', 'cmdline']):
        try:
            command = ' '.join(process.info.get('cmdline') or ())
        except (psutil.Error, TypeError):
            continue
        if str(app.service.jobs_dir / key) in command:
            leftovers.append(process.pid)
    assert not leftovers, leftovers


def test_unbound_runner_never_launches(app, tmp_path, monkeypatch):
    from operon.contracts import ContractError
    import subprocess
    plan = app.compile_plan(graph(tmp_path))
    def forbidden(*args, **kwargs):
        pytest.fail('RunPlan bypassed task admission')
    monkeypatch.setattr(subprocess, 'Popen', forbidden)
    with pytest.raises(ContractError, match='authoritative'):
        InvocationRunner(tmp_path / 'unbound').execute(plan)


def test_unavailable_task_authority_has_no_launch_fallback(app, tmp_path, monkeypatch):
    plan = app.compile_plan(graph(tmp_path))
    def unavailable(*args, **kwargs):
        raise RuntimeError('engine_unavailable')
    monkeypatch.setattr(app.jobs, 'submit', unavailable)
    with pytest.raises(RuntimeError, match='engine_unavailable'):
        app.run_plan(plan, root=tmp_path / 'unavailable')
    assert not list(app.service.jobs_dir.glob('*/job.json'))


def test_rehashed_executable_payload_cannot_override_live_compile(app, tmp_path, monkeypatch):
    from operon.contracts import RunPlan, ContractError
    plan = app.compile_plan(graph(tmp_path)).model_dump(mode='json')
    plan['units'][0]['payload']['task_manifest']['steps'][0]['params']['n_components'] = 1
    changed = RunPlan.model_validate(plan).with_identity()
    def forbidden(*args, **kwargs):
        pytest.fail('Inconsistent plan was submitted')
    monkeypatch.setattr(app.jobs, 'submit', forbidden)
    with pytest.raises(ContractError, match='recompile'):
        app.run_plan(changed)


def test_unconfirmed_stop_is_not_reported_as_cancelled(app, tmp_path, monkeypatch):
    plan = app.compile_plan(graph(tmp_path))
    job = {'id': 'unknown-stop', 'status': 'cancelled', 'logs_complete': True,
           'tree_exited': False, 'resources_released': False}
    monkeypatch.setattr(app.jobs, 'submit', lambda payload: job.copy())
    monkeypatch.setattr(app.jobs, 'details', lambda key: job.copy())
    receipt = app.run_plan(plan, run_id='unknown-stop')
    assert receipt.status == 'recovery_required'
    assert not receipt.tree_exited and not receipt.resources_released


def test_output_collection_verifies_worker_inventory(app, tmp_path):
    from operon.execution.adapters.native import NativeInvocationAdapter
    from operon.execution.context_bridge import write_output_manifest
    from operon.execution.invocation import ExitReceipt
    plan = app.compile_plan(graph(tmp_path))
    _, prepared = InvocationRunner(tmp_path / 'integrity').prepare(plan, run_id='check')
    (prepared.output_dir / 'run_summary.json').write_text('{"status":"complete"}', encoding='utf-8')
    figure = prepared.output_dir / 'figure.svg'
    figure.write_text('<svg/>', encoding='utf-8')
    manifest = prepared.context.attempt_root / prepared.spec.output_manifest
    write_output_manifest(prepared.output_dir, manifest, status='complete')
    original = manifest.read_bytes()
    adapter = NativeInvocationAdapter()
    stopped = ExitReceipt(0, 'succeeded', False)
    assert adapter.collect(prepared, stopped).status == 'complete'
    figure.write_text('<svg>corrupted</svg>', encoding='utf-8')
    assert adapter.collect(prepared, stopped).status == 'failed'
    assert manifest.read_bytes() == original
    figure.unlink()
    assert adapter.collect(prepared, stopped).status == 'failed'
    assert manifest.read_bytes() == original


def test_real_pool_owns_plan_worker_and_releases_lease(tmp_path, monkeypatch):
    from operon.pool_service import PoolService, PoolControlServer
    workspace = tmp_path / 'workspace'
    workspace.mkdir()
    gate = tmp_path / 'gate.json'
    monkeypatch.setenv('OPERON_ENVIRONMENT_GATE', str(gate))
    pool = PoolService(root=tmp_path / 'pool', admission_dir=tmp_path / 'admission',
        workspaces=[{'root': workspace, 'principal': 'k02-test'}], code_root=ROOT,
        capacity_bytes=2 * 1024 ** 3, cpu_threads=4, environment_gate=gate)
    server = PoolControlServer(pool, token='k02-test-only', port=0).start()
    application = None
    try:
        application = Application(Settings(workspace, workspace / '.studio', workspace / 'ui',
            testing=True, code_root=ROOT, pool_address=f'127.0.0.1:{server.address[1]}',
            pool_token='k02-test-only', pool_principal='k02-test'))
        assert application.service.admission is None
        assert application.service.scheduler is None
        plan = application.compile_plan(graph(workspace))
        receipt = application.run_plan(plan, run_id='shared-parity', timeout=90)
        assert receipt.status == 'succeeded', receipt
        assert receipt.tree_exited and receipt.resources_released
        attempt = pool.engine.store.attempt(receipt.attempt_id)
        assert attempt['fence'] == receipt.fence > 0
        assert pool.engine.store.lease(receipt.attempt_id)['state'] == 'released'
        directory = pool.resolve(workspace).jobs_dir / receipt.job_id
        envelope = json.loads((directory / 'invocation.json').read_text(encoding='utf-8'))
        assert envelope['fence'] == receipt.fence
        assert envelope['attempt_id'] == receipt.attempt_id
        assert len(pool.engine.store.attempts(receipt.job_id)) == 1
        repeat = application.run_plan(plan, run_id='shared-parity', timeout=90)
        assert repeat.job_id == receipt.job_id
        assert len(pool.engine.store.attempts(receipt.job_id)) == 1
    finally:
        if application:
            application.shutdown()
        server.close()
        pool.shutdown()
