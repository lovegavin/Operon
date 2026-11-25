"""MCP stdio adapter; no model provider, credentials or chat implementation."""
import base64
import binascii
import json
from pathlib import Path
from urllib.parse import quote, urlencode
from .client import Client, ClientError, data_directory


def installation_root() -> Path:
    """The application tree this adapter was started from."""
    return Path(__file__).resolve().parents[1]


def require_installation(root: Path | None = None) -> Path:
    """Refuse to serve from an installation that no longer exists.

    A process survives deleting its version directory. Its imports are already
    loaded, so it keeps answering with a dead code root and a stale pool
    registration, and the next client sees timeouts instead of a reconnect.
    Exiting here makes the client start the current installation instead.
    """
    value = (root or installation_root()).resolve()
    if not (value / 'operon' / 'managed_pool.py').is_file():
        raise SystemExit(
            f"Operon MCP server: the installation at {value} was removed or replaced; "
            "restart the MCP client so it starts the current version.")
    return value


def create_server(client):
    from mcp.server.fastmcp import FastMCP
    from .guidance import guide, instructions
    server = FastMCP("Operon", instructions=instructions())
    try:
        from . import __version__ as product_version
        server._mcp_server.version = product_version
    except Exception:  # pragma: no cover - the SDK keeps the attribute private
        pass

    def _download_root():
        value = client.workspace or client.status().get('workspace')
        if not value:
            raise ValueError('MCP client has no workspace; pass --workspace to the MCP server')
        return Path(value).resolve()

    def _download_target(destination):
        value = Path(str(destination))
        if value.is_absolute() or '..' in value.parts:
            raise ValueError('destination must be a relative path inside the workspace')
        root = _download_root()
        target = (root / value).resolve()
        if target != root and root not in target.parents:
            raise ValueError('destination escapes the workspace')
        return target

    def _payload(source, content_base64):
        if content_base64:
            try:
                return base64.b64decode(content_base64, validate=True)
            except (binascii.Error, ValueError) as error:
                raise ValueError('content_base64 is not valid base64') from error
        if not source:
            raise ValueError('provide source (a local file path) or content_base64')
        return Path(source).read_bytes()

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
    def operon_plan_compile(request: dict) -> dict:
        """Compile a graph or authoring-v2 request into a frozen RunPlan; never execute or install.

        request follows the strict /api/v1/plans/compile schema. Authoring-v2
        supplies independent parameters/inputs/environments objects explicitly.
        """
        return client.request('/v1/plans/compile', request)

    @server.tool()
    def operon_plan_submit(plan: dict, binding: dict, request_id: str) -> dict:
        """Explicitly submit one frozen RunPlan to the shared host pool; requires --allow-run.

        Binding uses workspace-relative package/environment/storage/input paths.
        Reuse the same request_id and content after an uncertain response.
        """
        return client.request('/v1/plans', {'plan': plan, 'binding': binding, 'request_id': request_id})

    @server.tool()
    def operon_plan_status(run_id: str) -> dict:
        """Read authoritative host-pool RunPlan status without starting work."""
        return client.request('/v1/plans/' + quote(run_id, safe=''))

    @server.tool()
    def operon_plan_events(run_id: str, after: int = 0, limit: int = 100, max_bytes: int = 32768) -> dict:
        """Read bounded host transition metadata; continue at next_cursor, or the retained floor after expiry."""
        return client.request('/v1/plans/' + quote(run_id, safe='') + '/events?' +
                              urlencode(dict(after=after, limit=limit, max_bytes=max_bytes)))

    @server.tool()
    def operon_plan_attempts(run_id: str, after: str = '', limit: int = 100, max_bytes: int = 32768) -> dict:
        """List owned attempts and states without process identities or filesystem paths."""
        return client.request('/v1/plans/' + quote(run_id, safe='') + '/attempts?' +
                              urlencode(dict(after=after, limit=limit, max_bytes=max_bytes)))

    @server.tool()
    def operon_plan_artifacts(run_id: str, after: str = '', limit: int = 100, max_bytes: int = 32768) -> dict:
        """List committed artifact IDs, hashes and sizes. This does not download or open output files."""
        return client.request('/v1/plans/' + quote(run_id, safe='') + '/artifacts?' +
                              urlencode(dict(after=after, limit=limit, max_bytes=max_bytes)))

    @server.tool()
    def operon_plan_logs(run_id: str, attempt_id: str, offset: int = 0, max_bytes: int = 16384,
                         encoding: str = 'text') -> dict:
        """Read at most 64 KiB of one owned attempt log; continue at next_offset. Base64 preserves raw bytes."""
        return client.request('/v1/plans/' + quote(run_id, safe='') + '/logs?' +
                              urlencode(dict(attempt_id=attempt_id, offset=offset, max_bytes=max_bytes, encoding=encoding)))

    @server.tool()
    def operon_plan_cancel(run_id: str) -> dict:
        """Request cancellation through the existing host coordinator; requires --allow-run."""
        return client.request('/v1/plans/' + quote(run_id, safe='') + '/cancel', {})

    @server.tool()
    def operon_plan_export(request: dict) -> dict:
        """Queue an explicit RunPlan export with frozen manifests/bindings; requires --allow-run.

        Returns a durable receipt, not a claim that the bundle already passed
        relocation checks. Reuse request_id after a lost response; never invent
        a new key to retry an unknown/building operation.
        """
        return client.request('/v1/plan-exports', request)

    @server.tool()
    def operon_plan_export_status(export_id: str | None = None, request_id: str | None = None) -> dict:
        """Read a build receipt by ID, or recover it by the original request_id after a lost reply."""
        if bool(export_id) == bool(request_id):
            raise ValueError('Provide exactly one export_id or request_id')
        return client.request('/v1/plan-exports/' + quote(export_id, safe='') if export_id
                              else '/v1/plan-exports/lookup?' + urlencode({'request_id': request_id}))

    @server.tool()
    def operon_plan_export_cancel(export_id: str) -> dict:
        """Cancel a queued/active package build; requires --allow-run and does not cancel scientific jobs."""
        return client.request('/v1/plan-exports/' + quote(export_id, safe='') + '/cancel', {})

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
        return client.request('/v1/environments/prepare',
                              {'names': names, 'dependencies': bool(dependencies)})

    @server.tool()
    def operon_environments_cancel(name: str, profile_id: str | None = None) -> dict:
        """Cancel a running or queued environment preparation.

        Requires --allow-plugins. The environment returns to missing and can be installed again.
        """
        suffix = '/environments/' + quote(name, safe='') + '/cancel'
        if profile_id:
            return client.request('/remote/' + quote(profile_id, safe='') + suffix, {})
        return client.request('/v1' + suffix, {})

    @server.tool()
    def operon_environment_retry(name: str, profile_id: str | None = None) -> dict:
        """Cancel a stale preparation and start it again; mirrors the UI repair button."""
        suffix = '/environments/' + quote(name, safe='') + '/retry'
        if profile_id:
            return client.request('/remote/' + quote(profile_id, safe='') + suffix, {})
        return client.request('/v1' + suffix, {})

    @server.tool()
    def operon_environment_repair(name: str, profile_id: str | None = None) -> dict:
        """Rewrite stale staging shebangs in an environment that is already installed.

        Requires --allow-plugins. Pass profile_id to repair that configured remote server.
        """
        suffix = '/environments/' + quote(name, safe='') + '/repair'
        if profile_id:
            return client.request('/remote/' + quote(profile_id, safe='') + suffix, {})
        return client.request('/v1' + suffix, {})

    @server.tool()
    def operon_environment_log(name: str, limit: int = 200, profile_id: str | None = None) -> dict:
        """Read the tail of one environment preparation log (at most 2000 lines).

        Read-only. Works for a running or finished preparation and reports the same lines the
        desktop log drawer shows. Pass profile_id to read the log kept on that remote server.
        """
        suffix = ('/environments/' + quote(name, safe='') + '/log?limit=' +
                  str(max(1, min(int(limit), 2000))))
        if profile_id:
            return client.request('/remote/' + quote(profile_id, safe='') + suffix)
        return client.request('/v1' + suffix)

    @server.tool()
    def operon_environment_dependency_install(name: str, kind: str, requirement: str,
                                              profile_id: str | None = None) -> dict:
        """Install one declared operator dependency into an isolated environment.

        kind is one of requirements, pip_wheels, pip_pypi, conda_packages, binaries or imports;
        requirement is the exact declared entry such as ``alphafold==2.3.2``. Requires
        --allow-plugins and explicit user intent. Pass profile_id to install on that remote.
        """
        payload = {'kind': str(kind or ''), 'name': str(requirement or '')}
        suffix = '/environments/' + quote(name, safe='') + '/dependencies/download'
        if profile_id:
            return client.request('/remote/' + quote(profile_id, safe='') + suffix, payload)
        return client.request('/v1' + suffix, payload)

    @server.tool()
    def operon_browse(path: str | None = None, show_files: bool = True,
                      profile_id: str | None = None, offset: int = 0,
                      hidden: bool = False) -> dict:
        """List drives or one directory so the link picker can walk the file system.

        Read-only. Returns the resolved path, its parent, the drive roots and up to 500 entries.
        Pass profile_id to browse the file system of that configured remote server; its
        listing pages 200 entries at a time, so keep the returned next_offset as offset and
        set hidden=True to include dotfiles.
        """
        payload = {'path': path, 'show_files': bool(show_files)}
        if profile_id:
            remote = dict(payload, offset=max(0, int(offset)), hidden=bool(hidden))
            return client.request('/remote/' + quote(profile_id, safe='') + '/browse', remote)
        return client.request('/browse', payload)

    def _with_parallel(graph, max_parallel_tasks):
        """Copy the graph and write the requested per-job concurrency into it."""
        if max_parallel_tasks is None:
            return graph
        value = int(max_parallel_tasks)
        if value < 0:
            raise ValueError('max_parallel_tasks must be zero (unlimited) or a positive integer')
        result = dict(graph or {})
        runtime = dict(result.get('runtime') or {})
        execution = dict(runtime.get('execution') or {})
        execution['max_parallel_tasks'] = value
        runtime['execution'] = execution
        result['runtime'] = runtime
        return result

    @server.tool()
    def operon_submit(request_id: str, graph: dict | None = None, workflow_id: str | None = None,
                       expected_version: int | None = None, view: str = 'brief',
                       max_parallel_tasks: int | None = None) -> dict:
        """Submit a workflow without a canvas; requires --allow-run. Exactly one graph or workflow_id.

        Reuse request_id only for identical retries. A saved workflow requires expected_version.
        max_parallel_tasks overrides the profile default for this job; 0 means unlimited.
        Returns a durable job ID immediately; closing the MCP connection does not cancel the task.
        """
        payload = {'request_id': request_id, 'expected_version': expected_version}
        if graph is not None:
            payload['graph'] = _with_parallel(graph, max_parallel_tasks)
        if workflow_id:
            payload['workflow_id'] = workflow_id
        from .agent_views import job_view
        job_view({}, view)
        return job_view(client.request('/v1/jobs', payload), view)

    @server.tool()
    def operon_submit_many(graphs: list[dict], request_ids: list[str] | None = None,
                           max_parallel_tasks: int | None = None, view: str = 'brief',
                           workers: int = 16) -> dict:
        """Submit a list of graphs concurrently; requires --allow-run.

        One MCP request carries many jobs, so a client that can only speak to one
        tool at a time no longer serialises the queue. Returns the accepted job
        IDs in the order of ``graphs`` plus per-index errors for the rejects.
        max_parallel_tasks is applied to every graph; 0 means unlimited.
        """
        from concurrent.futures import ThreadPoolExecutor
        from .agent_views import job_view
        items = list(graphs or [])
        if not items:
            raise ValueError('graphs must contain at least one graph')
        names = list(request_ids or [])
        if names and len(names) != len(items):
            raise ValueError('request_ids must be empty or match graphs in length')

        def one(index):
            payload = {'request_id': names[index] if names else f'mcp-batch-{index}'}
            payload['graph'] = _with_parallel(items[index], max_parallel_tasks)
            try:
                return {'index': index, 'job': job_view(client.request('/v1/jobs', payload), view)}
            except Exception as error:  # noqa: BLE001 - one reject must not hide the rest
                return {'index': index, 'error': f'{type(error).__name__}: {error}'}

        with ThreadPoolExecutor(max_workers=max(1, min(int(workers or 16), 64))) as pool:
            results = list(pool.map(one, range(len(items))))
        accepted = [item for item in results if 'job' in item]
        return {'items': results, 'accepted': len(accepted), 'rejected': len(results) - len(accepted)}

    @server.tool()
    def operon_jobs_many(job_ids: list[str], view: str = 'brief') -> dict:
        """Read several durable job statuses in one request.

        Mirrors operon_jobs for a list of IDs, so polling a batch is one call
        instead of one call per job.
        """
        from concurrent.futures import ThreadPoolExecutor
        from .agent_views import job_view
        ids = [str(item) for item in (job_ids or []) if item]
        if not ids:
            raise ValueError('job_ids must contain at least one id')

        def one(job_id):
            try:
                return {'job_id': job_id, 'job': job_view(client.request('/v1/jobs/' + quote(job_id, safe='')), view)}
            except Exception as error:  # noqa: BLE001 - report the miss, keep the batch
                return {'job_id': job_id, 'error': f'{type(error).__name__}: {error}'}

        with ThreadPoolExecutor(max_workers=max(1, min(len(ids), 32))) as pool:
            return {'items': list(pool.map(one, ids))}

    @server.tool()
    def operon_jobs(profile_id: str | None = None) -> dict:
        """List durable task status independently of open windows.

        Pass profile_id to list the jobs known to that configured remote server.
        """
        if profile_id:
            return client.request('/remote/' + quote(profile_id, safe='') + '/jobs')
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
    def operon_result_files(job_id: str | None = None, id: str | None = None) -> dict:
        """List every file below a job's result directory, local or ssh, with sizes."""
        reference = job_id or id
        if not reference:
            raise ValueError('job_id is required')
        return client.request('/v1/jobs/' + quote(reference, safe='') + '/results')

    @server.tool()
    def operon_plan_artifact_files(run_id: str, artifact_id: str, after: str = '', limit: int = 100) -> dict:
        """List bounded committed plan files; returned file IDs select subsequent reads."""
        return client.request('/v1/plans/' + quote(run_id, safe='') + '/artifacts/' + quote(artifact_id, safe='')
            + '/files?' + urlencode({'after': after, 'limit': limit}))

    @server.tool()
    def operon_plan_artifact_preview(run_id: str, artifact_id: str, file_id: str,
                                     max_bytes: int = 16384, max_rows: int = 100) -> dict:
        """Read a bounded text preview; binary files return metadata without full relay."""
        return client.request('/v1/plans/' + quote(run_id, safe='') + '/artifacts/' + quote(artifact_id, safe='')
            + '/files/' + quote(file_id, safe='') + '/preview?' + urlencode({'max_bytes': max_bytes, 'max_rows': max_rows}))

    @server.tool()
    def operon_download_plan_artifact(run_id: str, artifact_id: str, file_id: str, destination: str) -> dict:
        """Explicitly download one owned local committed file into the workspace."""
        return client.download('/v1/plans/' + quote(run_id, safe='') + '/artifacts/' + quote(artifact_id, safe='')
            + '/files/' + quote(file_id, safe='') + '/open', _download_target(destination))

    @server.tool()
    def operon_download_result(job_id: str, path: str, destination: str | None = None) -> dict:
        """Download one result file into the workspace; path comes from operon_result_files."""
        name = Path(str(path).replace('\\', '/')).name or 'result'
        target = _download_target(destination or f'results/{job_id}/{name}')
        route = '/v1/jobs/' + quote(job_id, safe='') + '/results/file?' + urlencode({'path': path})
        return client.download(route, target)

    @server.tool()
    def operon_download_results(job_id: str, destination: str | None = None,
                                 paths: list[str] | None = None) -> dict:
        """Download all or selected result files, preserving their relative paths."""
        listing = client.request('/v1/jobs/' + quote(job_id, safe='') + '/results')
        available = [item for item in listing.get('files') or []]
        wanted = set(paths or [])
        selected = [item for item in available if not wanted or item['path'] in wanted]
        missing = sorted(wanted - {item['path'] for item in selected})
        base = destination or f'results/{job_id}'
        downloaded, failed = [], []
        for item in selected:
            try:
                target = _download_target(str(Path(base) / item['path']))
                result = client.download('/v1/jobs/' + quote(job_id, safe='') + '/results/file?'
                                         + urlencode({'path': item['path']}), target)
                downloaded.append({'path': item['path'], 'target': result.get('path'), 'bytes': result.get('bytes')})
            except Exception as exc:
                failed.append({'path': item['path'], 'error': f'{type(exc).__name__}: {exc}'})
        return {'job_id': job_id, 'root': listing.get('root'), 'downloaded': downloaded,
                'failed': failed, 'missing': missing}

    @server.tool()
    def operon_download_artifact(job_id: str, artifact_id: str, role: str | None = None,
                                  destination: str | None = None) -> dict:
        """Download an artifact's retained file (optionally one role) into the workspace."""
        route = '/v1/jobs/' + quote(job_id, safe='') + '/artifacts/' + quote(artifact_id, safe='') + '/file'
        if role:
            route += '?' + urlencode({'role': role})
        target = _download_target(destination or f'results/{job_id}/artifacts/{artifact_id}/{role or "data"}')
        return client.download(route, target)

    @server.tool()
    def operon_download_report(job_id: str, index: int, destination: str | None = None) -> dict:
        """Download a stored job report JSON into the workspace."""
        target = _download_target(destination or f'reports/{job_id}-{index}.json')
        return client.download('/v1/jobs/' + quote(job_id, safe='') + f'/reports/{int(index)}', target)

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
    def operon_upload_file(source_path: str, path: str, overwrite: bool = True) -> dict:
        """Stream a local file into the Operon workspace without base64 framing.

        source_path is read by the MCP process (absolute paths are allowed); path is
        workspace-relative. The body is copied straight to disk, so this lifts the 50 MiB
        limit of operon_write_binary for large FASTA/FASTQ/PDB/BAM inputs. Requires edit scope.
        """
        query = urlencode({'path': path, 'overwrite': 'true' if overwrite else 'false'})
        return client.upload('/v1/workspace/files/raw?' + query, source_path)

    @server.tool()
    def operon_job_figure(job_id: str, index: int, format: str = 'png',
                          figure_id: str | None = None, destination: str | None = None) -> dict:
        """Download a rendered report figure (png, pdf, svg, ...) into the workspace.

        index is the zero-based report step that produced the figure; figure_id picks one
        figure when a step reported several. Requires read scope.
        """
        query = {'format': format}
        if figure_id:
            query['figure_id'] = figure_id
        target = _download_target(destination or f'reports/{job_id}-{index}.{format}')
        return client.download('/v1/jobs/' + quote(job_id, safe='') + f'/reports/{int(index)}/figure?'
                               + urlencode(query), target)

    @server.tool()
    def operon_remote_status(brief: bool = True) -> dict:
        """List SSH execution profiles with their connected state.

        brief=True returns the compact summary the desktop list uses; brief=False returns the
        full per-profile status, including the routes and libraries each server advertises.
        """
        return client.request('/remote/summary' if brief else '/remote')

    @server.tool()
    def operon_remote_ensure(profile_id: str) -> dict:
        """Idempotently reconnect a key/agent SSH profile before validate/prepare/run."""
        return client.request('/remote/' + quote(profile_id, safe='') + '/ensure', {})

    @server.tool()
    def operon_remote_install(profile_id: str, force: bool = False,
                              password: str | None = None,
                              passphrase: str | None = None) -> dict:
        """Start installing or upgrading the Operon server on a configured SSH profile.

        force=True lets the remote retire busy tasks and previous installations.
        password/passphrase are forwarded for this install only and never stored, matching
        the desktop install form; omit them when the profile uses a key or an ssh agent.
        Poll operon_remote_install_status for progress.
        """
        secret = {name: value for name, value in
                  (('password', password), ('passphrase', passphrase)) if value}
        return client.request('/remote/' + quote(profile_id, safe='') + '/install',
                              dict(secret, force=force))

    @server.tool()
    def operon_remote_install_status(profile_id: str) -> dict:
        """Read the background server installation/upgrade progress for a profile."""
        return client.request('/remote/' + quote(profile_id, safe='') + '/setup')

    @server.tool()
    def operon_remote_library_plan(profile_id: str) -> dict:
        """Compare the local operator library with a remote server's library.

        Returns the packages that the next synchronisation would install, the
        packages it would remove because the initiating machine does not have
        them, and the packages it cannot reconcile.
        """
        return client.request('/remote/' + quote(profile_id, safe='') + '/library/plan')

    @server.tool()
    def operon_remote_library_sync(profile_id: str) -> dict:
        """Force a remote server's operator library to match this machine.

        Installs missing or differing packages and removes packages that only
        exist on the remote side. Poll operon_remote_library_status.
        """
        return client.request('/remote/' + quote(profile_id, safe='') + '/library/sync', {})

    @server.tool()
    def operon_remote_library_status(profile_id: str) -> dict:
        """Read the background operator-library synchronisation status."""
        return client.request('/remote/' + quote(profile_id, safe='') + '/library/status')

    @server.tool()
    def operon_pool_status(profile_id: str | None = None) -> dict:
        """Show the shared pool: version, owner, workspaces and active tasks.

        Pass profile_id to read that configured remote server's pool.
        """
        if profile_id:
            return client.request('/remote/' + quote(profile_id, safe='') + '/pool')
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
    def operon_job(job_id: str | None = None, view: str = 'brief', wait_seconds: float = 0,
                   id: str | None = None, profile_id: str | None = None) -> dict:
        """Read brief status, or wait internally up to 120 seconds; a closed window returns running with wait_timed_out, never a failure."""
        import math
        from .agent_views import job_view, wait_job
        job_id = job_id or id
        if not job_id:
            raise ValueError('job_id is required')
        if not math.isfinite(wait_seconds) or not 0 <= wait_seconds <= 120:
            raise ValueError('wait_seconds must be between 0 and 120')
        job_view({}, view)
        if profile_id:
            import time
            from .agent_views import ACTIVE
            path = ('/remote/' + quote(profile_id, safe='') + '/jobs/' +
                    quote(job_id, safe=''))
            job = client.request(path)
            if wait_seconds:
                deadline = time.monotonic() + wait_seconds
                while job.get('status') in ACTIVE:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        return job_view({**job, 'wait_timed_out': True}, view)
                    time.sleep(min(0.5, remaining))
                    job = client.request(path)
            return job_view(job, view)
        try:
            job = client.request('/v1/jobs/' + quote(job_id, safe='') + '?view=' + view)
        except ClientError as error:
            if error.code != 'unknown_job':
                raise
            try:
                return client.request('/v1/large-resources/operations/' + quote(job_id, safe=''))
            except ClientError as missing:
                if missing.code != 'unknown_resource_operation':
                    raise
                raise ClientError(f'unknown job or resource operation: {job_id}', 'unknown_job') from missing
        return wait_job(client, job, wait_seconds, view=view) if wait_seconds else job

    @server.tool()
    def operon_cancel(job_id: str, profile_id: str | None = None) -> dict:
        """Cancel a running job locally or on a configured remote server.

        Requires --allow-run. Pass profile_id to cancel a job on that remote server.
        """
        if profile_id:
            return client.request('/remote/' + quote(profile_id, safe='') + '/jobs/'
                                  + quote(job_id, safe='') + '/cancel', {})
        return client.request('/v1/jobs/' + quote(job_id, safe='') + '/cancel', {})

    @server.tool()
    def operon_plugin_install(wheel: str) -> dict:
        """Install an explicitly selected trusted local plugin wheel. Requires --allow-plugins."""
        return client.request("/plugins/install", {"wheel": wheel})

    @server.tool()
    def operon_nodes(profile_id: str | None = None, refresh: bool = False) -> dict:
        """Discover compute nodes and their free CPU, memory, disk and GPU capacity.

        Read-only. ``target`` is the profile id used by execution settings
        (``local`` for this desktop) and ``score`` ranks free capacity: automatic
        placement prefers available nodes in descending score order. Pass
        profile_id to read one node; refresh=true bypasses the short cache.
        """
        suffix = '?refresh=1' if refresh else ''
        if profile_id:
            return client.request('/v1/nodes/' + quote(profile_id, safe='') + suffix)
        return client.request('/v1/nodes' + suffix)

    @server.tool()
    def operon_resources(profile_id: str | None = None) -> dict:
        """List the large resources declared by the installed library.

        Read-only. Each item reports presence, downloaded files, size, the
        declared HTTPS downloads, the official link units (``units``: name,
        state missing|downloaded|linked, source) and which environments and
        operators consume it. Use operon_resource_download to fetch one or
        operon_resource_link to attach an existing local tree or a single unit.
        Pass profile_id to inspect a configured remote server instead of this host.
        """
        if profile_id:
            return client.request('/remote/' + quote(profile_id, safe='') + '/resources')
        return client.request('/v1/large-resources')

    @server.tool()
    def operon_resource_download(name: str, root: str | None = None,
                                 overwrite: bool = False, unit: str | None = None,
                                 profile_id: str | None = None) -> dict:
        """Start one declared resource download; returns the durable operation id.

        ``unit`` selects one official maintenance unit (for example ``afdb``) and
        downloads only the files of that unit that are still missing; existing
        files are kept. Pass profile_id to download on a configured remote
        server. Poll operon_resources or operon_job(operation id).
        Requires --allow-plugins.
        """
        payload: dict = {'overwrite': bool(overwrite)}
        if root:
            payload['root'] = root
        if unit:
            payload['unit'] = unit
        if profile_id:
            return client.request('/remote/' + quote(profile_id, safe='') + '/resources/' +
                                  quote(name, safe='') + '/download', payload)
        return client.request('/v1/large-resources/' + quote(name, safe='') + '/download', payload)

    @server.tool()
    def operon_resource_link(name: str, source: str, replace: bool = False,
                             unit: str | None = None,
                             profile_id: str | None = None) -> dict:
        """Link an official maintenance unit into a resource root; copy no bytes.

        ``unit`` is either ``tree`` (upstream ships one directory, such as the
        AlphaFold-2 ``afdb`` bundle) or one expected file name (upstream keeps
        weights and databases apart). The source is any readable absolute path
        on the target host; no bytes are copied. Pass profile_id to link a path
        that lives on a configured remote server. Requires --allow-plugins.
        """
        payload: dict = {'source': source, 'replace': bool(replace)}
        if unit:
            payload['unit'] = unit
        if profile_id:
            return client.request('/remote/' + quote(profile_id, safe='') + '/resources/' +
                                  quote(name, safe='') + '/link', payload)
        return client.request('/v1/large-resources/' + quote(name, safe='') + '/link', payload)

    @server.tool()
    def operon_resource_unlink(name: str, unit: str | None = None,
                               profile_id: str | None = None) -> dict:
        """Remove one external link; the source tree is kept.

        ``unit`` selects the link to remove (``tree`` or one expected file
        name); omit it to remove the whole-resource link. Pass profile_id to act
        on a configured remote server. Requires --allow-plugins.
        """
        suffix = '' if not unit else '?unit=' + quote(unit, safe='')
        if profile_id:
            return client.request('/remote/' + quote(profile_id, safe='') + '/resources/' +
                                  quote(name, safe='') + '/link' + suffix, method='DELETE')
        return client.request('/v1/large-resources/' + quote(name, safe='') + '/link' + suffix,
                              method='DELETE')

    @server.tool()
    def operon_resource_cancel(name: str, profile_id: str | None = None) -> dict:
        """Cancel the active download of one resource. Requires --allow-run.

        Pass profile_id to cancel a download on that configured remote server.
        """
        if profile_id:
            return client.request('/remote/' + quote(profile_id, safe='') + '/resources/' +
                                  quote(name, safe='') + '/cancel', {})
        return client.request('/v1/large-resources/' + quote(name, safe='') + '/cancel', {})

    @server.tool()
    def operon_resource_log(name: str, limit: int = 200, profile_id: str | None = None) -> dict:
        """Read the tail of one resource download log (at most 2000 lines).

        Pass profile_id to read the log kept on that configured remote server.
        """
        suffix = ('/resources/' + quote(name, safe='') + '/log?limit=' +
                  str(max(1, min(int(limit), 2000))))
        if profile_id:
            return client.request('/remote/' + quote(profile_id, safe='') + suffix)
        return client.request('/v1/large-resources/' + quote(name, safe='') + '/log?limit=' +
                              str(max(1, min(int(limit), 2000))))

    @server.tool()
    def operon_library_install(path: str, name: str | None = None,
                               version: str | None = None) -> dict:
        """Install an operator library bundle as ``<name>-v<version>``.

        Libraries are equal-status branches (main, fork1, ...); operator and
        Reader ids must not overlap. Requires --allow-plugins.
        """
        payload = {'path': path}
        if name:
            payload['name'] = name
        if version:
            payload['version'] = version
        return client.request('/v1/libraries/install', payload)

    @server.tool()
    def operon_library_list() -> dict:
        """List installed operator-library branches."""
        return client.request('/v1/libraries')

    @server.tool()
    def operon_library_remove(name: str) -> dict:
        """Remove one operator-library branch. Other branches stay usable.

        Requires --allow-plugins.
        """
        return client.request('/v1/libraries/' + quote(name, safe=''), method='DELETE')

    @server.tool()
    def operon_routes_import(path: str) -> dict:
        """Import a route collection whose exact pins match the installed library."""
        return client.request('/v1/routes/import-collection', {'path': path})

    @server.tool()
    def operon_capabilities() -> dict:
        """Describe the service: API and protocol versions, capabilities and permission scopes."""
        return client.request('/v1/capabilities')

    @server.tool()
    def operon_service_status() -> dict:
        """Report the running service instance, headless mode and active jobs."""
        return client.request('/v1/service')

    @server.tool()
    def operon_service_stop() -> dict:
        """Stop a headless service once it has no active job. Requires --allow-run."""
        return client.request('/v1/service/stop', {})

    @server.tool()
    def operon_engine_status() -> dict:
        """Read engine queues, capacity and managed memory for this workspace."""
        return client.request('/v1/engine')

    @server.tool()
    def operon_engine_events(after: int = 0, limit: int = 200) -> dict:
        """Read resumable engine events after a cursor; pass the returned offset as ``after``."""
        return client.request('/v1/engine/events?' +
                              urlencode({'after': int(after), 'limit': int(limit)}))

    @server.tool()
    def operon_environment_status() -> dict:
        """Read the resolved operator environment without preparing it."""
        return client.request('/v1/environment')

    @server.tool()
    def operon_resource_limits() -> dict:
        """Report the CPU, memory and disk limits available to execution slots."""
        return client.request('/v1/resources')

    @server.tool()
    def operon_job_parameters(job_id: str) -> dict:
        """Read the exact parameters, execution settings and plugin lock of a submitted job."""
        return client.request('/v1/jobs/' + quote(job_id, safe='') + '/parameters')

    @server.tool()
    def operon_viewers(refresh: bool = False) -> dict:
        """List desktop result viewers and the formats they claim."""
        return client.request('/v1/viewers' + ('?refresh=true' if refresh else ''))

    @server.tool()
    def operon_viewer_configure(viewer: str, executable: str | None = None) -> dict:
        """Point one desktop viewer at an executable, or clear it. Requires --allow-run."""
        return client.request('/v1/viewers/' + quote(viewer, safe='') + '/configure',
                              {'executable': executable})

    @server.tool()
    def operon_viewer_default(extension: str, viewer: str | None = None) -> dict:
        """Choose the default viewer for one extension; omit the viewer to restore automatic selection."""
        return client.request('/v1/viewers/default', {'extension': extension, 'viewer': viewer})

    @server.tool()
    def operon_viewer_prepare(job_id: str, artifact_id: str, role: str) -> dict:
        """Materialise one retained artifact file so a desktop viewer can open it."""
        return client.request('/v1/jobs/' + quote(job_id, safe='') + '/artifacts/' +
                              quote(artifact_id, safe='') + '/prepare-viewer', {'role': role})

    @server.tool()
    def operon_storage_roots() -> dict:
        """List the storage roots explicitly configured for this profile."""
        return client.request('/v1/storage/roots')

    @server.tool()
    def operon_storage_browse(storage_id: str, path: str = '.', page_size: int | None = None,
                              cursor: str | None = None, hidden: bool = False) -> dict:
        """Browse one storage root a page at a time; pass the returned ``next_cursor`` as ``cursor``."""
        payload = {'storage_id': storage_id, 'relative_path': path, 'hidden': bool(hidden)}
        if page_size is not None:
            payload['page_size'] = int(page_size)
        if cursor:
            payload['cursor'] = cursor
        return client.request('/v1/storage/browse', payload)

    @server.tool()
    def operon_storage_stat(storage_id: str, path: str) -> dict:
        """Read one storage entry's kind, size, digest and modified time without opening it."""
        return client.request('/v1/storage/stat',
                              {'storage_id': storage_id, 'relative_path': path})

    @server.tool()
    def operon_storage_preview(storage_id: str, path: str, byte_limit: int | None = None,
                               row_limit: int | None = None) -> dict:
        """Read a bounded preview of a stored text or table file."""
        payload = {'storage_id': storage_id, 'relative_path': path}
        if byte_limit is not None:
            payload['byte_limit'] = int(byte_limit)
        if row_limit is not None:
            payload['row_limit'] = int(row_limit)
        return client.request('/v1/storage/preview', payload)

    @server.tool()
    def operon_storage_close() -> dict:
        """Close every storage browse cursor this connection still holds."""
        return client.request('/v1/storage/browse/close', {})

    @server.tool()
    def operon_storage_status() -> dict:
        """Report storage roots, open browse cursors and handle usage."""
        return client.request('/v1/storage/status')

    @server.tool()
    def operon_plugins() -> dict:
        """List installed plugins and their declared dependency state."""
        return client.request('/plugins')

    @server.tool()
    def operon_remote_save(profile: dict) -> dict:
        """Create or update one configured server profile."""
        return client.request('/v1/remotes', profile)

    @server.tool()
    def operon_remote_connect(profile_id: str, password: str | None = None,
                              passphrase: str | None = None) -> dict:
        """Connect to a configured server; secrets are forwarded for this call, never stored."""
        payload = {name: value for name, value in
                   (('password', password), ('passphrase', passphrase)) if value}
        return client.request('/v1/remotes/' + quote(profile_id, safe='') + '/connect', payload)

    @server.tool()
    def operon_remote_trust(profile_id: str, fingerprint: str | None = None) -> dict:
        """Trust a server host key, optionally pinning the exact fingerprint."""
        return client.request('/v1/remotes/' + quote(profile_id, safe='') + '/trust',
                              {'fingerprint': fingerprint})

    @server.tool()
    def operon_canvas_prepare(graph: dict, request_id: str) -> dict:
        """Prepare canvas edits for execution or export and return a preparation id."""
        return client.request('/v1/canvas-plans/prepare',
                              {'graph': graph, 'request_id': request_id})

    @server.tool()
    def operon_canvas_status(request_id: str) -> dict:
        """Read the progress of one canvas preparation."""
        return client.request('/v1/canvas-plans/status?' + urlencode({'request_id': request_id}))

    @server.tool()
    def operon_canvas_cancel(request_id: str) -> dict:
        """Cancel a pending canvas preparation. Requires --allow-run."""
        return client.request('/v1/canvas-plans/cancel', {'request_id': request_id})

    @server.tool()
    def operon_canvas_execute(preparation_id: str, request_id: str, action: str,
                              output: str | None = None) -> dict:
        """Run or export one prepared canvas plan. Requires --allow-run."""
        return client.request('/v1/canvas-plans/execute',
                              {'preparation_id': preparation_id, 'request_id': request_id,
                               'action': action, 'output': output})

    @server.tool()
    def operon_canvas_history() -> dict:
        """List recent canvas preparations for this workspace."""
        return client.request('/v1/canvas-plans/history')

    @server.tool()
    def operon_canvas_outcome(request_id: str) -> dict:
        """Read the finished outcome of one canvas execution."""
        return client.request('/v1/canvas-plans/outcome?' + urlencode({'request_id': request_id}))


    @server.tool()
    def operon_preferences() -> dict:
        """Read the profile's preferences: language, theme and the default parallel task count.

        parallel_tasks is the same default the desktop's Settings -> Execution field writes;
        a graph that sets runtime.execution.max_parallel_tasks still overrides it.
        """
        return client.request('/v1/preferences')

    @server.tool()
    def operon_preferences_save(preferences: dict, initialize: bool = False) -> dict:
        """Persist preferences (language, theme, parallel_tasks); requires edit scope.

        parallel_tasks is 0 (unlimited), 1-64, or null for the built-in default of 2; it is the same setting the
        desktop exposes under Settings -> Execution.
        """
        return client.request('/v1/preferences', {'preferences': preferences, 'initialize': initialize})

    @server.tool()
    def operon_workspace() -> dict:
        """Read the saved canvas workspace, or null when the profile has none."""
        return client.request('/v1/workspace')

    @server.tool()
    def operon_workspace_save(workspace: dict) -> dict:
        """Persist a complete canvas workspace; requires edit scope."""
        return client.request('/v1/workspace', workspace)

    @server.tool()
    def operon_version() -> dict:
        """Read the product build and version information."""
        return client.request('/v1/version')

    @server.tool()
    def operon_routes() -> list:
        """List registered workflow routes."""
        return client.request('/v1/routes')

    @server.tool()
    def operon_routes_register(workflow_ids: list[str]) -> list:
        """Register saved workflows as routes; requires edit scope."""
        return client.request('/v1/routes/register', {'workflow_ids': workflow_ids})

    @server.tool()
    def operon_library_state() -> dict:
        """Read disabled and hidden operator-library entries."""
        return client.request('/v1/library/state')

    @server.tool()
    def operon_library_manage(key: str, action: str) -> dict:
        """Disable, enable, restore or delete one library entry; requires edit scope."""
        return client.request('/v1/library/manage', {'key': key, 'action': action})

    @server.tool()
    def operon_route_collections() -> dict:
        """List installed route collections."""
        return client.request('/v1/route-collections')

    @server.tool()
    def operon_route_collection_remove(slug: str) -> dict:
        """Uninstall one route collection; requires edit scope."""
        return client.request('/v1/route-collections/' + quote(slug, safe=''), method='DELETE')

    @server.tool()
    def operon_routes_import_archive(source: str | None = None, content_base64: str | None = None) -> dict:
        """Import a route archive ZIP from a local path or base64 content; requires edit scope."""
        data = _payload(source, content_base64)
        return client.request('/v1/routes/import-archive', {'content_base64': base64.b64encode(data).decode('ascii')})

    @server.tool()
    def operon_workflow_import(source: str | None = None, content_base64: str | None = None) -> dict:
        """Import a workflow bundle ZIP from a local path or base64 content; requires edit scope."""
        data = _payload(source, content_base64)
        return client.request('/v1/workflows/import', {'content_base64': base64.b64encode(data).decode('ascii')})

    @server.tool()
    def operon_workflow_export(graph: dict, destination: str) -> dict:
        """Export a single-environment workflow ZIP into the workspace; returns path and size."""
        target = _download_target(destination)
        return client.download('/v1/workflows/export', target, payload={'graph': graph})

    @server.tool()
    def operon_contracts(graph: dict) -> dict:
        """Analyze reader and operator contracts without running or installing anything."""
        return client.request('/v1/contracts', {'graph': graph})

    @server.tool()
    def operon_graph_export(graph: dict) -> dict:
        """Export a workflow as YAML plus execution order; remote graphs use their profile."""
        return client.request('/v1/graphs/export', {'graph': graph})

    @server.tool()
    def operon_graph_import(text: str, base_dir: str = '.') -> dict:
        """Import workflow YAML into a graph; requires edit scope."""
        return client.request('/v1/graphs/import', {'text': text, 'base_dir': base_dir})

    @server.tool()
    def operon_execution_plan(graph: dict) -> dict:
        """Build a multi-environment execution plan without submitting it."""
        return client.request('/v1/execution/plan', {'graph': graph})

    @server.tool()
    def operon_execution_resources() -> dict:
        """Read host resources available for multi-environment execution."""
        return client.request('/v1/execution/resources')

    @server.tool()
    def operon_plugins_refresh() -> dict:
        """Rescan plugin source directories and refresh the catalog; requires plugins scope."""
        return client.request('/v1/plugins/refresh', {})

    @server.tool()
    def operon_plugins_dependencies() -> dict:
        """Check and repair plugin dependencies; requires plugins scope."""
        return client.request('/v1/plugins/dependencies', {})

    @server.tool()
    def operon_plugins_remove(name: str) -> dict:
        """Uninstall one plugin package; requires plugins scope."""
        return client.request('/v1/plugins/remove', {'name': name})

    @server.tool()
    def operon_plugins_manage(name: str, action: str) -> dict:
        """Enable, disable or restore one plugin package; requires plugins scope."""
        return client.request('/v1/plugins/manage', {'name': name, 'action': action})

    @server.tool()
    def operon_script_inspect(filename: str, code: str, script: dict | None = None) -> dict:
        """Validate a script operator source and list parameter candidates without running it."""
        return client.request('/v1/scripts/inspect', {'filename': filename, 'code': code, 'script': script})

    @server.tool()
    def operon_script_extract(script: dict, names: list[str]) -> dict:
        """Extract parameter declarations for named script values."""
        return client.request('/v1/scripts/extract', {'script': script, 'names': names})

    @server.tool()
    def operon_script_publish(script: dict, operator_id: str, title: str, category: str = 'data',
                              version: str = '0.1.0') -> dict:
        """Package and install one saved script operator; requires plugins scope."""
        return client.request('/v1/scripts/publish', {'script': script, 'operator_id': operator_id,
                                                      'title': title, 'category': category, 'version': version})

    @server.tool()
    def operon_operator_source(identifier: str) -> dict:
        """Read the exact registered source for one operator when it is available."""
        return client.request('/v1/operators/' + quote(identifier, safe='') + '/source')

    @server.tool()
    def operon_job_export(job_id: str, index: int) -> dict:
        """Read one small step report; large reports return a download message instead."""
        return client.request('/v1/jobs/' + quote(job_id, safe='') + '/exports/' + str(int(index)))

    @server.tool()
    def operon_remote_refresh(profile_id: str, verify_all: bool = False) -> dict:
        """Refresh one remote profile over its authorized SSH channel; requires edit scope."""
        return client.request('/v1/remotes/' + quote(profile_id, safe='') + '/refresh', {'verify_all': verify_all})

    @server.tool()
    def operon_remote_disconnect(profile_id: str) -> dict:
        """Disconnect one saved remote profile; requires edit scope."""
        return client.request('/v1/remotes/' + quote(profile_id, safe='') + '/disconnect', {})

    @server.tool()
    def operon_remote_remove(profile_id: str) -> dict:
        """Remove one saved remote profile; requires edit scope."""
        return client.request('/v1/remotes/' + quote(profile_id, safe='') + '/remove', {})

    @server.tool()
    def operon_remote_source(profile_id: str) -> dict:
        """Read source availability for one remote profile.

        Known limitation: the desktop route POSTs {'path': ..., 'reader': ...} to import one
        source file, but the /v1 route this tool reaches ignores the body, so the tool can
        only report availability. See docs/design/mcp_http_parity.md.
        """
        return client.request('/v1/remotes/' + quote(profile_id, safe='') + '/source', {})

    @server.tool()
    def operon_remote_library_check(profile_id: str) -> dict:
        """Check the remote library state for one profile."""
        return client.request('/v1/remotes/' + quote(profile_id, safe='') + '/library/check', {})

    @server.tool()
    def operon_remote_library_install(profile_id: str, request: dict | None = None) -> dict:
        """Start a remote library install for one profile; requires plugins scope."""
        return client.request('/v1/remotes/' + quote(profile_id, safe='') + '/library/install', request or {})

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
    from .installation_maintenance import require_idle
    require_idle()
    require_installation()
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
