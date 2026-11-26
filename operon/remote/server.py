"""Server-owned jobs, reached through SSH and a private Unix socket only."""
import argparse
import hashlib
from datetime import datetime, timezone
from operon.engine.transport import transport_admission
import json
import os
from pathlib import Path
import re
import socket
import stat
import struct
import subprocess
import sys
import tempfile
import threading
import time
import traceback
import uuid

from .protocol import Decoder, transmit
from operon.engine.control import ControlLoop, limits_from_environment
from operon.documents import CommandError


def _event_name(path, key, jobs_dir, job):
    """Stable offset key for an event file, including task-result runs."""
    try:
        return path.relative_to(jobs_dir/key).as_posix()
    except ValueError:
        output = job.get('output_dir')
        if output:
            try:
                return 'results/' + path.relative_to(Path(output)).as_posix()
            except ValueError:
                pass
        digest = hashlib.sha1(path.as_posix().encode('utf-8')).hexdigest()[:12]
        return 'external/' + digest + '-' + path.name


def receive(sock, size):
    chunks = bytearray()
    while len(chunks) < size:
        block = sock.recv(min(size-len(chunks), 65536))
        if not block:
            raise ConnectionError('Remote control connection closed')
        chunks.extend(block)
    return bytes(chunks)


def send_message(sock, value):
    data = json.dumps(value, ensure_ascii=False, allow_nan=False).encode()
    sock.sendall(struct.pack('!Q', len(data)) + data)


def read_message(sock):
    size = struct.unpack('!Q', receive(sock, 8))[0]
    if size > 128 * 1024**2:
        raise ValueError('Control metadata exceeds 128 MiB; input data must stay in server files')
    return json.loads(receive(sock, size))


def socket_path(workspace):
    if not hasattr(os, 'getuid') or not hasattr(socket, 'AF_UNIX'):
        raise RuntimeError('The remote job service requires a Linux/Unix Python runtime')
    directory = Path(tempfile.gettempdir()) / f'operon-ssh-{os.getuid()}'
    directory.mkdir(mode=0o700, exist_ok=True)
    info = directory.lstat()
    if stat.S_ISLNK(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
        raise RuntimeError('Remote control directory must be owned by this user with mode 0700')
    key = hashlib.sha256(str(Path(workspace).resolve()).encode()).hexdigest()[:24]
    return directory / (key + '.sock')


def pool_snapshot(service):
    """Read-only view of the shared pool that serves this workspace.

    Observation never starts a pool daemon: when nothing is running the
    desktop reports that no shared pool is active instead of masking the
    real owner of the workspace.
    """
    from operon import managed_pool
    try:
        snapshot = managed_pool.inspect_pool()
    except Exception as exc:  # noqa: BLE001 - status must not break a connection
        return {'available': False, 'error': f'{type(exc).__name__}: {exc}'}
    result = dict(snapshot or {'available': False})
    active, seen = [], set()
    try:
        history = service.history()
    except Exception:  # noqa: BLE001 - history is optional for liveness
        history = []
    for job in history or []:
        if not isinstance(job, dict):
            continue
        status = job.get('status')
        if status not in ('queued', 'preparing', 'running', 'recovery_required') and job.get('logs_complete') is not False:
            continue
        job_id = job.get('id')
        if job_id in seen:
            continue
        seen.add(job_id)
        active.append({'id': job_id, 'status': status,
                       'title': job.get('title') or job.get('name') or '',
                       'updated_at': job.get('updated_at')})
    result['active_jobs'] = active[:50]
    result['active_count'] = len(active)
    return result


_ENVIRONMENT_JOBS: dict[str, dict] = {}
_ENVIRONMENT_LOCK = threading.Lock()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _environment_plan(service):
    from operon import environment_install, environments
    root = environments.root()
    source = service.plugins.source_root
    catalog = getattr(service, 'catalog', None) or {}
    descriptors = list(catalog.get('operators') or ()) + list(catalog.get('readers') or ())
    with _ENVIRONMENT_LOCK:
        alive = set(_ENVIRONMENT_JOBS)
    plan = environment_install.plan(root, descriptors, source=str(source), alive=alive)
    return root, source, plan


_RESOURCE_CACHE: dict[str, object] = {'at': 0.0, 'items': {}}
_RESOURCE_TTL = 15.0


def _resource_catalogue(service) -> dict:
    """Return the resource catalogue keyed by id, cached briefly."""
    import time
    now = time.monotonic()
    cached = _RESOURCE_CACHE.get('items') or {}
    if cached and now - float(_RESOURCE_CACHE.get('at') or 0.0) < _RESOURCE_TTL:
        return cached  # type: ignore[return-value]
    try:
        from src.web import resource_api
        payload = resource_api.snapshot(service)
    except Exception:
        return cached  # type: ignore[return-value]
    items = {str(item.get('id') or ''): item for item in payload.get('resources') or []
             if isinstance(item, dict)}
    _RESOURCE_CACHE['items'] = items
    _RESOURCE_CACHE['at'] = now
    return items


_SNAPSHOT_SERVICE: dict[str, object] = {}


def resource_readiness(names: list[str], environment: str = '') -> tuple[int, int, list[str]]:
    """Return (ready cards, total cards, missing names) for one environment.

    Cards are the serialized units the panel renders and the verdict is
    ``resource_api.card_ready``, so a remote badge matches the local one.
    ``names`` stays authoritative for the manifest; ``environment`` additionally
    picks up resources that only reach it through an operator's environment,
    exactly like ``item['environments']``.
    """
    service = _SNAPSHOT_SERVICE.get('service')
    if service is None:
        return 0, 0, []
    from src.web import resource_api

    catalogue = _resource_catalogue(service)
    wanted: list[str] = []
    for name in names or ():
        text = str(name)
        if text and text not in wanted:
            wanted.append(text)
    if environment:
        for name, item in catalogue.items():
            if not isinstance(item, dict):
                continue
            owners = {str(value) for value in item.get('environments') or ()}
            if environment in owners and name not in wanted:
                wanted.append(name)
    ready = 0
    total = 0
    missing: list[str] = []
    for name in wanted:
        item = catalogue.get(name)
        if not isinstance(item, dict):
            continue
        cards = [card for card in item.get('components') or [] if isinstance(card, dict)]
        if not cards:
            cards = [card for card in item.get('units') or [] if isinstance(card, dict)] or [item]
        for card in cards:
            total += 1
            if resource_api.card_ready(card):
                ready += 1
            else:
                label = str(card.get('name') or item.get('official_root') or name)
                if label not in missing:
                    missing.append(label)
    return ready, total, missing


def declared_resources_gate(ready: int, total: int, status: str) -> bool:
    """Say whether a declared resource gap makes an environment incomplete.

    A resource that an environment declares in its own manifest is part of
    readiness: the operator cannot run without the files.  A resource that only
    names the environment as one of its consumers stays a warning, because
    several toolchains share it and a half-downloaded database must not lock a
    finished environment out of every client that gates on a ready status.
    """

    return bool(total) and int(ready) < int(total) and str(status or '') == 'ready'


def environment_snapshot(service) -> dict:
    _SNAPSHOT_SERVICE['service'] = service
    try:
        root, source, plan = _environment_plan(service)
    except Exception as exc:
        return {'root': None, 'source': None, 'environments': {}, 'running': {},
                'error': f'{type(exc).__name__}: {exc}'}
    from operon import environment_install, environments
    try:
        entries = environments.load()
    except Exception:
        entries = {}
    for name, item in (plan or {}).items():
        if not isinstance(item, dict):
            continue
        location = str(item.get('location') or '')
        if not location:
            try:
                from operon import environments as _environments
                location = str(_environments.root() / name)
            except Exception:
                location = ''
        entry = entries.get(name) if isinstance(entries, dict) else None
        _, _, rows = environment_install.dependency_status(entry or {}, location)
        item.update(environment_install.dependency_counts(rows))
        item['dependencies'] = rows
        entry_map = entry if isinstance(entry, dict) else {}
        declared = [str(value) for value in (entry_map.get('resources') or []) if value]
        ready_units, all_units, missing_names = resource_readiness(declared, name)
        item['resources_total'] = all_units
        item['resources_ready'] = ready_units
        item['resources_missing'] = missing_names
        if all_units and ready_units < all_units:
            # Two tiers.  A resource the environment declares itself is part of
            # readiness and flips the status to ``incomplete`` below.  A resource
            # that only lists the environment among its consumers stays a
            # warning: several toolchains share it, and refusing to plan because
            # a shared database is still downloading would gate a finished
            # environment out of every client.
            reason = f'资源未齐备（{ready_units}/{all_units}）'
            if missing_names:
                reason = f'{reason}：' + '、'.join(missing_names[:3])
            item['resources_warning'] = reason
            if not item.get('error'):
                item['error'] = reason
            own_ready, own_total, _ = resource_readiness(declared)
            item['resources_declared_ready'] = own_ready
            item['resources_declared_total'] = own_total
            if declared_resources_gate(own_ready, own_total, item.get('status')):
                item['status'] = 'incomplete'
        elif str(item.get('error') or '').startswith('资源未齐备'):
            # The units arrived; drop the reason an earlier snapshot left behind.
            item['error'] = ''
    with _ENVIRONMENT_LOCK:
        running = {name: dict(value) for name, value in _ENVIRONMENT_JOBS.items()}
    return {'root': str(root), 'source': str(source), 'environments': plan, 'running': running}


def environment_log(service, name: str, limit: int = 200) -> dict:
    from operon import environment_install

    root = Path(service.directory) / 'environments'
    path = environment_install.log_path(name, root)
    if not path.is_file():
        legacy = root / f'{name}.log'
        if legacy.is_file():
            path = legacy
    if not path.is_file():
        return {'name': name, 'text': '', 'path': str(path)}
    try:
        size = max(1, min(int(limit or 200), 2000))
    except (TypeError, ValueError):
        size = 200
    lines = path.read_text(encoding='utf-8', errors='replace').splitlines()[-size:]
    return {'name': name, 'text': '\n'.join(lines), 'path': str(path)}


def environment_repair(service, payload: dict | None = None) -> dict:
    from operon import environment_install
    from operon.documents import CommandError
    name = str((payload or {}).get('name') or '').strip()
    if not name:
        raise CommandError('unknown_environment', 'environment repair requires a name')
    snapshot = environment_snapshot(service)
    try:
        result = environment_install.repair(name, root=snapshot.get('root'))
    except ValueError as error:
        raise CommandError('unknown_environment', str(error)) from error
    return {**snapshot, 'repair': result}


def environment_dependency(service, payload: dict | None = None) -> dict:
    payload = payload or {}
    name = str(payload.get('name') or '').strip()
    if not name:
        raise ValueError('environments_dependency requires an environment name')
    kind = str(payload.get('kind') or '').strip()
    requirement = str(payload.get('requirement') or '').strip()
    def work():
        try:
            environment_install.install_dependency(name, kind, requirement,
                                                   root=environments.root())
        except Exception:
            # The queue records the failure in the environment log; the caller
            # already has its acknowledgement and must not block on pip.
            pass

    threading.Thread(target=work, name=f'remote-dependency-{name}', daemon=True).start()
    return {**environment_snapshot(service),
            'queued': {'kind': kind, 'name': requirement}}


def environment_cancel(service, payload: dict | None = None) -> dict:
    """Stop one environment preparation started through the remote agent."""
    import os
    import signal
    from operon import environment_install
    payload = payload or {}
    name = str(payload.get('name') or '')
    if not name:
        raise ValueError('environments_cancel requires an environment name')
    snapshot = environment_snapshot(service)
    root = snapshot.get('root')
    progress = environment_install.read_progress(name, root) or {}
    pid = progress.get('pid')
    stopped = False
    if isinstance(pid, int) and pid > 1:
        try:
            os.kill(pid, signal.SIGTERM)
            stopped = True
        except OSError:
            stopped = False
    with _ENVIRONMENT_LOCK:
        _ENVIRONMENT_JOBS.pop(name, None)
    environment_install.mark_cancelled(name, root)
    return {**environment_snapshot(service), 'cancelled': True, 'stopped': stopped}


def environment_retry(service, payload: dict | None = None) -> dict:
    """Cancel a stale preparation and start it again in one round trip."""
    payload = payload or {}
    name = str(payload.get('name') or '')
    if not name:
        raise ValueError('environments_retry requires an environment name')
    try:
        environment_cancel(service, {'name': name})
    except Exception:
        pass
    return environment_prepare(service, {'names': [name], 'force': True})


def environment_prepare(service, payload: dict | None = None) -> dict:
    from operon import environment_install
    payload = payload or {}
    names = payload.get('names') or None
    dependencies = bool(payload.get('dependencies'))
    force = bool(payload.get('force'))
    snapshot = environment_snapshot(service)
    if snapshot.get('error'):
        return snapshot
    started = []
    with _ENVIRONMENT_LOCK:
        for name, entry in (snapshot.get('environments') or {}).items():
            if names is not None and name not in names:
                continue
            status = (entry or {}).get('status') or ''
            if not force and not environment_install.needs_preparation(status):
                continue
            if name in _ENVIRONMENT_JOBS:
                continue
            _ENVIRONMENT_JOBS[name] = {'id': 'env-' + uuid.uuid4().hex[:12], 'phase': 'queued',
                                       'started_at': _now_iso()}
            started.append(name)

    def worker(name: str):
        try:
            environment_install.prepare(name, snapshot['root'], source=snapshot['source'])
        except Exception as exc:
            # A request that acknowledged the work must not hide its failure: the
            # next "prepare" call would look like a no-op on a stale snapshot.
            try:
                environment_install.mark_failed(name, snapshot['root'], exc)
            except Exception:
                pass
        finally:
            with _ENVIRONMENT_LOCK:
                _ENVIRONMENT_JOBS.pop(name, None)

    for name in started:
        threading.Thread(target=worker, args=(name,), name=f'environment-{name}', daemon=True).start()
    if dependencies:
        affected = []
        for env_name, entry in (snapshot.get('environments') or {}).items():
            if names is not None and env_name not in names:
                continue
            affected.extend((entry or {}).get('used_by') or [])
        ids = sorted(set(affected))

        def repair():
            try:
                service.dependencies.check(repair=True, repair_r=True, ids=ids or None)
            except Exception:
                pass
        if ids:
            threading.Thread(target=repair, name='dependency-repair', daemon=True).start()
    jobs = {name: _ENVIRONMENT_JOBS[name].get('id') for name in started if name in _ENVIRONMENT_JOBS}
    return {**environment_snapshot(service), 'started': started, 'jobs': jobs,
            'dependencies': dependencies}


def pool_stop(service, payload):
    """Stop the pool serving this workspace; force discards active work."""
    from operon import managed_pool
    force = payload.get('force') is True
    try:
        return managed_pool.stop_pool(force=force)
    except managed_pool.PoolClientError as exc:
        return {'stopped': False, 'forced': force, 'busy': True, 'error': str(exc)}


class RemoteService:
    def __init__(self, workspace, input_roots=None):
        self._lifecycle = threading.RLock()
        self._active_requests = 0
        self._draining = False
        self.stop_requested = threading.Event()
        from src.web.service import JobService, Settings
        from src.web.operator_catalog import catalog_from_descriptors
        from src.task.memory.config import MemoryConfig, AUTO_BUDGET_FRACTION
        workspace = Path(workspace).expanduser().resolve()
        self.workspace = workspace
        workspace.mkdir(parents=True, exist_ok=True)
        code = Path(__file__).resolve().parents[2]
        library_root = None
        candidate = code / 'library'
        if (candidate / 'registry.json').is_file() or (candidate / 'libraries').is_dir():
            library_root = candidate
        elif (code.parent.parent / 'library').is_dir():
            library_root = code.parent.parent / 'library'
        # Explicit interpreter selection must also select its command-line tools.
        binary_directory = str(Path(sys.executable).parent)
        current_path = os.environ.get('PATH', '')
        if os.path.normcase(current_path.split(os.pathsep)[0]) != os.path.normcase(binary_directory):
            os.environ['PATH'] = binary_directory + os.pathsep + current_path
        from operon.application import Application
        self.application = Application(Settings(workspace, workspace/'.studio', code/'frontend/dist',
                                          code_root=code, input_roots=input_roots or [Path('/')],
                                          manifest_only_registry=library_root is None,
                                          library_root=library_root),
                                  catalog_from_descriptors())
        self.service = self.application.service
        self.memory = {'automatic_memory_budget_bytes': self.service.resources()['capacity_bytes'],
                       'automatic_memory_fraction': AUTO_BUDGET_FRACTION}
        from .handshake import ManifestHandshake
        self.handshake = ManifestHandshake(self.service, self.memory)
        from .transfers import TransferStore
        self.transfers = TransferStore(workspace/'.studio'/'transfers', resolve_input=self.transfer_path)
        self.transport_leases = {}
        self.transport_active = {}
        self.lease_lock = threading.RLock()
        # Generated checkpoints and verified upload groups belong to this
        # service even when external input roots were restricted by the owner.
        if workspace not in self.service.settings.input_roots:
            self.service.settings.input_roots.append(workspace)

    def alive(self):
        """Daemon liveness includes every durable responsibility, not just workers."""
        handshake = getattr(self, 'handshake', None)
        transfers = getattr(self, 'transfers', None)
        application = getattr(self, 'application', None)
        canvas = getattr(application, 'canvas_plans', None)
        exports = getattr(application, 'plan_exports', None)
        with self._lease_guard():
            leases = bool(self.transport_leases) or bool(self.transport_active)
        return bool(self.service.processes or self.service.threads or leases or
                    (canvas is not None and canvas.active) or
                    (exports is not None and (exports._active or exports._pending)) or
                    (handshake is not None and handshake.maintenance_running) or
                    (transfers is not None and bool(getattr(transfers, 'tokens', {}))))

    def _lease_guard(self):
        # Lightweight dispatch fixtures construct RemoteService via __new__;
        # initialize concurrency state lazily so the public method contract
        # does not depend on the constructor.
        if not hasattr(self, 'lease_lock'):
            self.lease_lock = threading.RLock()
            self.transport_active = {}
        return self.lease_lock

    def _purge_transport_leases(self):
        now = time.monotonic()
        expired = []
        with self._lease_guard():
            for key, expires in list(self.transport_leases.items()):
                if expires < now and not self.transport_active.get(key):
                    del self.transport_leases[key]
                    expired.append(key)
        for key in expired:
            transport_admission(self.service).release(key)

    def _begin_transfer(self, key):
        """Pin a transport lease for the duration of an operation.

        Timeout cleanup must never release a buffer while a transfer still owns
        it; the active counter makes expiry conditional on no live operation.
        """
        with self._lease_guard():
            self.transport_active[key] = self.transport_active.get(key, 0) + 1
            if key not in self.transport_leases:
                ready = transport_admission(self.service).reserve(
                    key, {'reserved_bytes': 6 * 1024**2, 'cpu_threads': 0, 'kind': 'transport'})
                if not ready:
                    self.transport_active[key] -= 1
                    if not self.transport_active[key]:
                        del self.transport_active[key]
                    raise ValueError('Transfer memory is unavailable; retry admission')
            self.transport_leases[key] = time.monotonic() + 30

    def _end_transfer(self, key):
        with self._lease_guard():
            count = self.transport_active.get(key, 0) - 1
            if count > 0:
                self.transport_active[key] = count
            else:
                self.transport_active.pop(key, None)
            if key in self.transport_leases:
                self.transport_leases[key] = time.monotonic() + 30

    def transfer_path(self, value):
        from .transfers import no_symlinks
        no_symlinks((self.service.root/value).expanduser())
        return self.path(value)

    def graph_catalog(self, graph):
        return self.service.plugins.catalog_for(graph, self.service.base_catalog)

    def _journal(self):
        runtime = getattr(self.service, 'engine', None)
        if runtime is None or getattr(runtime, 'error', None):
            return None
        return getattr(runtime, 'journal', None)

    def _recover_run(self, request_id, digest):
        """Find durable job evidence for an interrupted submission."""
        for index, item in enumerate(self.service.jobs_dir.glob('*/job.json')):
            if index >= 10000:
                break
            try:
                record = json.loads(item.read_text(encoding='utf-8'))
            except (OSError, ValueError):
                continue
            runtime = record.get('graph', {}).get('runtime', {})
            if runtime.get('remote_request_id') != request_id:
                continue
            if runtime.get('remote_request_digest') != digest:
                raise ValueError('Submission identity was already used with a different graph')
            return self.service.details(record['id'])
        return None

    def events(self, params):
        if self.service.pool_remote:
            return self.service.events(params.get('after', params.get('cursor', 0)),
                                       run_id=params.get('run_id'), limit=params.get('limit', 200))
        journal = self._journal()
        if journal is None:
            return {'available': False, 'events': [], 'cursor': int(params.get('after', 0) or 0),
                    'has_more': False}
        after = params.get('after', params.get('cursor', 0))
        limit = params.get('limit', 200)
        try:
            after = max(0, int(after))
            limit = max(1, min(int(limit), 1000))
        except (TypeError, ValueError) as exc:
            raise ValueError('Invalid event cursor or limit') from exc
        page = journal.page(after, run_id=params.get('run_id'), limit=limit,
                            max_bytes=params.get('max_bytes', 256 * 1024))
        return {**page.to_json(), 'available': True}

    def close(self):
        self.handshake.close()
        with self._lease_guard():
            leases = list(self.transport_leases)
            self.transport_leases.clear()
            self.transport_active.clear()
        for lease in leases:
            transport_admission(self.service).release(lease)
        if hasattr(self, 'application'):
            self.application.shutdown()
        else:
            self.service.shutdown()

    def path(self, value):
        path = (self.service.root / value).expanduser().resolve()
        if not any(path.is_relative_to(root.resolve()) for root in self.service.settings.input_roots):
            raise ValueError('Path is outside the configured server data roots')
        return path

    def retire_if_idle(self):
        with self._lifecycle:
            if self._draining:
                return {'retired': True}
            if self._active_requests:
                return {'retired': False, 'reason': 'Requests are still in progress'}
            self._draining = True  # Reject new work before inventory, under the same lock.
        try:
            busy = self.alive() or any(job.get('status') in
                ('queued', 'preparing', 'uploading', 'running', 'waiting_connection', 'recovery_required')
                or job.get('logs_complete') is False for job in self.service.history())
            if busy:
                with self._lifecycle:
                    self._draining = False
                return {'retired': False, 'reason': 'Tasks, transfers or maintenance are still active'}
            self.stop_requested.set()
            return {'retired': True}
        except Exception:
            with self._lifecycle:
                self._draining = False
            raise

    def record_dispatch_error(self, exc, context):
        """Persist a sanitized dispatch traceback without touching jobs/state."""
        _event_log(self.workspace, 'dispatch.events.jsonl', {
            'event': 'dispatch_error',
            'operation': context.get('method'),
            'request_id': context.get('request_id'),
            'code': getattr(exc, 'code', type(exc).__name__),
            'error': str(exc),
            'traceback': traceback.format_exc(),
        })

    def dispatch(self, method, params):
        # Small direct-dispatch fixtures omit the daemon lifecycle entirely.
        if not hasattr(self, '_lifecycle'):
            return self._dispatch(method, params)
        if method == 'retire_if_idle':
            return self.retire_if_idle()
        with self._lifecycle:
            if self._draining:
                raise CommandError('server_draining', 'Server is restarting after an upgrade; reconnect.')
            self._active_requests += 1
        try:
            return self._dispatch(method, params)
        finally:
            with self._lifecycle:
                self._active_requests -= 1

    def _dispatch(self, method, params):
        if method != 'transport_release':
            self._purge_transport_leases()
        if method == 'canvas.capabilities':
            return {'version': 1, 'prepare': True, 'results': True, 'resumable_transfer': True}
        if method.startswith('canvas.'):
            from operon.canvas_api import PrepareCanvas, ExecuteCanvas
            service = self.application.canvas_plans
            if method == 'canvas.prepare':
                value = PrepareCanvas.model_validate(params)
                return service.start(value.graph, value.request_id)
            if method == 'canvas.status':
                return service.status(params['request_id'])
            if method == 'canvas.cancel':
                return service.cancel(params['request_id'])
            if method == 'canvas.outcome':
                return service.outcome(params['request_id'])
            if method == 'canvas.execute':
                value = ExecuteCanvas.model_validate(params)
                return service.execute(value.preparation_id, action=value.action,
                                       request_id=value.request_id, output=value.output)
            raise ValueError('Unknown canvas operation')
        if method == 'plan.read':
            operation = params['operation']
            plans = self.application.plans
            if operation not in ('details', 'cancel', 'events', 'attempts', 'artifacts', 'logs',
                                 'artifact_files', 'artifact_preview', 'artifact_file'):
                raise ValueError('Unknown plan operation')
            run = params['run_id']
            if operation == 'artifact_file':
                # Resolve ownership using opaque IDs before exposing a transport ref.
                with_result = plans.open_artifact(run, **params.get('query', {}))
                try:
                    descriptor = with_result.descriptor
                    path = self.service.directory / descriptor['relative_path']
                    return {'descriptor': descriptor, 'transfer': {'path': str(path),
                        'bytes': descriptor['size_bytes'], 'sha256': descriptor['sha256']}}
                finally:
                    with_result.close()
            return getattr(plans, operation)(run, **params.get('query', {}))
        if method in ('handshake', 'bootstrap'):
            value = self.handshake.response(params, legacy=method == 'bootstrap')
            if getattr(self.service, 'pool_remote', False):
                try:
                    self.service._ensure_pool_session()
                    capabilities = self.service.pool_client.status().get('capabilities', {})
                    if 'cluster.controller_fence.v1' in capabilities:
                        value['handshake']['engine_capabilities'].append('cluster.controller_fence.v1')
                        value['cluster_controller'] = capabilities['cluster.controller_fence.v1']
                    if 'cluster.invocation.v1' in capabilities:
                        value['handshake']['engine_capabilities'].append('cluster.invocation.v1')
                    if 'cluster.same_host_artifacts.v1' in capabilities:
                        value['handshake']['engine_capabilities'].append('cluster.same_host_artifacts.v1')
                except Exception:
                    # Optional cluster capability never turns unavailable pool
                    # discovery into an assertion that fenced control is ready.
                    pass
            return value
        if method in ('cluster.submit', 'cluster.lookup', 'cluster.status', 'cluster.cancel',
                      'cluster.plan.submit', 'cluster.plan.lookup', 'cluster.plan.status', 'cluster.plan.cancel'):
            # This daemon is reached through the SSH-authenticated OS account and
            # its 0600 local socket. Forward only to its existing registered pool.
            if not getattr(self.service, 'pool_remote', False):
                raise CommandError('capability_unavailable', 'Cluster control requires the shared host pool')
            self.service._ensure_pool_session()
            if Path(params.get('workspace', '')).expanduser().resolve() != self.service.root:
                raise CommandError('unauthorized', 'Cluster request targets another SSH workspace')
            if params.get('principal') != self.service.pool_principal:
                raise CommandError('unauthorized', 'Cluster principal is not this authenticated SSH account')
            return self.service.pool_client.request(method, params)
        if method == 'library_manifest':
            from copy import deepcopy
            from .library import inventory
            return {**inventory(self.service.plugins.state()),
                    'build': deepcopy(self.handshake.build),
                    'build_id': self.handshake.build.get('build_id', '')}
        if method == 'host_capacity':
            from operon import nodes
            marker = None
            try:
                from operon import environment_install
                candidate = Path(environment_install.root()) / 'core' / 'bin' / 'python'
                marker = str(candidate) if candidate.is_file() else None
            except Exception:  # noqa: BLE001 - capacity still answers without a marker
                marker = None
            return nodes.snapshot(self.workspace, ready_marker=marker)
        if method == 'build_info':
            from copy import deepcopy
            return {'build': deepcopy(self.handshake.build),
                    'build_id': self.handshake.build.get('build_id', ''),
                    'library': deepcopy(self.handshake.build.get('library', {}))}
        if method == 'pool_info':
            return pool_snapshot(self.service)
        if method == 'pool_stop':
            return pool_stop(self.service, params or {})
        if method == 'environments':
            return environment_snapshot(self.service)
        if method == 'environments_prepare':
            return environment_prepare(self.service, params or {})
        if method == 'environments_cancel':
            return environment_cancel(self.service, params)
        if method == 'environments_retry':
            return environment_retry(self.service, params)
        if method == 'environments_dependency':
            return environment_dependency(self.service, params)
        if method == 'environments_log':
            return environment_log(self.service, str((params or {}).get('name') or ''),
                                   (params or {}).get('limit') or 200)
        if method == 'environments_repair':
            return environment_repair(self.service, params)
        if method == 'resources':
            from src.web import resource_api
            return resource_api.snapshot(self.service)
        if method == 'resources_link':
            from src.web import resource_api
            payload = params or {}
            return resource_api.link(self.service, str(payload.get('name') or ''),
                                     str(payload.get('source') or ''),
                                     bool(payload.get('replace')),
                                     str(payload.get('unit') or '') or None)
        if method == 'resources_unlink':
            from src.web import resource_api
            payload = params or {}
            return resource_api.unlink(self.service, str(payload.get('name') or ''),
                                       str(payload.get('unit') or '') or None)
        if method == 'resources_download':
            from src.web import resource_api
            payload = params or {}
            return resource_api.start(self.service,
                                      str(payload.get('name') or ''),
                                      str(payload.get('root') or '') or None,
                                      bool(payload.get('overwrite')),
                                      str(payload.get('unit') or '') or None)
        if method == 'resources_cancel':
            from src.web import resource_api
            name = str((params or {}).get('name') or '')
            try:
                return resource_api.cancel(self.service, name)
            except KeyError as error:
                raise CommandError('no_running_download',
                                   f'no running download: {name}') from error
        if method == 'resources_log':
            from src.web import resource_api
            payload = params or {}
            return resource_api.read_log(self.service, str(payload.get('name') or ''),
                                         payload.get('limit') or 200)
        if method == 'library_remove':
            from operon.library_install import uninstall_library
            name = str((params or {}).get('name') or '')
            if not name:
                raise ValueError('library_remove requires a package name')
            return uninstall_library(self.service.plugins, name)
        if method == 'library_install':
            # JobService wraps _install_many in the shared environment gate.
            # Acquiring it here too would reject our own install as concurrent
            # maintenance. Its mutation boundary remains the single authority.
            return self.handshake.install_library(params, self.transfers, maintenance_factory=lambda: None)
        if method == 'refresh_registry':
            guard = (self.service.execution_environment_guard() if hasattr(self.service, 'execution_environment_guard') else getattr(self.service, 'environment_guard', None))
            environment = self.service.environment_identity() if guard is not None else None
            def acquire():
                return (guard, guard.begin(owner=self.service.owner, kind='registry-refresh',
                                           environment=environment)) if guard is not None else None
            # The handshake's single-flight decision owns acquisition. A
            # repeated refresh observes the existing operation, not a second
            # conflicting environment maintenance request.
            return self.handshake.refresh(params, maintenance_factory=acquire)
        if method == 'refresh_status':
            return self.handshake.response(params, legacy=True)
        if method in ('transport_reserve', 'transport_release'):
            key = params['id']
            if not isinstance(key, str) or not __import__('re').fullmatch('transfer-[a-f0-9]{32}', key):
                raise ValueError('Invalid transfer allocation identity')
            if method == 'transport_release':
                with self._lease_guard():
                    if self.transport_active.get(key):
                        raise ValueError('A transfer still owns this allocation')
                    self.transport_leases.pop(key, None)
                transport_admission(self.service).release(key)
                return {'released': True}
            # Framing/decoded buffers are bounded by the transport implementation.
            with self._lease_guard():
                reserved = transport_admission(self.service).reserve(
                    key, {'reserved_bytes': 6 * 1024**2, 'cpu_threads': 0, 'kind': 'transport'})
                if reserved:
                    self.transport_leases[key] = time.monotonic() + 30
            return {'reserved': reserved}
        if method.startswith('transfer_'):
            params = dict(params)
            lease = params.pop('_transport_lease', None)
            if lease:
                self._begin_transfer(lease)
                try:
                    return self.transfers.dispatch(method, params)
                finally:
                    self._end_transfer(lease)
            return self.transfers.dispatch(method, params)
        if method == 'events':
            return self.events(params)
        if method == 'engine_status':
            return self.service._engine_status()
        from src.web.models import Graph
        from src.web.service import safe_json
        from src.web.graph import compile_graph, relative_manifest
        from src.web.contracts import analyze_graph
        from src.web.parameters import freeze_graph
        from src.web.routes import prepare_interface
        service = self.service
        if method == 'validate_environment':
            from operon.readiness import inspect_declared_environment
            ids = params.get('ids')
            if not isinstance(ids, list) or any(not isinstance(key, str) for key in ids):
                raise ValueError('ids must be an explicit list of declaration IDs')
            scripts = params.get('scripts', {})
            if not isinstance(scripts, dict):
                raise ValueError('scripts must map node IDs to frozen script declarations')
            graph = Graph.model_validate(params['graph']) if params.get('graph') else None
            guard = (service.execution_environment_guard() if hasattr(service, 'execution_environment_guard') else getattr(service, 'environment_guard', None))
            token = None
            if params.get('repair') is True and guard is not None:
                token = guard.begin(owner=service.owner, kind='remote-repair',
                                    environment=service.environment_identity())
            try:
                return inspect_declared_environment(service, ids, graph=graph, scripts=scripts,
                                                    repair=params.get('repair') is True)
            finally:
                if token is not None:
                    guard.end(token)
        if method == 'resources':
            return service.resources()
        if method == 'pin_compatibility':
            from src.web.execution_pins import validated_pins
            return validated_pins(service, params.get('pins', {}))
        if method == 'file_stat':
            values = params.get('paths', [])
            if not isinstance(values, list) or len(values) > 256:
                raise ValueError('Invalid file metadata request')
            result = []
            for value in values:
                path = self.transfer_path(str(self.path(params.get('base', '.')) / value))
                result.append({'path': str(path), 'exists': path.is_file(),
                               'bytes': path.stat().st_size if path.is_file() else None})
            return result
        if method == 'exchange':
            key = params['job_id']; service.require(key)
            path = service.jobs_dir / key / 'output' / 'exchange.json'
            if not path.is_file():
                raise ValueError('The stage has no committed exchange outputs')
            value = json.loads(path.read_text(encoding='utf-8'))
            return value
        if method == 'preview':
            return service.preview(params['job_id'], params['artifact_id'],
                                   offset=params.get('offset', 0), limit=params.get('limit', 20))
        if method == 'result_files':
            key = params['job_id']; service.require(key)
            return service.result_files(key)
        if method == 'output_file':
            key = params['job_id']; kind = params['kind']
            if kind == 'artifact':
                path, _ = service.artifact(key, params['artifact_id'])
            elif kind == 'artifact_file':
                path = service.artifact_file(key, params['artifact_id'], params['role'])
            elif kind == 'figure':
                path = service.figure_file(key, params['index'], format=params.get('format'), **({'figure_id': params['figure_id']} if 'figure_id' in params else {}))
            elif kind == 'export':
                path = service.export_file(key, params['index'])
            elif kind == 'result':
                path = service.result_path(key, params['path'])
            else:
                raise ValueError('Unknown output kind')
            return {'path': str(path), 'bytes': path.stat().st_size, 'name': path.name}
        if method == 'browse':
            folder = self.path(params.get('path') or '.')
            if not folder.is_dir():
                raise ValueError('Choose an existing server directory')
            offset = max(0, int(params.get('offset', 0)))
            entries = []
            with os.scandir(folder) as listing:
                for item in listing:
                    if item.name.startswith('.') and not params.get('hidden', False):
                        continue
                    try:
                        path = self.path(str(folder/item.name))
                        info = item.stat()
                        entries.append({'name': item.name, 'path': str(path), 'directory': item.is_dir(),
                                        'bytes': info.st_size, 'modified': info.st_mtime})
                    except (PermissionError, FileNotFoundError, ValueError):
                        continue
            entries.sort(key=lambda item: (not item['directory'], item['name'].lower()))
            return {'path': str(folder), 'parent': str(folder.parent), 'entries': entries[offset:offset+200],
                    'next_offset': offset+200 if offset+200 < len(entries) else None}
        if method == 'source':
            from operon.reader_selection import candidates as select
            path = self.path(params['path'])
            if not path.is_file():
                raise ValueError('Choose an existing server file')
            candidates = select(service.catalog['readers'], path, params.get('reader'), check_siblings=True)
            if len(candidates) != 1:
                raise ValueError('No unique registered Reader matches this server file')
            reader = candidates[0]; settings = reader.get('file_input', {})
            return {'filename': path.name, 'reader': reader['id'], 'bytes': path.stat().st_size,
                    'source': {'reader': reader['id'], 'path': str(path), 'dims': settings.get('dims', ['sample', 'feature']),
                               'labels': settings.get('labels', {'sample': 'auto', 'feature': 'builtin'}),
                               'args': reader.get('runtime_defaults', {})}}
        if method in ('validate', 'prepare', 'export', 'run'):
            graph = Graph.model_validate(params['graph'])
            if method == 'run':
                request_id = params['request_id']
                digest = hashlib.sha256(json.dumps(params['graph'], sort_keys=True).encode()).hexdigest()
                if not isinstance(request_id, str) or not __import__('re').fullmatch('[a-f0-9-]{32,36}', request_id):
                    raise ValueError('Invalid submission identity')
                # Reconnect/retry must return the original job, even if the SSH
                # response vanished after the process was spawned.
                recovered = self._recover_run(request_id, digest)
                if recovered is not None:
                    return recovered
                graph.runtime['remote_request_id'] = request_id
                graph.runtime['remote_request_digest'] = digest
                from operon.readiness import required_ids, required_scripts, inspect_declared_environment
                checked = inspect_declared_environment(service, required_ids(graph, self.graph_catalog(graph)),
                                                       graph=graph, scripts=required_scripts(graph))
                missing = [key for key, item in {**checked['entries'], **checked['scripts']}.items()
                           if item.get('status') != 'passed']
                if missing:
                    raise ValueError('Execution dependencies are not ready: ' + ', '.join(missing))
                if getattr(service, 'pool_remote', False):
                    # The pool owns the durable claim. Forward the original key,
                    # including after a lost SSH response; never scan then launch
                    # with a new identity in a different allocator.
                    return service.launch(graph, request_id=request_id)
                journal = self._journal()
                if journal is None:
                    from .client import RemoteError
                    raise RemoteError('The submission journal is unavailable; no job was started.',
                                      code='engine_unavailable')
                try:
                    claim = journal.claim(request_id, digest, operation='run',
                                          receipt={'request_id': request_id})
                except Exception as exc:
                    if getattr(exc, 'code', None) == 'idempotency_conflict':
                        raise ValueError('Submission identity was already used with a different graph') from exc
                    from .client import RemoteError
                    from operon.engine.contracts import CommitOutcomeUnknown
                    if isinstance(exc, CommitOutcomeUnknown):
                        recovered = self._recover_run(request_id, digest)
                        if recovered is not None:
                            return recovered
                        raise RemoteError('Submission acknowledgement was lost; retry the same request identity.',
                                          code='submission_uncertain') from exc
                    raise RemoteError('The submission journal is unavailable; no job was started.',
                                      code='engine_unavailable') from exc
                if not claim.created:
                    record = claim.record
                    if record.get('run_id'):
                        return service.details(record['run_id'])
                    if record['state'] in ('claimed', 'launching'):
                        record = journal.wait(request_id, timeout=120) or record
                        if record.get('run_id'):
                            return service.details(record['run_id'])
                    recovered = self._recover_run(request_id, digest)
                    if recovered is not None:
                        journal.bind(request_id, recovered['id'])
                        return recovered
                    raise CommandError('submission_uncertain',
                                       'Submission was interrupted; inspect jobs before retrying', 409,
                                       {'request_id': request_id})
                try:
                    result = service.launch(graph)
                except Exception as exc:
                    recovered = self._recover_run(request_id, digest)
                    if recovered is not None:
                        journal.bind(request_id, recovered['id'])
                        return recovered
                    journal.fail(request_id, str(exc))
                    raise
                journal.bind(request_id, result['id'])
                return result
            catalog = self.graph_catalog(graph)
            if method == 'prepare':
                return prepare_interface(freeze_graph(service.plugins.pin(graph), catalog, service.root), catalog,
                                         service.root).model_dump(mode='json')
            manifest, order = compile_graph(graph, catalog, service.root,
                                            require_files=method == 'validate' and params.get('require_files', True), input_roots=service.settings.input_roots)
            if method == 'export':
                import yaml
                return {'yaml': yaml.safe_dump(relative_manifest(manifest, service.root/graph.base_dir, catalog),
                                               allow_unicode=True, sort_keys=False), 'order': order}
            return {'valid': True, 'order': order, 'contracts': analyze_graph(graph, catalog, service.root)}
        if method == 'history':
            return service.history()
        if method == 'console':
            key = params['job_id']; service.require(key)
            path = service.jobs_dir/key/'console.log'
            if not path.is_file():
                _, result = service.console_snapshot(key, service.details(key))
                return {'text': result['console'], 'offset': 0, 'done': True}
            with path.open('rb') as handle:
                handle.seek(max(0, int(params.get('offset', 0))))
                data = handle.read(64 * 1024)
                # Return bytes as base64 so chunk boundaries cannot split UTF-8.
                import base64
                return {'base64': base64.b64encode(data).decode(), 'offset': handle.tell(),
                        'done': not bool(handle.read(1))}
        if method == 'job':
            return service.details(params['job_id'])
        if method == 'cancel':
            return service.cancel(params['job_id'])
        if method == 'poll':
            key = params['job_id']; job = service.details(key)
            offsets = params.get('offsets', {}); result = {}; events = []; eof = True
            for path in service.event_paths(key):
                name = _event_name(path, key, service.jobs_dir, job)
                start = max(0, int(offsets.get(name, 0)))
                with path.open('rb') as handle:
                    handle.seek(min(start, path.stat().st_size))
                    for _ in range(200):
                        position = handle.tell(); line = handle.readline()
                        if not line: break
                        if not line.endswith(b'\n'):
                            handle.seek(position); break
                        try: events.append(json.loads(line))
                        except (ValueError, UnicodeDecodeError): pass
                    result[name] = handle.tell()
                    eof = eof and not bool(handle.read(1))
            _, console = service.console_snapshot(key, job)
            job.pop('graph', None)
            return safe_json({'job': job, 'events': sorted(events, key=lambda e: e.get('time', '')),
                              'offsets': result, 'done': job['status'] not in ('running', 'queued', 'preparing', 'uploading') and job.get('logs_complete', True) and eof,
                              **(console or {})})
        raise ValueError('Unknown remote operation')


def rpc(workspace, request):
    """Call the shared daemon, classifying pre-dispatch connection failures.

    A retry is safe only when connect failed before the request was sent.  Read
    or write failures may have reached a stateful operation and are never
    replayed.  Business exceptions from the daemon are returned as framed
    responses and are not converted into transport failures.
    """
    address = socket_path(workspace)
    client = None
    try:
        client = socket.socket(socket.AF_UNIX)
        client.settimeout(90)
        try:
            client.connect(str(address))
        except (FileNotFoundError, ConnectionRefusedError) as exc:
            raise DaemonUnavailable(
                f'The remote RPC daemon is unavailable at {address}',
                details={'phase': 'connect', 'retryable': True, 'socket': str(address),
                         'path': str(address), 'errno': getattr(exc, 'errno', None),
                         'request_id': request.get('id'), 'method': request.get('method'),
                         'cause': f'{type(exc).__name__}: {exc}'}) from exc
        try:
            send_message(client, request)
        except OSError as exc:
            raise RpcTransportError(
                'The RPC request could not be sent completely; it is not replayed',
                details={'phase': 'send', 'retryable': False, 'request_id': request.get('id'),
                         'method': request.get('method'),
                         'cause': f'{type(exc).__name__}: {exc}'}) from exc
        try:
            return read_message(client)
        except OSError as exc:
            raise RpcTransportError(
                'The RPC daemon connection failed after dispatch; it is not replayed',
                details={'phase': 'read', 'retryable': False, 'request_id': request.get('id'),
                         'method': request.get('method'),
                         'cause': f'{type(exc).__name__}: {exc}'}) from exc
    finally:
        if client is not None:
            client.close()


class DaemonUnavailable(OSError):
    code = 'service_unavailable'

    def __init__(self, message, *, details=None):
        super().__init__(message)
        self.details = details or {}


class RpcTransportError(OSError):
    code = 'remote_transport_error'

    def __init__(self, message, *, details=None):
        super().__init__(message)
        self.details = details or {}


def _sanitize_diagnostic(value):
    """Remove credential-shaped text before a traceback reaches a log.

    Exception strings are not trusted to be free of secrets.  This is applied
    to the complete formatted traceback, not only the message field.
    """
    text = str(value)
    text = re.sub(r'(?i)\b(password|passphrase|token|secret|authorization)\b'
                  r'\s*[:=]\s*([^\s,;]+)', lambda m: m.group(1) + '=<redacted>', text)
    text = re.sub(r'(?i)(https?://)[^/\s:@]+:[^/\s@]+@', r'\1<redacted>@', text)
    return text


def _event_log(workspace, filename, fields, *, limit=1024 * 1024):
    """Append a bounded, machine-readable diagnostic outside protocol stdout."""
    try:
        directory = Path(workspace) / '.studio' / 'remote'
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / filename
        try:
            if path.stat().st_size >= limit:
                path.replace(path.with_suffix(path.suffix + '.1'))
        except OSError:
            pass
        payload = {'time': datetime.now(timezone.utc).isoformat(), **fields}
        payload = {key: _sanitize_diagnostic(value) if isinstance(value, str) else value
                   for key, value in payload.items()}
        line = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str) + '\n'
        with path.open('a', encoding='utf-8') as stream:
            stream.write(line)
    except OSError:
        pass


def _bridge_event(workspace, **fields):
    """Local, secret-free bridge diagnostics; never writes to the RPC stream."""
    _event_log(workspace, 'bridge.events.jsonl', fields)


def _response_details(exc, *, request_id=None, method=None, trace_id=None, **extra):
    details = dict(getattr(exc, 'details', None) or {})
    details.setdefault('operation', method)
    details.setdefault('request_id', request_id)
    details.setdefault('trace_id', trace_id or uuid.uuid4().hex)
    details.update(extra)
    return details


def dispatch_with_recovery(workspace, request, *, ensure=None, log=None):
    """Dispatch one request, recovering only a pre-send missing daemon.

    The exact same request id is retried at most once after `ensure_daemon`.
    A post-send failure is surfaced and never replayed.  This is the common
    boundary used by the SSH bridge, so HTTP/MCP see stable codes and details.
    """
    ensure = ensure or ensure_daemon
    log = log or _bridge_event
    request_id = request.get('id')
    trace_id = uuid.uuid4().hex
    try:
        return rpc(workspace, request)
    except DaemonUnavailable as first:
        log(workspace, event='daemon_missing', request_id=request_id, trace_id=trace_id,
            method=request.get('method'), phase=first.details.get('phase'),
            error=str(first), cause=first.details.get('cause'),
            traceback=traceback.format_exc())
        try:
            ensure(workspace)
        except Exception as exc:  # noqa: BLE001 - explicit recovery failure
            details = _response_details(
                first, request_id=request_id, method=request.get('method'), trace_id=trace_id,
                phase='ensure', retryable=True, recovery='failed',
                recovery_attempted=True, cause=f'{type(exc).__name__}: {exc}')
            log(workspace, event='daemon_recovery_failed', request_id=request_id,
                trace_id=trace_id, method=request.get('method'), cause=details['cause'],
                traceback=traceback.format_exc())
            raise DaemonUnavailable(
                'The remote service could not be restarted. '
                f'Inspect .studio/remote/bridge.events.jsonl on the server (trace {trace_id}).',
                details=details) from exc
        try:
            response = rpc(workspace, request)
            log(workspace, event='daemon_recovered', request_id=request_id, trace_id=trace_id,
                method=request.get('method'), retry=1)
            return response
        except DaemonUnavailable as retry_exc:
            details = _response_details(
                retry_exc, request_id=request_id, method=request.get('method'), trace_id=trace_id,
                recovery='retry_failed', recovery_attempted=True, retry=1)
            log(workspace, event='daemon_recovery_failed', request_id=request_id,
                trace_id=trace_id, method=request.get('method'),
                cause=retry_exc.details.get('cause'), traceback=traceback.format_exc())
            raise DaemonUnavailable(
                'The remote service did not respond after recovery. '
                f'Inspect .studio/remote/bridge.events.jsonl on the server (trace {trace_id}).',
                details=details) from retry_exc
        except RpcTransportError as retry_exc:
            details = _response_details(
                retry_exc, request_id=request_id, method=request.get('method'), trace_id=trace_id,
                recovery='retry_transport_failed', recovery_attempted=True, retry=1)
            log(workspace, event='daemon_recovery_transport_failed', request_id=request_id,
                trace_id=trace_id, method=request.get('method'),
                cause=retry_exc.details.get('cause'), traceback=traceback.format_exc())
            raise RpcTransportError('The remote service failed after recovery; it was not replayed',
                                    details=details) from retry_exc
    except RpcTransportError as exc:
        # The request may already have been dispatched; never call ensure/retry.
        log(workspace, event='rpc_transport_failed', request_id=request_id, trace_id=trace_id,
            method=request.get('method'), phase=exc.details.get('phase'),
            cause=exc.details.get('cause'), traceback=traceback.format_exc())
        raise


def ensure_daemon(workspace, *, upgrade=False):
    import fcntl
    from .handshake import daemon_request, validate_daemon_response
    address = socket_path(workspace)
    with address.with_suffix('.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            response = rpc(workspace, daemon_request())
            value = validate_daemon_response(response)
            if not upgrade:
                return  # Ordinary connections reuse a compatible installed server.
            from operon import __version__
            expected_root = Path(__file__).resolve().parents[2]
            same_installation = (value.get('version') == __version__
                                 and value.get('code_root') == str(expected_root)
                                 and value.get('python') == sys.executable)
            if same_installation:
                return
            # Upgrading files does not replace a daemon already in memory.
            # Ask it to close only after atomically rejecting work and confirming
            # there are no tasks/transfers/maintenance or other active requests.
            retired = rpc(workspace, {'method': 'retire_if_idle', 'params': {}})
            if not retired.get('ok') or not retired.get('value', {}).get('retired'):
                reason = retired.get('value', {}).get('reason') or 'This older server cannot retire automatically'
                raise RuntimeError(reason + '. Finish old server tasks and close the previous server, then reconnect. '
                                   'Do not delete resource locks or terminate running workers.')
            deadline = time.monotonic() + 15
            while address.exists() and time.monotonic() < deadline:
                time.sleep(.1)
            if address.exists():
                raise RuntimeError('The previous server is still stopping; reconnect shortly')
        except DaemonUnavailable:
            pass
        directory = Path(workspace)/'.studio/remote'
        directory.mkdir(parents=True, exist_ok=True)
        with (directory/'service.log').open('ab') as log:
            subprocess.Popen([sys.executable, '-m', 'operon.remote.server', '--serve', '--workspace', str(workspace)],
                             cwd=Path(__file__).resolve().parents[2], stdin=subprocess.DEVNULL, stdout=log, stderr=log,
                             start_new_session=True)
        deadline = time.monotonic()+60
        while time.monotonic() < deadline:
            try:
                validate_daemon_response(rpc(workspace, daemon_request()))
                return
            except DaemonUnavailable:
                time.sleep(.15)
        raise DaemonUnavailable('Remote service did not start; inspect .studio/remote/service.log on the server',
                                details={'phase': 'start', 'retryable': True, 'socket': str(address)})


def serve(workspace):
    address = socket_path(workspace)
    service = RemoteService(workspace)
    address.unlink(missing_ok=True)
    loop = ControlLoop(service.dispatch, limits=limits_from_environment(),
                       on_error=service.record_dispatch_error)
    idle_seconds = float(os.environ.get('OPERON_REMOTE_IDLE_SECONDS', 300))
    with socket.socket(socket.AF_UNIX) as listener:
        listener.bind(str(address)); os.chmod(address, 0o600)
        listener.listen(64)
        try:
            loop.serve(listener, alive=service.alive, idle_seconds=idle_seconds,
                       stop_requested=service.stop_requested.is_set)
        finally:
            address.unlink(missing_ok=True)
            service.close()


class TerminalInput:
    """Unbuffered line input so select also observes already received lines."""
    def __init__(self):
        self.buffer = b''

    def line(self, deadline=None):
        import select
        while b'\n' not in self.buffer:
            timeout = None if deadline is None else max(0, deadline-time.monotonic())
            if not select.select([sys.stdin.fileno()], [], [], timeout)[0]:
                raise TimeoutError('SSH peer did not acknowledge the response')
            data = os.read(sys.stdin.fileno(), 65536)
            if not data: raise EOFError('SSH peer disconnected')
            self.buffer += data
        line, self.buffer = self.buffer.split(b'\n', 1)
        return line.decode('utf-8', errors='replace')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace', required=True)
    parser.add_argument('--serve', action='store_true')
    parser.add_argument('--upgrade', action='store_true', help='Retire an idle previous installation before reconnecting')
    parser.add_argument('--force-upgrade', action='store_true', help='Close all clients before replacing an installation')
    args = parser.parse_args()
    if args.force_upgrade:
        os.environ['OPERON_FORCE_POOL_REBIND'] = '1'
    workspace = Path(args.workspace).expanduser().resolve()
    if args.serve:
        serve(workspace); return
    try:
        if args.upgrade:
            ensure_daemon(workspace, upgrade=True)
        else:
            ensure_daemon(workspace)
    except Exception as exc:
        payload = {'code': getattr(exc, 'code', 'service_unavailable'), 'error': str(exc)}
        details = getattr(exc, 'details', None)
        if details:
            payload['details'] = details
        print('OPERON_REMOTE_ERROR ' + json.dumps(payload, ensure_ascii=False), flush=True)
        return
    print('\nOPERON_REMOTE_READY 1', flush=True)
    decoder = Decoder('Q')
    terminal = TerminalInput()
    def write(value):
        sys.stdout.write(value); sys.stdout.flush()
    while True:
        try: line = terminal.line()
        except EOFError: return
        if line.strip() == 'OPERON_REMOTE_CLOSE 1':
            return
        try: request = decoder.feed(line)
        except ValueError: continue
        if decoder.ack: write(decoder.ack)
        if request is None: continue
        try:
            response = dispatch_with_recovery(workspace, request)
        except Exception as exc:  # noqa: BLE001 - framed error is the bridge contract
            details = getattr(exc, 'details', None)
            response = {'ok': False, 'error': str(exc),
                        'code': getattr(exc, 'code', 'remote_error')}
            if details:
                response['details'] = details
        response['id'] = request.get('id')
        try: transmit(response, 'R', write, terminal.line)
        except (EOFError, TimeoutError): return


if __name__ == '__main__':
    main()
