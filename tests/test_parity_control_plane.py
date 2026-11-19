"""Parity coverage for the MCP tool surface and the CLI verb surface.

Every interactive control has to reach the same shared service through HTTP, MCP
and the CLI. These tests pin one adapter action to the exact HTTP route it must
forward to, so a control that exists in the UI but is missing (or misrouted) in
an adapter fails here instead of only during manual verification.
"""
import asyncio
from pathlib import Path
from types import SimpleNamespace

import pytest

from operon import cli
from operon.mcp_server import create_server

ROOT = Path(__file__).resolve().parents[1]

# tool name -> (arguments, expected (path,) or (path, payload) forwarded by the client)
MCP_FORWARDS = {
    'operon_capabilities': ({}, ('/v1/capabilities',)),
    'operon_browse': ({'path': '/'}, ('/browse', {'path': '/', 'show_files': True})),
    'operon_service_status': ({}, ('/v1/service',)),
    'operon_service_stop': ({}, ('/v1/service/stop', {})),
    'operon_engine_status': ({}, ('/v1/engine',)),
    'operon_engine_events': ({'after': 7, 'limit': 5}, ('/v1/engine/events?after=7&limit=5',)),
    'operon_environment_status': ({}, ('/v1/environment',)),
    'operon_resource_limits': ({}, ('/v1/resources',)),
    'operon_job_parameters': ({'job_id': 'a b'}, ('/v1/jobs/a%20b/parameters',)),
    'operon_viewers': ({'refresh': True}, ('/v1/viewers?refresh=true',)),
    'operon_viewer_configure': ({'viewer': 'igv'},
                                ('/v1/viewers/igv/configure', {'executable': None})),
    'operon_viewer_default': ({'extension': '.bam'},
                              ('/v1/viewers/default', {'extension': '.bam', 'viewer': None})),
    'operon_viewer_prepare': ({'job_id': 'j', 'artifact_id': 'a', 'role': 'data'},
                              ('/v1/jobs/j/artifacts/a/prepare-viewer', {'role': 'data'})),
    'operon_storage_roots': ({}, ('/v1/storage/roots',)),
    'operon_storage_browse': ({'storage_id': 'tmp'},
                              ('/v1/storage/browse',
                               {'storage_id': 'tmp', 'relative_path': '.', 'hidden': False})),
    'operon_storage_stat': ({'storage_id': 'tmp', 'path': 'a.txt'},
                            ('/v1/storage/stat',
                             {'storage_id': 'tmp', 'relative_path': 'a.txt'})),
    'operon_storage_preview': ({'storage_id': 'tmp', 'path': 'a.txt', 'byte_limit': 16},
                               ('/v1/storage/preview',
                                {'storage_id': 'tmp', 'relative_path': 'a.txt',
                                 'byte_limit': 16})),
    'operon_storage_close': ({}, ('/v1/storage/browse/close', {})),
    'operon_storage_status': ({}, ('/v1/storage/status',)),
    'operon_plugins': ({}, ('/plugins',)),
    'operon_remote_save': ({'profile': {'id': 'x'}}, ('/v1/remotes', {'id': 'x'})),
    'operon_remote_connect': ({'profile_id': 'x', 'password': 'p'},
                              ('/v1/remotes/x/connect', {'password': 'p'})),
    'operon_remote_trust': ({'profile_id': 'x', 'fingerprint': 'f'},
                            ('/v1/remotes/x/trust', {'fingerprint': 'f'})),
    'operon_remote_library_plan': ({'profile_id': 'x'}, ('/remote/x/library/plan',)),
    'operon_remote_library_status': ({'profile_id': 'x'}, ('/remote/x/library/status',)),
    'operon_remote_library_sync': ({'profile_id': 'x'}, ('/remote/x/library/sync', {})),
    'operon_environment_dependency_install':
        ({'name': 'web', 'kind': 'pip', 'requirement': 'numpy', 'profile_id': 'box'},
         ('/remote/box/environments/web/dependencies/download',
          {'kind': 'pip', 'name': 'numpy'})),
    'operon_resource_download':
        ({'name': 'genome', 'root': '/data', 'profile_id': 'box'},
         ('/remote/box/resources/genome/download',
          {'overwrite': False, 'root': '/data'})),
    'operon_canvas_prepare': ({'graph': {'nodes': []}, 'request_id': 'r'},
                              ('/v1/canvas-plans/prepare',
                               {'graph': {'nodes': []}, 'request_id': 'r'})),
    'operon_canvas_status': ({'request_id': 'r'}, ('/v1/canvas-plans/status?request_id=r',)),
    'operon_canvas_cancel': ({'request_id': 'r'},
                             ('/v1/canvas-plans/cancel', {'request_id': 'r'})),
    'operon_canvas_execute': ({'preparation_id': 'p', 'request_id': 'r', 'action': 'run'},
                              ('/v1/canvas-plans/execute',
                               {'preparation_id': 'p', 'request_id': 'r',
                                'action': 'run', 'output': None})),
    'operon_canvas_history': ({}, ('/v1/canvas-plans/history',)),
    'operon_canvas_outcome': ({'request_id': 'r'},
                              ('/v1/canvas-plans/outcome?request_id=r',)),
}


def call(tool, arguments):
    calls = []

    def request(*args):
        calls.append(args)
        return {'ok': True}

    server = create_server(SimpleNamespace(request=request))
    asyncio.run(server.call_tool(tool, arguments))
    assert calls == [MCP_FORWARDS[tool][1]], tool


@pytest.mark.parametrize('tool', sorted(MCP_FORWARDS))
def test_mcp_tool_forwards_to_the_shared_route(tool):
    call(tool, dict(MCP_FORWARDS[tool][0]))


def test_mcp_server_declares_every_parity_tool():
    server = create_server(SimpleNamespace(request=lambda *args: {}))
    names = {tool.name for tool in asyncio.run(server.list_tools())}
    assert set(MCP_FORWARDS) <= names
    # The pre-existing surface must stay intact.
    assert {'operon_context', 'operon_apply', 'operon_submit', 'operon_viewer'} <= names


class RecordingClient:
    instances = []

    def __init__(self, directory, **kwargs):
        self.calls = []
        self.scopes = list(kwargs.get('scopes') or [])
        RecordingClient.instances.append(self)

    def request(self, *args, **kwargs):
        self.calls.append(args)
        return {'ok': True}

    def close(self):
        pass


def run(monkeypatch, tmp_path, argv):
    monkeypatch.setattr(cli, 'Client', RecordingClient)
    RecordingClient.instances = []
    cli.execute(cli.parser().parse_args(['--workspace', str(tmp_path)] + argv))
    client = RecordingClient.instances[-1]
    return client.calls, client


# argv -> expected HTTP call
CLI_FORWARDS = {
    ('capabilities',): ('/v1/capabilities',),
    ('engine', 'status'): ('/v1/engine',),
    ('engine', 'events', '--after', '3'): ('/v1/engine/events?after=3&limit=200',),
    ('jobs', 'parameters', 'job-1'): ('/v1/jobs/job-1/parameters',),
    ('resources', 'limits'): ('/v1/resources',),
    ('storage', 'roots'): ('/v1/storage/roots',),
    ('storage', 'close'): ('/v1/storage/browse/close', {}),
    ('environment', 'retry', 'web'): ('/v1/environments/web/retry', {}),
    ('environment', 'retry', 'web', '--profile', 'box'):
        ('/remote/box/environments/web/retry', {}),
    ('environment', 'dependency', 'web', 'pip', 'numpy', '--profile', 'box'):
        ('/remote/box/environments/web/dependencies/download',
         {'kind': 'pip', 'name': 'numpy'}),
    ('resources', 'download', 'genome', '--profile', 'box'):
        ('/remote/box/resources/genome/download',
         {'root': None, 'overwrite': False, 'unit': None}),
    ('servers', 'install', 'box'): ('/remote/box/install', {}),
    ('servers', 'setup', 'box'): ('/remote/box/setup',),
    ('browse', '--path', '/tmp'): ('/browse', {'files': True, 'path': '/tmp'}),
    ('canvas', 'history'): ('/v1/canvas-plans/history',),
    ('canvas', 'status', 'r'): ('/v1/canvas-plans/status?request_id=r',),
    ('canvas', 'outcome', '--request-id', 'r'): ('/v1/canvas-plans/outcome?request_id=r',),
    ('canvas', 'cancel', '--request-id', 'r'): ('/v1/canvas-plans/cancel', {'request_id': 'r'}),
    ('canvas', 'execute', '--preparation-id', 'p', '--request-id', 'r'):
        ('/v1/canvas-plans/execute',
         {'preparation_id': 'p', 'request_id': 'r', 'action': 'run', 'output': None}),
}


@pytest.mark.parametrize('argv', list(CLI_FORWARDS))
def test_cli_verb_forwards_to_the_shared_route(monkeypatch, tmp_path, argv):
    calls, _ = run(monkeypatch, tmp_path, list(argv))
    assert calls == [CLI_FORWARDS[argv]]


def test_cli_canvas_prepare_reads_the_workflow_file(monkeypatch, tmp_path):
    graph = tmp_path / 'graph.json'
    graph.write_text('{"nodes": [], "edges": []}', encoding='utf-8')
    calls, _ = run(monkeypatch, tmp_path,
                   ['canvas', 'prepare', '--file', str(graph), '--request-id', 'r'])
    assert calls == [('/v1/canvas-plans/prepare',
                      {'graph': {'nodes': [], 'edges': []}, 'request_id': 'r'})]


def test_cli_requests_run_scope_for_executing_canvas_actions(monkeypatch, tmp_path):
    _, client = run(monkeypatch, tmp_path, ['canvas', 'cancel', '--request-id', 'r'])
    assert 'run' in client.scopes
    _, client = run(monkeypatch, tmp_path, ['canvas', 'history'])
    assert 'run' not in client.scopes


def test_cli_parser_accepts_every_parity_verb():
    for command, action in (('environment', 'retry'), ('storage', 'roots'),
                            ('storage', 'close'), ('jobs', 'parameters'),
                            ('servers', 'install'), ('servers', 'setup'),
                            ('resources', 'limits')):
        assert cli.parser().parse_args([command, action]).action == action
    assert cli.parser().parse_args(['capabilities']).command == 'capabilities'
    for action in ('prepare', 'status', 'cancel', 'execute', 'history', 'outcome'):
        assert cli.parser().parse_args(['canvas', action]).action == action


def test_agent_bridge_exposes_the_parity_routes():
    source = (ROOT / 'operon' / 'bridge.py').read_text(encoding='utf-8')
    for route in ('/api/agent/browse',
                  '/api/agent/remote/{key}/browse',
                  '/api/agent/remote/{key}/library/plan',
                  '/api/agent/remote/{key}/library/status',
                  '/api/agent/remote/{key}/library/sync',
                  '/api/agent/remote/{key}/environments/{name}/retry',
                  '/api/agent/remote/{key}/environments/{name}/cancel',
                  '/api/agent/remote/{key}/environments/{name}/dependencies/download',
                  '/api/agent/remote/{key}/resources/{name}/download'):
        assert route in source, route
