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


def _declared_resources(library):
    """Return ``(name, entry)`` pairs from either environment manifest shape.

    ``environment_install.environments.load()`` hands back ``{name: entry}``,
    while a manifest file may nest the same rows under an ``environments`` key.
    The rows themselves carry no id, so the mapping key is the environment name.
    """
    if not isinstance(library, dict):
        return []
    rows = library.get('environments')
    if isinstance(rows, dict):
        pairs = list(rows.items())
    elif isinstance(rows, list):
        pairs = [(str(entry.get('id') or entry.get('name') or ''), entry)
                 for entry in rows if isinstance(entry, dict)]
    else:
        pairs = [(key, value) for key, value in library.items() if key != 'schema_version']
    return [(str(name), entry) for name, entry in pairs
            if str(name or '') and isinstance(entry, dict)]


def mount_environments(app, service):
    from operon import environment_install, environments

    app.state.environment_tasks = set()
    jobs = {}
    # /api/jobs/{id} lives in src/web/api.py and must resolve the ids this queue
    # hands to the panel, so publish the dict instead of keeping it closure-local.
    app.state.environment_jobs = jobs
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
                    project, version = environment_install.metadata_name(name)
                    if project:
                        versions[_normalise(project)] = version
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

    def resource_counts() -> dict:
        """Per environment: the maintenance resources its panel section shows.

        ``names`` is the canonical list: the same source feeds the serialized
        ``resources`` array and ``resources_total``/``resources_ready``, so a
        header can never disagree with the list below it.  A resource counts
        once per environment and is ready only when every serialized component
        is ready.  Every resource that names the environment is counted
        (declared in ``environments.json`` or reached through an operator's
        environment); counting only declared ids left environments such as
        ``core`` at 0/0 while five cards were on screen.
        """
        counts: dict = {}
        try:
            from . import resource_api as _resource_api
        except Exception:
            return counts
        # Seed from the manifest so a resource the snapshot cannot enumerate is
        # still named, counted, and reported missing instead of silently
        # disappearing from the list while its count stayed behind.
        for environment, entry in _declared_resources(declared()):
            names: list[str] = []
            for value in entry.get('resources') or []:
                rid = str(value)
                if rid and rid not in names:
                    names.append(rid)
            counts[environment] = {
                'total': len(names), 'ready': 0,
                'missing': list(names), 'names': names,
            }
        try:
            payload = _resource_api.snapshot(service) or {}
        except Exception:
            return counts
        rows = payload.get('resources')
        if isinstance(rows, dict):
            rows = list(rows.values())
        seen: set[tuple[str, str]] = set()
        for item in rows or []:
            if not isinstance(item, dict):
                continue
            rid = str(item.get('id') or '')
            if not rid:
                continue
            cards = [card for card in item.get('components') or [] if isinstance(card, dict)]
            if not cards:
                cards = [card for card in item.get('units') or [] if isinstance(card, dict)] or [item]
            for environment in item.get('environments') or []:
                environment = str(environment)
                bucket = counts.setdefault(
                    environment,
                    {'total': 0, 'ready': 0, 'missing': [], 'names': []},
                )
                key = (environment, rid)
                if key in seen:
                    continue
                seen.add(key)
                if rid not in bucket['names']:
                    bucket['names'].append(rid)
                    bucket['total'] += 1
                    bucket['missing'].append(rid)
                if all(_resource_api.card_ready(card) for card in cards):
                    bucket['ready'] += 1
                    if rid in bucket['missing']:
                        bucket['missing'].remove(rid)
        return counts

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
        counts = resource_counts()
        for name, item in (data.get('environments') or {}).items():
            if not isinstance(item, dict):
                continue
            bucket = counts.get(str(name)) or {
                'total': 0, 'ready': 0, 'missing': [],
                'shared_total': 0, 'shared_ready': 0,
            }
            item['resources'] = list(bucket.get('names') or [])
            item['resources_total'] = int(bucket['total'])
            item['resources_ready'] = int(bucket['ready'])
            item['resources_missing'] = list(bucket['missing'][:8])
            item['shared_resources_total'] = int(bucket.get('shared_total', 0))
            item['shared_resources_ready'] = int(bucket.get('shared_ready', 0))
            total, ready = int(bucket['total']), int(bucket['ready'])
            if total and ready < total:
                missing_names = [str(name) for name in bucket['missing'][:3]]
                reason = '资源未齐备（%d/%d）' % (ready, total)
                if missing_names:
                    reason += '：' + '、'.join(missing_names)
                if not item.get('error'):
                    item['error'] = reason
                if str(item.get('status') or '') == 'ready':
                    item['status'] = 'incomplete'
        return {**data, 'operations': operations}

    def _synthetic_log(name: str) -> str:
        """Render whatever the run left behind when no log file exists yet."""
        lines: list[str] = []
        progress = {}
        try:
            from operon import environment_install
            progress = environment_install.read_progress(name, source_root()) or {}
        except Exception:
            progress = {}
        if progress:
            stamp = str(progress.get('updated_at') or '')
            lines.append(f'[{stamp}] phase={progress.get("phase")} detail={progress.get("detail") or ""}')
            command = progress.get('command')
            if command:
                lines.append(f'[{stamp}] $ {command}')
            if progress.get('expected_bytes'):
                lines.append(f'[{stamp}] bytes={progress.get("bytes") or 0}/{progress.get("expected_bytes")}')
            if progress.get('error'):
                lines.append(f'[{stamp}] error: {progress["error"]}')
        try:
            from operon import environment_install
            error_file = environment_install._error_path(name, source_root())
            if error_file.is_file():
                import json
                payload = json.loads(error_file.read_text(encoding='utf-8'))
                lines.append(f'[{payload.get("at")}] failed: {payload.get("message")}')
        except Exception:
            pass
        if not lines:
            lines.append('该环境还没有运行记录。执行「准备」「安装依赖」或「下载资源」后会在这里留下完整日志。')
        return '\n'.join(lines) + '\n'

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

    def start_dependency(name, kind, requirement):
        """Queue one declared dependency install and return the tracked job."""
        environments.describe(name, source_root())
        entry = described().get(name) or {}
        status = str(entry.get('status') or '')
        if status not in {'ready', 'incomplete'}:
            # There is one install action: installing a dependency on an environment
            # that was never created first creates it and installs its declared
            # dependencies, then keeps the requested requirement in the same job.
            job = start(name)
            job['dependency'] = requirement
            job['kind'] = 'install'
            return job
        requirement = str(requirement or '')
        kind = str(kind or '')
        if not requirement:
            raise ValueError('missing dependency name')
        if not kind:
            wanted = requirement.split('==')[0].split('>=')[0].split('=')[0].strip()
            for row in entry.get('dependencies') or []:
                name_value = str(row.get('name') or '')
                bare = name_value.split('==')[0].split('>=')[0].split('=')[0].strip()
                if bare and wanted and bare == wanted:
                    kind = str(row.get('kind') or '')
                    break
            kind = kind or 'requirements'
        key = uuid.uuid4().hex
        job = {'id': key, 'name': name, 'status': 'queued', 'error': None,
               'started_at': _now(), 'finished_at': None,
               'kind': 'dependency', 'dependency': requirement}
        jobs[key] = job
        current[name] = key
        control = environment_install._Control()
        controls[key] = control
        log = log_path(name)

        def emit(line):
            with log.open('a', encoding='utf-8') as stream:
                stream.write(str(line) + '\n')
                stream.flush()

        def work():
            try:
                emit(f'$ install dependency {kind}:{requirement} into {name}')
                environment_install.install_dependency(
                    name, kind, requirement, None, emit,
                    control=control, source=source_root())
                job['status'] = 'complete'
                emit(f'OK {name} dependency {requirement}')
            except environment_install.Cancelled:
                job['status'] = 'cancelled'
                emit(f'CANCELLED {name} dependency {requirement}')
            except BaseException as exc:  # one bad package must not stop the queue
                job['status'] = 'failed'
                job['error'] = str(exc)
                emit(f'FAIL {name} dependency {requirement}: {exc}')
            finally:
                if key in cancelled or control.stopped:
                    job['status'] = 'cancelled'
                controls.pop(key, None)
                job['finished_at'] = _now()

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
            job = start_dependency(
                name, str(body.get('kind') or ''), str(body.get('name') or ''))
            return {'status': job.get('status'), 'job': job.get('id'), 'name': name}
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
                 if environment_install.needs_preparation(item['status'])),
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

    @app.post('/api/environments/{name}/repair')
    def repair_environment(name: str):
        try:
            result = environment_install.repair(name)
        except ValueError as exc:
            raise HTTPException(404, str(exc)) from exc
        return {**snapshot(), 'repair': result}

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
                'cancelled': False,
                'job': None,
                'completed': True,
                'reason': reason,
            }
        handle = controls.get(str(job_id)) if job_id is not None else None
        if handle is not None:
            handle.stop()
        signal_stop(name)
        environment_install.mark_cancelled(name)
        return {**snapshot(), 'cancelled': True, 'job': job_id, 'completed': False}

    @app.get('/api/environments/{name}/log')
    @app.get('/api/v1/environments/{name}/log')
    def read_log(name: str, limit: int = 200):
        try:
            environments.describe(name, source_root())
        except ValueError as exc:
            raise HTTPException(404, str(exc)) from exc
        log = log_path(name)
        try:
            from operon import environment_install
            durable = environment_install.log_path(name)
        except Exception:
            durable = None
        if durable is not None and durable.is_file() and (not log.is_file() or durable.stat().st_size > log.stat().st_size):
            log = durable
        if not log.is_file():
            return {'name': name, 'text': _synthetic_log(name)}
        text = log.read_text(encoding='utf-8', errors='replace')
        if not text.strip():
            text = _synthetic_log(name)
        lines = text.splitlines()
        limit = max(1, min(int(limit), 2000))
        return {'name': name, 'text': '\n'.join(lines[-limit:])}
