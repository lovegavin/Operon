"""Thin authenticated storage adapter shared by desktop and headless hosts."""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager, suppress
import hashlib
import threading
import uuid

from fastapi import Request
from fastapi.responses import JSONResponse
from pydantic import Field

from .contracts.base import ContractModel
from .contracts.storage import StorageRef
from .storage import BrowseRequest, PreviewRequest, StorageError
from .storage.configuration import PROFILE_OWNER


class CancelBrowse(ContractModel):
    cursor: str = Field(min_length=1, max_length=256)


class CloseBrowse(ContractModel):
    pass


def mount_storage(app, application, bridge):
    storage, dispatcher = application.storage, application.storage_dispatch

    def scope(request):
        actor = bridge.actor(request, 'context')
        # Discovery/studio credentials authenticate the local profile owner.
        # Agent display names are never principals or authorization grants.
        if actor == 'user':
            connection = 'studio'
        else:
            token = request.headers.get('authorization', '').removeprefix('Bearer ')
            connection = hashlib.sha256(token.encode()).hexdigest()
        client_session = request.headers.get('x-operon-storage-session', '')
        if len(client_session) > 128 or any(ord(value) < 32 for value in client_session):
            raise StorageError('Invalid storage session identifier', code='invalid_request')
        return PROFILE_OWNER, connection + (':' + client_session if client_session else '')

    @app.exception_handler(StorageError)
    async def storage_error(request, error):
        status = {'storage_forbidden': 403, 'storage_not_found': 404, 'storage_busy': 429,
                  'storage_unavailable': 503, 'browse_cursor_expired': 409,
                  'browse_cursor_scope': 409, 'browse_changed': 409,
                  'storage_changed': 409, 'storage_cancelled': 409}.get(error.code, 422)
        payload = error.to_json()
        payload['request_id'] = uuid.uuid4().hex
        if error.code == 'storage_busy':
            payload['retry_after'] = 0.2
        return JSONResponse(payload, status_code=status)

    async def invoke(request, function, payload, *, browse=False):
        principal, session_id = scope(request)
        cancel = threading.Event()
        def work():
            return function(payload, principal=principal, cancel=cancel,
                            **({'session_id': session_id} if browse else {}))
        task = asyncio.create_task(dispatcher.run(work, principal=principal))
        try:
            while not task.done():
                done, _ = await asyncio.wait((task,), timeout=0.1)
                if done:
                    break
                if await request.is_disconnected():
                    cancel.set()
                    if browse:
                        await dispatcher.run(lambda: storage.cancel_session(principal=principal, session_id=session_id),
                                             principal=principal, lifecycle=True)
                    raise StorageError('Storage request disconnected', code='storage_cancelled')
            return await task
        finally:
            if not task.done():
                cancel.set()
                task.cancel()
                with suppress(asyncio.CancelledError, StorageError):
                    await task

    @app.get('/api/v1/storage/roots')
    async def roots(request: Request):
        principal, _ = scope(request)
        return await dispatcher.run(lambda: {'roots': storage.mounts.references(principal)},
                                    principal=principal, lifecycle=True)

    @app.post('/api/v1/storage/browse')
    async def browse(request: Request, payload: BrowseRequest):
        return await invoke(request, storage.list, payload, browse=True)

    @app.post('/api/v1/storage/stat')
    async def stat(request: Request, payload: StorageRef):
        return await invoke(request, storage.stat, payload)

    @app.post('/api/v1/storage/preview')
    async def preview(request: Request, payload: PreviewRequest):
        return await invoke(request, storage.preview, payload)

    @app.post('/api/v1/storage/browse/cancel')
    async def cancel(request: Request, payload: CancelBrowse):
        principal, session_id = scope(request)
        cancelled = await dispatcher.run(lambda: storage.cancel(payload.cursor, principal=principal, session_id=session_id),
                                         principal=principal, lifecycle=True)
        return {'cancelled': cancelled}

    @app.post('/api/v1/storage/browse/close')
    async def close_session(request: Request, payload: CloseBrowse | None = None):
        principal, session_id = scope(request)
        count = await dispatcher.run(lambda: storage.cancel_session(principal=principal, session_id=session_id),
                                     principal=principal, lifecycle=True)
        return {'closed': count}

    @app.get('/api/v1/storage/status')
    async def status(request: Request):
        principal, _ = scope(request)
        return await dispatcher.run(storage.status, principal=principal, lifecycle=True)

    # Integrate into the existing app lifespan; no second server or private
    # event loop. The maintenance operation uses the reserved bounded lane.
    previous_lifespan = app.router.lifespan_context
    @asynccontextmanager
    async def lifespan(instance):
        async def expire():
            while True:
                await asyncio.sleep(1)
                try:
                    await dispatcher.run(storage.expire_idle, principal=PROFILE_OWNER, lifecycle=True)
                except StorageError:
                    pass
        async with previous_lifespan(instance):
            maintenance = asyncio.create_task(expire())
            try:
                yield
            finally:
                maintenance.cancel()
                with suppress(asyncio.CancelledError):
                    await maintenance
    app.router.lifespan_context = lifespan
