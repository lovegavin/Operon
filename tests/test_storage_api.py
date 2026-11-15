"""Shared storage product adapters; no real SSH acceptance is implied."""
import asyncio
import json
from pathlib import Path
import threading

from fastapi.testclient import TestClient
import pytest

from operon.headless import create_headless_app
from operon.storage import BrowseLimits, StorageError
from operon.storage.configuration import PROFILE_OWNER, configured_mounts
from operon.storage.dispatch import StorageDispatch
from src.web.service import Settings


ROOT = Path(__file__).resolve().parents[1]


def make_app(tmp_path, *, mount=True):
    data = tmp_path / '.studio'
    data.mkdir()
    content = tmp_path / 'allowed'
    content.mkdir()
    (content / 'first.txt').write_bytes(b'first\n')
    (content / 'second.txt').write_bytes(b'second\n')
    (tmp_path / 'unconfigured.txt').write_text('not an implicit storage root')
    if mount:
        (data / 'storage-mounts.json').write_text(json.dumps({
            'format': 'operon.storage-mounts', 'schema_version': 1,
            'mounts': [{'kind': 'local', 'storage_id': 'allowed', 'root': str(content),
                        'principals': [PROFILE_OWNER]}]}), encoding='utf-8')
    return create_headless_app(Settings(tmp_path, data, tmp_path / 'no-ui', testing=True, code_root=ROOT))


def connect(client, app, name='Storage test', scopes=None):
    response = client.post('/api/agent/connect', headers={'X-Operon-Bridge': app.state.bridge.secret},
                           json={'name': name, 'scopes': ['context'] if scopes is None else scopes})
    assert response.status_code == 200
    return {'Authorization': 'Bearer ' + response.json()['token']}


def test_storage_endpoints_use_explicit_roots_strict_models_and_shared_lifecycle(tmp_path):
    app = make_app(tmp_path)
    with TestClient(app, base_url='http://127.0.0.1') as client:
        payload = {'storage_id': 'allowed', 'relative_path': 'first.txt'}
        assert client.post('/api/v1/storage/stat', json=payload).status_code == 403
        headers = connect(client, app)
        response = client.post('/api/v1/storage/stat', json=payload, headers=headers)
        assert response.status_code == 200, response.text
        assert response.json()['size_bytes'] == 6
        preview = client.post('/api/v1/storage/preview', json=payload, headers=headers)
        assert preview.status_code == 200 and preview.json()['text'] == 'first\n'
        forbidden = client.post('/api/v1/storage/stat', headers=headers,
                                json={'storage_id': 'workspace', 'relative_path': 'unconfigured.txt'})
        assert forbidden.status_code == 403 and forbidden.json()['code'] == 'storage_forbidden'
        assert forbidden.json()['request_id'] and 'next_actions' in forbidden.json()
        invalid = client.post('/api/v1/storage/browse', headers=headers,
                              json={'storage_id': 'allowed', 'page_size': True})
        assert invalid.status_code == 422
        assert client.post('/api/v1/storage/preview', headers=headers,
                           json={**payload, 'byte_limit': 1024 * 1024 + 1}).status_code == 422
        schema = client.get('/api/v1/openapi.json', headers=headers).json()
        assert '/api/v1/storage/browse' in schema['paths']
        assert schema['components']['schemas']['BrowseRequest']['additionalProperties'] is False
        assert client.get('/api/v1/storage/status', headers=headers).json()['limits']['cursor_idle_seconds'] == 30
    assert app.state.application.storage._closed


def test_missing_opt_in_configuration_exposes_no_storage(tmp_path):
    app = make_app(tmp_path, mount=False)
    with TestClient(app, base_url='http://127.0.0.1') as client:
        headers = connect(client, app)
        response = client.post('/api/v1/storage/browse', headers=headers, json={'storage_id': 'allowed'})
        assert response.status_code == 403
        assert response.json()['code'] == 'storage_forbidden'
        assert client.get('/api/v1/storage/roots', headers=headers).json() == {'roots': []}


def test_storage_roots_only_disclose_authorized_references_without_opening_backends(tmp_path):
    app = make_app(tmp_path)
    class Unopened:
        def open(self):
            pytest.fail('Root discovery opened a filesystem or SSH session')
    app.state.application.storage.mounts.register('visible', Unopened(), principals=[PROFILE_OWNER])
    app.state.application.storage.mounts.register('private', Unopened(), principals=['different-owner'])
    with TestClient(app, base_url='http://127.0.0.1') as client:
        assert client.get('/api/v1/storage/roots').status_code == 403
        response = client.get('/api/v1/storage/roots', headers=connect(client, app))
        assert response.status_code == 200, response.text
        roots = response.json()['roots']
        assert {item['storage_id'] for item in roots} == {'allowed', 'visible'}
        assert all(item['relative_path'] == '.' for item in roots)
        assert all(set(item) == {'storage_id', 'relative_path', 'version', 'digest'} for item in roots)
        assert str(tmp_path) not in response.text
        assert app.state.application.storage.status()['browse_handles'] == 0


def test_authenticated_account_grant_ignores_names_but_cursor_is_connection_scoped(tmp_path):
    app = make_app(tmp_path)
    with TestClient(app, base_url='http://127.0.0.1') as client:
        first = connect(client, app, name='same display name')
        second = connect(client, app, name='same display name')
        payload = {'storage_id': 'allowed', 'page_size': 1}
        page = client.post('/api/v1/storage/browse', headers=first, json=payload).json()
        assert page['next_cursor']
        other = client.post('/api/v1/storage/browse', headers=second,
                            json={**payload, 'cursor': page['next_cursor']})
        assert other.status_code == 409 and other.json()['code'] == 'browse_cursor_scope'
        assert other.json()['next_actions'] == [{'action': 'restart_browse', 'cursor': None}]
        # Either connection reads its owner's explicitly configured mount,
        # independent of presentation name, while cursors remain isolated.
        assert client.post('/api/v1/storage/stat', headers=second,
                           json={'storage_id': 'allowed', 'relative_path': 'first.txt'}).status_code == 200
        assert client.post('/api/agent/disconnect', headers=first).status_code == 200
        assert app.state.application.storage.status()['browse_handles'] == 0


def test_ui_session_close_only_closes_its_namespace_and_revoke_closes_connection(tmp_path):
    app = make_app(tmp_path)
    with TestClient(app, base_url='http://127.0.0.1') as client:
        headers = connect(client, app)
        for session in ('one', 'two'):
            response = client.post('/api/v1/storage/browse',
                                   headers={**headers, 'X-Operon-Storage-Session': session},
                                   json={'storage_id': 'allowed', 'page_size': 1})
            assert response.status_code == 200
        closed = client.post('/api/v1/storage/browse/close',
                             headers={**headers, 'X-Operon-Storage-Session': 'one'})
        assert closed.json() == {'closed': 1}
        assert app.state.application.storage.status()['browse_handles'] == 1
        records = client.get('/api/agent/connections', headers=headers).json()
        response = client.post('/api/agent/connections/revoke',
                               headers={'X-Studio-Token': app.state.bridge.studio_token},
                               json={'id': records[0]['id']})
        assert response.status_code == 200
        assert app.state.application.storage.status()['browse_handles'] == 0


def test_storage_configuration_rejects_ambiguous_and_secret_fields(tmp_path):
    path = tmp_path / 'mounts.json'
    path.write_text('{"mounts": [], "mounts": []}')
    with pytest.raises(ValueError, match='Duplicate'):
        configured_mounts(path)
    path.write_text(json.dumps({'mounts': [{'kind': 'sftp', 'storage_id': 'remote', 'root': '/data',
                                           'principals': [PROFILE_OWNER], 'ssh': {'host': 'storage.example',
                                           'username': 'synthetic', 'password': 'must-not-be-stored'}}]}))
    with pytest.raises(ValueError):
        configured_mounts(path)
    path.write_text(json.dumps({'mounts': [{'kind': 'local', 'storage_id': 'local', 'root': 'relative',
                                           'principals': [PROFILE_OWNER]}]}))
    with pytest.raises(StorageError) as error:
        configured_mounts(path)
    assert error.value.code == 'storage_configuration_invalid'


def test_storage_dispatch_bounds_before_submission_and_reserves_cancel_lane():
    async def scenario():
        dispatcher = StorageDispatch(BrowseLimits(io_slots=1, io_slots_per_principal=1, lifecycle_slots=1))
        entered, release = threading.Event(), threading.Event()
        def blocked():
            entered.set()
            assert release.wait(5)
            return 'finished'
        task = asyncio.create_task(dispatcher.run(blocked, principal='owner'))
        try:
            for _ in range(100):
                if entered.is_set():
                    break
                await asyncio.sleep(.01)
            assert entered.is_set()
            with pytest.raises(StorageError) as error:
                await dispatcher.run(lambda: pytest.fail('Unadmitted work executed'), principal='other')
            assert error.value.code == 'storage_busy'
            assert await dispatcher.run(lambda: 'cancel lane', principal='owner', lifecycle=True) == 'cancel lane'
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
            # Cancelling the await does not free capacity while the I/O runs.
            with pytest.raises(StorageError):
                await dispatcher.run(lambda: None, principal='other')
        finally:
            release.set()
            dispatcher.close()
    asyncio.run(scenario())


def test_cli_storage_uses_read_scope_bounded_pages_and_closes_cursor(tmp_path, monkeypatch):
    from operon import cli
    calls, instances = [], []
    class Client:
        def __init__(self, *args, **kwargs):
            instances.append(self)
            self.options = kwargs
            self.closed = False
        def request(self, path, payload=None):
            calls.append((path, dict(payload or {})))
            if path.endswith('/cancel'):
                return {'cancelled': True}
            return {'entries': [], 'next_cursor': 'opaque', 'listing_revision': 'rev',
                    'order': 'filesystem', 'complete': False}
        def close(self): self.closed = True
    monkeypatch.setattr(cli, 'Client', Client)
    args = cli.parser().parse_args(['--workspace', str(tmp_path), 'storage', 'browse', 'configured', '--pages', '2'])
    result = cli.execute(args)
    assert len(result['pages']) == 2 and result['cursor_closed'] and not result['complete']
    assert all(page['next_cursor'] is None for page in result['pages'])
    assert calls[0][1]['cursor'] is None and calls[1][1]['cursor'] == 'opaque'
    assert calls[-1] == ('/v1/storage/browse/cancel', {'cursor': 'opaque'})
    assert instances[0].options['scopes'] == ['context'] and instances[0].closed


def test_cli_rejects_invalid_storage_request_before_connecting(tmp_path, monkeypatch):
    from operon import cli
    monkeypatch.setattr(cli, 'Client', lambda *a, **k: pytest.fail('Invalid request started a client'))
    args = cli.parser().parse_args(['--workspace', str(tmp_path), 'storage', 'browse', 'configured', '--page-size', '1001'])
    with pytest.raises(ValueError):
        cli.execute(args)
