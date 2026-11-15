"""Small permission-checked adapters; clients never supply generated manifests."""
from fastapi import Request
from pydantic import Field
from .contracts.base import ContractModel
from .storage.configuration import PROFILE_OWNER


class PrepareCanvas(ContractModel):
    graph: dict
    request_id: str = Field(min_length=1, max_length=200)


class ExecuteCanvas(ContractModel):
    preparation_id: str = Field(min_length=1, max_length=200)
    request_id: str = Field(min_length=1, max_length=200)
    action: str
    output: str | None = None


class CancelPreparation(ContractModel):
    request_id: str = Field(min_length=1, max_length=200)


def mount_canvas(app, application, bridge):
    @app.post('/api/v1/canvas-plans/prepare')
    async def prepare(request: Request, payload: PrepareCanvas):
        bridge.actor(request, 'run')
        return application.canvas_plans.start(payload.graph, payload.request_id)

    @app.get('/api/v1/canvas-plans/status')
    async def status(request: Request, request_id: str):
        bridge.actor(request, 'context')
        return application.canvas_plans.status(request_id)

    @app.post('/api/v1/canvas-plans/cancel')
    async def cancel(request: Request, payload: CancelPreparation):
        bridge.actor(request, 'run')
        return application.canvas_plans.cancel(payload.request_id)

    @app.post('/api/v1/canvas-plans/execute')
    async def execute(request: Request, payload: ExecuteCanvas):
        bridge.actor(request, 'run')
        return await application.storage_dispatch.run(lambda: application.canvas_plans.execute(
            payload.preparation_id, action=payload.action, request_id=payload.request_id, output=payload.output),
            principal=PROFILE_OWNER)

    @app.get('/api/v1/canvas-plans/history')
    async def history(request: Request):
        bridge.actor(request, 'context')
        return application.canvas_plans.history()

    @app.get('/api/v1/canvas-plans/outcome')
    async def outcome(request: Request, request_id: str):
        bridge.actor(request, 'context')
        return await application.storage_dispatch.run(lambda: application.canvas_plans.outcome(request_id),
                                                      principal=PROFILE_OWNER, lifecycle=True)
