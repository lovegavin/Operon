"""Mutual exclusion between dependency mutation and running attempts.

Full immutable environment generations are not implemented yet.  This guard is
the explicit, tested fallback required before the generation mechanism exists:
a repair/install takes an exclusive maintenance marker and must first observe
zero live attempt leases; new attempts cannot acquire a lease while maintenance
is active.  It never claims to provide rollback or two generations at once.

Leases record both the launcher service identity and (after spawn) the worker
process identity, so an orphaned worker keeps the exclusion even if its launcher
died.  Stale records are pruned by process identity, never by timeout alone.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys
import threading
import uuid
from functools import lru_cache

from .contracts import EngineError
from .fs import FileLock
from .supervisor import identity_alive


class EnvironmentBusy(EngineError):
    code = 'environment_busy'
    status = 409


class EnvironmentGuardError(EngineError):
    code = 'environment_gate_unavailable'
    status = 503


def _now():
    return datetime.now(timezone.utc).isoformat()


@lru_cache(maxsize=128)
def _interpreter_identity(executable, file_stamp, config_stamp):
    import subprocess
    code = ('import json,sys; print(json.dumps({"executable":sys.executable,'
            '"version":list(sys.version_info[:3]),"prefix":sys.prefix,'
            '"base_prefix":sys.base_prefix,"implementation":sys.implementation.name}))')
    try:
        result = subprocess.run([executable, '-I', '-c', code], check=True,
                                capture_output=True, text=True, timeout=30,
                                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        value = json.loads(result.stdout)
        for key in ('executable', 'prefix', 'base_prefix'):
            value[key] = os.path.normcase(str(Path(value[key]).resolve()))
        return value
    except Exception as exc:
        raise EnvironmentGuardError('Cannot verify the selected interpreter identity') from exc


def environment_identity(python=None, *, plugin_generation=None,
                         dependency_fingerprint=None) -> str:
    """Identity of the dependency interpreter, not of a workspace.

    Two workspaces or installation directories that resolve the same Python
    executable and dependency generation share one exclusion domain.  The
    application code directory is deliberately excluded: it is not the
    dependency environment and must not create a second pool.
    """
    # Do not resolve a venv's executable symlink before launching it: doing so
    # selects the base environment and loses its prefix.
    executable = str(Path(python or sys.executable).expanduser().absolute())
    path = Path(executable)
    try:
        stat = path.stat()
        config = path.parent.parent / 'pyvenv.cfg'
        config_stat = config.stat() if config.exists() else None
        actual = _interpreter_identity(executable, (stat.st_mtime_ns, stat.st_size),
                                       (config_stat.st_mtime_ns, config_stat.st_size) if config_stat else None)
    except OSError as exc:
        raise EnvironmentGuardError('The selected interpreter cannot be inspected') from exc
    value = {
        'schema_version': 1,
        **actual,
        'plugin_generation': str(plugin_generation or ''),
        'dependency_fingerprint': str(dependency_fingerprint or ''),
    }
    return 'env-' + hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(',', ':')).encode('utf-8')).hexdigest()[:24]


def _alive(identity):
    if not identity:
        return False
    return identity_alive(identity)


@dataclass(frozen=True)
class MaintenanceToken:
    id: str
    kind: str
    owner: dict
    acquired_at: str
    environment: str = 'default'

    def to_json(self):
        return {'id': self.id, 'kind': self.kind, 'owner': self.owner,
                'acquired_at': self.acquired_at, 'environment': self.environment}


class EnvironmentGuard:
    def __init__(self, path=None):
        default = Path(os.environ.get('BIOPIPE_ENVIRONMENT_GATE') or
                       (Path.home() / '.biopipe' / 'environment-gate.json'))
        self.path = Path(path or default)
        self.lock = FileLock(self.path.with_suffix('.lock'))
        self.mutex = threading.RLock()

    # -- state ---------------------------------------------------------
    def _read(self):
        try:
            value = json.loads(self.path.read_text(encoding='utf-8'))
        except FileNotFoundError:
            return {'schema_version': 1, 'leases': {}, 'maintenance': None}
        except (OSError, ValueError) as exc:
            raise EnvironmentGuardError(
                f'Environment gate state is unreadable; refusing to guess: {exc}') from exc
        if not isinstance(value, dict):
            raise EnvironmentGuardError('Environment gate state has an invalid shape')
        value.setdefault('schema_version', 1)
        value.setdefault('leases', {})
        value.setdefault('maintenance', None)
        value.setdefault('maintenances', {})
        legacy = value.get('maintenance')
        if legacy and not value['maintenances']:
            value['maintenances'][legacy.get('environment') or 'default'] = legacy
        for lease in value['leases'].values():
            lease.setdefault('environment', 'default')
        return value

    def _write(self, value):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_name(self.path.name + '.' + uuid.uuid4().hex + '.tmp')
        temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True),
                             encoding='utf-8')
        os.replace(temporary, self.path)

    @staticmethod
    def _prune(state):
        leases = {}
        for key, lease in state.get('leases', {}).items():
            if _alive(lease.get('service')) or _alive(lease.get('worker')):
                leases[key] = lease
        state['leases'] = leases
        maintenances = state.get('maintenances') or {}
        maintenances = {env: token for env, token in maintenances.items()
                        if token and _alive(token.get('owner'))}
        state['maintenances'] = maintenances
        state['maintenance'] = next(iter(maintenances.values()), None)

    # -- attempt leases ------------------------------------------------
    def acquire_job(self, job_id, *, service, worker=None, workspace=None, kind='job',
                    environment='default'):
        with self.lock, self.mutex:
            state = self._read()
            self._prune(state)
            active = (state.get('maintenances', {}).get(environment) or
                      state.get('maintenances', {}).get('default'))
            if active:
                raise EnvironmentBusy(
                    'An environment repair/install is in progress; starting new work is blocked',
                    details={'maintenance': active.get('kind'), 'environment': environment,
                             'since': active.get('acquired_at')})
            lease = state['leases'].get(job_id, {})
            lease.update({'job_id': job_id, 'kind': kind, 'service': service,
                          'worker': worker or lease.get('worker'), 'workspace': workspace,
                          'environment': environment, 'updated_at': _now()})
            lease.setdefault('created_at', lease['updated_at'])
            state['leases'][job_id] = lease
            self._write(state)
            return lease

    def bind_worker(self, job_id, worker):
        with self.lock, self.mutex:
            state = self._read()
            self._prune(state)
            lease = state['leases'].get(job_id)
            if lease is None:
                raise EnvironmentGuardError(
                    'The attempt environment lease disappeared before worker registration')
            lease['worker'] = worker
            lease['updated_at'] = _now()
            self._write(state)
            return lease

    def ensure_job(self, job_id, *, service, worker=None, workspace=None, kind='job',
                   environment='default'):
        with self.lock, self.mutex:
            state = self._read()
            self._prune(state)
            lease = state['leases'].get(job_id)
            if lease is None:
                return self.acquire_job(job_id, service=service, worker=worker,
                                        workspace=workspace, kind=kind,
                                        environment=environment)
            if worker:
                lease['worker'] = worker
            lease['environment'] = environment
            lease['updated_at'] = _now()
            self._write(state)
            return lease

    def release_job(self, job_id):
        with self.lock, self.mutex:
            state = self._read()
            self._prune(state)
            lease = state['leases'].pop(job_id, None)
            self._write(state)
            return lease is not None

    def release_all(self, service_identity=None):
        """Release leases owned by a terminating launcher without a worker."""
        with self.lock, self.mutex:
            state = self._read()
            removed = []
            for key, lease in list(state['leases'].items()):
                if (service_identity is None or lease.get('service') == service_identity) and \
                        not _alive(lease.get('worker')):
                    removed.append(key)
                    del state['leases'][key]
            self._prune(state)
            self._write(state)
            return removed

    # -- exclusive maintenance -----------------------------------------
    def begin(self, *, owner, kind='repair', environment='default'):
        token = MaintenanceToken(uuid.uuid4().hex, kind, owner, _now(), environment)
        with self.lock, self.mutex:
            state = self._read()
            self._prune(state)
            active = (state.get('maintenances', {}).get(environment) or
                      state.get('maintenances', {}).get('default'))
            if active:
                raise EnvironmentBusy(
                    'Another environment repair/install is already active',
                    details={'kind': active.get('kind'), 'environment': environment,
                             'since': active.get('acquired_at')})
            leased = [key for key, lease in state['leases'].items()
                      if environment == 'default' or
                      (lease.get('environment') or 'default') == environment]
            if leased:
                raise EnvironmentBusy(
                    'Running attempts still use this environment; drain or wait for them',
                    details={'active_attempts': sorted(leased), 'environment': environment})
            state['maintenances'][environment] = token.to_json()
            state['maintenance'] = token.to_json()
            self._write(state)
            return token

    def end(self, token):
        with self.lock, self.mutex:
            state = self._read()
            active = state.get('maintenances', {}).get(token.environment)
            if active and active.get('id') == token.id:
                del state['maintenances'][token.environment]
                state['maintenance'] = next(iter(state['maintenances'].values()), None)
                self._write(state)
                return True
            return False

    @contextmanager
    def maintenance(self, *, owner, kind='repair', environment='default'):
        token = self.begin(owner=owner, kind=kind, environment=environment)
        try:
            yield token
        finally:
            self.end(token)

    # -- diagnostics ---------------------------------------------------
    def status(self):
        with self.lock, self.mutex:
            state = self._read()
            before = len(state['leases'])
            self._prune(state)
            if len(state['leases']) != before:
                self._write(state)
            return {'path': str(self.path), 'leases': sorted(state['leases']),
                    'maintenance': state.get('maintenance'),
                    'maintenances': dict(state.get('maintenances') or {}),
                    'environments': sorted({lease.get('environment') or 'default'
                                            for lease in state['leases'].values()}),
                    'active_attempts': len(state['leases'])}
