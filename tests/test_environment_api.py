"""Environment status endpoint and unknown-name handling."""
import json
from pathlib import Path

from fastapi.testclient import TestClient

from src.web.api import create_app
from src.web.service import Settings

ROOT = Path(__file__).resolve().parents[1]
ENVIRONMENT_MANIFEST = ROOT / 'library/seed/operon/environments.json'


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
        expected = json.loads(ENVIRONMENT_MANIFEST.read_text(encoding='utf-8'))
        assert item['python'] == expected['environments']['openmm81']['python']
        assert item['status'] in {'missing', 'stale', 'ready', 'failed'}
        assert 'used_by' in item


def test_environment_retry_rejects_unknown_name(tmp_path):
    with TestClient(studio(tmp_path)) as client:
        client.headers['X-Studio-Token'] = client.get('/api/bootstrap').json()['token']
        response = client.post('/api/environments/nope/retry')
        assert response.status_code == 404


def test_unknown_job_id_reports_unknown_job(tmp_path):
    with TestClient(studio(tmp_path)) as client:
        client.headers['X-Studio-Token'] = client.get('/api/bootstrap').json()['token']
        response = client.get('/api/jobs/not-a-real-job')
        assert response.status_code == 404
        assert response.json()['detail']['code'] == 'unknown_job'


def test_pool_status_endpoint_reports_local_state(tmp_path):
    with TestClient(studio(tmp_path)) as client:
        client.headers['X-Studio-Token'] = client.get('/api/bootstrap').json()['token']
        response = client.get('/api/pool')
        assert response.status_code == 200
        body = response.json()
        assert {'location', 'instance', 'workspaces', 'active', 'remotes'} <= set(body)
        assert isinstance(body['active'], list)
        assert 'closing' in body['instance']


def test_environment_resources_list_matches_its_counts(tmp_path, monkeypatch):
    rows = [
        {'id': f'unit{i}', 'components': [{'state': 'downloaded'}], 'environments': ['core']}
        for i in range(5)
    ]
    monkeypatch.setattr('src.web.resource_api.snapshot', lambda service: {'resources': rows})
    with TestClient(studio(tmp_path)) as client:
        client.headers['X-Studio-Token'] = client.get('/api/bootstrap').json()['token']
        response = client.get('/api/environments')
        assert response.status_code == 200
        item = response.json()['environments']['core']
        assert item['resources_total'] == 5
        assert len(item['resources']) == item['resources_total']
        assert set(item['resources']) == {f'unit{i}' for i in range(5)}
        assert item['resources_ready'] == 5
        assert item['shared_resources_total'] <= item['resources_total']
        assert item['shared_resources_total'] == 5
        assert item['shared'] is True
        assert item['shared'] == (item['shared_resources_total'] > 0)


def test_cancel_reports_not_cancelled_and_completed_for_an_idle_environment(tmp_path):
    with TestClient(studio(tmp_path)) as client:
        client.headers['X-Studio-Token'] = client.get('/api/bootstrap').json()['token']
        response = client.post('/api/environments/openmm81/cancel')
        assert response.status_code == 200
        body = response.json()
        assert body['cancelled'] is False
        assert body['completed'] is True
        assert body['job'] is None
        assert body['reason']


def test_cancel_reports_cancelled_for_a_running_job(tmp_path):
    app = studio(tmp_path)
    with TestClient(app) as client:
        client.headers['X-Studio-Token'] = client.get('/api/bootstrap').json()['token']
        app.state.environment_jobs['job-1'] = {
            'id': 'job-1', 'name': 'openmm81', 'status': 'running',
        }
        response = client.post('/api/environments/openmm81/cancel')
        assert response.status_code == 200
        body = response.json()
        assert body['cancelled'] is True
        assert body['completed'] is False
        assert body['job'] == 'job-1'


def test_shared_flag_matches_the_shared_unit_count(tmp_path, monkeypatch):
    monkeypatch.setattr('src.web.resource_api.snapshot',
                        lambda service: {'resources': []})
    with TestClient(studio(tmp_path)) as client:
        client.headers['X-Studio-Token'] = client.get('/api/bootstrap').json()['token']
        response = client.get('/api/environments')
        assert response.status_code == 200
        environments = response.json()['environments']
        item = environments['core']
        assert item['shared_resources_total'] == 0
        assert item['shared'] is False
        assert item['managed'] is True
        for name, entry in environments.items():
            assert entry['shared'] == (entry['shared_resources_total'] > 0), name
