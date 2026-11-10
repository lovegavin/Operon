"""Environment isolation fallback: exclusive maintenance vs running workers."""
import json
import os
from pathlib import Path
import time

import pytest

from operon.engine.environment import EnvironmentBusy, EnvironmentGuard, EnvironmentGuardError
from operon.engine.facade import owner_identity
from operon.engine.supervisor import identity_for_pid
from src.web.models import Graph


def test_selected_interpreter_identity_is_independent_of_manager_prefix(tmp_path, monkeypatch):
    import subprocess
    import sys
    from operon.engine.environment import environment_identity
    original = environment_identity(sys.executable)
    monkeypatch.setattr(sys, 'prefix', str(tmp_path / 'another-manager'))
    assert environment_identity(sys.executable) == original
    subprocess.run([sys.executable, '-m', 'venv', '--without-pip', str(tmp_path / 'venv')], check=True)
    python = tmp_path / 'venv' / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
    assert environment_identity(python) != original
    with pytest.raises(EnvironmentGuardError):
        environment_identity(tmp_path / 'missing-python')


def test_running_attempt_blocks_repair_and_repair_blocks_new_attempt(tmp_path):
    guard = EnvironmentGuard(tmp_path / 'gate.json')
    service = owner_identity()
    guard.acquire_job('job-1', service=service, workspace=str(tmp_path))
    status = guard.status()
    assert 'job-1' in status['leases']
    with pytest.raises(EnvironmentBusy):
        guard.begin(owner=service, kind='repair')
    worker = identity_for_pid(__import__('os').getpid()).to_json()
    guard.bind_worker('job-1', worker)
    assert guard.status()['leases'] == ['job-1']
    guard.release_job('job-1')
    token = guard.begin(owner=service, kind='repair')
    with pytest.raises(EnvironmentBusy):
        guard.acquire_job('job-2', service=service)
    assert guard.end(token)
    guard.acquire_job('job-2', service=service)
    guard.release_job('job-2')


def test_live_worker_keeps_exclusion_after_launcher_death(tmp_path):
    guard = EnvironmentGuard(tmp_path / 'gate.json')
    dead = {'pid': 99999999, 'created': 0}
    worker = identity_for_pid(__import__('os').getpid()).to_json()
    guard.acquire_job('orphan', service=dead, worker=worker)
    with pytest.raises(EnvironmentBusy):
        guard.begin(owner=owner_identity())
    # A dead launcher and dead worker are pruned; only identity proves death.
    guard.acquire_job('dead', service=dead, worker=dead)
    guard.release_job('orphan')
    token = guard.begin(owner=owner_identity())
    assert token
    guard.end(token)
    assert guard.status()['leases'] == []


def test_corrupt_gate_fails_closed(tmp_path):
    path = tmp_path / 'gate.json'
    path.write_text('{not json', encoding='utf-8')
    guard = EnvironmentGuard(path)
    with pytest.raises(EnvironmentGuardError):
        guard.acquire_job('job', service=owner_identity())
    with pytest.raises(EnvironmentGuardError):
        guard.begin(owner=owner_identity())


def wait_until(check, timeout=20):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        value = check()
        if value:
            return value
        time.sleep(.05)
    pytest.fail('Timed out waiting for worker')


@pytest.fixture
def service(tmp_path, monkeypatch):
    from src.web.admission import HostAdmission, MIB
    from src.web.operator_catalog import catalog_from_descriptors
    import src.web.service as module
    from src.web.service import JobService, Settings

    monkeypatch.setattr(module, 'HostAdmission',
                        lambda path: HostAdmission(path, available_bytes=2048 * MIB, cpu_threads=2))
    gate = tmp_path / 'environment-gate.json'
    monkeypatch.setenv('OPERON_ENVIRONMENT_GATE', str(gate))
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
    settings = Settings(tmp_path, tmp_path / 's', tmp_path / 'ui', testing=True, code_root=code)
    result = JobService(settings, catalog_from_descriptors())
    yield result, gate
    result.shutdown()


def test_job_lifecycle_holds_and_releases_environment_lease(service):
    result, gate = service
    job = result.launch(Graph.model_validate(result.demo))
    started = result.jobs_dir / job['id'] / 'output/started.json'
    wait_until(started.exists)
    status = result.environment_guard.status()
    assert job['id'] in status['leases']
    with pytest.raises(EnvironmentBusy):
        result.environment_guard.begin(owner=result.owner)
    (result.jobs_dir / job['id'] / 'finish').touch()
    wait_until(lambda: result.details(job['id'])['logs_complete'])
    assert result.environment_guard.status()['leases'] == []


def test_readiness_repair_is_blocked_while_a_job_holds_the_gate(service):
    result, gate = service
    from types import SimpleNamespace
    from operon.documents import CommandError
    from operon.readiness import ReadinessService
    token = result.environment_guard.begin(owner=result.owner, kind='test')
    try:
        with pytest.raises(CommandError) as error:
            ReadinessService(SimpleNamespace(service=result)).validate(
                Graph.model_validate(result.demo), {}, repair=True)
        assert error.value.code == 'environment_busy'
    finally:
        result.environment_guard.end(token)


def test_new_work_is_rejected_while_repair_holds_the_gate(service):
    result, gate = service
    token = result.environment_guard.begin(owner=result.owner, kind='test-repair')
    try:
        job = result.launch(Graph.model_validate(result.demo))
        assert job['status'] == 'failed'
        assert 'environment' in (job.get('error') or '').lower()
        assert job['id'] not in result.processes
    finally:
        assert result.environment_guard.end(token)
    job = result.launch(Graph.model_validate(result.demo))
    assert job['status'] == 'running'
    (result.jobs_dir / job['id'] / 'finish').touch()
    wait_until(lambda: result.details(job['id'])['logs_complete'])

def test_different_environment_identities_do_not_block_each_other(tmp_path):
    from operon.engine.environment import EnvironmentGuard, EnvironmentBusy
    guard = EnvironmentGuard(tmp_path / 'gate.json')
    first = guard.begin(owner={'pid': os.getpid(), 'created': __import__('psutil').Process().create_time()},
                        kind='repair', environment='env-a')
    second = guard.begin(owner={'pid': os.getpid(), 'created': __import__('psutil').Process().create_time()},
                         kind='repair', environment='env-b')
    assert guard.status()['active_attempts'] == 0
    with pytest.raises(EnvironmentBusy):
        guard.acquire_job('job-a', service={'pid': os.getpid(), 'created': __import__('psutil').Process().create_time()},
                          environment='env-a')
    assert guard.end(first) and guard.end(second)

def test_unconfirmed_worker_stop_keeps_lease_and_reports_recovery(service, monkeypatch):
    import psutil
    from src.web.service import write_json
    result, gate = service
    job = result.launch(Graph.model_validate(result.demo))
    started = result.jobs_dir / job['id'] / 'output/started.json'
    wait_until(started.exists)
    worker = result.require(job['id'])['worker']
    record = result.require(job['id'])
    record['owner'] = {'pid': 99999999, 'created': 0.0}
    write_json(result.jobs_dir / job['id'] / 'job.json', record)
    def denied(self):
        raise psutil.AccessDenied(pid=self.pid)
    monkeypatch.setattr(psutil.Process, 'suspend', denied)
    result._refresh_jobs()
    recovered = result.require(job['id'])
    assert recovered['status'] == 'recovery_required'
    assert recovered.get('tree_exited') is False
    assert job['id'] in result.environment_guard.status()['leases']
    assert recovered['allocation']['state'] != 'released'
    (result.jobs_dir / job['id'] / 'finish').touch()
    wait_until(lambda: result.details(job['id'])['logs_complete'])
