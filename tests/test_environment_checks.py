"""Draft dependency checks and strict preflight share receipts, not data requirements."""
from copy import deepcopy
from pathlib import Path

from fastapi.testclient import TestClient
import pytest

from src.web.api import create_app
from src.web.service import Settings

ROOT = Path(__file__).resolve().parents[1]


def test_desktop_dependency_check_and_explicit_repair_before_data(tmp_path, monkeypatch):
    app = create_app(Settings(tmp_path, tmp_path / '.studio', tmp_path / 'ui', testing=True, code_root=ROOT))
    with TestClient(app, base_url='http://127.0.0.1') as client:
        boot = client.get('/api/bootstrap').json()
        headers = {'X-Studio-Token': boot['token']}
        client.headers.update(headers)
        graph = deepcopy(boot['demo'])
        graph['runtime'] = {'execution': {'mode': 'manual', 'kind': 'local'}}
        source = next(node for node in graph['nodes'] if node['kind'] == 'source')
        original = source['source']['path']
        source['source'].update(path='', reader='CsvReader')
        deps = app.state.service.dependencies
        calls, ready = [], [False]
        def probe(*, ids, repair, repair_r):
            calls.append((set(ids), repair))
            deps.sync(app.state.service.plugins.state())
            ready[0] |= repair
            for key in ids:
                deps.entries[key].update(status='passed' if ready[0] else 'failed',
                                         error='' if ready[0] else 'Synthetic missing dependency')
            return deps.snapshot()
        monkeypatch.setattr(deps, 'check', probe)
        with monkeypatch.context() as isolation:
            isolation.setattr(app.state.service, 'resources', lambda: pytest.fail('Dependency check started resource admission'))
            checked = client.post('/api/check-environment', json=graph)
        assert checked.status_code == 200, checked.text
        assert checked.json()['scope'] == 'dependencies'
        assert checked.json()['readiness']['status'] == 'blocked'
        assert 'CsvReader' in calls[0][0] and not calls[0][1]
        assert client.post('/api/validate', json=graph).status_code == 422
        fixed = client.post('/api/prepare-environment', json=graph)
        assert fixed.status_code == 200, fixed.text
        assert fixed.json()['readiness']['status'] == 'ready'
        assert calls[-1][1]
        assert client.post('/api/validate', json=graph).status_code == 422
        source['source']['path'] = original
        before = len(calls)
        full = client.post('/api/validate', json=graph)
        assert full.status_code == 200, full.text
        assert full.json()['readiness']['dependencies_cached']
        assert len(calls) == before
        # A receipt cannot bypass a missing file, invalid topology or parameters.
        source['source']['path'] = 'not-created.csv'
        missing = client.post('/api/validate', json=graph)
        assert missing.status_code == 422, missing.text
        assert 'file unavailable' in missing.text
        draft = deepcopy(graph)
        draft['edges'] = []
        assert client.post('/api/check-environment', json=draft).status_code == 200
        assert client.post('/api/validate', json=draft).status_code == 422
        invalid = deepcopy(graph)
        next(node for node in invalid['nodes'] if node['kind'] == 'source')['source']['path'] = original
        next(node for node in invalid['nodes'] if node.get('operator') == 'pca')['params']['n_components'] = 'invalid'
        assert client.post('/api/check-environment', json=invalid).status_code == 200
        assert client.post('/api/validate', json=invalid).status_code == 422
        assert client.get('/api/jobs').json() == []


def test_versioned_dependency_endpoint_accepts_draft_without_prepare_or_run(tmp_path):
    app = create_app(Settings(tmp_path, tmp_path / '.studio', tmp_path / 'ui', testing=True, code_root=ROOT))
    with TestClient(app, base_url='http://127.0.0.1') as client:
        token = client.get('/api/bootstrap').json()['token']
        graph = {'nodes': [{'id': 's', 'kind': 'source', 'position': {'x': 0, 'y': 0}, 'source': {'path': ''}}], 'edges': []}
        result = client.post('/api/v1/workflows/check-environment', headers={'X-Studio-Token': token}, json={'graph': graph})
        assert result.status_code == 200, result.text
        assert result.json()['readiness']['unresolved_sources'] == ['s']
        assert result.json()['scope'] == 'dependencies'
        assert 'valid' not in result.json()
