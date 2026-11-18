"""Large-resource downloads and external links for the installed library.

The library declares downloadable weights and databases in ``resources.json``;
this module lists them, runs the library's own downloader in a background
thread, tracks progress, and supports cancellation.  It also links an existing
local directory into a resource root without copying bytes, and reports which
operators declare each resource.  It deliberately keeps the HTTP surface tiny so
the same functions back the desktop API, the versioned control API and the MCP
adapter.
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

_SCAN_SUFFIXES = ('.parameters.json', '.py', '.md')
_SCAN_LIMIT = 256 * 1024
_used_by_cache: dict[tuple[str, str], dict[str, tuple[str, ...]]] = {}
_used_by_lock = threading.Lock()


class LinkUnsupported(RuntimeError):
    """The installed operator library predates external resource linking."""


def _now() -> str:
    return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())


def _code_root(service) -> Path:
    state = service.plugins.state()
    paths = state.get('code_paths') or []
    if not paths:
        raise ValueError('The installed library has no code root; import a library first.')
    return Path(service.plugins.directory) / paths[0]


def _manifest(root: Path) -> Path:
    for pattern in ('*/steps/resources.json', 'resources.json', '*/resources.json'):
        for path in sorted(root.glob(pattern)):
            return path
    raise ValueError('The installed library has no resources.json.')


def _modules(service):
    root = _code_root(service)
    text = str(root)
    if text not in sys.path:
        sys.path.insert(0, text)
    common = importlib.import_module('operon_core.steps._resources_common')
    fetch = importlib.import_module('operon_core.steps.resource_fetch')
    try:
        link = importlib.import_module('operon_core.steps.resource_link')
    except ImportError:
        link = None
    return root, common, fetch, link


def _resource(service, name: str):
    root, common, fetch, link = _modules(service)
    resources = common.load_resources(_manifest(root))
    if name not in resources:
        raise KeyError(name)
    return root, common, fetch, link, resources[name]


def _expected_files(common, resource) -> list[str]:
    """Expected relative file names, tolerating a library without the helper."""
    getter = getattr(common, 'expected_files', None)
    if callable(getter):
        try:
            return [str(name) for name in getter(resource)]
        except Exception:  # noqa: BLE001 - a broken helper must not break listing
            pass
    declared = getattr(resource, 'expected_files', ()) or getattr(resource, 'files', ())
    return [str(name) for name in declared or ()]


def _link_roots(common) -> list[str]:
    getter = getattr(common, 'link_roots', None)
    if callable(getter):
        try:
            return [str(path) for path in getter() or []]
        except Exception:  # noqa: BLE001 - an old helper must not break listing
            pass
    return []


def _link_state(common, resource) -> dict:
    getter = getattr(common, 'link_state', None)
    if callable(getter):
        try:
            state = dict(getter(resource) or {})
            return {'linked': bool(state.get('linked')), 'source': state.get('source'),
                    'mode': state.get('mode')}
        except Exception:  # noqa: BLE001
            pass
    return {'linked': False, 'source': None, 'mode': None}


def _size_bytes(root, names) -> int:
    if not root:
        return 0
    base = Path(str(root))
    total = 0
    for name in names:
        try:
            path = base / str(name)
            if path.is_file():
                total += path.stat().st_size
        except OSError:
            continue
    return total


def _used_by_map(root: Path, release: dict, probes: list[str]) -> dict[str, list[str]]:
    """Map each resource env (or id) to operators whose files mention it."""
    version = str(release.get('version') or release.get('tag') or '')
    key = (str(root), version)
    with _used_by_lock:
        cached = _used_by_cache.get(key)
    if cached is None:
        found: dict[str, set[str]] = {}
        try:
            candidates = [path for path in root.rglob('*')
                          if path.is_file() and path.name != 'resources.json'
                          and path.name.endswith(_SCAN_SUFFIXES)]
        except OSError:
            candidates = []
        for path in candidates:
            try:
                if path.stat().st_size > _SCAN_LIMIT:
                    continue
                content = path.read_text(encoding='utf-8', errors='replace')
            except OSError:
                continue
            owner = path.name.split('.')[0]
            if not owner:
                continue
            for probe in probes:
                if not probe:
                    continue
                if probe.isupper():
                    # Environment variables are read straight from the process
                    # environment, so any mention of the name is a real use.
                    if probe in content:
                        found.setdefault(probe, set()).add(owner)
                elif any(
                    probe in line and not line.lstrip().startswith(('import ', 'from '))
                    for line in content.splitlines()
                ):
                    # A lower-case resource id counts when the code mentions it
                    # for real; importing a helper from a similarly named module
                    # is not the same as consuming the resource.
                    found.setdefault(probe, set()).add(owner)
        cached = {probe: tuple(sorted(owners)) for probe, owners in found.items()}
        with _used_by_lock:
            _used_by_cache[key] = cached
    return {probe: list(owners) for probe, owners in cached.items()}


def _environment_map(service) -> dict[str, str]:
    """Map each operator id to the isolated environment its descriptor declares."""
    catalog = getattr(service, 'catalog', None) or {}
    found: dict[str, str] = {}
    for entry in list(catalog.get('operators') or []) + list(catalog.get('readers') or []):
        environment = (entry.get('resources') or {}).get('environment')
        identifier = entry.get('id')
        if environment and identifier:
            found[str(identifier)] = str(environment)
    return found


def _declared_environments() -> set[str]:
    """Return the isolated environment names the imported library declares.

    A resource whose id equals an environment name belongs to that environment
    even when no operator descriptor mentions it, because the environment is
    what consumes the weights or database the resource provides.
    """
    try:
        from operon import environments
        return {str(name) for name in environments.load()}
    except Exception:  # noqa: BLE001
        return set()


def operation(job_id: str) -> dict | None:
    job = _jobs.get(job_id)
    return dict(job) if job else None


def snapshot(service) -> dict:
    root, common, _fetch, _link = _modules(service)
    resources = common.load_resources(_manifest(root))
    release = service.plugins.state().get('library_release') or {}
    probes = sorted({probe for resource in resources.values()
                    for probe in (resource.env, resource.id) if probe})
    used_by = _used_by_map(root, release, [probe for probe in probes if probe])
    environment_of = _environment_map(service)
    declared = _declared_environments()
    link_roots = _link_roots(common)
    items = []
    for resource in resources.values():
        item = common.check_resource(resource)
        names = _expected_files(common, resource)
        state = _link_state(common, resource)
        matched = set(used_by.get(resource.id, ()))
        if resource.env:
            matched.update(used_by.get(resource.env, ()))
        item['downloads'] = [dict(entry) for entry in resource.downloads]
        item['used_by'] = sorted(matched)
        owned = {environment_of[name] for name in item['used_by']
                 if environment_of.get(name)}
        if resource.id in declared:
            owned.add(resource.id)
        item['environments'] = sorted(owned)
        item['link_roots'] = list(link_roots)
        item['expected_files'] = names
        item['linked'] = bool(item.get('linked', state['linked']))
        item['source'] = item.get('source') or state['source']
        item['mode'] = item.get('mode') or state['mode']
        item['size_bytes'] = _size_bytes(item.get('root'), names)
        items.append(item)
    return {
        'library': release,
        'library_root': str(Path(service.plugins.directory)),
        'resources': items,
        'operations': list(_jobs.values())[-20:],
    }


def _target_root(fetch, resource, root):
    return fetch._target_root(resource, root)


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
    return {"path": relative, "status": "downloaded", "bytes": written, "sha256": digest}


def start(service, name: str, root: str | None = None, overwrite: bool = False) -> dict:
    _root_path, _common, fetch, _link_module, resource = _resource(service, name)
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

    target = _target_root(fetch, resource, root)

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
    return {'name': name, 'text': chr(10).join(lines[-limit:])}


def _record_link(name: str, status: str, result: dict, *, source: str = '') -> dict:
    job = {'id': uuid.uuid4().hex, 'name': name, 'kind': 'link', 'status': status,
           'error': None, 'started_at': _now(), 'finished_at': _now(),
           'bytes': 0, 'files': len(result.get('files') or []), 'completed_bytes': 0,
           'phase': 'complete', 'current': str(result.get('source') or source or ''),
           'mode': result.get('mode'), 'root': result.get('root'),
           'source': result.get('source') or source or None}
    with _lock:
        _jobs[job['id']] = job
    return job


def link(service, name: str, source: str, replace: bool = False) -> dict:
    """Link an existing local tree into the resource root without copying bytes."""
    _root, common, _fetch, link_module, resource = _resource(service, name)
    operation_link = getattr(link_module, 'link', None) if link_module is not None else None
    if not callable(operation_link):
        raise LinkUnsupported('The installed library does not support linking existing resources.')
    result = dict(operation_link(resource, source, replace=bool(replace),
                                 allowed_roots=_link_roots(common)) or {})
    result.setdefault('id', result.get('name') or name)
    job = _record_link(name, 'linked', result, source=source)
    result['operation'] = job['id']
    return result


def unlink(service, name: str) -> dict:
    """Remove the external link recorded for one resource, keeping the source."""
    _root, common, _fetch, link_module, resource = _resource(service, name)
    operation_unlink = getattr(link_module, 'unlink', None) if link_module is not None else None
    if not callable(operation_unlink):
        raise LinkUnsupported('The installed library does not support unlinking resources.')
    result = dict(operation_unlink(resource) or {})
    result.setdefault('id', result.get('name') or name)
    resolve = getattr(common, 'resolve_root', None)
    root = None
    if callable(resolve):
        try:
            resolved = resolve(resource)
        except Exception:  # noqa: BLE001 - reporting must not fail a successful unlink
            resolved = None
        if resolved:
            root = str(resolved)
    result.setdefault('root', root)
    job = _record_link(name, 'unlinked', result)
    result['operation'] = job['id']
    return result


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

    @app.post('/api/resources/{name}/link')
    def link_resource(name: str, payload: dict | None = None):
        body = payload or {}
        try:
            return link(service, name, str(body.get('source') or ''),
                        bool(body.get('replace', False)))
        except KeyError as exc:
            raise HTTPException(404, f"unknown resource: {name}") from exc
        except LinkUnsupported as exc:
            raise HTTPException(501, str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc

    @app.delete('/api/resources/{name}/link')
    def unlink_resource(name: str):
        try:
            return unlink(service, name)
        except KeyError as exc:
            raise HTTPException(404, f"unknown resource: {name}") from exc
        except LinkUnsupported as exc:
            raise HTTPException(501, str(exc)) from exc
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
