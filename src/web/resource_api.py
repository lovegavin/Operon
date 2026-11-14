"""Candidate app-side large-resource manager.

This module is the application half of the library ``resource_fetch`` interface:
it reads the installed library's ``resources.json``, reports presence, and runs
the library's downloader in a background thread.  It is intentionally small so
it can be ported onto the collaborator's application tree.
"""
from __future__ import annotations

import importlib
import sys
import threading
import time
import uuid
from pathlib import Path

from fastapi import HTTPException

_jobs: dict[str, dict] = {}
_running: dict[str, str] = {}
_lock = threading.Lock()


def _now() -> str:
    return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())


def _code_root(service) -> Path:
    state = service.plugins.state()
    paths = state.get('code_paths') or []
    if not paths:
        raise ValueError('The installed library has no code root; import a library first.')
    return Path(service.plugins.directory) / paths[0]


def _manifest(root: Path) -> Path:
    for path in sorted(root.glob('*/steps/resources.json')):
        return path
    raise ValueError('The installed library has no resources.json.')


def _modules(service):
    root = _code_root(service)
    text = str(root)
    if text not in sys.path:
        sys.path.insert(0, text)
    common = importlib.import_module('operon_core.steps._resources_common')
    fetch = importlib.import_module('operon_core.steps.resource_fetch')
    return root, common, fetch


def _resource(service, name: str):
    root, common, fetch = _modules(service)
    resources = common.load_resources(_manifest(root))
    if name not in resources:
        raise KeyError(name)
    return root, common, fetch, resources[name]


def snapshot(service) -> dict:
    root, common, _ = _modules(service)
    items = []
    for resource in common.load_resources(_manifest(root)).values():
        item = common.check_resource(resource)
        item['downloads'] = [dict(entry) for entry in resource.downloads]
        item['used_by'] = []
        items.append(item)
    release = service.plugins.state().get('library_release') or {}
    return {
        'library': release,
        'library_root': str(Path(service.plugins.directory)),
        'resources': items,
        'operations': list(_jobs.values())[-20:],
    }


def _target_root(common, resource, root):
    if root:
        return Path(str(root)).expanduser()
    resolved = common.resolve_root(resource)
    if resolved is not None:
        return resolved
    return Path.home() / '.local' / 'share' / 'operon' / 'resources' / resource.id


def start(service, name: str, root: str | None = None, overwrite: bool = False) -> dict:
    _code_root_path, common, fetch, resource = _resource(service, name)
    if not resource.downloads:
        raise ValueError(f"resource '{name}' has no downloadable files")
    with _lock:
        active = _running.get(name)
        if active and _jobs.get(active, {}).get('status') == 'running':
            return dict(_jobs[active])
        key = uuid.uuid4().hex
        job = {'id': key, 'name': name, 'status': 'running', 'error': None,
               'started_at': _now(), 'finished_at': None, 'bytes': 0, 'files': 0,
               'phase': 'starting'}
        _jobs[key] = job
        _running[name] = key
    logs = Path(service.directory) / 'resources'
    logs.mkdir(parents=True, exist_ok=True)
    log = logs / f'{name}.log'

    def emit(line: str) -> None:
        with log.open('a', encoding='utf-8') as stream:
            stream.write(str(line) + '\n')
            stream.flush()

    target = _target_root(common, resource, root)

    def run() -> None:
        try:
            target.mkdir(parents=True, exist_ok=True)
            emit(f'START {name} -> {target}')
            job['phase'] = 'downloading'
            for entry in resource.downloads:
                emit(f'GET {entry.get("url")} -> {entry.get("path")}')
                result = fetch._download_one(entry, target, overwrite=overwrite)
                job['files'] += 1
                job['bytes'] += int(result.get('bytes') or 0)
                emit(f'OK {entry.get("path")} {result.get("status")} {result.get("bytes", 0)}')
            job['status'] = 'succeeded'
            job['phase'] = 'complete'
        except Exception as exc:  # noqa: BLE001 - surfaced in the job and log
            job['status'] = 'failed'
            job['phase'] = 'failed'
            job['error'] = str(exc)
            emit(f'FAIL {name}: {exc}')
        finally:
            job['finished_at'] = _now()
            with _lock:
                if _running.get(name) == job['id']:
                    _running.pop(name, None)

    threading.Thread(target=run, name=f'resource-{name}', daemon=True).start()
    return dict(job)


def read_log(service, name: str, limit: int = 200) -> dict:
    _resource(service, name)
    log = Path(service.directory) / 'resources' / f'{name}.log'
    if not log.is_file():
        return {'name': name, 'text': ''}
    lines = log.read_text(encoding='utf-8', errors='replace').splitlines()
    limit = max(1, min(int(limit), 2000))
    return {'name': name, 'text': '\n'.join(lines[-limit:])}


def mount_resources(app, service) -> None:
    @app.get('/api/resources')
    def list_resources():
        try:
            return snapshot(service)
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc

    @app.post('/api/resources/{name}/download')
    def download(name: str, payload: dict | None = None):
        body = payload or {}
        try:
            return start(service, name, body.get('root'), bool(body.get('overwrite', False)))
        except KeyError as exc:
            raise HTTPException(404, f"unknown resource: {name}") from exc
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc

    @app.get('/api/resources/{name}/log')
    def log(name: str, limit: int = 200):
        try:
            return read_log(service, name, limit)
        except KeyError as exc:
            raise HTTPException(404, f"unknown resource: {name}") from exc
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc
