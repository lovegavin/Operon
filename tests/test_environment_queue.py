"""Prepare-all queues every environment and orders the queue by expected size."""
import threading
import time
from pathlib import Path

from fastapi.testclient import TestClient

from src.web.api import create_app
from src.web.service import Settings

ROOT = Path(__file__).resolve().parents[1]


def client(tmp_path):
    app = create_app(Settings(tmp_path, tmp_path / 'studio', ROOT / 'frontend/dist',
                               testing=True, code_root=ROOT, desktop=True))
    http = TestClient(app)
    http.headers['X-Studio-Token'] = http.get('/api/bootstrap').json()['token']
    return app, http


def wait_for(fetch, predicate, attempts=600, delay=0.02):
    value = None
    for _ in range(attempts):
        value = fetch()
        if predicate(value):
            return value
        time.sleep(delay)
    return value


def test_prepare_all_is_serial_and_sorted_by_expected_size(tmp_path, monkeypatch):
    from operon import environment_install

    release = threading.Event()
    started = []

    def blocking(name, root=None, source=None, log=None, control=None):
        started.append(name)
        while not release.is_set():
            if control is not None and control.stopped:
                raise environment_install.Cancelled('cancelled while testing')
            time.sleep(0.01)
        return {'name': name, 'status': 'ready', 'error': ''}

    monkeypatch.setattr(environment_install, 'prepare', blocking)
    _, http = client(tmp_path)
    body = http.post('/api/environments/prepare', json={}).json()
    prepared = body['prepared']
    names = [item['name'] for item in prepared]
    sizes = {name: environment_install.estimates.expected(name) for name in names}
    assert names[0] == 'openmm81'
    assert sizes[names[0]] == min(sizes.values())
    assert sizes == dict(sorted(sizes.items(), key=lambda kv: kv[1]))
    assert all(item['status'] in {'queued', 'running'} for item in prepared)

    wait_for(lambda: started, bool)
    assert started == [names[0]], started

    snapshot = http.get('/api/environments').json()['environments']
    assert snapshot[names[0]]['expected_bytes'] > 0
    queued = [name for name in names[1:] if snapshot[name]['status'] == 'queued']
    assert len(queued) == len(names) - 1
    assert sorted(snapshot[name]['queue_position'] for name in queued) == list(
        range(1, len(queued) + 1))

    release.set()
    wait_for(
        lambda: [name for name in names
                 if http.get('/api/environments').json()['environments'][name]['status']
                 not in {'installing', 'queued'}],
        lambda value: len(value) == len(names))


def test_cancelling_a_queued_entry_removes_it_from_the_queue(tmp_path, monkeypatch):
    from operon import environment_install

    release = threading.Event()

    def blocking(name, root=None, source=None, log=None, control=None):
        while not release.is_set():
            if control is not None and control.stopped:
                raise environment_install.Cancelled('cancelled while testing')
            time.sleep(0.01)
        return {'name': name, 'status': 'ready', 'error': ''}

    monkeypatch.setattr(environment_install, 'prepare', blocking)
    _, http = client(tmp_path)
    prepared = http.post('/api/environments/prepare', json={}).json()['prepared']
    waiting = prepared[-1]['name']
    response = http.post(f'/api/environments/{waiting}/cancel')
    assert response.status_code == 200, response.text
    snapshot = http.get('/api/environments').json()['environments']
    assert snapshot[waiting]['status'] != 'queued'
    release.set()
    wait_for(lambda: http.get('/api/environments').json()['environments'],
             lambda value: all(item['status'] not in {'installing', 'queued'}
                               for item in value.values()))
