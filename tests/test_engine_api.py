"""Shared service boundary exposes engine state and durable events."""
from pathlib import Path

from fastapi.testclient import TestClient

from biopipe.headless import create_headless_app
from src.web.service import Settings

ROOT = Path(__file__).resolve().parents[1]


def auth(client, app):
    response = client.post('/api/agent/connect',
                           headers={'X-BioPipe-Bridge': app.state.bridge.secret},
                           json={'name': 'engine-status', 'scopes': ['context']})
    assert response.status_code == 200, response.text
    return {'Authorization': 'Bearer ' + response.json()['token']}


def test_headless_service_exposes_coordinator_mode(tmp_path, monkeypatch):
    monkeypatch.setenv('BIOPIPE_ADMISSION_DIR', str(tmp_path / 'admission'))
    monkeypatch.setenv('BIOPIPE_ENGINE_DIR', str(tmp_path / 'engine'))
    app = create_headless_app(Settings(tmp_path, tmp_path / '.studio', tmp_path / 'none',
                                       testing=True, code_root=ROOT,
                                       engine_mode='coordinator'))
    with TestClient(app, base_url='http://127.0.0.1') as client:
        headers = auth(client, app)
        status = client.get('/api/v1/engine', headers=headers)
        assert status.status_code == 200, status.text
        body = status.json()
        assert body['mode'] == 'coordinator'
        assert body['available'] is True
        assert body['journal']['schema_version'] == 1
        assert app.state.service.coordinator is not None
        assert app.state.service.scheduler is None


def test_headless_service_exposes_engine_status_and_events(tmp_path, monkeypatch):
    monkeypatch.setenv('BIOPIPE_ADMISSION_DIR', str(tmp_path / 'admission'))
    monkeypatch.setenv('BIOPIPE_ENGINE_DIR', str(tmp_path / 'engine'))
    app = create_headless_app(Settings(tmp_path, tmp_path / '.studio', tmp_path / 'none',
                                       testing=True, code_root=ROOT))
    with TestClient(app, base_url='http://127.0.0.1') as client:
        assert client.get('/api/v1/engine').status_code == 403
        headers = auth(client, app)
        status = client.get('/api/v1/engine', headers=headers)
        assert status.status_code == 200, status.text
        body = status.json()
        assert body['available'] is True
        assert body['mode'] == 'legacy'
        assert body['journal']['schema_version'] == 1
        page = client.get('/api/v1/engine/events?after=0&limit=10', headers=headers)
        assert page.status_code == 200, page.text
        assert page.json()['available'] is True
        assert 'cursor' in page.json() and 'events' in page.json()
