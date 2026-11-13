"""MCP stdio adapter; no model provider, credentials or chat implementation."""
import json
from pathlib import Path
from urllib.parse import quote, urlencode
from .client import Client, data_directory


def create_server(client):
    from mcp.server.fastmcp import FastMCP
    from .guidance import guide, instructions
    server = FastMCP("Operon", instructions=instructions())

    @server.tool()
    def operon_guide(topic: str = 'start', if_sha256: str | None = None) -> dict:
        """Read one installed operating guide: index, start, operators, canvas, workflow, jobs, results or api.

        No analysis or catalog scan. Cache by sha256; if unchanged, content is omitted.
        """
        return guide(topic, if_sha256=if_sha256)

    @server.tool()
    def operon_sessions() -> list[dict]:
        """List canvas windows and their activity/selection revision."""
        return client.sessions()

    @server.tool()
    def operon_context(session_id: str | None = None, scope: str = "selection") -> dict:
        """Read current selection, neighboring nodes, parameters and info contracts. Call before answering canvas questions."""
        return client.context(session_id, scope)

    @server.tool()
    def operon_catalog() -> dict:
        """Compatibility endpoint for the complete catalog. Prefer operator_search and operator_describe for bounded discovery."""
        return client.request("/catalog")

    @server.tool()
    def operon_operator_search(query: str = '', kind: str | None = None, category: str | None = None,
                                limit: int = 5, offset: int = 0, view: str = 'brief') -> dict:
        """Search installed operator/Reader summaries without importing implementations or loading all documentation."""
        params = {'query': query, 'kind': kind, 'category': category, 'limit': limit, 'offset': offset, 'view': view}
        return client.request('/v1/operators?' + urlencode({k: v for k, v in params.items() if v is not None}))

    @server.tool()
    def operon_operator_describe(ids: list[str], sections: list[str] | None = None, generation: str | None = None,
                                  view: str = 'schema') -> dict:
        """Read schemas/contracts and a document section index for up to 20 IDs. Request named sections or ['*'] explicitly.

        view=schema gives executable schemas, docs gives only identity/document sections, full gives all metadata.
        Use generation from artifact provenance or the full job to read pinned documentation.
        """
        return client.request('/v1/operators/describe', {'ids': ids, 'sections': sections, 'generation': generation, 'view': view})

    @server.tool()
    def operon_workflows(workflow_id: str | None = None) -> dict:
        """List saved workflows or retrieve one with its independent frozen parameters; no desktop session required."""
        value = client.request('/v1/workflows' + ('/' + quote(workflow_id, safe='') if workflow_id else ''))
        return value if workflow_id else {'items': value}

    @server.tool()
    def operon_workflow_save(graph: dict, workflow_id: str | None = None, expected_version: int | None = None) -> dict:
        """Create or update a saved workflow. Updates require its current version; saving never runs it."""
        return client.request('/v1/workflows', {'graph': graph, 'workflow_id': workflow_id, 'expected_version': expected_version})

    @server.tool()
    def operon_workflow_prepare(graph: dict, require_files: bool = True) -> dict:
        """Freeze defaults and validate contracts/files/environment without running or installing dependencies.

        Returns the prepared graph and readiness. Inspect blocked entries before submission;
        environment repair requires the separate, explicitly authorized prepare_environment tool.
        """
        prepared = client.request('/v1/workflows/prepare', {'graph': graph})
        checked = client.request('/v1/workflows/validate', {'graph': prepared, 'require_files': require_files})
        return {**checked, 'graph': prepared}

    @server.tool()
    def operon_workflow_check_environment(graph: dict) -> dict:
        """Check only this draft's dependencies on its selected hosts, without data files.

        Read-only. Does not authorize execution; validate the complete workflow before running.
        Passed host receipts are reused until declarations, scripts or environments change.
        """
        return client.request('/v1/workflows/check-environment', {'graph': graph})

    @server.tool()
    def operon_workflow_prepare_environment(graph: dict) -> dict:
        """Explicitly install/repair dependencies for this route's selected environments; requires --allow-plugins.

        Call only when the user authorized environment installation/repair. Validation and running
        never grant this permission. Checks only this route, returns readiness, and does not run a job.
        A transport timeout is not proof installation failed: reconnect and validate before retrying.
        """
        return client.request('/v1/workflows/prepare-environment', {'graph': graph})

    @server.tool()
    def operon_environments(profile_id: str | None = None) -> dict:
        """List isolated operator environments declared by the active library and their status.

        Read-only. status is missing, stale, ready or failed; used_by lists the operators that
        need the environment. Pass profile_id to inspect one configured remote server instead of
        this host; a remote read never installs anything.
        """
        if profile_id:
            return client.request('/remote/' + quote(profile_id, safe='') + '/environments')
        return client.request('/v1/environments')

    @server.tool()
    def operon_environments_prepare(names: list[str] | None = None, profile_id: str | None = None,
                                    dependencies: bool = False) -> dict:
        """Install isolated environments and optionally repair operator dependencies.

        Requires --allow-plugins and explicit user intent. Pass profile_id to install on that
        configured remote server; its install runs on the server and survives a client timeout.
        Missing environments are all prepared when names is omitted. Each environment is a
        dedicated Python interpreter; installing one can take several minutes.
        """
        if profile_id:
            return client.request('/remote/' + quote(profile_id, safe='') + '/environments/prepare',
                                  {'names': names, 'dependencies': dependencies})
        return client.request('/v1/environments/prepare', {'names': names})

    @server.tool()
    def operon_submit(request_id: str, graph: dict | None = None, workflow_id: str | None = None,
                       expected_version: int | None = None, view: str = 'brief') -> dict:
        """Submit a workflow without a canvas; requires --allow-run. Exactly one graph or workflow_id.

        Reuse request_id only for identical retries. A saved workflow requires expected_version.
        Returns a durable job ID immediately; closing the MCP connection does not cancel the task.
        """
        payload = {'request_id': request_id, 'expected_version': expected_version}
        if graph is not None:
            payload['graph'] = graph
        if workflow_id:
            payload['workflow_id'] = workflow_id
        from .agent_views import job_view
        job_view({}, view)
        return job_view(client.request('/v1/jobs', payload), view)

    @server.tool()
    def operon_jobs() -> dict:
        """List durable task status independently of open windows."""
        return {'items': client.request('/v1/jobs')}

    @server.tool()
    def operon_logs(job_id: str, offset: int = 0, limit: int = 4096, encoding: str = 'text') -> dict:
        """Read a small console chunk and byte cursor. encoding=base64 supports exact byte reconstruction; both is explicit."""
        return client.request('/v1/jobs/' + quote(job_id, safe='') + '/logs?' + urlencode({'offset': offset, 'limit': limit, 'encoding': encoding}))

    @server.tool()
    def operon_artifacts(job_id: str, artifact_id: str | None = None, preview: bool = False) -> dict:
        """List artifact/report links or inspect one artifact. preview reads a bounded sample, never the whole tensor."""
        path = '/v1/jobs/' + quote(job_id, safe='') + '/artifacts'
        if artifact_id:
            path += '/' + quote(artifact_id, safe='') + ('/preview' if preview else '')
        return client.request(path)

    @server.tool()
    def operon_artifact_table(job_id: str, artifact_id: str, offset: int = 0, limit: int = 100) -> dict:
        """Paginated artifact table with column and row labels; works for local and ssh jobs."""
        return client.request('/v1/jobs/' + quote(job_id, safe='') + '/artifacts/' + quote(artifact_id, safe='') + '/table?'
                              + urlencode({'offset': offset, 'limit': limit}))

    @server.tool()
    def operon_viewer(job_id: str, artifact_id: str, role: str, viewer: str | None = None) -> dict:
        """List matching installed viewers; with viewer ID, launch one (requires --allow-run).

        Use a retained file role from artifact preview. Desktop first; web entries are manual links.
        status=started confirms process launch, not file rendering. Remote files are fetched locally.
        """
        path = '/v1/jobs/' + quote(job_id, safe='') + '/artifacts/' + quote(artifact_id, safe='')
        if viewer:
            return client.request(path + '/open-viewer', {'role': role, 'viewer': viewer})
        return client.request(path + '/viewers?' + urlencode({'role': role}))

    @server.tool()
    def operon_task(base_dir: str, folders: list[str] | None = None) -> dict:
        """Create a task scaffold (input/results/reports/figures) below base_dir, which is relative to the workspace.

        Use this before writing inputs or asking an agent to place reports. Operon's internal .studio state is never writable.
        """
        return client.request('/v1/tasks', {'base_dir': base_dir, 'folders': folders})

    @server.tool()
    def operon_write_text(path: str, content: str, overwrite: bool = True) -> dict:
        """Write UTF-8 text into the Operon workspace through the backend, creating parent folders.

        path is workspace-relative; absolute paths, "..", symbolic links and Operon internal state are rejected.
        """
        return client.request('/v1/workspace/files', {'path': path, 'content': content, 'overwrite': overwrite})

    @server.tool()
    def operon_write_binary(path: str, content_base64: str, overwrite: bool = True) -> dict:
        """Write base64-encoded binary data (PNG, PDF, ZIP, ...) into the Operon workspace through the backend.

        path is workspace-relative; absolute paths, "..", symbolic links and Operon internal state are rejected.
        content_base64 is standard base64 without a data-URL prefix; decoded content is limited to 50 MiB.
        """
        return client.request('/v1/workspace/files/binary',
                              {'path': path, 'content': content_base64, 'overwrite': overwrite})

    @server.tool()
    def operon_remote_status() -> dict:
        """List SSH execution profiles with their connected state."""
        return client.request('/remote/summary')

    @server.tool()
    def operon_remote_ensure(profile_id: str) -> dict:
        """Idempotently reconnect a key/agent SSH profile before validate/prepare/run."""
        return client.request('/remote/' + quote(profile_id, safe='') + '/ensure', {})

    @server.tool()
    def operon_remote_install(profile_id: str, force: bool = False) -> dict:
        """Start installing or upgrading the Operon server on a configured SSH profile.

        force=True lets the remote retire busy tasks and previous installations.
        Poll operon_remote_install_status for progress.
        """
        return client.request('/remote/' + quote(profile_id, safe='') + '/install',
                              {'force': force})

    @server.tool()
    def operon_remote_install_status(profile_id: str) -> dict:
        """Read the background server installation/upgrade progress for a profile."""
        return client.request('/remote/' + quote(profile_id, safe='') + '/setup')

    @server.tool()
    def operon_pool_status() -> dict:
        """Show the local shared pool: version, owner, workspaces and active tasks."""
        return client.request('/pool')

    @server.tool()
    def operon_pool_stop(force: bool = False) -> dict:
        """Stop the local shared pool. force=True discards its active tasks."""
        return client.request('/pool/stop', {'force': force})

    @server.tool()
    def operon_remote_pool_stop(profile_id: str, force: bool = False) -> dict:
        """Stop one remote server's shared pool. force=True discards its active tasks."""
        return client.request('/remote/' + quote(profile_id, safe='') + '/pool/stop',
                              {'force': force})

    @server.tool()
    def operon_validate(graph: dict) -> dict:
        """Validate a complete route without running it or installing dependencies. Check readiness before running.

        Missing node positions are automatically laid out.
        """
        return client.request("/validate", {"graph": graph})

    @server.tool()
    def operon_graph(session_id: str) -> dict:
        """Read the complete canvas workspace and its revision."""
        return client.request(f"/sessions/{session_id}")

    @server.tool()
    def operon_open(session_id: str, expected_revision: int, graph: dict,
                    document_id: str | None = None, mode: str = "replace") -> dict:
        """Write a graph into the user's canvas. document_id targets an existing tab; mode=replace overwrites the active tab, append adds one. Returns {document_id, revision}."""
        return client.request(f"/sessions/{session_id}/open", {"graph": graph, "expected_revision": expected_revision,
                              "document_id": document_id, "mode": mode})

    @server.tool()
    def operon_apply(session_id: str, document_id: str, expected_revision: int, commands: list[dict], request_id: str) -> dict:
        """Atomically apply add_node, update_node, remove_node, connect, disconnect or configure commands.

        add_node: {op,node}; update_node: {op,id,patch}; remove_node: {op,id};
        connect: {op,edge}; disconnect: {op,id}; configure: {op,patch:{name,memory,base_dir,params,runtime}};
        set_graph: {op,graph}.
        One call creates one undo entry. Reuse request_id only when retrying identical commands.
        """
        return client.request(f"/sessions/{session_id}/apply", {"document_id": document_id, "expected_revision": expected_revision,
                              "commands": commands, "request_id": request_id})

    @server.tool()
    def operon_set_execution(session_id: str, document_id: str, expected_revision: int,
                              execution: dict, request_id: str) -> dict:
        """Set the execution device on an existing document: {kind:'local'|'ssh', profile_id?, mode?}. One transaction."""
        kind = str(execution.get("kind", "local"))
        if kind not in ("local", "ssh"):
            raise ValueError("execution.kind must be 'local' or 'ssh'")
        if kind == "ssh" and not execution.get("profile_id"):
            raise ValueError("execution.profile_id is required for ssh")
        runtime = {"execution": {k: execution[k] for k in ("kind", "profile_id", "mode") if k in execution}}
        return client.request(f"/sessions/{session_id}/apply", {"document_id": document_id,
                              "expected_revision": expected_revision, "request_id": request_id,
                              "commands": [{"op": "configure", "patch": {"runtime": runtime}}]})

    @server.tool()
    def operon_status() -> dict:
        """Report the MCP connection, scopes, installed version and the active canvas session/document."""
        status = client.status()
        try:
            status["sessions"] = client.sessions()
        except Exception as error:  # noqa: BLE001 - status must stay readable
            status["sessions_error"] = str(error)
        return status

    @server.tool()
    def operon_undo(session_id: str, document_id: str, expected_revision: int, redo: bool = False,
                     transaction_id: str | None = None) -> dict:
        """Undo/redo the latest edit, or a named transaction without erasing later unrelated edits.

        Overlapping later edits return undo_conflict; re-read them before choosing a new edit.
        Editing undo does not cancel a running job.
        """
        return client.request(f"/sessions/{session_id}/undo", {"document_id": document_id, "expected_revision": expected_revision,
                              "redo": redo, 'transaction_id': transaction_id})

    @server.tool()
    def operon_events(session_id: str, after: int = 0, limit: int = 20) -> dict:
        """Read bounded human/agent changes and short before/after previews. Continue at next_cursor.

        If reset=true, re-read graph/context; seq is the head, not a pagination cursor.
        Read transaction_diff only for needed details. Selection events do not change graph revision.
        """
        return client.request(f"/sessions/{session_id}/events?" + urlencode({'after': after, 'limit': limit}))

    @server.tool()
    def operon_transaction_diff(session_id: str, transaction_id: str, offset: int = 0, limit: int = 20) -> dict:
        """Read one edit's paginated code/parameter/edge differences, with truncation marked.

        Long values are previews: fetch the current node/source separately rather than treating them as replacement text.
        """
        return client.request(f"/sessions/{session_id}/transactions/" + quote(transaction_id, safe='') + '?'
                              + urlencode({'offset': offset, 'limit': limit}))

    @server.tool()
    def operon_run(session_id: str, document_id: str, expected_revision: int, request_id: str | None = None) -> dict:
        """Run the selected graph only on an explicit user request. Requires --allow-run."""
        return client.request(f"/sessions/{session_id}/run", {"document_id": document_id, "expected_revision": expected_revision,
                                                           **({'request_id': request_id} if request_id else {})})

    @server.tool()
    def operon_job(job_id: str, view: str = 'brief', wait_seconds: float = 0) -> dict:
        """Read brief status, or wait internally up to 120 seconds; a closed window returns running with wait_timed_out, never a failure."""
        import math
        from .agent_views import job_view, wait_job
        if not math.isfinite(wait_seconds) or not 0 <= wait_seconds <= 120:
            raise ValueError('wait_seconds must be between 0 and 120')
        job_view({}, view)
        job = client.request('/v1/jobs/' + quote(job_id, safe='') + '?view=' + view)
        return wait_job(client, job, wait_seconds, view=view) if wait_seconds else job

    @server.tool()
    def operon_cancel(job_id: str) -> dict:
        """Cancel a running job. Requires --allow-run."""
        return client.request('/v1/jobs/' + quote(job_id, safe='') + '/cancel', {})

    @server.tool()
    def operon_plugin_install(wheel: str) -> dict:
        """Install an explicitly selected trusted local plugin wheel. Requires --allow-plugins."""
        return client.request("/plugins/install", {"wheel": wheel})

    @server.tool()
    def operon_library_install(path: str) -> dict:
        """Install an Operon 5.0.0 operator library bundle. Requires --allow-plugins."""
        return client.request('/v1/libraries/install', {'path': path})

    @server.tool()
    def operon_routes_import(path: str) -> dict:
        """Import a route collection whose exact pins match the installed library."""
        return client.request('/v1/routes/import-collection', {'path': path})

    @server.resource("operon://selection")
    def current_selection() -> str:
        return json.dumps(client.context(), ensure_ascii=False)

    @server.resource('operon://guide')
    def operating_guide() -> str:
        return json.dumps(guide(), ensure_ascii=False)

    @server.resource('operon://guide/{topic}')
    def operating_topic(topic: str) -> str:
        return json.dumps(guide(topic), ensure_ascii=False)

    @server.resource("operon://sessions/{session_id}/selection")
    def selection(session_id: str) -> str:
        return json.dumps(client.context(session_id), ensure_ascii=False)

    @server.resource("operon://catalog")
    def catalog_resource() -> str:
        return json.dumps(client.request("/catalog"), ensure_ascii=False)

    return server


def serve(args):
    scopes = ["context"]
    if not args.read_only:
        scopes.append("edit")
    if args.allow_run:
        scopes.append("run")
    if args.allow_plugins:
        scopes.append("plugins")
    from src.web.profile import resolve_profile
    profile = resolve_profile(Path(__file__).resolve().parents[1], profile_dir=args.profile_dir, workspace=args.workspace, data_dir=args.data_dir)
    client = Client(profile.data_dir, instance=args.instance, name="MCP agent", scopes=scopes, auto_start=True, workspace=profile.workspace, require_api=1)
    try:
        create_server(client).run(transport="stdio")
    finally:
        client.close()
