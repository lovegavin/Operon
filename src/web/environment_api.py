"""Isolated operator environments: declared status, background preparation, logs."""
from __future__ import annotations

import json
import os
from collections import deque
import signal
import subprocess
import threading
import time
import uuid
from pathlib import Path

from fastapi import HTTPException

# A complete environment is a few hundred megabytes to several gigabytes; the
# panel polls every few seconds, so a short cache keeps /api/environments cheap.
_SIZE_TTL = 90.0
_VERSION_TTL = 300.0
_USED_BY_LIMIT = 64
_OPERATORS_TTL = 60.0


def _now():
    return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())


def _iso(seconds):
    """Render an epoch-seconds progress stamp as the ISO text the panel expects."""
    if isinstance(seconds, str):
        return seconds
    if not isinstance(seconds, (int, float)) or not seconds:
        return ''
    return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(float(seconds)))


def _usage(directory):
    size = files = 0
    for parent, _, names in os.walk(directory):
        for item in names:
            try:
                size += (Path(parent) / item).stat().st_size
                files += 1
            except OSError:
                pass
    return size, files


def mount_environments(app, service):
    from operon import environment_install, environments

    app.state.environment_tasks = set()
    jobs = {}
    current = {}
    cancelled = set()
    controls = {}
    pending = deque()
    queue_lock = threading.Lock()
    drainer = {'thread': None}
    logs = service.directory / 'environments'
    sizes = {}
    versions = {}
    operator_cache = {'at': 0.0, 'map': {}}

    def source_root():
        try:
            source = service.plugins.source_root
        except Exception:
            return None
        return None if source is None else str(source)

    def descriptors():
        try:
            return service.plugins.state().get('descriptors') or []
        except Exception:
            return []

    def operator_map():
        """Group the installed operators by the environment they belong to."""
        now = time.monotonic()
        if operator_cache['map'] and now - operator_cache['at'] < _OPERATORS_TTL:
            return operator_cache['map']
        grouped = {}
        for descriptor in descriptors():
            resources = descriptor.get('resources') if isinstance(descriptor, dict) else None
            name = (resources or {}).get('environment') if isinstance(resources, dict) else None
            identifier = descriptor.get('id') if isinstance(descriptor, dict) else None
            if not name or not identifier:
                continue
            grouped.setdefault(str(name), []).append(str(identifier))
        for names in grouped.values():
            names.sort()
        operator_cache['map'] = grouped
        operator_cache['at'] = now
        return grouped

    def plan():
        return environment_install.plan(environments.root(), descriptors(), source=source_root())

    def manifest():
        path = environments.manifest_path(source_root())
        return {'path': str(path), 'present': path.is_file()}

    def declared():
        """Raw manifest entries: notes/title are authored there, not in the planner."""
        try:
            entries = environments.load(source_root())
        except Exception:
            return {}
        return entries if isinstance(entries, dict) else {}

    def owners():
        result = {}
        for descriptor in descriptors():
            name = (descriptor.get('resources') or {}).get('environment')
            identifier = descriptor.get('id')
            if name and identifier:
                result.setdefault(name, []).append(identifier)
        return {name: sorted(set(values)) for name, values in result.items()}

    def size_bytes(location):
        if not location:
            return 0
        cached = sizes.get(location)
        now = time.monotonic()
        if cached and cached[0] > now:
            return cached[1]
        try:
            value = _usage(location)[0] if Path(location).is_dir() else 0
        except OSError:
            value = 0
        sizes[location] = (now + _SIZE_TTL, value)
        return value

    def python_version(item):
        interpreter = item.get('interpreter') or ''
        if not interpreter:
            return ''
        try:
            stamp = Path(interpreter).stat().st_mtime
        except OSError:
            stamp = 0
        cached = versions.get(interpreter)
        if cached and cached[0] > time.monotonic() and cached[1] == stamp:
            return cached[2]
        version = ''
        meta = Path(item.get('location') or '') / 'conda-meta'
        if meta.is_dir():
            for path in sorted(meta.glob('python-3*.json'), reverse=True):
                try:
                    version = str(json.loads(path.read_text(encoding='utf-8')).get('version') or '')
                except (OSError, ValueError):
                    version = ''
                if version:
                    break
        if not version:
            try:
                completed = subprocess.run(
                    [interpreter, '-c', 'import platform; print(platform.python_version())'],
                    capture_output=True, text=True, timeout=5)
                version = completed.stdout.strip().splitlines()[0] if completed.stdout.strip() else ''
            except Exception:
                version = ''
        versions[interpreter] = (time.monotonic() + _VERSION_TTL, stamp, version)
        return version

    def updated_at(name, item):
        stamp = (item.get('progress') or {}).get('updated_at')
        text = _iso(stamp)
        if text:
            return text
        try:
            created = environment_install.receipt(name, environments.root()).get('created_at')
        except Exception:
            created = ''
        return created if isinstance(created, str) else ''

    def dependencies(entry):
        """Flatten one environment definition into installable dependency rows."""
        rows = []
        for key, kind in (('requirements', 'requirements'), ('pip_wheels', 'wheel'),
                          ('pip_pypi', 'pypi'), ('conda_packages', 'conda'),
                          ('binaries', 'binary')):
            for value in entry.get(key) or []:
                rows.append({'kind': kind, 'name': str(value)})
        for value in entry.get('imports') or []:
            rows.append({'kind': 'import', 'name': str(value)})
        return rows

    _INSTALLED_TTL = 20.0
    installed_cache: dict[str, tuple[float, dict, set, set]] = {}

    def _site_packages(location: str) -> Path | None:
        base = Path(location)
        candidates = [base / 'Lib' / 'site-packages']
        candidates.extend(sorted(base.glob('lib/python*/site-packages')))
        for candidate in candidates:
            if candidate.is_dir():
                return candidate
        return None

    def _normalise(name: str) -> str:
        return str(name).strip().lower().replace('_', '-').replace(' ', '-')

    def _requirement_name(value: str) -> str:
        head = str(value).split(';')[0].strip()
        for marker in ('[', '=', '<', '>', '!', '~', ' '):
            head = head.split(marker)[0]
        return _normalise(head)

    def installed_index(location: str) -> tuple[dict, set, set]:
        """Return package versions, conda package names and importable names for one environment."""
        if not location:
            return {}, set(), set()
        stamp = time.monotonic()
        cached = installed_cache.get(location)
        if cached and stamp - cached[0] < _INSTALLED_TTL:
            return cached[1], cached[2], cached[3]
        versions: dict[str, str] = {}
        packages: set[str] = set()
        imports: set[str] = set()
        base = Path(location)
        site = _site_packages(location)
        if site is not None:
            for entry in site.iterdir():
                name = entry.name
                if name.endswith('.dist-info') or name.endswith('.egg-info'):
                    stem = name.rsplit('.', 2)[0]
                    parts = stem.replace('-', '_').split('_')
                    if parts:
                        versions[_normalise(parts[0])] = parts[1] if len(parts) > 1 else ''
                imports.add(_normalise(name.split('.')[0].lower()))
                if name.endswith('.py'):
                    imports.add(_normalise(name[:-3]))
                elif name.endswith('.pyc'):
                    imports.add(_normalise(name[:-4]))
        meta = base / 'conda-meta'
        if meta.is_dir():
            for entry in meta.glob('*.json'):
                stem = entry.stem
                chunk = stem.rsplit('-', 2)
                if len(chunk) >= 2:
                    packages.add(_normalise(chunk[0]))
                    versions.setdefault(_normalise(chunk[0]), chunk[1])
        installed_cache[location] = (stamp, versions, packages, imports)
        return versions, packages, imports

    def dependency_installed(row: dict, location: str) -> bool:
        versions, packages, imports = installed_index(location)
        kind = str(row.get('kind') or '')
        name = str(row.get('name') or '')
        if kind in ('requirements', 'pypi', 'wheel'):
            return _requirement_name(name) in versions
        if kind == 'conda':
            return _requirement_name(name) in packages or _requirement_name(name) in versions
        if kind == 'import':
            return _normalise(name.split('.')[0].lower()) in imports
        if kind == 'binary':
            base = Path(location) if location else None
            if base is None:
                return False
            executable = name.split(' ')[0]
            for folder in ('Scripts', 'bin', ''):
                candidate = (base / folder / executable) if folder else (base / executable)
                if candidate.exists():
                    return True
            return False
        return False

    def augment(name, item, entry=None, used_by=None):
        """Add the panel-facing facts without dropping any planner key."""
        entry = entry if isinstance(entry, dict) else {}
        notes = entry.get('notes')
        item['title'] = str(entry.get('title') or name)
        item['notes'] = notes if isinstance(notes, str) else ''
        item['planned'] = bool(entry.get('planned'))
        item['size_bytes'] = int(size_bytes(item.get('location') or ''))
        item['python_version'] = python_version(item)
        item['updated_at'] = updated_at(name, item)
        owned = list(used_by if used_by is not None else item.get('used_by') or [])
        item['used_by_count'] = len(owned)
        item['used_by'] = owned[:_USED_BY_LIMIT]
        members = operator_map().get(name) or []
        item['operator_count'] = len(members)
        item['operators'] = members[:_USED_BY_LIMIT]
        item['expected_bytes'] = environment_install.estimates.expected(
            name, entry, environments.root())
        item['resources'] = [str(value) for value in entry.get('resources') or []]
        rows = dependencies(entry)
        location = str(item.get('location') or '')
        for row in rows:
            row['installed'] = dependency_installed(row, location)
        item['dependencies'] = rows
        item['dependency_total'] = len(rows)
        item['dependency_installed'] = sum(1 for row in rows if row.get('installed'))
        item['supported'] = environment_install.platform_supported(entry)
        item['platform_note'] = environment_install.unsupported_reason(entry)
        item['shared'] = bool(entry.get('shared'))
        item['managed'] = not bool(entry.get('shared'))
        with queue_lock:
            waiting = [entry[0] for entry in pending]
        if name in waiting:
            item['status'] = 'queued'
            item['error'] = ''
            item['queue_position'] = waiting.index(name) + 1
        else:
            item['queue_position'] = 0
        return item

    def described():
        entries, owned = declared(), owners()
        result = plan()
        for name, item in result.items():
            augment(name, item, entries.get(name), owned.get(name) or item.get('used_by') or [])
        return result

    def operation(value):
        """Normalize one tracked job for the operations list."""
        item = dict(value)
        if item.get('id') in cancelled or item.get('cancelled'):
            item['status'] = 'cancelled'
        item['cancelable'] = item.get('status') in {'running', 'queued'}
        info = {}
        try:
            info = environment_install.read_progress(item.get('name') or '') or {}
        except Exception:
            info = {}
        if item.get('status') == 'running':
            for key in ('phase', 'detail'):
                if not item.get(key):
                    item[key] = info.get(key) or ''
            for key in ('bytes', 'files'):
                if item.get(key) is None:
                    item[key] = info.get(key, 0)
            if not item.get('updated_at'):
                item['updated_at'] = info.get('updated_at')
        elif not item.get('finished_at'):
            # Synthesised operations carry no finish stamp; the last progress
            # write is the moment the work stopped.
            item['finished_at'] = _iso(item.get('updated_at') or info.get('updated_at')) or None
        item.pop('cancelled', None)
        return item

    def snapshot():
        recover_queue()
        application = getattr(service, 'application', None)
        data = None
        if application is not None:
            try:
                data = application.isolated_environments()
            except Exception:
                data = None
        operations = []
        if data is not None:
            operations.extend(data.get('operations') or [])
        known = {item.get('id') for item in operations}
        for job in list(jobs.values())[-20:]:
            if job.get('id') not in known:
                operations.append(job)
        operations = [operation(value) for value in operations]
        if data is None:
            data = {'root': str(environments.root()), 'manifest': manifest(),
                    'environments': described()}
        else:
            entries, owned = declared(), owners()
            environments_data = data.get('environments') or {}
            for name, item in environments_data.items():
                if isinstance(item, dict):
                    augment(name, item, entries.get(name), owned.get(name) or item.get('used_by') or [])
            data = {**data, 'environments': environments_data}
        return {**data, 'operations': operations}

    def log_path(name):
        logs.mkdir(parents=True, exist_ok=True)
        return logs / f'{name}.log'

    def drain_pending():
        while True:
            with queue_lock:
                if not pending:
                    drainer['thread'] = None
                    return
                name, key, work, control = pending.popleft()
            job = jobs.get(key) or {}
            if control.stopped:
                job.update({'status': 'cancelled', 'error': None, 'finished_at': _now()})
                continue
            job['status'] = 'running'
            try:
                work()
            except BaseException as error:  # a broken job must never stop the queue
                job['status'] = 'failed'
                job['error'] = str(error)
                job['finished_at'] = _now()

    def ensure_drainer():
        with queue_lock:
            thread = drainer['thread']
            if thread is not None and thread.is_alive():
                return
            thread = threading.Thread(target=drain_pending, name='environment-queue', daemon=True)
            drainer['thread'] = thread
            app.state.environment_tasks.add(thread)
            thread.start()

    def recover_queue():
        """Restart the drainer when items wait but no worker thread survives."""
        with queue_lock:
            if not pending:
                return
            thread = drainer['thread']
            if thread is not None and thread.is_alive():
                return
        ensure_drainer()

    def start(name):
        environments.describe(name, source_root())
        running = current.get(name)
        if running and jobs.get(running, {}).get('status') in {'running', 'queued'}:
            return jobs[running]
        key = uuid.uuid4().hex
        job = {'id': key, 'name': name, 'status': 'queued', 'error': None,
               'started_at': _now(), 'finished_at': None}
        jobs[key] = job
        current[name] = key
        control = environment_install._Control()
        controls[key] = control
        log = log_path(name)
        log.write_text('', encoding='utf-8')

        def emit(line):
            with log.open('a', encoding='utf-8') as stream:
                stream.write(str(line) + '\n')
                stream.flush()

        def work():
            try:
                result = environment_install.prepare(name, None, source_root(), emit, control=control)
                job['status'] = 'complete' if (result or {}).get('status') == 'ready' else 'failed'
                job['error'] = (result or {}).get('error') or None
            except environment_install.Cancelled:
                job['status'] = 'cancelled'
                job['error'] = None
                emit(f'CANCELLED {name}')
            except Exception as exc:
                job['status'] = 'failed'
                job['error'] = str(exc)
                emit(f'FAIL {name}: {exc}')
            finally:
                if key in cancelled or control.stopped:
                    job['status'] = 'cancelled'
                    job['error'] = None
                controls.pop(key, None)
                job['finished_at'] = _now()

        # Serial by design: parallel installers race for one micromamba image and
        # one disk. The queue keeps the caller's order and reports positions.
        with queue_lock:
            pending.append((name, key, work, control))
        ensure_drainer()
        return job

    def signal_stop(name):
        """Best-effort termination of the installer process; prepare() reports the failure."""
        try:
            pid = (environment_install.read_progress(name) or {}).get('pid')
        except Exception:
            pid = None
        if not isinstance(pid, int) or pid <= 1:
            return False
        try:
            os.kill(pid, getattr(signal, 'SIGTERM', 15))
        except OSError:
            return False
        return True

    def import_summary():
        """Report declared environments after an import; installation stays explicit."""
        return {'root': str(environments.root()), 'manifest': manifest(),
                'environments': described(), 'prepared': []}

    service.environments_after_install = import_summary

    @app.get('/api/environments')
    def list_environments():
        return snapshot()

    @app.post('/api/environments/{name}/dependencies/download')
    @app.post('/api/v1/environments/{name}/dependencies/download')
    def download_dependency(name: str, payload: dict | None = None):
        body = payload or {}
        try:
            return environment_install.install_dependency(
                name, str(body.get('kind') or ''), str(body.get('name') or ''))
        except KeyError as exc:
            raise HTTPException(404, f"unknown environment: {name}") from exc
        except (ValueError, FileNotFoundError) as exc:
            raise HTTPException(409, str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(409, str(exc)) from exc

    @app.post('/api/environments/prepare')
    def prepare(payload: dict):
        names = payload.get('names')
        if names is None and isinstance(payload.get('environments'), list):
            names = payload['environments']
        extra = sorted(set(payload) - {'names', 'environments'})
        if extra:
            raise HTTPException(422, f"不认识的字段：{', '.join(extra)}。请用 names 指定要准备的环境。")
        entries = declared()
        if names is None:
            entries_by_name = entries
            names = sorted(
                (name for name, item in plan().items()
                 if item['status'] not in {'ready', 'queued', 'installing'}),
                key=lambda name: environment_install.estimates.expected(
                    name, entries_by_name.get(name), environments.root()) or 0)
        if not isinstance(names, list) or not all(isinstance(name, str) for name in names):
            raise HTTPException(422, '请提供需要准备的环境名称列表。')
        for name in names:
            try:
                environments.describe(name, source_root())
            except ValueError as exc:
                raise HTTPException(404, str(exc)) from exc
        prepared = []
        for name in names:
            job = start(name)
            prepared.append({'name': name, 'job': job['id'], 'status': job['status']})
        return {**snapshot(), 'prepared': prepared}

    @app.post('/api/environments/{name}/retry')
    @app.post('/api/v1/environments/{name}/retry')
    def retry(name: str):
        try:
            job = start(name)
        except ValueError as exc:
            raise HTTPException(404, str(exc)) from exc
        return {**snapshot(), 'job': job['id']}

    @app.post('/api/environments/{name}/cancel')
    @app.post('/api/v1/environments/{name}/cancel')
    def cancel(name: str):
        try:
            environments.describe(name, source_root())
        except ValueError as exc:
            raise HTTPException(404, str(exc)) from exc
        job_id = None
        # A queued environment never started, so cancellation is queue removal.
        with queue_lock:
            waiting = deque()
            while pending:
                entry = pending.popleft()
                if entry[0] == name and job_id is None:
                    queued = jobs.get(entry[1]) or {}
                    queued.update({'status': 'cancelled', 'error': None, 'finished_at': _now()})
                    controls.pop(entry[1], None)
                    current.pop(name, None)
                    job_id = entry[1]
                else:
                    waiting.append(entry)
            pending.extend(waiting)
        for job in list(jobs.values()):
            if job.get('name') == name and job.get('status') == 'running':
                cancelled.add(job['id'])
                job['status'] = 'cancelled'
                job_id = job['id']
        application = getattr(service, 'application', None)
        remote_jobs = getattr(application, '_environment_jobs', None) or {}
        for job in list(remote_jobs.values()):
            if job.get('name') == name and job.get('status') == 'running':
                job['cancelled'] = True
                if job.get('id'):
                    cancelled.add(str(job['id']))
                job_id = job_id or job.get('id')
        if job_id is None:
            reaped = environment_install.reap_stale(name)
            items = (snapshot().get('environments') or {})
            item = items.get(name) or {}
            finished = str(item.get('status') or '') == 'ready'
            if reaped:
                reason = reaped
            elif finished:
                reason = '该环境已完成安装，取消无效。'
            else:
                reason = '没有正在进行的准备任务。'
            return {
                **snapshot(),
                'cancelled': bool(reaped),
                'job': None,
                'completed': finished and not reaped,
                'reason': reason,
            }
        handle = controls.get(str(job_id)) if job_id is not None else None
        if handle is not None:
            handle.stop()
        signal_stop(name)
        marked = environment_install.mark_cancelled(name)
        return {**snapshot(), 'cancelled': True, 'job': job_id, 'completed': not marked}

    @app.get('/api/environments/{name}/log')
    @app.get('/api/v1/environments/{name}/log')
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
