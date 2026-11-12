"""Isolated operator environments: declared status, background preparation, logs."""
from __future__ import annotations

import asyncio
import time
import uuid

from fastapi import HTTPException


def _now():
    return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())


def mount_environments(app, service):
    from operon import environment_install, environments

    app.state.environment_tasks = set()
    jobs = {}
    current = {}
    logs = service.directory / 'environments'

    def source_root():
        try:
            return str(service.plugins.source_root)
        except Exception:
            return None

    def descriptors():
        try:
            return service.plugins.state().get('descriptors') or []
        except Exception:
            return []

    def plan():
        return environment_install.plan(environments.root(), descriptors(), source=source_root())

    def manifest():
        path = environments.manifest_path(source_root())
        return {'path': str(path), 'present': path.is_file()}

    def snapshot():
        return {'root': str(environments.root()), 'manifest': manifest(),
                'environments': plan(), 'operations': list(jobs.values())[-20:]}

    def log_path(name):
        logs.mkdir(parents=True, exist_ok=True)
        return logs / f'{name}.log'

    def start(name):
        environments.describe(name, source_root())
        running = current.get(name)
        if running and jobs.get(running, {}).get('status') == 'running':
            return jobs[running]
        key = uuid.uuid4().hex
        job = {'id': key, 'name': name, 'status': 'running', 'error': None,
               'started_at': _now(), 'finished_at': None}
        jobs[key] = job
        current[name] = key
        log = log_path(name)
        log.write_text('', encoding='utf-8')

        def emit(line):
            with log.open('a', encoding='utf-8') as stream:
                stream.write(str(line) + '\n')
                stream.flush()

        async def run():
            try:
                result = await asyncio.to_thread(environment_install.prepare,
                                                 name, None, source_root(), emit)
                job['status'] = 'complete' if (result or {}).get('status') == 'ready' else 'failed'
                job['error'] = (result or {}).get('error') or None
            except Exception as exc:
                job['status'] = 'failed'
                job['error'] = str(exc)
                emit(f'FAIL {name}: {exc}')
            finally:
                job['finished_at'] = _now()

        task = asyncio.create_task(run())
        app.state.environment_tasks.add(task)
        task.add_done_callback(app.state.environment_tasks.discard)
        return job

    def import_summary():
        """Report declared environments after an import; installation stays explicit."""
        return {'root': str(environments.root()), 'manifest': manifest(),
                'environments': plan(), 'prepared': []}

    service.environments_after_install = import_summary

    @app.get('/api/environments')
    def list_environments():
        return snapshot()

    @app.post('/api/environments/prepare')
    def prepare(payload: dict):
        names = payload.get('names')
        if names is None:
            names = [name for name, item in plan().items() if item['status'] != 'ready']
        if not isinstance(names, list) or not all(isinstance(name, str) for name in names):
            raise HTTPException(422, '请提供需要准备的环境名称列表。')
        prepared = []
        for name in names:
            try:
                job = start(name)
            except ValueError as exc:
                raise HTTPException(404, str(exc)) from exc
            prepared.append({'name': name, 'job': job['id'], 'status': job['status']})
        return {**snapshot(), 'prepared': prepared}

    @app.post('/api/environments/{name}/retry')
    def retry(name: str):
        try:
            job = start(name)
        except ValueError as exc:
            raise HTTPException(404, str(exc)) from exc
        return {**snapshot(), 'job': job['id']}

    @app.get('/api/environments/{name}/log')
    def read_log(name: str, limit: int = 200):
        try:
            environments.describe(name, source_root())
        except ValueError as exc:
            raise HTTPException(404, str(exc)) from exc
        log = log_path(name)
        if not log.is_file():
            return {'name': name, 'text': ''}
        lines = log.read_text(encoding='utf-8', errors='replace').splitlines()
        limit = max(1, min(int(limit), 2000))
        return {'name': name, 'text': '\n'.join(lines[-limit:])}
