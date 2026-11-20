"""Versioned application API, mounted by both desktop and headless hosts."""
import base64
import binascii
from pathlib import Path

import yaml
from fastapi import Request
from fastapi.responses import FileResponse, Response, JSONResponse
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, ConfigDict, Field, model_validator
from typing import Literal

from .documents import CommandError
from .bytecode import io_path


class GraphRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    graph: dict


class ValidationRequest(GraphRequest):
    require_files: bool = False


class WorkflowRequest(GraphRequest):
    workflow_id: str | None = None
    expected_version: int | None = Field(default=None, ge=1, strict=True)


class SubmissionRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    graph: dict | None = None
    workflow_id: str | None = None
    expected_version: int | None = Field(default=None, ge=1, strict=True)
    request_id: str | None = Field(default=None, min_length=1, max_length=200)

    @model_validator(mode='after')
    def one_source(self):
        if (self.graph is not None) == bool(self.workflow_id):
            raise ValueError('Provide exactly one graph or workflow_id')
        if self.workflow_id and self.expected_version is None:
            raise ValueError('Saved workflow submission requires expected_version')
        return self


class EnvironmentRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    names: list[str] | None = Field(default=None, max_length=20)
    dependencies: bool = False


class TaskRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    base_dir: str = Field(min_length=1, max_length=200)
    folders: list[str] | None = Field(default=None, max_length=20)


class WorkspaceFileRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    path: str = Field(min_length=1, max_length=500)
    content: str
    overwrite: bool = True


class WorkspaceBinaryRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    path: str = Field(min_length=1, max_length=500)
    content: str
    overwrite: bool = True


class DescribeRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    ids: list[str] = Field(min_length=1, max_length=20)
    sections: list[str] | None = Field(default=None, max_length=30)
    generation: str | None = None
    view: Literal['schema', 'docs', 'full'] = 'full'


class LibraryRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    path: str = Field(min_length=1, max_length=1000)
    name: str | None = Field(default=None, max_length=64)
    version: str | None = Field(default=None, max_length=32)


class RouteCollectionRequest(LibraryRequest):
    pass


def _missing_job(error: Exception) -> bool:
    """Whether a backend lookup reported a job that does not exist."""
    if isinstance(error, KeyError):
        return True
    try:
        from .pool_service import PoolClientError
    except Exception:  # pragma: no cover - optional service module
        return False
    if not isinstance(error, PoolClientError):
        return False
    text = str(error).lower()
    return 'unknown' in text or 'not found' in text or 'no such' in text


def _unknown_job(key: str) -> CommandError:
    return CommandError('unknown_job', f'unknown job: {key}', 404)


def mount_control(app, application, bridge):
    from .viewer_api import mount_viewers
    mount_viewers(app, application, bridge)
    from .storage_api import mount_storage
    mount_storage(app, application, bridge)
    from .plan_api import mount_plans
    mount_plans(app, application, bridge)
    def authorize(request, scope='context'):
        return bridge.actor(request, scope)

    @app.exception_handler(RequestValidationError)
    async def invalid_request(request, error):
        if not request.url.path.startswith('/api/v1/'):
            from fastapi.exception_handlers import request_validation_exception_handler
            return await request_validation_exception_handler(request, error)
        details = [{'location': list(item['loc']), 'message': item['msg'], 'type': item['type']} for item in error.errors()]
        return JSONResponse({'code': 'invalid_request', 'message': 'Request does not match the application API schema',
                             'details': details}, status_code=422)

    @app.get('/api/v1/capabilities')
    def capabilities(request: Request):
        authorize(request)
        return {'api_version': 1, 'operator_protocol': 3, 'headless': bool(getattr(app.state, 'headless', False)),
                'capabilities': ['workflows', 'tasks', 'artifacts', 'operator-docs', 'canvas-sessions', 'agent-guides', 'brief-views', 'result-viewers', 'workflow-readiness', 'explicit-environment-preparation', 'transaction-diffs',
                                'task-scaffolding', 'workspace-files', 'workspace-binary-files',
                                'library-install', 'route-collection-import', 'storage-browse', 'storage-preview',
                                'plan-compile', 'plan-submit', 'run-plan-export', 'large-resource-download',
                                'large-resource-link'],
                'guides_href': '/api/v1/guides', 'openapi_href': '/api/v1/openapi.json',
                'permission_scopes': ['context', 'edit', 'run', 'plugins']}

    @app.post('/api/v1/workflows/prepare-environment')
    def prepare_environment(request: Request, payload: GraphRequest):
        authorize(request, 'plugins')
        return application.check_environment(payload.graph, repair=True)

    @app.post('/api/v1/workflows/check-environment')
    def check_environment(request: Request, payload: GraphRequest):
        authorize(request)
        return application.check_environment(payload.graph)

    @app.get('/api/v1/environment')
    def environment_status(request: Request):
        authorize(request)
        return application.environment_status()

    @app.get('/api/v1/environments')
    def environments(request: Request):
        authorize(request)
        return application.isolated_environments()

    @app.post('/api/v1/environments/prepare')
    def prepare_environments(request: Request, payload: EnvironmentRequest):
        authorize(request, 'plugins')
        return {**application.isolated_environments(),
                'dependencies': payload.dependencies,
                'prepared': application.start_isolated_environments(
                    payload.names, dependencies=payload.dependencies)}

    @app.post('/api/v1/environments/{name}/repair')
    def repair_environment(request: Request, name: str):
        authorize(request, 'plugins')
        from . import environment_install
        try:
            result = environment_install.repair(name)
        except ValueError as error:
            raise CommandError('unknown_environment', str(error)) from error
        return {**application.isolated_environments(), 'repair': result}

    @app.get('/api/v1/large-resources')
    def large_resources(request: Request):
        authorize(request)
        from src.web import resource_api
        try:
            return resource_api.snapshot(application.service)
        except ValueError as error:
            raise CommandError('resource_unavailable', str(error)) from error

    @app.post('/api/v1/large-resources/{name}/download')
    def large_resource_download(request: Request, name: str, payload: dict | None = None):
        authorize(request, 'plugins')
        from src.web import resource_api
        body = payload or {}
        try:
            return resource_api.start(application.service, name, body.get('root'),
                                      bool(body.get('overwrite', False)),
                                      str(body.get('unit') or '') or None)
        except KeyError as error:
            raise CommandError('unknown_resource', f'unknown resource: {name}') from error
        except ValueError as error:
            raise CommandError('resource_rejected', str(error), 409) from error

    @app.post('/api/v1/large-resources/{name}/link')
    def large_resource_link(request: Request, name: str, payload: dict | None = None):
        authorize(request, 'plugins')
        from src.web import resource_api
        body = payload or {}
        try:
            return resource_api.link(application.service, name, str(body.get('source') or ''),
                                     bool(body.get('replace', False)),
                                     str(body.get('unit') or '') or None)
        except KeyError as error:
            raise CommandError('unknown_resource', f'unknown resource: {name}') from error
        except resource_api.LinkUnsupported as error:
            raise CommandError('link_unsupported', str(error), 501) from error
        except ValueError as error:
            raise CommandError('link_rejected', str(error), 409) from error

    @app.delete('/api/v1/large-resources/{name}/link')
    def large_resource_unlink(request: Request, name: str, unit: str | None = None):
        authorize(request, 'plugins')
        from src.web import resource_api
        try:
            return resource_api.unlink(application.service, name, unit)
        except KeyError as error:
            raise CommandError('unknown_resource', f'unknown resource: {name}') from error
        except resource_api.LinkUnsupported as error:
            raise CommandError('link_unsupported', str(error), 501) from error
        except ValueError as error:
            raise CommandError('link_rejected', str(error), 409) from error

    @app.post('/api/v1/large-resources/{name}/cancel')
    def large_resource_cancel(request: Request, name: str):
        authorize(request, 'run')
        from src.web import resource_api
        try:
            return resource_api.cancel(application.service, name)
        except KeyError as error:
            raise CommandError('no_running_download', f'no running download: {name}') from error

    @app.get('/api/v1/large-resources/operations/{job_id}')
    def large_resource_operation(request: Request, job_id: str):
        authorize(request)
        from src.web import resource_api
        job = resource_api.operation(job_id)
        if job is None:
            raise CommandError('unknown_resource_operation', f'unknown resource operation: {job_id}')
        return job

    @app.get('/api/v1/large-resources/{name}/log')
    def large_resource_log(request: Request, name: str, limit: int = 200):
        authorize(request)
        from src.web import resource_api
        try:
            return resource_api.read_log(application.service, name, limit)
        except KeyError as error:
            raise CommandError('unknown_resource', f'unknown resource: {name}') from error

    @app.get('/api/v1/libraries')
    def libraries(request: Request):
        authorize(request)
        from .library_install import libraries_view
        return libraries_view(application.service.plugins)

    @app.post('/api/v1/libraries/install')
    def install_library(request: Request, payload: LibraryRequest):
        authorize(request, 'plugins')
        from .library_install import install_library as install
        try:
            result = install(application.service.plugins, payload.path, name=payload.name, version=payload.version)
        except ValueError as error:
            raise CommandError('library_install_failed', str(error)) from error
        application.service.refresh_catalog()
        return result

    @app.delete('/api/v1/libraries/{name}')
    def remove_library(request: Request, name: str):
        authorize(request, 'plugins')
        from .library_install import uninstall_library
        try:
            result = uninstall_library(application.service.plugins, name)
        except ValueError as error:
            raise CommandError('library_remove_failed', str(error)) from error
        application.service.refresh_catalog()
        return result

    @app.post('/api/v1/routes/import-collection')
    def import_route_collection(request: Request, payload: RouteCollectionRequest):
        authorize(request, 'edit')
        from .library_install import install_routes_collection
        try:
            return install_routes_collection(application.service, payload.path)
        except ValueError as error:
            raise CommandError('route_collection_import_failed', str(error)) from error

    @app.post('/api/v1/tasks')
    def task_scaffold(request: Request, payload: TaskRequest):
        authorize(request, 'edit')
        return application.task_files.scaffold(payload.base_dir, payload.folders)

    @app.post('/api/v1/workspace/files')
    def write_workspace_file(request: Request, payload: WorkspaceFileRequest):
        authorize(request, 'edit')
        return application.task_files.write_text(payload.path, payload.content, payload.overwrite)

    @app.post('/api/v1/workspace/files/binary')
    def write_workspace_binary(request: Request, payload: WorkspaceBinaryRequest):
        authorize(request, 'edit')
        try:
            data = base64.b64decode(payload.content, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise CommandError('invalid_content', f'content must be base64-encoded bytes: {exc}', 422) from exc
        return application.task_files.write_binary(payload.path, data, payload.overwrite)

    @app.get('/api/v1/guides')
    def guides(request: Request):
        authorize(request)
        from .guidance import guide
        return guide('index')

    @app.get('/api/v1/guides/{topic}')
    def guide_topic(topic: str, request: Request, if_sha256: str | None = None):
        authorize(request)
        from .guidance import guide
        return guide(topic, if_sha256=if_sha256)

    @app.get('/api/v1/openapi.json', include_in_schema=False)
    def api_schema(request: Request):
        authorize(request)
        from copy import deepcopy
        schema = deepcopy(app.openapi())
        schema['paths'] = {path: value for path, value in schema['paths'].items() if path.startswith('/api/v1/')}
        schema.setdefault('components', {}).setdefault('securitySchemes', {})['OperonToken'] = {'type': 'http', 'scheme': 'bearer'}
        schema['security'] = [{'OperonToken': []}]
        return schema

    @app.get('/api/v1/workflows')
    def workflows(request: Request):
        authorize(request)
        return application.workflows.list()

    @app.post('/api/v1/workflows/prepare')
    def prepare(request: Request, payload: GraphRequest):
        authorize(request)
        return application.prepare(payload.graph).model_dump(mode='json')

    @app.post('/api/v1/workflows/validate')
    def validate(request: Request, payload: ValidationRequest):
        authorize(request)
        return application.validate(payload.graph, require_files=payload.require_files)

    @app.post('/api/v1/workflows/export')
    def export(request: Request, payload: GraphRequest):
        authorize(request)
        from src.web.parameters import export_bundle
        return Response(export_bundle(application.prepare(payload.graph)), media_type='application/zip')

    @app.post('/api/v1/workflows')
    def save(request: Request, payload: WorkflowRequest):
        authorize(request, 'edit')
        return application.workflows.save(payload.graph, workflow_id=payload.workflow_id,
                                          expected_version=payload.expected_version)

    @app.get('/api/v1/workflows/{key}')
    def workflow(key: str, request: Request):
        authorize(request)
        return application.workflows.get(key)

    @app.post('/api/v1/jobs', status_code=202)
    def submit(request: Request, payload: SubmissionRequest):
        authorize(request, 'run')
        return application.jobs.submit(payload.model_dump(exclude_none=True))

    @app.get('/api/v1/jobs')
    def jobs(request: Request):
        authorize(request)
        return application.jobs.list()

    @app.get('/api/v1/jobs/{key}')
    def job(key: str, request: Request, view: Literal['brief', 'full'] = 'full'):
        authorize(request)
        from .agent_views import job_view
        try:
            detail = application.jobs.details(key)
        except Exception as error:
            if _missing_job(error):
                raise _unknown_job(key) from error
            raise
        return job_view(detail, view)

    @app.post('/api/v1/jobs/{key}/cancel')
    def cancel(key: str, request: Request):
        authorize(request, 'run')
        try:
            return application.jobs.cancel(key)
        except Exception as error:
            if _missing_job(error):
                raise _unknown_job(key) from error
            raise

    @app.get('/api/v1/jobs/{key}/logs')
    def logs(key: str, request: Request, offset: int = 0, limit: int = 65536,
             encoding: Literal['text', 'base64', 'both'] = 'both'):
        authorize(request)
        from .agent_views import log_view
        try:
            entries = application.jobs.logs(key, offset=offset, limit=limit)
        except Exception as error:
            if _missing_job(error):
                raise _unknown_job(key) from error
            raise
        return log_view(entries, encoding)

    @app.get('/api/v1/jobs/{key}/parameters')
    def parameters(key: str, request: Request):
        authorize(request)
        from src.web.models import Graph
        from src.web.parameters import split_graph
        try:
            job = application.jobs.details(key)
        except Exception as error:
            if _missing_job(error):
                raise _unknown_job(key) from error
            raise
        _, values = split_graph(Graph.model_validate(job['graph']))
        return {'job_id': key, 'values': values,
                'execution': job['graph'].get('runtime', {}).get('execution', {}),
                'memory': job['graph'].get('memory', {}), 'plugin_lock': job['graph'].get('plugin_lock', {})}

    @app.get('/api/v1/jobs/{key}/artifacts')
    def artifacts(key: str, request: Request):
        authorize(request)
        return application.artifacts.list(key)

    @app.get('/api/v1/jobs/{key}/artifacts/{artifact_id}')
    def artifact(key: str, artifact_id: str, request: Request):
        authorize(request)
        return application.artifacts.metadata(key, artifact_id)

    @app.get('/api/v1/jobs/{key}/artifacts/{artifact_id}/preview')
    def preview(key: str, artifact_id: str, request: Request, offset: int = 0, limit: int = 100):
        authorize(request)
        return application.artifacts.preview(key, artifact_id, offset=offset, limit=limit)

    @app.get('/api/v1/jobs/{key}/artifacts/{artifact_id}/table')
    def artifact_table(key: str, artifact_id: str, request: Request, offset: int = 0, limit: int = 100):
        authorize(request)
        value = application.artifacts.preview(key, artifact_id, offset=offset, limit=limit)
        return {'artifact_id': artifact_id, 'columns': value.get('columns', []), 'rows': value.get('rows', []),
                'row_labels': value.get('row_labels', []), 'total': value.get('total', 0),
                'offset': value.get('offset', offset), 'limit': value.get('limit', limit), 'descriptor': value.get('descriptor')}

    @app.get('/api/v1/jobs/{key}/artifacts/{artifact_id}/file')
    def artifact_file(key: str, artifact_id: str, request: Request, role: str | None = None):
        authorize(request)
        path = application.artifacts.file(key, artifact_id, role)
        return FileResponse(io_path(path), filename=path.name)

    @app.get('/api/v1/jobs/{key}/results')
    def results(key: str, request: Request):
        authorize(request)
        try:
            return application.artifacts.results(key)
        except Exception as error:
            if _missing_job(error):
                raise _unknown_job(key) from error
            raise

    @app.get('/api/v1/jobs/{key}/results/file')
    def result_file(key: str, path: str, request: Request):
        authorize(request)
        resolved = application.artifacts.result(key, path)
        return FileResponse(io_path(resolved), filename=resolved.name)

    @app.get('/api/v1/jobs/{key}/reports/{index}')
    def report(key: str, index: int, request: Request):
        authorize(request)
        return FileResponse(io_path(application.artifacts.report(key, index)), media_type='application/json')

    @app.get('/api/v1/jobs/{key}/reports/{index}/figure')
    def figure(key: str, index: int, request: Request, format: str | None = None, figure_id: str | None = None):
        authorize(request)
        return FileResponse(io_path(application.artifacts.figure(key, index, format, figure_id)), content_disposition_type='inline')

    @app.get('/api/v1/operators')
    def search(request: Request, query: str = '', kind: str | None = None, category: str | None = None,
               limit: int = 20, offset: int = 0, view: Literal['brief', 'full'] = 'full'):
        authorize(request)
        return application.operator_docs.search(query, kind=kind, category=category, limit=limit, offset=offset, view=view)

    @app.post('/api/v1/operators/describe')
    def describe(request: Request, payload: DescribeRequest):
        authorize(request)
        return application.operator_docs.describe(payload.ids, sections=payload.sections, generation=payload.generation, view=payload.view)

    @app.get('/api/v1/resources')
    def resources(request: Request):
        authorize(request)
        return application.executions.resources()

    @app.get('/api/v1/engine')
    def engine_status(request: Request):
        authorize(request)
        return application.engine_status()

    @app.get('/api/v1/engine/events')
    def engine_events(request: Request, after: int = 0, limit: int = 200):
        authorize(request)
        return application.events(after, limit=max(1, min(int(limit), 1000)))

    @app.get('/api/v1/remotes')
    def remotes(request: Request):
        authorize(request)
        return application.service.remotes.status()

    @app.post('/api/v1/remotes')
    def save_remote(request: Request, payload: dict):
        authorize(request, 'edit')
        return application.service.remotes.save(payload)

    @app.post('/api/v1/remotes/{key}/connect')
    def connect_remote(key: str, request: Request, payload: dict):
        authorize(request, 'run')
        return application.service.remotes.connect(key, {k: str(payload[k]) for k in ('password', 'passphrase') if payload.get(k)})

    @app.post('/api/v1/remotes/{key}/trust')
    def trust_remote(key: str, request: Request, payload: dict):
        authorize(request, 'edit')
        application.service.remotes.trust(key, payload.get('fingerprint'))
        return {'trusted': True}


    # --- Desktop parity: preferences, workspace, routes and library ---
    def _payload_bytes(payload):
        data = payload.get('content_base64') if isinstance(payload, dict) else None
        if not isinstance(data, str) or not data:
            raise CommandError('invalid_request', 'content_base64 is required', 422)
        try:
            return base64.b64decode(data, validate=True)
        except (binascii.Error, ValueError) as error:
            raise CommandError('invalid_content', 'content_base64 is not valid base64', 422) from error

    @app.get('/api/v1/preferences')
    def read_preferences(request: Request):
        authorize(request)
        from src.web.preferences import load
        return load(application.service.directory)

    @app.post('/api/v1/preferences')
    def write_preferences(request: Request, payload: dict):
        authorize(request, 'edit')
        from src.web.preferences import Preferences, save
        values = payload.get('preferences', {})
        if not isinstance(values, dict):
            raise CommandError('invalid_request', 'preferences must be an object', 422)
        return save(application.service.directory, Preferences.model_validate(values), bool(payload.get('initialize', False)))

    @app.get('/api/v1/workspace')
    def read_workspace(request: Request):
        authorize(request)
        return application.service.routes.load_workspace()

    @app.post('/api/v1/workspace')
    def write_workspace(request: Request, payload: dict):
        authorize(request, 'edit')
        from src.web.models import Workspace
        application.service.routes.save_workspace(Workspace.model_validate(payload))
        return {'saved': True}

    @app.get('/api/v1/version')
    def read_version(request: Request):
        authorize(request)
        from operon import build_info
        return build_info.info()

    @app.get('/api/v1/routes')
    def read_routes(request: Request):
        authorize(request)
        return application.service.routes.routes()

    @app.post('/api/v1/routes/register')
    def write_routes(request: Request, payload: dict):
        authorize(request, 'edit')
        from src.web.models import RegisterRoutes
        return application.service.routes.register(RegisterRoutes.model_validate(payload).workflow_ids)

    @app.get('/api/v1/library/state')
    def read_library_state(request: Request):
        authorize(request)
        return application.service.routes.library_state()

    @app.post('/api/v1/library/manage')
    def write_library_state(request: Request, payload: dict):
        authorize(request, 'edit')
        from src.web.models import LibraryAction
        action = LibraryAction.model_validate(payload)
        return application.service.routes.manage_item(action.key, action.action)

    @app.get('/api/v1/route-collections')
    def read_route_collections(request: Request):
        authorize(request)
        from operon.library_install import route_collections
        return route_collections(application.service)

    @app.delete('/api/v1/route-collections/{slug}')
    def delete_route_collection(slug: str, request: Request):
        authorize(request, 'edit')
        from operon.library_install import uninstall_routes_collection
        try:
            result = uninstall_routes_collection(application.service, slug)
        except ValueError as error:
            raise CommandError('collection_missing', str(error), 404) from error
        application.service.refresh_catalog()
        return result

    @app.post('/api/v1/routes/import-archive')
    def import_routes_archive(request: Request, payload: dict):
        authorize(request, 'edit')
        data = _payload_bytes(payload)
        from src.web.route_archive import route_members
        from src.web.parameters import import_bundle
        from operon.pins import strip_pins
        try:
            members = route_members(data)
        except (ValueError, KeyError) as error:
            raise CommandError('invalid_route_archive', str(error), 422) from error
        registered, failed, migrations = {}, [], []
        for name, content in members:
            try:
                graph = import_bundle(content)
                pins = strip_pins(graph)
                if pins:
                    migrations.append({'route': name, 'pins': pins,
                                       'reason': 'Recorded route pins; operators resolve by id against the installed library'})
                key = application.workflows.save(graph)['id']
                for item in application.service.routes.register([key]):
                    registered[item['id']] = item
            except Exception as error:
                failed.append({'name': name, 'error': str(error)})
        if not registered:
            detail = failed[0]['error'] if failed else 'no importable routes'
            raise CommandError('route_import_failed', 'Route package contains no importable routes: ' + detail, 422)
        return {'routes': list(registered.values()), 'failed': failed, 'pin_migrations': migrations}

    @app.post('/api/v1/workflows/import')
    def import_workflow_archive(request: Request, payload: dict):
        authorize(request, 'edit')
        data = _payload_bytes(payload)
        from operon.workflow_archive import is_workflow_archive, import_archive
        from src.web.parameters import import_bundle
        try:
            if is_workflow_archive(data):
                staging = application.service.directory / 'staging'
                staging.mkdir(exist_ok=True)
                return import_archive(data, staging, application.service.root)
            return import_bundle(data).model_dump(mode='json')
        except ValueError as error:
            raise CommandError('workflow_import_failed', str(error), 422) from error

    @app.post('/api/v1/contracts')
    def analyze_contracts(request: Request, payload: GraphRequest):
        authorize(request)
        from src.web.models import Graph
        from src.web.contracts import analyze_graph
        graph = Graph.model_validate(payload.graph)
        settings = application.service.settings
        return analyze_graph(graph, application.catalog_for(graph), settings.root, input_roots=settings.input_roots)

    @app.post('/api/v1/graphs/export')
    def export_graph(request: Request, payload: GraphRequest):
        authorize(request)
        from src.web.models import Graph
        from src.web.graph import compile_graph, project_path, relative_manifest
        from src.web.source_paths import remote_profile
        graph = Graph.model_validate(payload.graph)
        service = application.service
        if application.executions.applies(graph):
            raise CommandError('multi_environment', 'Multi-environment workflows must be exported as a route package.', 409)
        profile = remote_profile(graph)
        if profile:
            return service.remotes.call(profile, 'export', {'graph': graph.model_dump(mode='json')})
        settings, catalog = service.settings, service.plugins.catalog_for(graph, service.base_catalog)
        manifest, order = compile_graph(graph, catalog, settings.root, input_roots=settings.input_roots)
        manifest = relative_manifest(manifest, project_path(settings.root, '.', graph.base_dir), catalog)
        return {'yaml': yaml.safe_dump(manifest, allow_unicode=True, sort_keys=False), 'order': order}

    @app.post('/api/v1/graphs/import')
    def import_graph(request: Request, payload: dict):
        authorize(request, 'edit')
        from src.web.graph import GraphError, import_manifest, input_path, project_path
        from src.web.models import ManifestImport
        model = ManifestImport.model_validate(payload)
        settings, service = application.service.settings, application.service
        try:
            import_root = settings.code_root or settings.root
            raw = yaml.safe_load(model.text)
            if isinstance(raw, dict) and raw.get('format') == 'operon.workflow':
                from operon.workflow_spec import WorkflowError, compile_spec, parse
                try:
                    directory = project_path(settings.root, '.', model.base_dir)
                except GraphError as error:
                    raise WorkflowError('The YAML project base directory must be inside the current workspace: '
                                        + str(settings.root) + '. Copy the complete YAML project there and select '
                                        'its relative directory, or import a complete workflow ZIP.') from error
                return compile_spec(parse(model.text), directory)
            sources = raw.get('sources') if isinstance(raw, dict) else None
            if isinstance(sources, dict) and sources:
                try:
                    if all(input_path(settings.root, source['path'], model.base_dir, settings.input_roots).is_file()
                           for source in sources.values()):
                        import_root = settings.root
                except (GraphError, KeyError, TypeError):
                    pass
            return import_manifest(model.text, model.base_dir, service.catalog, import_root,
                                   input_roots=settings.input_roots).model_dump(mode='json')
        except yaml.YAMLError as error:
            raise CommandError('invalid_yaml', 'YAML is malformed; check indentation and fields.', 422) from error


    # --- Desktop parity: plugins, scripts, execution and remotes ---
    @app.post('/api/v1/plugins/refresh')
    def refresh_plugins(request: Request):
        authorize(request, 'plugins')
        service = application.service
        service.plugins.refresh()
        service.dependencies.sync(service.plugins.state())
        service.refresh_catalog()
        return service.plugins.state()

    @app.post('/api/v1/plugins/dependencies')
    def check_plugin_dependencies(request: Request):
        authorize(request, 'plugins')
        service = application.service
        service.dependencies.check(repair=not service.settings.testing)
        return {'dependencies': service.dependencies.snapshot()}

    @app.post('/api/v1/plugins/remove')
    def remove_plugin(request: Request, payload: dict):
        authorize(request, 'plugins')
        service = application.service
        name = payload.get('name')
        if name not in {item['name'] for item in service.plugins.state()['packages']}:
            raise CommandError('plugin_missing', 'This plugin is not installed.', 422)
        result = service.plugins.install(None, remove=name)
        service.dependencies.sync(service.plugins.state())
        service.refresh_catalog()
        return result or {'removed': name}

    @app.post('/api/v1/plugins/manage')
    def manage_plugin(request: Request, payload: dict):
        authorize(request, 'plugins')
        action, name = payload.get('action'), payload.get('name')
        if action not in {'enable', 'disable', 'restore'} or not isinstance(name, str):
            raise CommandError('invalid_plugin_action', 'Select a valid package and action.', 422)
        service = application.service
        result = service.plugins.manage(name, action)
        service.dependencies.sync(service.plugins.state())
        service.refresh_catalog()
        return result or {'managed': name, 'action': action}

    @app.post('/api/v1/scripts/inspect')
    def inspect_script(request: Request, payload: dict):
        authorize(request, 'edit')
        filename, code = payload.get('filename'), payload.get('code')
        if not isinstance(filename, str) or not isinstance(code, str):
            raise CommandError('invalid_request', 'filename and code are required', 422)
        if Path(filename).name != filename or '/' in filename or '\\' in filename:
            raise CommandError('invalid_filename', 'Script filename must be a basename', 422)
        from operon.script_operators import inspect_source, parameter_candidates, validate_script
        try:
            snapshot = inspect_source(filename, code)
            if payload.get('script') is not None:
                previous = validate_script(payload['script'])
                if previous['language'] != snapshot['language']:
                    raise ValueError('Changing language requires creating a new script operator')
                snapshot['parameters_schema'] = previous['parameters_schema']
                snapshot = validate_script(snapshot)
            candidates = parameter_candidates(snapshot['code']) if snapshot['language'] == 'python' else []
            return {'script': snapshot, 'candidates': candidates}
        except (ValueError, SyntaxError) as error:
            raise CommandError('invalid_script', str(error), 422) from error

    @app.post('/api/v1/scripts/extract')
    def extract_script(request: Request, payload: dict):
        authorize(request, 'edit')
        script, names = payload.get('script'), payload.get('names')
        if not isinstance(script, dict) or not isinstance(names, list):
            raise CommandError('invalid_request', 'script and names are required', 422)
        from operon.script_operators import extract_parameters
        try:
            return extract_parameters(script, names)
        except (ValueError, SyntaxError) as error:
            raise CommandError('invalid_script', str(error), 422) from error

    @app.get('/api/v1/operators/{identifier}/source')
    def read_operator_source(identifier: str, request: Request):
        authorize(request)
        from src.web.script_api import source_for
        return source_for(application.service.plugins, identifier)

    @app.post('/api/v1/scripts/publish')
    def publish_script(request: Request, payload: dict):
        authorize(request, 'plugins')
        from tempfile import TemporaryDirectory
        from operon.script_operators import export_script_package
        from operon.dropins import single_file_wheel
        service = application.service
        script, operator_id, title = payload.get('script'), payload.get('operator_id'), payload.get('title')
        if not isinstance(script, dict) or not isinstance(operator_id, str) or not isinstance(title, str):
            raise CommandError('invalid_request', 'script, operator_id and title are required', 422)
        directory = service.directory / 'script-inspection'
        directory.mkdir(parents=True, exist_ok=True)
        try:
            if any(item['id'] == operator_id for item in service.plugins.state()['descriptors']):
                raise ValueError('This operator ID already exists; choose a distinct ID for this saved script')
            with TemporaryDirectory(dir=directory) as folder:
                project = export_script_package(script, folder, operator_id=operator_id, title=title,
                                                category=payload.get('category', 'data'),
                                                version=payload.get('version', '0.1.0'))
                source = Path(folder) / project['module'] / '__init__.py'
                metadata = {'name': project['package'], 'version': project['version'],
                            'dependencies': ['operon-studio>=3.0.0,<4']}
                source.write_text('OPERON_PLUGIN = ' + repr(metadata) + '\n' + source.read_text(encoding='utf-8'),
                                  encoding='utf-8')
                wheel = single_file_wheel(source, Path(folder) / 'dist')
                service.plugins.install(wheel)
            service.refresh_catalog()
            return {'id': operator_id, 'catalog': service.catalog}
        except ValueError as error:
            raise CommandError('script_publish_failed', str(error), 422) from error

    @app.get('/api/v1/jobs/{key}/exports/{index}')
    def job_export(key: str, index: int, request: Request):
        authorize(request)
        path = application.jobs.backend(key).export_file(key, index)
        if io_path(path).stat().st_size > 4 * 1024 * 1024:
            return {'message': 'The step report is large; download it instead.'}
        from src.web.service import read_json, safe_json
        return safe_json(read_json(path))

    @app.post('/api/v1/execution/plan')
    def execution_plan(request: Request, payload: GraphRequest):
        authorize(request)
        from src.web.models import Graph
        return application.executions.plan(Graph.model_validate(payload.graph))

    @app.get('/api/v1/execution/resources')
    def execution_resources(request: Request):
        authorize(request)
        return application.executions.resources()

    @app.post('/api/v1/remotes/{key}/refresh')
    def refresh_remote(key: str, request: Request, payload: dict | None = None):
        authorize(request, 'edit')
        return application.service.remotes.refresh(key, verify_all=bool((payload or {}).get('verify_all', False)))

    @app.post('/api/v1/remotes/{key}/disconnect')
    def disconnect_remote(key: str, request: Request):
        authorize(request, 'edit')
        application.service.remotes.disconnect(key)
        return {'disconnected': True}

    @app.post('/api/v1/remotes/{key}/remove')
    def remove_remote(key: str, request: Request):
        authorize(request, 'edit')
        application.service.remotes.remove(key)
        return {'removed': True}

    @app.post('/api/v1/remotes/{key}/source')
    def remote_source(key: str, request: Request):
        authorize(request)
        return application.service.remotes.call(key, 'source')

    @app.post('/api/v1/remotes/{key}/library/check')
    def check_remote_library(key: str, request: Request):
        authorize(request)
        return application.service.remotes.check_library(key)

    @app.post('/api/v1/remotes/{key}/library/install')
    def install_remote_library(key: str, request: Request, payload: dict | None = None):
        authorize(request, 'plugins')
        return application.service.remotes.start_library_install(key, payload or {})

    @app.get('/api/v1/service')
    def status(request: Request):
        authorize(request)
        return {'instance_id': bridge.id, 'headless': bool(getattr(app.state, 'headless', False)),
                'jobs': application.jobs.list()}

    @app.post('/api/v1/service/stop')
    def stop(request: Request, payload: dict):
        authorize(request, 'run')
        if not getattr(app.state, 'headless', False):
            raise CommandError('desktop_owned', 'This service is owned by Studio; close its window to stop it', 409)
        callback = getattr(app.state, 'request_shutdown', None)
        if callback is None:
            raise CommandError('shutdown_unavailable', 'This host does not expose a shutdown callback', 409)
        with application.submission_guard:
            active = application.jobs.active_ids()
            if active:
                raise CommandError('jobs_active', 'Cancel or finish active jobs before stopping the service', 409, {'jobs': active})
            application.stopping = True
            callback()
        return {'stopping': True, 'instance_id': bridge.id}
