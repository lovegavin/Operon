"""HTTP adapters for the shared application plan service; execution is explicit."""
import uuid
from typing import Annotated, Literal
from urllib.parse import quote

from fastapi import Path, Query, Request
from fastapi.responses import JSONResponse, StreamingResponse
from starlette.background import BackgroundTask

from .contracts.base import ContractError, ContractModel
from .contracts.plan_operations import PlanCompileRequest, PlanSubmitRequest
from .contracts.plan_export import PlanExportRequest
from .plan_service import PlanOperationError
from .storage import StorageError
from .storage.configuration import PROFILE_OWNER


class CancelPlanRequest(ContractModel):
    pass


RunId = Annotated[str, Path(min_length=1, max_length=200, pattern=r'^[A-Za-z0-9_.:-]+$')]


def mount_plans(app, application, bridge):
    from .plan_binding_options import mount_binding_options
    mount_binding_options(app, application, bridge)
    from .plan_ui_state import mount_plan_ui_state
    mount_plan_ui_state(app, application, bridge)
    @app.exception_handler(ContractError)
    async def operation_error(request, error):
        payload = error.to_json()
        payload['request_id'] = uuid.uuid4().hex
        retry = getattr(error, 'retry_after', None)
        if retry is not None:
            payload['retry_after'] = retry
        status = {'engine_unavailable': 503, 'submission_unknown': 503,
                  'stale_plan_identity': 409, 'idempotency_conflict': 409,
                  'export_not_found': 404, 'export_busy': 429, 'export_queue_full': 429,
                  'export_destination_busy': 409, 'export_owner_required': 409,
                  'export_unavailable': 503}.get(error.code, getattr(error, 'status', 422))
        return JSONResponse(payload, status_code=status)

    async def invoke(function, *, lifecycle=False):
        try:
            # Reuse bounded application offload; scientific ownership stays in
            # the host pool. Status/cancel have the reserved lifecycle lane.
            return await application.storage_dispatch.run(function, principal=PROFILE_OWNER,
                                                          lifecycle=lifecycle)
        except StorageError as exc:
            closed = exc.code == 'storage_unavailable'
            error = PlanOperationError('Application operation dispatch is unavailable' if closed
                                       else 'Application operation capacity is occupied',
                                       code='engine_unavailable' if closed else 'busy')
            error.status, error.retry_after = (503, None) if closed else (429, 0.2)
            raise error from exc

    @app.post('/api/v1/plans/compile')
    async def compile_plan(request: Request, payload: PlanCompileRequest):
        bridge.actor(request, 'context')
        return await invoke(lambda: application.plans.compile(payload))

    @app.post('/api/v1/plans', status_code=202)
    async def submit_plan(request: Request, payload: PlanSubmitRequest):
        bridge.actor(request, 'run')
        return await invoke(lambda: application.plans.submit(payload))

    @app.get('/api/v1/plans/{run_id}')
    async def details(run_id: RunId, request: Request):
        bridge.actor(request, 'context')
        return await invoke(lambda: application.plans.details(run_id), lifecycle=True)

    @app.post('/api/v1/plans/{run_id}/cancel')
    async def cancel(run_id: RunId, request: Request, payload: CancelPlanRequest | None = None):
        bridge.actor(request, 'run')
        return await invoke(lambda: application.plans.cancel(run_id), lifecycle=True)

    def read_query(request, values):
        # Query scalars are decoded by FastAPI before entering strict shared
        # models. Reject extra selectors instead of silently ignoring paths.
        if set(request.query_params) - set(values) or any(len(request.query_params.getlist(key)) != 1
                                                         for key in request.query_params):
            raise PlanOperationError('Unknown plan result query fields', code='invalid_plan_query')
        return values

    @app.get('/api/v1/plans/{run_id}/events')
    async def events(run_id: RunId, request: Request, after: int = Query(0, ge=0, le=2**63 - 1),
                     limit: int = Query(100, ge=1, le=200), max_bytes: int = Query(32768, ge=2048, le=65536)):
        bridge.actor(request, 'context')
        values = read_query(request, dict(after=after, limit=limit, max_bytes=max_bytes))
        return await invoke(lambda: application.plans.events(run_id, **values))

    @app.get('/api/v1/plans/{run_id}/attempts')
    async def attempts(run_id: RunId, request: Request,
                       after: str = Query('', max_length=600, pattern=r'^[A-Za-z0-9_.:/-]*$'),
                       limit: int = Query(100, ge=1, le=200), max_bytes: int = Query(32768, ge=2048, le=65536)):
        bridge.actor(request, 'context')
        values = read_query(request, dict(after=after, limit=limit, max_bytes=max_bytes))
        return await invoke(lambda: application.plans.attempts(run_id, **values))

    @app.get('/api/v1/plans/{run_id}/artifacts')
    async def artifacts(run_id: RunId, request: Request,
                        after: str = Query('', max_length=600, pattern=r'^[A-Za-z0-9_.:/-]*$'),
                        limit: int = Query(100, ge=1, le=200), max_bytes: int = Query(32768, ge=2048, le=65536)):
        bridge.actor(request, 'context')
        values = read_query(request, dict(after=after, limit=limit, max_bytes=max_bytes))
        return await invoke(lambda: application.plans.artifacts(run_id, **values))

    @app.get('/api/v1/plans/{run_id}/logs')
    async def logs(run_id: RunId, request: Request,
                   attempt_id: str = Query(..., min_length=1, max_length=200, pattern=r'^[A-Za-z0-9_.:-]+$'),
                   offset: int = Query(0, ge=0, le=2**63 - 1), max_bytes: int = Query(16384, ge=1, le=65536),
                   encoding: Literal['text', 'base64'] = 'text'):
        bridge.actor(request, 'context')
        values = read_query(request, dict(attempt_id=attempt_id, offset=offset, max_bytes=max_bytes, encoding=encoding))
        return await invoke(lambda: application.plans.logs(run_id, **values))

    @app.get('/api/v1/plans/{run_id}/artifacts/{artifact_id}/files')
    async def artifact_files(run_id: RunId, artifact_id: RunId, request: Request,
                             after: str = Query('', max_length=64, pattern=r'^[a-f0-9]*$'),
                             limit: int = Query(100, ge=1, le=200), max_bytes: int = Query(32768, ge=2048, le=65536)):
        bridge.actor(request, 'context')
        values = read_query(request, dict(after=after, limit=limit, max_bytes=max_bytes))
        return await invoke(lambda: application.plans.artifact_files(run_id, artifact_id=artifact_id, **values))

    @app.get('/api/v1/plans/{run_id}/artifacts/{artifact_id}/files/{file_id}/preview')
    async def artifact_preview(run_id: RunId, artifact_id: RunId, request: Request,
                               file_id: str = Path(pattern=r'^[a-f0-9]{64}$'),
                               max_bytes: int = Query(16384, ge=1, le=65536), max_rows: int = Query(100, ge=1, le=1000)):
        bridge.actor(request, 'context')
        values = read_query(request, dict(max_bytes=max_bytes, max_rows=max_rows))
        return await invoke(lambda: application.plans.artifact_preview(run_id, artifact_id=artifact_id,
                                                                       file_id=file_id, **values))

    @app.get('/api/v1/plans/{run_id}/artifacts/{artifact_id}/files/{file_id}/open')
    async def artifact_open(run_id: RunId, artifact_id: RunId, request: Request,
                            file_id: str = Path(pattern=r'^[a-f0-9]{64}$'), inline: bool = False):
        bridge.actor(request, 'context')
        read_query(request, dict(inline=inline))
        opened = await invoke(lambda: application.plans.open_artifact(run_id, artifact_id=artifact_id, file_id=file_id))
        item = opened.descriptor
        # SVG/HTML and other active formats never share the application origin inline.
        disposition = 'inline' if inline and item['media_type'] in ('image/png', 'image/jpeg', 'image/gif', 'image/webp') else 'attachment'
        headers = {'Content-Disposition': disposition + "; filename*=UTF-8''" + quote(item['name'].split('/')[-1], safe=''),
                   'Content-Length': str(item['size_bytes']), 'X-Content-Type-Options': 'nosniff',
                   'Content-Security-Policy': "sandbox; default-src 'none'", 'Cache-Control': 'private, no-store',
                   'ETag': '"' + item['sha256'] + '"'}
        return StreamingResponse(opened.chunks(), media_type=item['media_type'], headers=headers,
                                 background=BackgroundTask(opened.close))

    @app.post('/api/v1/plan-exports', status_code=202)
    async def submit_export(request: Request, payload: PlanExportRequest):
        bridge.actor(request, 'run')
        return await invoke(lambda: application.plan_exports.submit(payload))

    @app.get('/api/v1/plan-exports/lookup')
    async def lookup_export(request: Request, request_id: str):
        bridge.actor(request, 'context')
        return await invoke(lambda: application.plan_exports.details(request_id=request_id), lifecycle=True)

    @app.get('/api/v1/plan-exports/{export_id}')
    async def export_details(export_id: str, request: Request):
        bridge.actor(request, 'context')
        return await invoke(lambda: application.plan_exports.details(export_id), lifecycle=True)

    @app.post('/api/v1/plan-exports/{export_id}/cancel')
    async def export_cancel(export_id: str, request: Request, payload: CancelPlanRequest | None = None):
        bridge.actor(request, 'run')
        return await invoke(lambda: application.plan_exports.cancel(export_id), lifecycle=True)
