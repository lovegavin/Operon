"""Runtime panel contract: enriched environment facts, operations, cancellation."""
import copy
import time
from pathlib import Path

from fastapi.testclient import TestClient

from src.web.api import create_app
from src.web.service import Settings

ROOT = Path(__file__).resolve().parents[1]


def studio(tmp_path):
    return create_app(Settings(tmp_path, tmp_path / 'studio', ROOT / 'frontend/dist',
                               testing=True, code_root=ROOT, desktop=True))


def client(tmp_path):
    app = studio(tmp_path)
    http = TestClient(app)
    http.headers['X-Studio-Token'] = http.get('/api/bootstrap').json()['token']
    return app, http


def test_environments_carry_panel_facts(tmp_path):
    _, http = client(tmp_path)
    body = http.get('/api/environments').json()
    assert isinstance(body['operations'], list)
    item = body['environments']['openmm81']
    assert item['status'] in {'missing', 'stale', 'ready', 'failed', 'installing'}
    assert item['title']
    assert isinstance(item['notes'], str) and item['notes']
    assert isinstance(item['size_bytes'], int) and item['size_bytes'] >= 0
    assert isinstance(item['python_version'], str)
    assert isinstance(item['updated_at'], str)
    assert isinstance(item['used_by'], list)
    assert item['used_by_count'] == len(item['used_by'])


def test_used_by_is_capped_but_counted(tmp_path):
    app, http = client(tmp_path)
    application = app.state.application
    names = [f'operator_{index}' for index in range(12)]
    original = application.isolated_environments

    def isolated():
        data = copy.deepcopy(original())
        data['environments']['capdemo'] = {
            'name': 'capdemo', 'python': '3.11', 'status': 'missing', 'error': '',
            'used_by': names, 'progress': None,
        }
        return data

    application.isolated_environments = isolated
    item = http.get('/api/environments').json()['environments']['capdemo']
    assert item['used_by_count'] == 12
    assert item['used_by'] == names[:8]


def test_cancel_without_a_running_job_is_rejected(tmp_path):
    _, http = client(tmp_path)
    response = http.post('/api/environments/openmm81/cancel')
    assert response.status_code == 404
    assert '没有正在进行的准备任务' in response.json()['detail']


def test_cancel_marks_a_running_operation(tmp_path):
    app, http = client(tmp_path)
    application = app.state.application
    original = application.isolated_environments
    job = {'id': 'job-1', 'name': 'openmm81', 'status': 'running', 'error': None,
           'started_at': '2026-01-01T00:00:00Z', 'finished_at': None, 'phase': 'installing'}
    application._environment_jobs = {'job-1': dict(job)}

    def isolated():
        data = copy.deepcopy(original())
        data['operations'] = [dict(job)]
        data['environments']['openmm81']['status'] = 'installing'
        return data

    application.isolated_environments = isolated
    response = http.post('/api/environments/openmm81/cancel')
    assert response.status_code == 200, response.text
    body = response.json()
    assert body['cancelled'] is True
    assert body['job'] == 'job-1'
    operation = next(value for value in body['operations'] if value['id'] == 'job-1')
    assert operation['status'] == 'cancelled'
    assert operation['cancelable'] is False


def test_prepare_runs_background_work_and_starts_a_job(tmp_path, monkeypatch):
    """POST /prepare must schedule the install without an event loop in the handler."""
    from operon import environment_install

    calls = []

    def fake_prepare(name, root=None, source=None, log=None, control=None):
        calls.append(name)
        if log:
            log(f'fake install {name}')
        return {'name': name, 'status': 'ready', 'error': ''}

    monkeypatch.setattr(environment_install, 'prepare', fake_prepare)
    _, http = client(tmp_path)
    response = http.post('/api/environments/prepare', json={'names': ['openmm81']})
    assert response.status_code == 200, response.text
    body = response.json()
    assert [item['name'] for item in body['prepared']] == ['openmm81']
    job_id = body['prepared'][0]['job']

    status = None
    for _ in range(100):
        operations = http.get('/api/environments').json()['operations']
        status = next((item['status'] for item in operations if item['id'] == job_id), None)
        if status == 'complete':
            break
        time.sleep(0.02)
    assert calls == ['openmm81']
    assert status == 'complete', status


def test_unknown_name_rejects_the_whole_prepare(tmp_path, monkeypatch):
    from operon import environment_install

    calls = []

    def fake_prepare(name, root=None, source=None, log=None, control=None):
        calls.append(name)

    monkeypatch.setattr(environment_install, 'prepare', fake_prepare)
    _, http = client(tmp_path)
    response = http.post('/api/environments/prepare', json={'names': ['openmm81', 'nope']})
    assert response.status_code == 404
    assert calls == []
    assert http.get('/api/environments').json()['operations'] == []


def test_cancel_stops_a_running_installation(tmp_path, monkeypatch):
    """cancel() must reach the installer, not just relabel the operation."""
    from operon import environment_install

    started = {}

    def slow_prepare(name, root=None, source=None, log=None, control=None):
        started['control'] = control
        for _ in range(500):
            if control is not None and control.stopped:
                raise environment_install.Cancelled('cancelled while testing')
            time.sleep(0.01)
        return {'name': name, 'status': 'ready', 'error': ''}

    monkeypatch.setattr(environment_install, 'prepare', slow_prepare)
    _, http = client(tmp_path)
    body = http.post('/api/environments/prepare', json={'names': ['openmm81']}).json()
    job_id = body['prepared'][0]['job']
    for _ in range(200):
        if started.get('control') is not None:
            break
        time.sleep(0.01)
    cancelled = http.post('/api/environments/openmm81/cancel')
    assert cancelled.status_code == 200, cancelled.text
    operation = None
    for _ in range(300):
        operations = http.get('/api/environments').json()['operations']
        operation = next((item for item in operations if item['id'] == job_id), None)
        if operation and operation['status'] != 'running':
            break
        time.sleep(0.01)
    assert operation is not None
    assert operation['status'] == 'cancelled', operation
    assert not operation['error']
    assert operation['finished_at']
    assert started['control'].stopped is True
