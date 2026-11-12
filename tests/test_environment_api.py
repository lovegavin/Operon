"""Environment status endpoint and unknown-name handling."""
from pathlib import Path

from fastapi.testclient import TestClient

from src.web.api import create_app
from src.web.service import Settings

ROOT = Path(__file__).resolve().parents[1]


def studio(tmp_path):
    return create_app(Settings(tmp_path, tmp_path / 'studio', ROOT / 'frontend/dist',
                               testing=True, code_root=ROOT, desktop=True))


def test_environments_endpoint_reports_declared_environments(tmp_path):
    with TestClient(studio(tmp_path)) as client:
        client.headers['X-Studio-Token'] = client.get('/api/bootstrap').json()['token']
        response = client.get('/api/environments')
        assert response.status_code == 200
        body = response.json()
        assert body['root']
        assert {'antifold', 'esm3', 'boltz', 'openmm81'} <= set(body['environments'])
        item = body['environments']['openmm81']
        assert item['python'] == '3.11'
        assert item['status'] in {'missing', 'stale', 'ready', 'failed'}
        assert 'used_by' in item


def test_environment_retry_rejects_unknown_name(tmp_path):
    with TestClient(studio(tmp_path)) as client:
        client.headers['X-Studio-Token'] = client.get('/api/bootstrap').json()['token']
        response = client.post('/api/environments/nope/retry')
        assert response.status_code == 404


def test_pool_status_endpoint_reports_local_state(tmp_path):
    with TestClient(studio(tmp_path)) as client:
        client.headers['X-Studio-Token'] = client.get('/api/bootstrap').json()['token']
        response = client.get('/api/pool')
        assert response.status_code == 200
        body = response.json()
        assert {'location', 'instance', 'workspaces', 'active', 'remotes'} <= set(body)
        assert isinstance(body['active'], list)
        assert 'closing' in body['instance']
