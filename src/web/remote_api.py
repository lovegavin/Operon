"""Local desktop endpoints; all remote operations travel over authenticated SSH."""
import asyncio
import base64
import json

from fastapi import Request
from fastapi.responses import JSONResponse, StreamingResponse
from operon.remote.client import RemoteError, HostKeyRequired
from .remote_service import RemoteManager


def mount_remote(app, service):
    manager = service.remotes or RemoteManager(service)
    service.remotes = manager

    @app.exception_handler(RemoteError)
    async def remote_error(request, exc):
        value = {'message': str(exc), 'code': exc.code, 'node_id': exc.node_id}
        if isinstance(exc, HostKeyRequired):
            value.update(fingerprint=exc.key['fingerprint'], changed=exc.changed)
        return JSONResponse(value, status_code=409 if exc.code == 'host_key_required' else 422)

    @app.get('/api/remote')
    def profiles():
        return manager.status()

    @app.get('/api/remote/summary')
    def summary():
        return manager.status(brief=True)

    @app.post('/api/remote/profiles')
    def save(payload: dict):
        return manager.save(payload)

    @app.post('/api/remote/{key}/connect')
    def connect(key: str, payload: dict):
        return manager.connect(key, {k: str(payload[k]) for k in ('password', 'passphrase') if payload.get(k)})

    @app.post('/api/remote/{key}/install')
    def install(key: str, payload: dict):
        force = payload.get('force', False)
        if not isinstance(force, bool):
            raise RemoteError('force must be boolean')
        return manager.connect(key, {k: str(payload[k]) for k in ('password', 'passphrase') if payload.get(k)},
                               install=True, force=force)

    @app.post('/api/remote/{key}/refresh')
    def refresh(key: str, payload: dict | None = None):
        value = (payload or {}).get('verify_all', False)
        if not isinstance(value, bool):
            raise RemoteError('verify_all must be boolean')
        return manager.refresh(key, verify_all=value)

    @app.get('/api/remote/{key}/build')
    def build(key: str):
        return manager.build(key)

    @app.get('/api/remote/{key}/setup')
    def setup(key: str):
        return manager.setup_status(key)

    @app.post('/api/remote/{key}/library/check')
    def check_library(key: str):
        return manager.check_library(key)

    @app.post('/api/remote/{key}/library/install')
    def install_library(key: str, payload: dict):
        return manager.start_library_install(key, payload)

    @app.post('/api/remote/{key}/library/sync')
    def sync_library(key: str):
        return manager.start_library_sync(key)

    @app.get('/api/remote/{key}/library/plan')
    def library_plan(key: str):
        return manager.library_plan(key)

    @app.get('/api/remote/{key}/library/status')
    def library_status(key: str):
        return manager.library_status(key)

    @app.get('/api/remote/{key}/environments')
    def remote_environments(key: str):
        return manager.environments(key)

    @app.post('/api/remote/{key}/environments/prepare')
    def remote_prepare_environments(key: str, payload: dict | None = None):
        payload = payload or {}
        return manager.prepare_environments(key, payload.get('names'), bool(payload.get('dependencies')))

    @app.post('/api/remote/{key}/environments/{name}/dependencies/download')
    def remote_dependency_download(key: str, name: str, payload: dict | None = None):
        return manager.install_dependency(key, name, payload or {})

    @app.post('/api/remote/{key}/environments/{name}/cancel')
    def remote_cancel_environment(key: str, name: str):
        return manager.cancel_environment(key, name)

    @app.post('/api/remote/{key}/environments/{name}/retry')
    def remote_environment_retry(key: str, name: str):
        return manager.environment_retry(key, name)

    @app.post('/api/remote/{key}/environments/{name}/repair')
    def remote_environment_repair(key: str, name: str):
        return manager.environment_repair(key, name)

    @app.get('/api/remote/{key}/environments/{name}/log')
    def remote_environment_log(key: str, name: str, limit: int = 200):
        return manager.environment_log(key, name, limit)

    @app.get('/api/remote/{key}/resources')
    def remote_resources(key: str):
        return manager.call(key, 'resources')

    @app.post('/api/remote/{key}/resources/{name}/link')
    def remote_resource_link(key: str, name: str, payload: dict | None = None):
        payload = payload or {}
        return manager.call(key, 'resources_link',
                            {'name': name, 'source': str(payload.get('source') or ''),
                             'replace': bool(payload.get('replace')),
                             'unit': str(payload.get('unit') or '')})

    @app.post('/api/remote/{key}/resources/{name}/download')
    def remote_resource_download(key: str, name: str, payload: dict | None = None):
        payload = payload or {}
        return manager.call(key, 'resources_download',
                            {'name': name,
                             'unit': str(payload.get('unit') or ''),
                             'root': str(payload.get('root') or ''),
                             'overwrite': bool(payload.get('overwrite'))})

    @app.delete('/api/remote/{key}/resources/{name}/link')
    def remote_resource_unlink(key: str, name: str, unit: str | None = None):
        return manager.call(key, 'resources_unlink', {'name': name, 'unit': unit or ''})

    @app.post('/api/remote/{key}/resources/{name}/cancel')
    def remote_resource_cancel(key: str, name: str):
        return manager.call(key, 'resources_cancel', {'name': name})

    @app.get('/api/remote/{key}/resources/{name}/log')
    def remote_resource_log(key: str, name: str, limit: int = 200):
        return manager.call(key, 'resources_log', {'name': name, 'limit': limit})

    @app.get('/api/remote/{key}/pool')
    def remote_pool(key: str):
        return manager.pool_info(key)

    @app.post('/api/remote/{key}/pool/stop')
    def remote_pool_stop(key: str, payload: dict | None = None):
        return manager.pool_stop(key, force=bool((payload or {}).get('force')))

    @app.post('/api/remote/{key}/trust')
    def trust(key: str, payload: dict):
        manager.trust(key, payload.get('fingerprint'))
        return {'trusted': True}

    @app.post('/api/remote/{key}/disconnect')
    def disconnect(key: str):
        manager.disconnect(key)
        return {'disconnected': True}

    @app.post('/api/remote/{key}/remove')
    def remove(key: str):
        manager.remove(key)
        return {'removed': True}

    @app.post('/api/remote/{key}/browse')
    def browse(key: str, payload: dict):
        return manager.call(key, 'browse', payload)

    @app.post('/api/remote/{key}/source')
    def source(key: str, payload: dict):
        return manager.call(key, 'source', payload)

    async def events(key, request):
        manager.reference(key)
        async def stream():
            offsets, sequence = {}, 0
            while not await request.is_disconnected():
                try:
                    payload = await asyncio.to_thread(manager.poll, key, offsets)
                    offsets = payload.pop('offsets')
                except RemoteError as exc:
                    yield 'event: remote-error\ndata: '+json.dumps({'message': str(exc)})+'\n\n'
                    # Keep the SSE alive so reconnecting SSH resumes from its cursor.
                    await asyncio.sleep(3)
                    continue
                sequence += 1
                yield f'id: {sequence}\nevent: update\ndata: {json.dumps(payload, ensure_ascii=False, allow_nan=False)}\n\n'
                if payload['done']: break
                await asyncio.sleep(1)
        return StreamingResponse(stream(), media_type='text/event-stream', headers={'X-Accel-Buffering': 'no'})

    def console(key):
        ref = manager.reference(key)
        def chunks():
            offset = 0
            while True:
                value = manager.call(ref['profile_id'], 'console', {'job_id': ref['job_id'], 'offset': offset})
                yield base64.b64decode(value['base64']) if 'base64' in value else value['text'].encode()
                offset = value['offset']
                if value['done']: break
        return StreamingResponse(chunks(), media_type='text/plain; charset=utf-8')

    return events, console
