"""Candidate app-side large-resource manager.

This module is the application half of the library ``resource_fetch`` interface:
it reads the installed library's ``resources.json``, reports presence, and runs
the library's downloader in a background thread.  It is intentionally small so
it can be ported onto the collaborator's application tree.
"""
from __future__ import annotations

import hashlib
import importlib
import os
import sys
import threading
import time
import uuid
from pathlib import Path

from fastapi import HTTPException

_jobs: dict[str, dict] = {}
_running: dict[str, str] = {}
_cancel: dict[str, threading.Event] = {}
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


def operation(job_id: str) -> dict | None:
    job = _jobs.get(job_id)
    return dict(job) if job else None


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


def _part_bytes(target: Path, resource) -> int:
    total = 0
    for entry in resource.downloads:
        path = target / str(entry.get('path') or '')
        part = path.with_name(path.name + '.part')
        try:
            if part.is_file():
                total += part.stat().st_size
        except OSError:
            pass
    return total


class _Cancelled(Exception):
    """Raised when the user cancels a download."""


def _sha256(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def _download(entry: dict, root: Path, *, overwrite: bool, event, job: dict, opener) -> dict:
    """Stream one file with cancellation, progress and integrity checks."""

    url = str(entry["url"])
    if not url.startswith("https://"):
        raise ValueError(f"only https:// downloads are allowed: {url!r}")
    relative = str(entry["path"])
    candidate = Path(relative)
    if not relative or candidate.is_absolute() or ".." in candidate.parts:
        raise ValueError(f"unsafe download path: {relative!r}")
    target = (root.resolve() / candidate).resolve()
    if target != root.resolve() and root.resolve() not in target.parents:
        raise ValueError(f"download path escapes the resource root: {relative!r}")
    expected_bytes = int(entry.get("bytes") or 0)
    expected_sha = str(entry.get("sha256") or "").lower()
    if target.is_file() and not overwrite:
        actual = target.stat().st_size
        if expected_bytes and actual != expected_bytes:
            raise ValueError(f"{target} exists with {actual} bytes, expected {expected_bytes}")
        if expected_sha and _sha256(target) != expected_sha:
            raise ValueError(f"{target} exists with a different sha256")
        job["completed_bytes"] = int(job.get("completed_bytes") or 0) + actual
        return {"path": relative, "status": "existing", "bytes": actual}
    target.parent.mkdir(parents=True, exist_ok=True)
    partial = target.with_name(target.name + ".part")
    hasher = hashlib.sha256()
    written = 0
    with opener(url, str(entry.get("token_env") or "")) as response, partial.open("wb") as handle:
        while True:
            if event.is_set():
                handle.close()
                partial.unlink(missing_ok=True)
                raise _Cancelled("cancelled")
            chunk = response.read(1024 * 1024)
            if not chunk:
                break
            hasher.update(chunk)
            handle.write(chunk)
            written += len(chunk)
            job["bytes"] = int(job.get("completed_bytes") or 0) + written
    if expected_bytes and written != expected_bytes:
        partial.unlink(missing_ok=True)
        raise ValueError(f"download size mismatch for {relative}: got {written}, expected {expected_bytes}")
    digest = hasher.hexdigest()
    if expected_sha and digest != expected_sha:
        partial.unlink(missing_ok=True)
        raise ValueError(f"download sha256 mismatch for {relative}: got {digest}, expected {expected_sha}")
    os.replace(partial, target)
    job["completed_bytes"] = int(job.get("completed_bytes") or 0) + written
    return {"path": relative, "status": "downloaded", "bytes": written, "sha256": digest}


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
               'completed_bytes': 0, 'phase': 'starting', 'current': ''}
        _jobs[key] = job
        _running[name] = key
        event = threading.Event()
        _cancel[key] = event
    logs = Path(service.directory) / 'resources'
    logs.mkdir(parents=True, exist_ok=True)
    log = logs / f'{name}.log'

    def emit(line: str) -> None:
        with log.open('a', encoding='utf-8') as stream:
            stream.write(str(line) + '\n')
            stream.flush()

    target = _target_root(common, resource, root)

    def watch() -> None:
        while job['status'] == 'running':
            try:
                job['bytes'] = int(job.get('completed_bytes') or 0) + _part_bytes(target, resource)
            except Exception:
                pass
            time.sleep(0.5)

    def run() -> None:
        try:
            target.mkdir(parents=True, exist_ok=True)
            emit(f'START {name} -> {target}')
            job['phase'] = 'downloading'
            for entry in resource.downloads:
                if event.is_set():
                    raise RuntimeError('cancelled')
                job['current'] = str(entry.get('path') or '')
                emit(f'GET {entry.get("url")} -> {entry.get("path")}')
                result = _download(entry, target, overwrite=overwrite, event=event, job=job, opener=fetch._open_url)
                job['files'] += 1
                job['completed_bytes'] = int(job.get('completed_bytes') or 0) + int(result.get('bytes') or 0)
                job['bytes'] = int(job.get('completed_bytes') or 0)
                emit(f'OK {entry.get("path")} {result.get("status")} {result.get("bytes", 0)}')
            if event.is_set():
                raise RuntimeError('cancelled')
            job['status'] = 'succeeded'
            job['phase'] = 'complete'
        except Exception as exc:  # noqa: BLE001 - surfaced in the job and log
            cancelled = event.is_set() or str(exc) == 'cancelled'
            job['status'] = 'cancelled' if cancelled else 'failed'
            job['phase'] = 'cancelled' if cancelled else 'failed'
            job['error'] = 'cancelled' if cancelled else str(exc)
            emit(f'{"CANCEL" if cancelled else "FAIL"} {name}: {exc}')
        finally:
            job['finished_at'] = _now()
            with _lock:
                if _running.get(name) == job['id']:
                    _running.pop(name, None)
                _cancel.pop(job['id'], None)

    threading.Thread(target=watch, name=f'resource-watch-{name}', daemon=True).start()
    threading.Thread(target=run, name=f'resource-{name}', daemon=True).start()
    return dict(job)


def cancel(service, name: str) -> dict:
    with _lock:
        key = _running.get(name)
        if not key:
            raise KeyError(name)
        event = _cancel.get(key)
        if event is None:
            raise KeyError(name)
        event.set()
        job = _jobs.get(key)
        if job:
            job['phase'] = 'cancelling'
        return dict(job or {})


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

    @app.post('/api/resources/{name}/cancel')
    def cancel_download(name: str):
        try:
            return cancel(service, name)
        except KeyError as exc:
            raise HTTPException(404, f"no running download: {name}") from exc

    @app.get('/api/resources/operations/{job_id}')
    def operation_status(job_id: str):
        job = operation(job_id)
        if job is None:
            raise HTTPException(404, f"unknown resource operation: {job_id}")
        return job

    @app.get('/api/resources/{name}/log')
    def log(name: str, limit: int = 200):
        try:
            return read_log(service, name, limit)
        except KeyError as exc:
            raise HTTPException(404, f"unknown resource: {name}") from exc
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc
