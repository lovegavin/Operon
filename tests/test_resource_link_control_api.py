"""Versioned control API mapping for large-resource links."""
from pathlib import Path

from fastapi.testclient import TestClient

from operon.headless import create_headless_app
from src.web.service import Settings

ROOT = Path(__file__).resolve().parents[1]


def connect(client, app, scopes):
    response = client.post('/api/agent/connect',
                           headers={'X-Operon-Bridge': app.state.bridge.secret},
                           json={'name': 'resource-link-test', 'scopes': scopes})
    assert response.status_code == 200, response.text
    return {'Authorization': 'Bearer ' + response.json()['token']}


def test_link_requires_plugins_scope(tmp_path):
    app = create_headless_app(Settings(tmp_path, tmp_path / 'profile', tmp_path / 'no-ui',
                                       testing=True, code_root=ROOT))
    with TestClient(app, base_url='http://127.0.0.1') as client:
        read = connect(client, app, ['context'])
        response = client.post('/api/v1/large-resources/esmfold/link', headers=read,
                               json={'source': '/data/weights/esmfold'})
        assert response.status_code == 403
        assert client.delete('/api/v1/large-resources/esmfold/link',
                             headers=read).status_code == 403


def test_link_error_codes_are_stable(tmp_path, monkeypatch):
    """KeyError/ValueError/LinkUnsupported map to 422/409/501 without a real library."""
    from src.web import resource_api

    app = create_headless_app(Settings(tmp_path, tmp_path / 'profile', tmp_path / 'no-ui',
                                       testing=True, code_root=ROOT))

    def missing(service, name, source, replace=False, unit=None):
        raise KeyError(name)

    def rejected(service, name, source, replace=False, unit=None):
        raise ValueError('source is outside the allowed link roots')

    def unsupported(service, name, source, replace=False, unit=None):
        raise resource_api.LinkUnsupported('The installed library does not support linking.')

    with TestClient(app, base_url='http://127.0.0.1') as client:
        plugins = connect(client, app, ['context', 'plugins'])

        monkeypatch.setattr(resource_api, 'link', missing)
        monkeypatch.setattr(resource_api, 'unlink',
                            lambda service, name, unit=None: (_ for _ in ()).throw(KeyError(name)))
        posted = client.post('/api/v1/large-resources/nope/link', headers=plugins,
                             json={'source': '/data/weights/x'})
        assert posted.status_code == 422
        assert posted.json()['code'] == 'unknown_resource'
        deleted = client.delete('/api/v1/large-resources/nope/link', headers=plugins)
        assert deleted.status_code == 422
        assert deleted.json()['code'] == 'unknown_resource'

        monkeypatch.setattr(resource_api, 'link', rejected)
        rejected_response = client.post('/api/v1/large-resources/esmfold/link', headers=plugins,
                                        json={'source': '/etc/passwd'})
        assert rejected_response.status_code == 409
        assert rejected_response.json()['code'] == 'link_rejected'
        assert 'allowed link roots' in rejected_response.json()['message']

        monkeypatch.setattr(resource_api, 'link', unsupported)
        unsupported_response = client.post('/api/v1/large-resources/esmfold/link', headers=plugins,
                                           json={'source': '/data/weights/x'})
        assert unsupported_response.status_code == 501
        assert unsupported_response.json()['code'] == 'link_unsupported'
