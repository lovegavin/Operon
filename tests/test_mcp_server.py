"""Coverage for the MCP tools added for full desktop-control parity.

Each new tool must forward to the same authorized /api/v1 route the desktop
uses, and every such route must declare the same authorization scope as the
legacy /api handler it replaces. The retry regression pins the client transport
call that previously used a nonexistent ``post`` method.
"""
import ast
import asyncio
from pathlib import Path
from types import SimpleNamespace

import pytest

from operon.mcp_server import create_server

ROOT = Path(__file__).resolve().parents[1]

# tool name -> (arguments, expected client.request positional args)
NEW_FORWARDS = {
    'operon_preferences': ({}, ('/v1/preferences',)),
    'operon_preferences_save': (
        {'preferences': {'theme': 'dark'}, 'initialize': True},
        ('/v1/preferences', {'preferences': {'theme': 'dark'}, 'initialize': True})),
    'operon_workspace': ({}, ('/v1/workspace',)),
    'operon_workspace_save': (
        {'workspace': {'active_id': 'doc'}},
        ('/v1/workspace', {'active_id': 'doc'})),
    'operon_version': ({}, ('/v1/version',)),
    'operon_routes': ({}, ('/v1/routes',)),
    'operon_routes_register': (
        {'workflow_ids': ['route_a', 'route_b']},
        ('/v1/routes/register', {'workflow_ids': ['route_a', 'route_b']})),
    'operon_library_state': ({}, ('/v1/library/state',)),
    'operon_library_manage': (
        {'key': 'operon/reader', 'action': 'disable'},
        ('/v1/library/manage', {'key': 'operon/reader', 'action': 'disable'})),
    'operon_route_collections': ({}, ('/v1/route-collections',)),
    'operon_routes_import_archive': (
        {'content_base64': 'emlw'},
        ('/v1/routes/import-archive', {'content_base64': 'emlw'})),
    'operon_workflow_import': (
        {'content_base64': 'emlw'},
        ('/v1/workflows/import', {'content_base64': 'emlw'})),
    'operon_contracts': (
        {'graph': {'nodes': []}},
        ('/v1/contracts', {'graph': {'nodes': []}})),
    'operon_graph_export': (
        {'graph': {'nodes': []}},
        ('/v1/graphs/export', {'graph': {'nodes': []}})),
    'operon_graph_import': (
        {'text': 'operon: 1', 'base_dir': 'workflows'},
        ('/v1/graphs/import', {'text': 'operon: 1', 'base_dir': 'workflows'})),
    'operon_execution_plan': (
        {'graph': {'nodes': []}},
        ('/v1/execution/plan', {'graph': {'nodes': []}})),
    'operon_execution_resources': ({}, ('/v1/execution/resources',)),
    'operon_plugins_refresh': ({}, ('/v1/plugins/refresh', {})),
    'operon_plugins_dependencies': ({}, ('/v1/plugins/dependencies', {})),
    'operon_plugins_remove': (
        {'name': 'operon-demo'}, ('/v1/plugins/remove', {'name': 'operon-demo'})),
    'operon_plugins_manage': (
        {'name': 'operon-demo', 'action': 'enable'},
        ('/v1/plugins/manage', {'name': 'operon-demo', 'action': 'enable'})),
    'operon_script_inspect': (
        {'filename': 'demo.py', 'code': 'x = 1'},
        ('/v1/scripts/inspect',
         {'filename': 'demo.py', 'code': 'x = 1', 'script': None})),
    'operon_script_extract': (
        {'script': {'code': 'x = 1'}, 'names': ['a']},
        ('/v1/scripts/extract', {'script': {'code': 'x = 1'}, 'names': ['a']})),
    'operon_script_publish': (
        {'script': {'code': 'x = 1'}, 'operator_id': 'demo', 'title': 'Demo'},
        ('/v1/scripts/publish',
         {'script': {'code': 'x = 1'}, 'operator_id': 'demo', 'title': 'Demo',
          'category': 'data', 'version': '0.1.0'})),
    'operon_operator_source': (
        {'identifier': 'operon/demo'}, ('/v1/operators/operon%2Fdemo/source',)),
    'operon_job_export': (
        {'job_id': 'job 1', 'index': 2}, ('/v1/jobs/job%201/exports/2',)),
    'operon_remote_refresh': (
        {'profile_id': 'profile 1', 'verify_all': True},
        ('/v1/remotes/profile%201/refresh', {'verify_all': True})),
    'operon_remote_disconnect': (
        {'profile_id': 'profile 1'}, ('/v1/remotes/profile%201/disconnect', {})),
    'operon_remote_remove': (
        {'profile_id': 'profile 1'}, ('/v1/remotes/profile%201/remove', {})),
    'operon_remote_source': (
        {'profile_id': 'profile 1'}, ('/v1/remotes/profile%201/source', {})),
    'operon_remote_library_check': (
        {'profile_id': 'profile 1'}, ('/v1/remotes/profile%201/library/check', {})),
    'operon_remote_library_install': (
        {'profile_id': 'profile 1', 'request': {'version': '1.0'}},
        ('/v1/remotes/profile%201/library/install', {'version': '1.0'})),
}

NEW_TOOLS = set(NEW_FORWARDS) | {'operon_workflow_export', 'operon_route_collection_remove'}


def call(tool, arguments):
    calls = []

    def request(*args, **kwargs):
        calls.append((args, kwargs))
        return {'ok': True}

    server = create_server(SimpleNamespace(request=request))
    asyncio.run(server.call_tool(tool, arguments))
    return calls


@pytest.mark.parametrize('tool', sorted(NEW_FORWARDS))
def test_new_mcp_tool_forwards_to_the_authorized_route(tool):
    calls = call(tool, dict(NEW_FORWARDS[tool][0]))
    assert calls == [(NEW_FORWARDS[tool][1], {})], tool


def test_new_mcp_surface_is_complete():
    server = create_server(SimpleNamespace(request=lambda *args, **kwargs: {}))
    names = {tool.name for tool in asyncio.run(server.list_tools())}
    assert NEW_TOOLS <= names
    assert len(names) == 141


def test_route_collection_remove_uses_delete():
    calls = call('operon_route_collection_remove', {'slug': 'collection one'})
    assert calls == [(('/v1/route-collections/collection%20one',), {'method': 'DELETE'})]


def test_workflow_export_streams_into_the_workspace(tmp_path):
    calls = []

    def download(*args, **kwargs):
        calls.append((args, kwargs))
        return {'path': str(tmp_path / 'workflow.zip'), 'bytes': 10}

    client = SimpleNamespace(request=lambda *a, **k: {}, download=download,
                             workspace=str(tmp_path), status=lambda: {})
    server = create_server(client)
    asyncio.run(server.call_tool('operon_workflow_export',
                                 {'graph': {'nodes': []}, 'destination': 'out/workflow.zip'}))
    assert calls == [(('/v1/workflows/export', tmp_path / 'out' / 'workflow.zip'),
                      {'payload': {'graph': {'nodes': []}}})]


def test_environment_retry_uses_the_client_request_transport():
    calls = []

    def request(*args, **kwargs):
        calls.append((args, kwargs))
        return {'ok': True}

    client = SimpleNamespace(request=request)
    server = create_server(client)
    asyncio.run(server.call_tool('operon_environment_retry', {'name': 'web'}))
    asyncio.run(server.call_tool('operon_environment_retry',
                                 {'name': 'web', 'profile_id': 'box'}))
    assert calls == [(('/v1/environments/web/retry', {}), {}),
                     (('/remote/box/environments/web/retry', {}), {})]


def _route_scopes():
    tree = ast.parse((ROOT / 'operon' / 'control_api.py').read_text(encoding='utf-8'))
    found = {}
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for decorator in node.decorator_list:
            if not (isinstance(decorator, ast.Call)
                    and isinstance(decorator.func, ast.Attribute)
                    and decorator.func.attr in {'get', 'post', 'delete', 'put', 'patch'}
                    and decorator.args and isinstance(decorator.args[0], ast.Constant)):
                continue
            method = decorator.func.attr.upper()
            path = decorator.args[0].value
            scope = None
            for child in ast.walk(node):
                if (isinstance(child, ast.Call) and isinstance(child.func, ast.Name)
                        and child.func.id == 'authorize'):
                    scope = child.args[1].value if len(child.args) > 1 else 'context'
                    break
            found[(method, path)] = scope
    return found


EXPECTED_SCOPES = {
    ('GET', '/api/v1/preferences'): 'context',
    ('POST', '/api/v1/preferences'): 'edit',
    ('GET', '/api/v1/workspace'): 'context',
    ('POST', '/api/v1/workspace'): 'edit',
    ('GET', '/api/v1/version'): 'context',
    ('GET', '/api/v1/routes'): 'context',
    ('POST', '/api/v1/routes/register'): 'edit',
    ('GET', '/api/v1/library/state'): 'context',
    ('POST', '/api/v1/library/manage'): 'edit',
    ('GET', '/api/v1/route-collections'): 'context',
    ('DELETE', '/api/v1/route-collections/{slug}'): 'edit',
    ('POST', '/api/v1/routes/import-archive'): 'edit',
    ('POST', '/api/v1/workflows/import'): 'edit',
    ('POST', '/api/v1/contracts'): 'context',
    ('POST', '/api/v1/graphs/export'): 'context',
    ('POST', '/api/v1/graphs/import'): 'edit',
    ('POST', '/api/v1/execution/plan'): 'context',
    ('GET', '/api/v1/execution/resources'): 'context',
    ('POST', '/api/v1/plugins/refresh'): 'plugins',
    ('POST', '/api/v1/plugins/dependencies'): 'plugins',
    ('POST', '/api/v1/plugins/remove'): 'plugins',
    ('POST', '/api/v1/plugins/manage'): 'plugins',
    ('POST', '/api/v1/scripts/inspect'): 'edit',
    ('POST', '/api/v1/scripts/extract'): 'edit',
    ('GET', '/api/v1/operators/{identifier}/source'): 'context',
    ('POST', '/api/v1/scripts/publish'): 'plugins',
    ('GET', '/api/v1/jobs/{key}/exports/{index}'): 'context',
    ('POST', '/api/v1/remotes/{key}/refresh'): 'edit',
    ('POST', '/api/v1/remotes/{key}/disconnect'): 'edit',
    ('POST', '/api/v1/remotes/{key}/remove'): 'edit',
    ('POST', '/api/v1/remotes/{key}/source'): 'context',
    ('POST', '/api/v1/remotes/{key}/library/check'): 'context',
    ('POST', '/api/v1/remotes/{key}/library/install'): 'plugins',
}


def test_new_control_routes_require_the_same_scope_as_the_desktop_handler():
    scopes = _route_scopes()
    for route, scope in EXPECTED_SCOPES.items():
        assert route in scopes, route
        assert scopes[route] == scope, route



def test_new_v1_routes_enforce_agent_scopes(tmp_path, monkeypatch):
    monkeypatch.setenv('PYTHONUTF8', '1')
    monkeypatch.setenv('OPERON_REGISTRY_MAINTENANCE', '1')
    from fastapi.testclient import TestClient
    from operon.headless import create_headless_app
    from src.web.service import Settings

    settings = Settings(tmp_path, tmp_path / '.studio', tmp_path / 'ui', testing=True, code_root=ROOT)
    app = create_headless_app(settings)
    with TestClient(app, base_url='http://127.0.0.1') as client:
        secret = app.state.bridge.secret

        def headers(*scopes):
            reply = client.post('/api/agent/connect', headers={'X-Operon-Bridge': secret},
                                json={'name': 'scope-test', 'scopes': list(scopes)})
            assert reply.status_code == 200, reply.text
            return {'Authorization': 'Bearer ' + reply.json()['token']}

        read = headers('context')
        edit = headers('context', 'edit')
        plugins = headers('context', 'plugins')
        assert client.get('/api/v1/preferences', headers=read).status_code == 200
        assert client.post('/api/v1/preferences', headers=read,
                           json={'preferences': {'theme': 'dark'}}).status_code == 403
        assert client.post('/api/v1/preferences', headers=edit,
                           json={'preferences': {'theme': 'dark'}}).status_code == 200
        assert client.post('/api/v1/plugins/refresh', headers=edit).status_code == 403
        reply = client.post('/api/v1/remotes/missing/library/install', headers=plugins, json={})
        assert reply.status_code == 422, reply.text
