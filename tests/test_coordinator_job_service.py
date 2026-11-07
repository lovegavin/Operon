"""Product-level coordinator takeover of the real JobService worker path."""
import json
from pathlib import Path
import time

import pytest

from src.web.admission import HostAdmission, MIB
from src.web.models import Graph
from src.web.operator_catalog import catalog_from_descriptors
from src.web.service import JobService, Settings

ROOT = Path(__file__).resolve().parents[1]


def wait_until(check, timeout=30):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        value = check()
        if value:
            return value
        time.sleep(.05)
    pytest.fail('Timed out waiting for coordinator/worker')


@pytest.fixture
def service(tmp_path, monkeypatch):
    import src.web.service as module
    monkeypatch.setattr(module, 'HostAdmission',
                        lambda path: HostAdmission(path, available_bytes=2048 * MIB, cpu_threads=2))
    monkeypatch.setenv('BIOPIPE_ENVIRONMENT_GATE', str(tmp_path / 'gate.json'))
    code = tmp_path / 'code'
    (code / 'scripts').mkdir(parents=True)
    (code / 'scripts/run.py').write_text('''import json,os,sys,time
from pathlib import Path
task=Path(sys.argv[1]); output=task/'output'; output.mkdir()
(output/'started.json').write_text(json.dumps({'pid':os.getpid()}))
events=output/'runs'/'r'; events.mkdir(parents=True)
(events/'events.jsonl').write_text(json.dumps({'event':'step_started','index':1,'name':'synthetic'})+'\\n')
while not (task/'finish').exists():
    if (task/'cancel.requested').exists(): sys.exit(1)
    time.sleep(.03)
(output/'run_summary.json').write_text(json.dumps({'status':'complete'}))
''', encoding='utf-8')
    settings = Settings(tmp_path, tmp_path / 's', tmp_path / 'ui', testing=True,
                        code_root=code, engine_mode='coordinator')
    result = JobService(settings, catalog_from_descriptors())
    yield result
    result.shutdown()


def finish(service, job):
    (service.jobs_dir / job['id'] / 'finish').touch()
    wait_until(lambda: service.details(job['id'])['logs_complete'])
    return service.details(job['id'])


def test_launch_dispatches_through_coordinator_and_releases_after_exit(service):
    assert service.coordinator is not None and service.scheduler is None
    job = service.launch(Graph.model_validate(service.demo))
    wait_until(lambda: (service.jobs_dir / job['id'] / 'output/started.json').exists())
    assert service.details(job['id'])['scheduling'] == 'coordinator'
    attempts = service.engine.store.attempts(job['id'])
    assert len(attempts) == 1
    lease = service.engine.store.lease(attempts[0]['id'])
    assert lease['state'] != 'released'
    assert service.details(job['id'])['allocation']['state'] == 'coordinated'
    # The legacy admission ledger is not an independent allocator in this mode.
    assert service.admission.resources()['reservations'] == {}
    result = finish(service, job)
    assert result['status'] == 'complete'
    wait_until(lambda: service.engine.store.run(job['id'])['status'] == 'complete')
    run = service.engine.store.run(job['id'])
    assert run['status'] == 'complete'
    attempt = service.engine.store.attempt(attempts[0]['id'])
    assert attempt['state'] == 'succeeded'
    assert service.engine.store.lease(attempts[0]['id'])['state'] == 'released'
    assert service.environment_guard.status()['leases'] == []
    assert service.coordinator.status()['active_attempts'] == 0
    artifacts = service.engine.store.connection.execute(
        "SELECT id FROM artifacts WHERE attempt_id=? AND state='committed'",
        (attempts[0]['id'],)).fetchall()
    assert artifacts
    artifact = service.engine.store.artifact(artifacts[0]['id'])
    assert artifact['location'] == str(service.jobs_dir / job['id'] / 'output')
    assert artifact['manifest']['files']
    assert service.engine.store.references(artifact['id'])


def test_public_cancel_flows_through_coordinator_and_leaves_no_worker(service):
    job = service.launch(Graph.model_validate(service.demo))
    wait_until(lambda: (service.jobs_dir / job['id'] / 'output/started.json').exists())
    attempts = service.engine.store.attempts(job['id'])
    pid = service.details(job['id'])['worker']['pid']
    requested = service.cancel(job['id'])
    assert requested['id'] == job['id']
    wait_until(lambda: service.details(job['id'])['logs_complete'])
    result = service.details(job['id'])
    assert result['status'] == 'cancelled'
    wait_until(lambda: service.engine.store.run(job['id'])['status'] == 'cancelled')
    assert service.engine.store.attempt(attempts[0]['id'])['state'] == 'cancelled'
    assert service.engine.store.lease(attempts[0]['id'])['state'] == 'released'
    assert service.environment_guard.status()['leases'] == []
    import psutil
    assert not psutil.pid_exists(pid) or psutil.Process(pid).status() == psutil.STATUS_ZOMBIE


def test_coordinator_restart_adopts_a_live_jobservice_worker(service, tmp_path):
    job = service.launch(Graph.model_validate(service.demo))
    wait_until(lambda: (service.jobs_dir / job['id'] / 'output/started.json').exists())
    attempts = service.engine.store.attempts(job['id'])
    assert len(attempts) == 1
    # Simulate a coordinator crash without cancelling the scientific worker.
    service.coordinator.stop(cancel_attempts=False)
    service.coordinator = None
    # Same-process restart simulation: a real crashed process is reconciled by
    # the admission ledger; release the test owner's claim explicitly.
    service.admission.release_coordinator(service.owner)
    service._coordinator_claimed = False
    second = JobService(Settings(tmp_path, tmp_path / 's', tmp_path / 'ui', testing=True,
                                 code_root=service.settings.code_root, engine_mode='coordinator'),
                        catalog_from_descriptors())
    try:
        wait_until(lambda: second.coordinator is not None)
        wait_until(lambda: (second.engine.store.attempts(job['id'])[0]['state'] == 'running'))
        assert len(second.engine.store.attempts(job['id'])) == 1
        (second.jobs_dir / job['id'] / 'finish').touch()
        wait_until(lambda: second.details(job['id'])['logs_complete'])
        wait_until(lambda: second.engine.store.run(job['id'])['status'] == 'complete')
        assert len(second.engine.store.attempts(job['id'])) == 1
        assert second.engine.store.lease(attempts[0]['id'])['state'] == 'released'
    finally:
        second.shutdown()


def test_real_describe_workflow_runs_through_coordinator(tmp_path):
    table = tmp_path / 'input.csv'
    table.write_text('a,b,c\n1,2,4\n2,5,7\n3,8,1\n7,2,9\n4,6,3\n', encoding='utf-8')
    settings = Settings(tmp_path, tmp_path / 'studio', ROOT / 'frontend/dist', testing=True,
                        code_root=ROOT, engine_mode='coordinator')
    service = JobService(settings, catalog_from_descriptors())
    try:
        graph = Graph.model_validate({
            'schema_version': 2, 'name': 'coordinated describe', 'base_dir': str(tmp_path),
            'memory': {'enabled': True, 'auto_spill': True, 'budget_mb': 32,
                       'process_limit_mb': 512, 'chunk_mb': .01, 'io_buffer_kb': 4},
            'nodes': [
                {'id': 'input', 'kind': 'source', 'position': {'x': 0, 'y': 0},
                 'source': {'path': str(table), 'dims': ['sample', 'feature'],
                            'labels': {'sample': 'auto', 'feature': 'builtin'}}},
                {'id': 'summary', 'kind': 'operator', 'operator': 'describe', 'params': {},
                 'position': {'x': 1, 'y': 0}}],
            'edges': [{'id': 'e1', 'source': 'input', 'target': 'summary'}]})
        job = service.launch(graph)
        result = wait_until(lambda: (service.details(job['id']) if
                                     service.details(job['id'])['status'] in
                                     ('complete', 'failed', 'cancelled') else None))
        assert result['status'] == 'complete', result.get('error') or result.get('console')
        assert result['summary']['steps']
        wait_until(lambda: service.engine.store.run(job['id'])['status'] == 'complete')
        artifacts = service.engine.store.connection.execute(
            "SELECT id FROM artifacts WHERE attempt_id=(SELECT id FROM attempts WHERE unit_id "
            "IN (SELECT id FROM units WHERE run_id=?) LIMIT 1) AND state='committed'",
            (job['id'],)).fetchall()
        assert artifacts
        assert service.environment_guard.status()['leases'] == []
    finally:
        service.shutdown()


def test_coordinator_mode_refuses_a_dirty_legacy_queue(tmp_path, monkeypatch):
    import src.web.service as module
    monkeypatch.setattr(module, 'HostAdmission',
                        lambda path: HostAdmission(path, available_bytes=2048 * MIB, cpu_threads=2))
    settings = Settings(tmp_path, tmp_path / 's', tmp_path / 'ui', testing=True, code_root=ROOT)
    legacy = JobService(settings, catalog_from_descriptors())
    try:
        job = legacy.launch(Graph.model_validate(legacy.demo))
        with pytest.raises(RuntimeError, match='drained legacy queue'):
            JobService(Settings(tmp_path, tmp_path / 's', tmp_path / 'ui', testing=True,
                                code_root=ROOT, engine_mode='coordinator'),
                       catalog_from_descriptors())
    finally:
        legacy.shutdown()
