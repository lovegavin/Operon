"""Automatic, per-host/account pool discovery and detached lifecycle.

Only the control service is started here. Scientific interpreters and packages
remain explicit workflow targets. The existing PoolService is the sole resource
authority; bootstrap never falls back to a legacy scheduler.
"""
from __future__ import annotations

import argparse
from functools import lru_cache
import hashlib
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import threading
import time

from . import __version__
from .engine.facade import owner_identity
from .engine.fs import FileLock, atomic_json
from .pool_service import PoolClient, PoolClientError, PoolControlServer, PoolError, PoolService
from src.web.admission import process_alive


@lru_cache(maxsize=8)
def implementation(root):
    """Application code identity, excluding the independently installed library."""
    root = Path(root)
    digest = hashlib.sha256(__version__.encode())
    for directory in ('biopipe', 'biopipe_sdk', 'src'):
        for path in sorted((root / directory).rglob('*.py')):
            digest.update(path.relative_to(root).as_posix().encode())
            digest.update(path.read_bytes())
    return digest.hexdigest()


def locations(settings=None):
    explicit = getattr(settings, 'admission_dir', None)
    admission = Path(explicit or os.environ.get('BIOPIPE_ADMISSION_DIR') or
                     Path.home() / '.biopipe' / 'admission' / socket.gethostname()).resolve()
    return admission, admission / 'managed-pool'


def _read(path, default=None):
    try:
        return json.loads(Path(path).read_text(encoding='utf-8'))
    except FileNotFoundError:
        return default
    except (OSError, ValueError) as exc:
        raise PoolClientError(f'Cannot read shared pool state: {path}', code='engine_unavailable') from exc


def _alive(record):
    return bool(record and process_alive(record.get('owner') or {}))


def _client(record, root, timeout=30):
    address = record.get('address') or []
    if len(address) != 2 or address[0] != '127.0.0.1':
        raise PoolClientError('Invalid local pool discovery address', code='engine_unavailable')
    token = (root / 'token').read_text(encoding='utf-8')
    return PoolClient(address, token, timeout=timeout)


def _spawn(root, admission, code_root):
    env = dict(os.environ, PYTHONUTF8='1', PYTHONIOENCODING='utf-8', PYTHONUNBUFFERED='1',
               BIOPIPE_REGISTRY_MAINTENANCE='1')
    # Internal workspace adapters must not recursively connect to their pool.
    for key in ('BIOPIPE_POOL_ADDRESS', 'BIOPIPE_POOL_TOKEN', 'BIOPIPE_POOL_PRINCIPAL',
                'BIOPIPE_ENGINE_MODE'):
        env.pop(key, None)
    env['PYTHONPATH'] = str(code_root)
    command = [sys.executable, '-m', 'biopipe.managed_pool', '--start',
               '--root', str(root), '--admission', str(admission), '--code-root', str(code_root)]
    with (root / 'pool.log').open('ab') as log:
        # A short-lived launcher removes the daemon from the desktop/backend
        # process tree. A later forced client exit cannot kill other clients' pool.
        helper = subprocess.Popen(command, cwd=code_root, env=env, stdin=subprocess.DEVNULL,
                                  stdout=log, stderr=subprocess.STDOUT,
                                  creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        if helper.wait(timeout=20) != 0:
            raise PoolClientError(f'Shared pool launcher failed; see {root / "pool.log"}',
                                  code='engine_unavailable')


def ensure_pool(settings):
    admission, root = locations(settings)
    code_root = Path(__file__).resolve().parents[1]
    expected = implementation(str(code_root))
    root.mkdir(parents=True, exist_ok=True)
    with FileLock(root / 'start.lock', timeout=90):
        record = _read(root / 'instance.json')
        if _alive(record):
            if record.get('implementation') != expected:
                raise PoolClientError('Another Operon version owns the shared pool. Finish its tasks and '
                                      'close its clients before switching versions.', code='pool_upgrade_required')
            if record.get('closing'):
                # A confirmed draining process still owns the epoch. Do not
                # start a second authority while it releases resources.
                deadline = time.monotonic() + 10
                while _alive(record) and time.monotonic() < deadline:
                    time.sleep(.05)
                if _alive(record):
                    raise PoolClientError('Shared pool is still stopping; retry shortly', code='engine_unavailable')
            else:
                return record, root
        error_path = root / 'startup-error.json'
        error_path.unlink(missing_ok=True)
        _spawn(root, admission, code_root)
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            record = _read(root / 'instance.json')
            if _alive(record) and not record.get('closing') and record.get('implementation') == expected:
                return record, root
            error = _read(error_path)
            if error:
                raise PoolClientError(error.get('error') or 'Shared pool startup failed',
                                      code='engine_unavailable', details={'log': str(root / 'pool.log')})
            time.sleep(.05)
        raise PoolClientError(f'Shared pool startup timed out; see {root / "pool.log"}',
                              code='engine_unavailable')


class ManagedPoolClient(PoolClient):
    def __init__(self, settings, *, principal):
        super().__init__(('127.0.0.1', 0), '', timeout=60)
        self.settings, self.principal = settings, principal
        self.record = None
        self._binding_lock = threading.RLock()

    def close_session(self, session_id=None, *, workspace=None, principal=None):
        # A shutdown must neither start a daemon nor resurrect a subscription.
        # Reconnection can have replaced the client's original session id.
        with self._binding_lock:
            current = self.session_id
            try:
                if current and _alive(self.record):
                    plain = _client(self.record, locations(self.settings)[1], timeout=5)
                    return plain.close_session(current, workspace=workspace, principal=principal)
                return {'closed': True, 'pool_closed': False}
            finally:
                self.session_id = None
                self._session_context = None

    def _bind(self):
        with self._binding_lock:
            if _alive(self.record):
                return
            record, root = ensure_pool(self.settings)
            plain = _client(record, root, timeout=60)
            plain.request('workspace.register', {
                'root': str(self.settings.root.resolve()),
                'data_dir': str(self.settings.data_dir.resolve()),
                'code_root': str((self.settings.code_root or Path(__file__).resolve().parents[1]).resolve()),
                'principal': self.principal,
                'worker_python': self.settings.worker_python or sys.executable,
                'manifest_only_registry': self.settings.manifest_only_registry,
                'input_roots': [str(p.resolve()) for p in self.settings.input_roots or []],
                'implementation': implementation(str(Path(__file__).resolve().parents[1])),
            })
            self.address, self.token, self.record = plain.address, plain.token, record
            if self._session_context:
                reopened = plain.open_session(**self._session_context)
                self.session_id = reopened['session_id']

    def request(self, method, params=None, *, _retry_session=True):
        self._bind()
        try:
            return super().request(method, params, _retry_session=_retry_session)
        except PoolClientError as exc:
            if exc.code == 'pool_draining':
                # Rejected before dispatch: reconnect safely. Accepted/unknown
                # run submissions are never blindly retried on transport errors.
                with self._binding_lock:
                    self.record = None
                if _retry_session:
                    self._bind()
                    return super().request(method, params, _retry_session=False)
            raise


class ManagedControlServer(PoolControlServer):
    def __init__(self, pool, *, token, root, code_root):
        self.root, self.code_root = root, code_root
        self.identity = implementation(str(code_root))
        self.lifecycle = threading.RLock()
        self.inflight = 0
        self.closing = False
        self.last_activity = time.monotonic()
        super().__init__(pool, token=token)

    def announcement(self):
        return {'version': __version__, 'implementation': self.identity,
                'address': list(self.address), 'owner': self.pool.owner,
                'closing': self.closing, 'managed': True}

    def _work_active(self):
        for service in list(self.pool.services.values()):
            if any(job.get('status') in ('queued', 'preparing', 'running', 'recovery_required')
                   or job.get('logs_complete') is False for job in list(service.jobs.values())):
                return True
        status = self.pool.coordinator.status()
        return bool(status.get('active_attempts') or any((status.get('pool', {}).get('used') or {}).values()))

    def try_idle_close(self, *, grace=2):
        with self.lifecycle:
            if self.closing:
                return True
            with self.pool._state_lock:
                for key, session in list(self.pool.sessions.items()):
                    owner = session.get('owner')
                    if owner and not process_alive(owner):
                        self.pool.sessions.pop(key, None)
                observed = bool(self.pool.sessions)
            if self.inflight or observed or self._work_active():
                self.last_activity = time.monotonic()
                return False
            if time.monotonic() - self.last_activity < grace:
                return False
            self.closing = True
            atomic_json(self.root / 'instance.json', self.announcement())
            return True

    def dispatch(self, method, params):
        self._check(params or {})
        with self.lifecycle:
            if self.closing:
                raise PoolError('The idle shared pool is stopping; reconnect', code='pool_draining')
            self.inflight += 1
            self.last_activity = time.monotonic()
        try:
            if method == 'workspace.register':
                if params.get('implementation') != self.identity:
                    raise PoolError('Client and pool application versions differ', code='pool_upgrade_required')
                spec = {key: params.get(key) for key in ('root', 'data_dir', 'code_root', 'principal', 'input_roots', 'worker_python')}
                spec['manifest_only_registry'] = params.get('manifest_only_registry', True)
                if not isinstance(spec['manifest_only_registry'], bool):
                    raise PoolError('Catalog policy must be a boolean')
                if not all(isinstance(spec[k], str) and Path(spec[k]).is_absolute()
                           for k in ('root', 'data_dir', 'code_root')):
                    raise PoolError('Workspace registration needs absolute local paths')
                if not Path(spec['root']).is_dir() or not Path(spec['code_root']).is_dir():
                    raise PoolError('Workspace and application directories must exist')
                if spec['worker_python'] is not None and (not isinstance(spec['worker_python'], str)
                        or not Path(spec['worker_python']).is_absolute() or not Path(spec['worker_python']).is_file()):
                    raise PoolError('Workspace interpreter must be an existing absolute executable path')
                # Persist bindings before acknowledging. Only registration owns
                # this lock; slow job dispatch/status never waits on registry I/O.
                with self.pool._registration_lock:
                    service = self.pool.add_workspace(**spec)
                    records = _read(self.root / 'workspaces.json', {})
                    spec['input_roots'] = [str(p) for p in service.settings.input_roots]
                    records[str(service.root)] = spec
                    atomic_json(self.root / 'workspaces.json', records)
                return {'workspace_id': service.engine.workspace_id, 'registered': True}
            if method == 'pool.retire':
                with self.lifecycle:
                    if self.inflight != 1 or self._work_active():
                        raise PoolError('Finish or cancel active tasks before stopping the shared pool',
                                        code='pool_busy')
                    self.closing = True
                    atomic_json(self.root / 'instance.json', self.announcement())
                return {'stopping': True, 'active_tasks_cancelled': False}
            value = super().dispatch(method, params)
            if method == 'pool.status':
                value.update(managed=True, version=__version__, implementation=self.identity,
                             discovery_file=str(self.root / 'instance.json'))
            return value
        finally:
            with self.lifecycle:
                self.inflight -= 1


def serve(root, admission, code_root):
    root, admission, code_root = Path(root), Path(admission), Path(code_root)
    service = server = None
    # A lifetime lock plus HostAdmission ownership prevents duplicate daemons,
    # including a caller that timed out while the first daemon was still starting.
    with FileLock(root / 'owner.lock', timeout=1):
        try:
            token_path = root / 'token'
            if not token_path.exists():
                fd = os.open(token_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                with os.fdopen(fd, 'w', encoding='utf-8') as stream:
                    stream.write(secrets.token_urlsafe(32))
            saved = _read(root / 'workspaces.json', {})
            workspaces = [spec for spec in saved.values()
                          if Path(spec['root']).is_dir() and Path(spec['data_dir']).is_dir()]
            service = PoolService(root=root, admission_dir=admission, workspaces=workspaces, code_root=code_root)
            server = ManagedControlServer(service, token=token_path.read_text(encoding='utf-8'),
                                          root=root, code_root=code_root).start()
            atomic_json(root / 'instance.json', server.announcement())
            # Give the bootstrapping client time to register and subscribe.
            server.last_activity = time.monotonic() + 10
            while not server.try_idle_close():
                time.sleep(.2)
        except Exception as exc:
            atomic_json(root / 'startup-error.json', {'error': f'{type(exc).__name__}: {exc}'})
            raise
        finally:
            if server is not None:
                server.close()
            if service is not None:
                service.shutdown()


def inspect_pool(*, stop=False):
    """CLI observation never starts a daemon just to display its status."""
    _, root = locations()
    record = _read(root / 'instance.json')
    if not _alive(record):
        return {'available': False, 'managed': True, 'mode': 'pool', 'running': False}
    if record.get('closing'):
        return {'available': False, 'managed': True, 'mode': 'pool', 'stopping': True}
    client = _client(record, root)
    return client.request('pool.retire') if stop else client.status()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--start', action='store_true')
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--admission', type=Path, required=True)
    parser.add_argument('--code-root', type=Path, required=True)
    args = parser.parse_args()
    if args.start:
        command = [sys.executable, '-m', 'biopipe.managed_pool', '--root', str(args.root),
                   '--admission', str(args.admission), '--code-root', str(args.code_root)]
        with (args.root / 'pool.log').open('ab') as log:
            subprocess.Popen(command, cwd=args.code_root, stdin=subprocess.DEVNULL, stdout=log,
                             stderr=subprocess.STDOUT, start_new_session=os.name != 'nt',
                             creationflags=(subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP |
                                            subprocess.CREATE_NO_WINDOW) if os.name == 'nt' else 0)
    else:
        serve(args.root, args.admission, args.code_root)


if __name__ == '__main__':
    main()
