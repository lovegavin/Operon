"""Parity guard: every frontend API method must reach a tool, or say why it cannot.

`frontend/src/api.ts` is the desktop HTTP surface. `operon/mcp_server.py` is the agent
surface. This module keeps the two in step: each method is mapped to the MCP tool that
reaches the same route, and a small allowlist records the methods that are deliberately
not exposed to agents, each with its reason.

The route comparison is intentionally coarse - it pins the route family each tool calls
(``/api/agent`` mirror, or the ``/v1`` control plane) and leaves exact payload pinning to
``tests/test_parity_control_plane.py``.
"""

from __future__ import annotations

import ast
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[1]
API_SOURCE = ROOT / 'frontend' / 'src' / 'api.ts'
SERVER_SOURCE = ROOT / 'operon' / 'mcp_server.py'

# api.ts exported the surface as one object literal; keep this pinned so a silent parser
# drift cannot shrink the audit.
EXPECTED_API_METHODS = 106

# method -> (MCP tool, route tokens the tool must still call)
PARITY: dict[str, tuple[str, tuple[str, ...]]] = {
    'catalogIfChanged': ('operon_catalog', ('/catalog',)),
    'inspectScript': ('operon_script_inspect', ('/v1/scripts/inspect',)),
    'extractScript': ('operon_script_extract', ('/v1/scripts/extract',)),
    'publishScript': ('operon_script_publish', ('/v1/scripts/publish',)),
    'operatorSource': ('operon_operator_source', ('/v1/operators/', '/source')),
    'prepareEnvironment': ('operon_workflow_prepare_environment',
                           ('/v1/workflows/prepare-environment',)),
    'checkEnvironment': ('operon_workflow_check_environment',
                         ('/v1/workflows/check-environment',)),
    'environments': ('operon_environments', ('/v1/environments',)),
    'prepareEnvironments': ('operon_environments_prepare', ('/environments/prepare',)),
    'remoteEnvironmentRetry': ('operon_environment_retry', ('/environments/', '/retry')),
    'retryEnvironment': ('operon_environment_retry', ('/environments/', '/retry')),
    'environmentLog': ('operon_environment_log', ('/environments/', '/log')),
    'cancelEnvironment': ('operon_environments_cancel', ('/environments/', '/cancel')),
    'version': ('operon_version', ('/v1/version',)),
    'pool': ('operon_pool_status', ('/pool',)),
    'stopPool': ('operon_pool_stop', ('/pool/stop',)),
    'remotePoolStop': ('operon_remote_pool_stop', ('/remote/', '/pool/stop')),
    'remoteEnvironments': ('operon_environments', ('/remote/', '/environments')),
    'remotePrepareEnvironments': ('operon_environments_prepare',
                                  ('/remote/', '/environments/prepare')),
    'remoteEnvironmentDependencyDownload': ('operon_environment_dependency_install',
                                            ('/environments/', '/dependencies/download')),
    'remoteCancelEnvironment': ('operon_environments_cancel', ('/environments/', '/cancel')),
    'remoteEnvironmentLog': ('operon_environment_log', ('/environments/', '/log')),
    'remoteResources': ('operon_resources', ('/remote/', '/resources')),
    'remoteLinkResource': ('operon_resource_link', ('/resources/', '/link')),
    'remoteUnlinkResource': ('operon_resource_unlink', ('/resources/', '/link')),
    'savePreferences': ('operon_preferences_save', ('/v1/preferences',)),
    'viewers': ('operon_viewers', ('/v1/viewers',)),
    'configureViewer': ('operon_viewer_configure', ('/v1/viewers/', '/configure')),
    'defaultViewer': ('operon_viewer_default', ('/v1/viewers/default',)),
    'artifactViewers': ('operon_viewer', ('/viewers',)),
    'openViewer': ('operon_viewer', ('/open-viewer',)),
    'prepareViewer': ('operon_viewer_prepare', ('/prepare-viewer',)),
    'executionPlan': ('operon_execution_plan', ('/v1/execution/plan',)),
    'executionResources': ('operon_execution_resources', ('/v1/execution/resources',)),
    'remoteStatus': ('operon_remote_status', ('/remote/summary',)),
    'saveRemote': ('operon_remote_save', ('/v1/remotes',)),
    'connectRemote': ('operon_remote_connect', ('/v1/remotes/', '/connect')),
    'installRemote': ('operon_remote_install', ('/remote/', '/install')),
    'refreshRemote': ('operon_remote_refresh', ('/v1/remotes/', '/refresh')),
    'checkRemoteLibrary': ('operon_remote_library_check', ('/v1/remotes/', '/library/check')),
    'installRemoteLibrary': ('operon_remote_library_install',
                             ('/v1/remotes/', '/library/install')),
    'remoteLibraryStatus': ('operon_remote_library_status', ('/remote/', '/library/status')),
    'remoteLibraryPlan': ('operon_remote_library_plan', ('/remote/', '/library/plan')),
    'syncRemoteLibrary': ('operon_remote_library_sync', ('/remote/', '/library/sync')),
    'remoteSetup': ('operon_remote_install_status', ('/remote/', '/setup')),
    'trustRemote': ('operon_remote_trust', ('/v1/remotes/', '/trust')),
    'disconnectRemote': ('operon_remote_disconnect', ('/v1/remotes/', '/disconnect')),
    'removeRemote': ('operon_remote_remove', ('/v1/remotes/', '/remove')),
    'browsePath': ('operon_browse', ('/browse',)),
    'browseRemote': ('operon_browse', ('/remote/', '/browse')),
    'sourceRemote': ('operon_remote_source', ('/v1/remotes/', '/source')),
    'largeResources': ('operon_resources', ('/v1/large-resources',)),
    'largeResourceLink': ('operon_resource_link', ('/large-resources/', '/link')),
    'largeResourceUnlink': ('operon_resource_unlink', ('/large-resources/', '/link')),
    'largeResourceDownload': ('operon_resource_download', ('/large-resources/', '/download')),
    'remoteResourceDownload': ('operon_resource_download',
                               ('/remote/', '/resources/', '/download')),
    'environmentDependencyDownload': ('operon_environment_dependency_install',
                                      ('/environments/', '/dependencies/download')),
    'storageRoots': ('operon_storage_roots', ('/v1/storage/roots',)),
    'browseStorage': ('operon_storage_browse', ('/v1/storage/browse',)),
    'statStorage': ('operon_storage_stat', ('/v1/storage/stat',)),
    'previewStorage': ('operon_storage_preview', ('/v1/storage/preview',)),
    'closeStorageBrowse': ('operon_storage_close', ('/v1/storage/browse/close',)),
    'plugins': ('operon_plugins', ('/plugins',)),
    'refreshPlugins': ('operon_plugins_refresh', ('/v1/plugins/refresh',)),
    'repairDependencies': ('operon_plugins_dependencies', ('/v1/plugins/dependencies',)),
    'removePlugin': ('operon_plugins_remove', ('/v1/plugins/remove',)),
    'managePlugin': ('operon_plugins_manage', ('/v1/plugins/manage',)),
    'installPlugin': ('operon_plugin_install', ('/plugins/install',)),
    'libraries': ('operon_library_list', ('/v1/libraries',)),
    'installLibrary': ('operon_library_install', ('/v1/libraries/install',)),
    'deleteLibrary': ('operon_library_remove', ('/v1/libraries/',)),
    'routeCollections': ('operon_route_collections', ('/v1/route-collections',)),
    'deleteRouteCollection': ('operon_route_collection_remove', ('/v1/route-collections/',)),
    'catalog': ('operon_catalog', ('/catalog',)),
    'workspace': ('operon_workspace', ('/v1/workspace',)),
    'saveWorkspace': ('operon_workspace_save', ('/v1/workspace',)),
    'workflows': ('operon_workflows', ('/v1/workflows',)),
    'workflow': ('operon_workflows', ('/v1/workflows',)),
    'prepareWorkflow': ('operon_workflow_prepare', ('/v1/workflows/prepare',)),
    'exportWorkflow': ('operon_workflow_export', ('/v1/workflows/export',)),
    'importWorkflow': ('operon_workflow_import', ('/v1/workflows/import',)),
    'saveWorkflow': ('operon_workflow_save', ('/v1/workflows',)),
    'importRouteArchive': ('operon_routes_import_archive', ('/v1/routes/import-archive',)),
    'importRouteCollection': ('operon_routes_import', ('/v1/routes/import-collection',)),
    'routes': ('operon_routes', ('/v1/routes',)),
    'libraryState': ('operon_library_state', ('/v1/library/state',)),
    'manageLibrary': ('operon_library_manage', ('/v1/library/manage',)),
    'registerRoutes': ('operon_routes_register', ('/v1/routes/register',)),
    'validate': ('operon_validate', ('/validate',)),
    'contracts': ('operon_contracts', ('/v1/contracts',)),
    'export': ('operon_graph_export', ('/v1/graphs/export',)),
    'import': ('operon_graph_import', ('/v1/graphs/import',)),
    'run': ('operon_submit', ('/v1/jobs',)),
    'history': ('operon_jobs', ('/v1/jobs',)),
    'job': ('operon_job', ('/v1/jobs/',)),
    'cancel': ('operon_cancel', ('/v1/jobs/', '/cancel')),
    'preview': ('operon_artifacts', ('/v1/jobs/', '/preview')),
    'step': ('operon_job_export', ('/v1/jobs/', '/exports/')),
}

# Methods that must not become MCP tools. Every entry needs its reason: the audit fails
# when a reason is missing, so a new method cannot be waved through without an argument.
ALLOWLIST: dict[str, str] = {
    # reason: the generic /api/agent passthrough IS the MCP transport; exposing it as a
    # tool would let an agent call arbitrary bridge routes and bypass the tool contracts.
    'agent': 'Generic bridge passthrough; the MCP transport already is that channel.',
    # reason: bootstrap hands the browser a studio token and remembers it in module state;
    # MCP authenticates with the bridge token from /api/agent/connect and has no SPA session.
    'bootstrap': 'SPA session bootstrap that stores X-Studio-Token; MCP connects via the bridge.',
    # reason: the helper only joins the configured base URL with a path and sends nothing.
    'url': 'Pure base+path string helper; it performs no HTTP request.',
    # reason: these three upload browser File objects (multipart, blob chunks, per-batch
    # accounting). Agents create the same workspace files with operon_task plus
    # operon_write_text / operon_write_binary, so no binary upload tool is needed.
    'upload': 'Browser File upload choreography; agents use operon_write_binary instead.',
    'uploadFiles': 'Browser batch upload choreography; agents use operon_write_binary instead.',
    'uploadReference': 'Browser File upload choreography; agents use operon_write_binary instead.',
    # reason: opens the plugin folder in the desktop file manager; there is no HTTP route
    # behind it and an agent cannot observe a GUI side effect.
    'openPluginFolder': 'Desktop file-manager affordance with no HTTP route behind it.',
    # reason: polls a legacy async plugin handle; the bridge and /v1 plugin routes are
    # synchronous and already return the terminal state, so there is nothing to poll.
    'pluginOperation': 'Polls a legacy async UI handle; bridge and /v1 plugin calls are synchronous.',
}

API_KEY = re.compile(r'^  ([A-Za-z_][A-Za-z0-9_]*)\s*:')
CALL = {'request', 'download'}


def api_methods() -> list[str]:
    """Return the method names declared in the exported ``api`` object literal."""
    text = API_SOURCE.read_text(encoding='utf-8')
    start = text.index('export const api = {')
    names: list[str] = []
    for line in text[start:].splitlines()[1:]:
        if line.startswith('}'):
            break
        match = API_KEY.match(line)
        if match:
            names.append(match.group(1))
    return names


def local_assignments(function: ast.AST) -> dict[str, list[ast.AST]]:
    """Collect simple local assignments so paths built through variables stay visible."""
    found: dict[str, list[ast.AST]] = {}
    for node in ast.walk(function):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    found.setdefault(target.id, []).append(node.value)
        elif isinstance(node, ast.AugAssign) and isinstance(node.target, ast.Name):
            found.setdefault(node.target.id, []).append(node.value)
    return found


def route_shape(node: ast.AST, assignments: dict[str, list[ast.AST]] | None = None,
                seen: frozenset[str] = frozenset()) -> str:
    """Join the string constants of a path expression, following local variables."""
    assignments = assignments or {}
    parts: list[tuple[int, int, str]] = []
    for child in ast.walk(node):
        if isinstance(child, ast.Name) and child.id in assignments and child.id not in seen:
            for value in assignments[child.id]:
                parts.append((getattr(value, 'lineno', 0), getattr(value, 'col_offset', 0),
                              route_shape(value, assignments, seen | {child.id})))
        elif isinstance(child, ast.Constant) and isinstance(child.value, str):
            parts.append((getattr(child, 'lineno', 0), getattr(child, 'col_offset', 0),
                          child.value))
    return '|'.join(value for _, _, value in sorted(parts))


def mcp_tools() -> dict[str, dict[str, object]]:
    """Return every ``@server.tool()`` function with its parameters, docstring and routes."""
    tree = ast.parse(SERVER_SOURCE.read_text(encoding='utf-8'))
    tools: dict[str, dict[str, object]] = {}
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        declares = False
        for decorator in node.decorator_list:
            if (isinstance(decorator, ast.Call) and isinstance(decorator.func, ast.Attribute)
                    and decorator.func.attr == 'tool'):
                declares = True
        if not declares:
            continue
        assignments = local_assignments(node)
        routes: list[str] = []
        for child in ast.walk(node):
            if not isinstance(child, ast.Call):
                continue
            if not isinstance(child.func, ast.Attribute) or child.func.attr not in CALL:
                continue
            if not isinstance(child.func.value, ast.Name) or child.func.value.id != 'client':
                continue
            if child.args:
                routes.append(route_shape(child.args[0], assignments))
        tools[node.name] = {
            'params': [arg.arg for arg in node.args.args if arg.arg != 'self'],
            'doc': (ast.get_docstring(node) or '').strip(),
            'routes': routes,
        }
    return tools


def test_api_method_count_is_pinned() -> None:
    names = api_methods()
    assert len(names) == EXPECTED_API_METHODS, (
        f'api.ts declares {len(names)} methods, expected {EXPECTED_API_METHODS}. '
        'Update PARITY/ALLOWLIST together with this pin.')
    assert len(set(names)) == len(names), 'api.ts declares a duplicate method name'


def test_every_api_method_is_classified() -> None:
    names = set(api_methods())
    classified = set(PARITY) | set(ALLOWLIST)
    assert not names - classified, f'unmapped api methods: {sorted(names - classified)}'
    assert not classified - names, f'stale entries, not in api.ts: {sorted(classified - names)}'


def test_every_mapped_tool_exists() -> None:
    tools = mcp_tools()
    missing = sorted({tool for tool, _ in PARITY.values()} - set(tools))
    assert not missing, f'MCP tools missing from operon/mcp_server.py: {missing}'


def test_every_mapped_tool_calls_its_route() -> None:
    tools = mcp_tools()
    problems = []
    for method, (tool, tokens) in sorted(PARITY.items()):
        routes = '||'.join(tools[tool]['routes'])  # type: ignore[arg-type]
        absent = [token for token in tokens if token not in routes]
        if absent:
            problems.append(f'{method} -> {tool} no longer calls {absent} (routes: {routes})')
    assert not problems, '\n'.join(problems)


def test_every_mapped_tool_is_documented() -> None:
    tools = mcp_tools()
    undocumented = sorted(tool for tool, _ in PARITY.values() if not tools[tool]['doc'])
    assert not undocumented, f'MCP tools without a docstring: {undocumented}'


# Tools that work on the profile collection rather than on one profile: listing and
# creating do not address a server, so they take no profile_id.
PROFILE_FREE_TOOLS = {
    # reason: lists profiles (optionally with full status); no single profile is addressed.
    'operon_remote_status',
    # reason: saves the profile document given in the call; the profile is the payload.
    'operon_remote_save',
}


def test_remote_tools_take_a_profile_id() -> None:
    tools = mcp_tools()
    problems = []
    for method, (tool, tokens) in sorted(PARITY.items()):
        if tool in PROFILE_FREE_TOOLS:
            continue
        if not any(token.startswith(('/remote/', '/v1/remotes')) for token in tokens):
            continue
        params = tools[tool]['params']
        if 'profile_id' not in params:  # type: ignore[operator]
            problems.append(f'{method} -> {tool} handles a remote route but takes {params}')
    assert not problems, '\n'.join(problems)


def test_allowlisted_methods_bring_a_reason() -> None:
    thin = sorted(method for method, reason in ALLOWLIST.items() if len(reason.strip()) < 20)
    assert not thin, f'allowlist entries need a real reason: {thin}'
