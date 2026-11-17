"""Unknown job identifiers are reported as a 404 on every job lookup endpoint."""
from pathlib import Path

from fastapi.testclient import TestClient

from operon.headless import create_headless_app
from src.web.service import Settings

ROOT = Path(__file__).resolve().parents[1]


def test_unknown_job_is_a_404_on_lookup_endpoints(tmp_path, monkeypatch):
    monkeypatch.setenv('PYTHONUTF8', '1')
    monkeypatch.setenv('OPERON_REGISTRY_MAINTENANCE', '1')
    settings = Settings(tmp_path, tmp_path / '.studio', tmp_path / 'nonexistent-ui', testing=True, code_root=ROOT)
    app = create_headless_app(settings)
    with TestClient(app, base_url='http://127.0.0.1') as client:
        reply = client.post('/api/agent/connect', headers={'X-Operon-Bridge': app.state.bridge.secret},
                            json={'name': 'unknown-job-test', 'scopes': ['context', 'run']})
        assert reply.status_code == 200, reply.text
        headers = {'Authorization': 'Bearer ' + reply.json()['token']}
        for path in ('/api/v1/jobs/missing-job', '/api/v1/jobs/missing-job/logs'):
            reply = client.get(path, headers=headers)
            assert reply.status_code == 404, (path, reply.text)
            assert reply.json()['code'] == 'unknown_job', (path, reply.text)
        reply = client.get('/api/v1/jobs/missing-job/results', headers=headers)
        assert reply.status_code == 404, reply.text
        reply = client.post('/api/v1/jobs/missing-job/cancel', headers=headers)
        assert reply.status_code == 404, reply.text