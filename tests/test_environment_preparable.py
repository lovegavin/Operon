"""The UI, /api/v1 and remote prepare-all share one preparation verdict."""
from pathlib import Path

from fastapi.testclient import TestClient

from operon import environment_install
from src.web.api import create_app
from src.web.service import Settings

ROOT = Path(__file__).resolve().parents[1]


def test_needs_preparation_covers_every_unfinished_status():
    for status in ('missing', 'failed', 'stale', 'incomplete'):
        assert environment_install.needs_preparation(status), status
    for status in ('ready', 'queued', 'installing', ''):
        assert not environment_install.needs_preparation(status), status


def test_v1_prepare_all_uses_the_shared_verdict(tmp_path, monkeypatch):
    app = create_app(Settings(tmp_path, tmp_path / 'studio', ROOT / 'frontend/dist',
                               testing=True, code_root=ROOT, desktop=True))
    plan = {name: {'status': status} for name, status in {
        'a-missing': 'missing', 'b-failed': 'failed', 'c-stale': 'stale',
        'd-incomplete': 'incomplete', 'e-ready': 'ready'}.items()}
    monkeypatch.setattr(environment_install, 'plan', lambda *args, **kwargs: plan)
    monkeypatch.setattr(environment_install, 'prepare', lambda *args, **kwargs: {})
    monkeypatch.setattr(environment_install.estimates, 'expected',
                        lambda *args, **kwargs: 0)
    with TestClient(app) as client:
        client.headers['X-Studio-Token'] = client.get('/api/bootstrap').json()['token']
        response = client.post('/api/v1/environments/prepare', json={})
    assert response.status_code == 200, response.text
    names = [item['name'] for item in response.json()['prepared']]
    assert names == ['a-missing', 'b-failed', 'c-stale', 'd-incomplete']
