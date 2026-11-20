"""Adapter parity for the environment repair and local dependency forwarding gaps."""
import threading
from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient

from operon.application import Application
from operon import environment_install
from operon.headless import create_headless_app
from src.web.service import Settings

ROOT = Path(__file__).resolve().parents[1]


def test_start_isolated_environments_repairs_dependencies(tmp_path, monkeypatch):
    checked = threading.Event()
    calls = []

    def check(**kwargs):
        calls.append(kwargs)
        checked.set()

    plan = {'demo': {'status': 'missing', 'used_by': ['alpha', 'beta']}}
    monkeypatch.setattr(environment_install, 'plan',
                        lambda root, descriptors, source=None: plan)
    monkeypatch.setattr(environment_install, 'prepare',
                        lambda name, root, source=None: {'status': 'ready'})
    application = Application.__new__(Application)
    application.service = SimpleNamespace(
        dependencies=SimpleNamespace(check=check),
        plugins=SimpleNamespace(state=lambda: {'descriptors': []}))
    application._library_source = lambda: tmp_path
    started = application.start_isolated_environments(['demo'], dependencies=True)
    assert [item['name'] for item in started] == ['demo']
    assert checked.wait(5)
    assert calls == [{'repair': True, 'repair_r': True, 'ids': ['alpha', 'beta']}]


def test_local_prepare_accepts_dependencies_and_repair_route(tmp_path, monkeypatch):
    monkeypatch.setenv('PYTHONUTF8', '1')
    monkeypatch.setenv('OPERON_REGISTRY_MAINTENANCE', '1')
    settings = Settings(tmp_path, tmp_path / '.studio', tmp_path / 'ui', testing=True,
                        code_root=ROOT)
    app = create_headless_app(settings)
    with TestClient(app, base_url='http://127.0.0.1') as client:
        reply = client.post('/api/agent/connect',
                            headers={'X-Operon-Bridge': app.state.bridge.secret},
                            json={'name': 'environment-gap-test',
                                  'scopes': ['context', 'plugins']})
        assert reply.status_code == 200, reply.text
        headers = {'Authorization': 'Bearer ' + reply.json()['token']}
        prepared = client.post('/api/v1/environments/prepare', headers=headers,
                               json={'names': ['__not_declared__'], 'dependencies': True})
        assert prepared.status_code == 200, prepared.text
        assert prepared.json()['dependencies'] is True
        missing = client.post('/api/v1/environments/__not_declared__/repair',
                              headers=headers)
        assert missing.status_code == 422, missing.text
        assert missing.json()['code'] == 'unknown_environment'


def _tool_text(result):
    import json
    blocks = result[0] if isinstance(result, tuple) else result
    block = blocks[0]
    payload = getattr(block, 'text', block)
    return json.loads(payload) if isinstance(payload, str) else payload


def test_remote_job_view_keeps_brief_shape():
    import asyncio
    from types import SimpleNamespace
    from operon.mcp_server import create_server

    calls = []

    def request(*args, **kwargs):
        calls.append((args, kwargs))
        if args[0].startswith('/remote/'):
            return {'id': 'j1', 'name': 'demo', 'status': 'running', 'progress': 1,
                    'secret': 'must-not-leak'}
        return {}

    server = create_server(SimpleNamespace(request=request))
    payload = _tool_text(asyncio.run(server.call_tool(
        'operon_job', {'job_id': 'j1', 'profile_id': 'box'})))
    assert calls[-1][0][0] == '/remote/box/jobs/j1'
    assert payload['id'] == 'j1' and payload['status'] == 'running'
    assert 'secret' not in payload


def test_remote_job_wait_timeout_marks_flag():
    import asyncio
    from types import SimpleNamespace
    from operon.mcp_server import create_server

    def request(*args, **kwargs):
        return {'id': 'j1', 'name': 'demo', 'status': 'running'}

    server = create_server(SimpleNamespace(request=request))
    payload = _tool_text(asyncio.run(server.call_tool(
        'operon_job', {'job_id': 'j1', 'profile_id': 'box', 'wait_seconds': 0.01})))
    assert payload['wait_timed_out'] is True
