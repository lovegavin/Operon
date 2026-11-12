"""Shared pool, running tasks and environment progress for the status panel."""
from __future__ import annotations

import json
from pathlib import Path

from fastapi import HTTPException

ACTIVE = {'queued', 'preparing', 'running', 'recovery_required'}


def _read(path: Path):
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return {}


def mount_pool(app, service):
    from operon import managed_pool

    @app.get('/api/pool')
    def pool_status():
        _, root = managed_pool.locations(getattr(service, 'settings', None))
        instance = _read(root / 'instance.json')
        spaces = _read(root / 'workspaces.json') or {}
        active, workspaces = [], []
        for key, spec in spaces.items():
            workspace = Path(spec.get('workspace') or spec.get('root') or key)
            jobs = []
            for item in sorted((workspace / '.studio' / 'jobs').glob('*/job.json')):
                data = _read(item)
                if not data:
                    continue
                value = {'id': data.get('id') or item.parent.name, 'status': data.get('status'),
                         'title': data.get('title') or '', 'updated_at': data.get('updated_at')}
                jobs.append(value)
                if value['status'] in ACTIVE or data.get('logs_complete') is False:
                    active.append({**value, 'workspace': str(workspace)})
            workspaces.append({'root': str(workspace), 'code_root': spec.get('code_root'),
                               'jobs': len(jobs)})
        owner = instance.get('owner') or {}
        return {'location': str(root),
                'instance': {'version': instance.get('version'),
                             'implementation': instance.get('implementation'),
                             'address': instance.get('address'),
                             'pid': owner.get('pid'),
                             'closing': bool(instance.get('closing'))},
                'workspaces': workspaces, 'active': active,
                'remotes': service.remotes.status(brief=True) if getattr(service, 'remotes', None) else []}

    @app.post('/api/pool/stop')
    def pool_stop(payload: dict | None = None):
        try:
            return managed_pool.stop_pool(force=bool((payload or {}).get('force')))
        except managed_pool.PoolClientError as exc:
            raise HTTPException(409, str(exc)) from exc
