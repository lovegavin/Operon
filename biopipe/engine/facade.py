"""Shared engine facade and the durable submission journal.

The journal gives every adapter (desktop, headless, MCP, SSH server) one atomic
idempotency index while an existing scientific job directory remains the
execution record during migration.  Coordinator-native runs additionally use
the engine state machine and pool leases.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import getpass
import hashlib
import os
from pathlib import Path
import platform
import re
import socket
import time
import uuid

from .contracts import (
    EngineError, IdempotencyConflictError, PoolSpec, RunState, UnavailableStateError,
    UnsupportedOperationError,
)
from .coordinator import Coordinator
from .events import EventStream, compact_run
from .state import ClaimResult, StateStore, now_iso
from .telemetry import METRICS

MIB = 1024 ** 2
MODES = ('legacy', 'shadow', 'coordinator')


def _safe_principal(value: str) -> str:
    value = re.sub(r'[^A-Za-z0-9_.:@-]+', '_', (value or '').strip())[:128]
    return value or 'local'


def default_principal() -> str:
    """Scheduling/fairness identity, not the physical pool owner."""
    return _safe_principal(os.environ.get('BIOPIPE_ENGINE_PRINCIPAL') or getpass.getuser())


def pool_owner() -> str:
    """OS account that owns the machine capacity boundary."""
    return _safe_principal(getpass.getuser())


def capacity_domain() -> str:
    # Deliberately independent of BIOPIPE_ENGINE_PRINCIPAL: changing a
    # client/fairness label must not grant another full machine's capacity.
    user = pool_owner()
    if hasattr(os, 'getuid'):
        user = f'{user}:{os.getuid()}'
    return f'host:{socket.gethostname()}:{user}'


def workspace_id(root: str | Path) -> str:
    return 'ws-' + hashlib.sha256(str(Path(root).resolve()).encode('utf-8')).hexdigest()[:24]


def pool_id(domain: str | None = None, scope: str | None = None) -> str:
    """Physical pool identity: capacity domain + control scope.

    Scheduling principals, projects, clients and workspace paths are excluded.
    Those are fairness dimensions inside the one physical pool.
    """
    domain = domain or capacity_domain()
    seed = f'{domain}\0{scope or ""}'
    return 'pool-' + hashlib.sha256(seed.encode('utf-8')).hexdigest()[:24]


def owner_identity(service_id: str | None = None) -> dict:
    value = {'pid': os.getpid(), 'service_id': service_id or uuid.uuid4().hex,
             'boot_id': _boot(), 'host': socket.gethostname()}
    try:
        import psutil
        value['created'] = psutil.Process().create_time()
    except Exception:  # noqa: BLE001 - identity remains partially usable
        value['created'] = None
    return value


def _boot() -> str:
    try:
        value = Path('/proc/sys/kernel/random/boot_id').read_text(encoding='utf-8').strip()
        if value:
            return value
    except OSError:
        pass
    try:
        import psutil
        return f'boot:{int(psutil.boot_time())}'
    except Exception:  # noqa: BLE001
        return 'boot:unknown'


def pool_from_host(*, root, admission=None, mode='legacy', principal=None,
                   ceiling_bytes=None, cpu_threads=None, scratch_bytes=None,
                   scope=None) -> PoolSpec:
    """Freeze one pool from the existing startup snapshot.

    The default ceiling is the admission service's 90%-of-available snapshot.
    No code path rescans free memory to redefine this number while the pool is
    alive.  An explicit ceiling is accepted only from trusted configuration.
    ``principal`` is the scheduling identity stored on runs; the physical pool
    owner remains the OS account.
    """
    principal = _safe_principal(principal or default_principal())
    owner = pool_owner()
    if ceiling_bytes is None:
        if admission is not None:
            ceiling_bytes = int(admission.capacity)
        else:
            from src.task.memory.config import AUTO_BUDGET_FRACTION
            from src.task.memory.system import available_memory
            ceiling_bytes = int(available_memory() * AUTO_BUDGET_FRACTION)
    if cpu_threads is None:
        if admission is not None:
            cpu_threads = int(admission.cpus)
        else:
            from src.web.admission import cpu_capacity
            cpu_threads = cpu_capacity()
    reserve = min(max(64 * MIB, ceiling_bytes // 20), max(1, ceiling_bytes // 4))
    reserve = min(reserve, max(0, ceiling_bytes - 1))
    transport = min(max(1 * MIB, ceiling_bytes // 50), max(1, ceiling_bytes // 8))
    return PoolSpec(pool_id=pool_id(scope=scope), principal=owner,
                    capacity_domain=capacity_domain(), ceiling_bytes=int(ceiling_bytes),
                    management_reserve_bytes=int(min(reserve, max(0, ceiling_bytes - 1))),
                    cpu_threads=max(1, int(cpu_threads)), scratch_bytes=int(scratch_bytes or 0),
                    transport_reserve_bytes=int(transport), mode=mode)


class EngineJournal:
    """Durable request claims and job lifecycle events for adapter-managed runs."""

    def __init__(self, store: StateStore, *, principal: str, owner: dict | None = None,
                 workspace: str | None = None):
        self.store, self.principal = store, principal
        self.owner = owner or owner_identity()
        self.workspace = workspace
        self.events = EventStream(store)
        self._events = 0

    def claim(self, key: str, digest: str, *, operation='run', receipt=None) -> ClaimResult:
        value = self.store.claim_request(principal=self.principal, key=key, digest=digest,
                                         operation=operation, owner=self.owner, receipt=receipt)
        METRICS.increment('journal.claims_created' if value.created else 'journal.claims_reused')
        return value

    def request(self, key: str) -> dict | None:
        return self.store.request(self.principal, key)

    def wait(self, key: str, *, timeout=120.0, interval=0.05) -> dict | None:
        """Wait for the claiming request to publish an outcome.

        The socket/HTTP handler is not blocked for the full timeout unless the
        request is genuinely in flight; a stale claim is detected from the
        durable owner identity and heartbeat.
        """
        deadline = time.monotonic() + max(0.0, timeout)
        while time.monotonic() < deadline:
            value = self.request(key)
            if value is None:
                return None
            if value['state'] not in ('claimed', 'launching'):
                return value
            if self._owner_stale(value):
                return value
            time.sleep(interval)
        return self.request(key)

    def _owner_stale(self, record: dict) -> bool:
        owner = record.get('owner') or {}
        if not owner:
            return True
        if owner.get('boot_id') and owner['boot_id'] != _boot():
            return True
        if owner.get('pid') == os.getpid():
            return False
        created = owner.get('created')
        if created is None:
            return False
        try:
            import psutil
            return psutil.Process(int(owner['pid'])).create_time() != float(created)
        except Exception:  # noqa: BLE001 - absence is not proof; keep waiting
            return True

    def bind(self, key: str, job_id: str, *, receipt=None) -> dict:
        return self.store.update_request(self.principal, key, state='submitted', run_id=job_id,
                                         receipt=receipt or {})

    def fail(self, key: str, error: str) -> dict:
        return self.store.update_request(self.principal, key, state='pending', receipt={'error': error})

    def record_event(self, kind: str, *, job_id=None, **fields) -> None:
        try:
            self.store.append_event('job:' + kind, principal=self.principal, run_id=job_id,
                                    workspace_id=self.workspace,
                                    revision=int(fields.pop('revision', 0)), payload=fields)
            self._events += 1
            if self._events % 4096 == 0:
                self.store.prune_events(keep=40000)
        except Exception:  # noqa: BLE001 - journal diagnostics must not fail a job transition
            METRICS.increment('journal.event_errors')

    def page(self, cursor=0, **filters):
        filters.setdefault('principal', self.principal)
        return self.events.page(cursor, **filters)

    def snapshot(self, limit=200):
        return self.events.snapshot(principal=self.principal, limit=limit)


class EngineFacade:
    """Operations shared by adapters over the durable journal and coordinator."""

    def __init__(self, runtime: 'EngineRuntime', coordinator: Coordinator | None = None):
        self.runtime = runtime
        self.store = runtime.store
        self.coordinator = coordinator
        self.events = EventStream(self.store)

    @property
    def mode(self) -> str:
        return self.runtime.mode

    def capabilities(self) -> list[str]:
        values = ['durable_requests', 'durable_events', 'request_ids', 'engine_state_v1']
        if self.coordinator is not None:
            values.extend(['concurrent_control', 'resource_leases', 'engine_resource_authority'])
        return values

    def submit(self, *, key: str, digest: str, graph: dict, parameters: dict, execution: dict,
               units: list[dict], project: str = 'default', principal: str | None = None,
               operation: str = 'run', run_id: str | None = None) -> dict:
        if self.coordinator is None:
            raise UnsupportedOperationError(
                'Coordinator mode is not active for this pool; the legacy executor remains authoritative')
        return self.coordinator.submit(
            key=key, digest=digest, graph=graph, parameters=parameters, execution=execution,
            units=units, workspace_id=self.runtime.workspace_id, principal=principal,
            project=project, operation=operation, run_id=run_id)

    def cancel(self, run_id: str, *, expected_revision=None, reason='client request') -> dict:
        if self.coordinator is None:
            raise UnsupportedOperationError('There is no coordinator to cancel this run')
        self._authorized(run_id)
        return self.coordinator.cancel(run_id, expected_revision=expected_revision, reason=reason)

    def status(self, run_id: str) -> dict:
        self._authorized(run_id)
        return self.coordinator.details(run_id) if self.coordinator else self.store.run(run_id)

    def _authorized(self, run_id):
        run = self.store.run(run_id)
        if run['principal'] != self.runtime.principal:
            from .contracts import UnauthorizedError
            raise UnauthorizedError('This run belongs to a different authenticated principal',
                                    details={'run_id': run_id})
        return run

    def list(self, *, limit=200) -> list[dict]:
        return [compact_run(run) for run in self.store.list_runs(
            principal=self.runtime.principal, workspace_id=self.runtime.workspace_id, limit=limit)]

    def page(self, cursor=0, **filters):
        return self.events.page(cursor, principal=self.runtime.principal,
                                workspace_id=self.runtime.workspace_id, **filters)

    def snapshot(self, *, limit=200) -> dict:
        return self.events.snapshot(workspace_id=self.runtime.workspace_id, limit=limit)

    def diagnostics(self) -> dict:
        snapshot = self.coordinator.status() if self.coordinator else {
            'pool': self.runtime.resources.snapshot().to_json(), 'epoch': self.runtime.epoch}
        snapshot['mode'] = self.mode
        snapshot['journal'] = self.store.operational_snapshot()
        snapshot['capabilities'] = self.capabilities()
        return snapshot


class EngineRuntime:
    """Owns the state store, pool identity and optional coordinator facade."""

    def __init__(self, store: StateStore, spec: PoolSpec, *, workspace_root, mode='legacy',
                 principal=None, workspace=None, journal=True, owner=None):
        self.store, self.spec = store, spec
        self.mode = mode
        self.principal = principal or spec.principal
        self.workspace_root = Path(workspace_root)
        self.workspace_id = workspace or workspace_id(self.workspace_root)
        self.owner = owner or owner_identity()
        self.epoch = 0
        self.spec, self.epoch = store.ensure_pool(spec)
        store.register_workspace(self.workspace_id, self.spec.pool_id, str(self.workspace_root.resolve()),
                                 self.principal)
        from .resources import PoolResources
        self.resources = PoolResources(store, self.spec, self.epoch)
        self.journal = EngineJournal(store, principal=self.principal, owner=self.owner,
                                     workspace=self.workspace_id) if journal else None
        self.facade = EngineFacade(self)
        self.error = None

    @classmethod
    def open(cls, *, data_dir=None, workspace_root, admission=None, mode=None, principal=None,
             ceiling_bytes=None, cpu_threads=None, journal=True, create=True):
        mode = mode or os.environ.get('BIOPIPE_ENGINE_MODE', 'legacy')
        if mode not in MODES:
            raise ValueError(f'BIOPIPE_ENGINE_MODE must be one of {MODES}')
        env_dir = os.environ.get('BIOPIPE_ENGINE_DIR')
        if env_dir:
            directory = Path(env_dir)
        elif data_dir is not None:
            directory = Path(data_dir) / 'engine'
        elif admission is not None:
            # One control database per authorized host pool, not per workspace.
            directory = Path(admission.directory) / 'engine'
        else:
            directory = Path(workspace_root) / '.studio' / 'engine'
        scope = str(directory.resolve())
        principal = _safe_principal(principal or default_principal())
        try:
            store = StateStore(directory / 'state.sqlite3', create=create)
        except UnavailableStateError as exc:
            runtime = cls.__new__(cls)
            runtime.store = None
            runtime.error = str(exc)
            runtime.journal = None
            runtime.facade = None
            runtime.mode = mode
            runtime.spec = None
            runtime.resources = None
            runtime.workspace_root = Path(workspace_root)
            runtime.workspace_id = workspace_id(workspace_root)
            runtime.principal = principal
            runtime.owner = owner_identity()
            runtime.epoch = 0
            return runtime
        spec = pool_from_host(root=workspace_root, admission=admission, mode=mode,
                              principal=principal, ceiling_bytes=ceiling_bytes,
                              cpu_threads=cpu_threads, scope=scope)
        return cls(store, spec, workspace_root=workspace_root, mode=mode, principal=principal,
                   journal=journal, owner=owner_identity())

    def coordinator(self, executor, *, project='default', policy=None, config=None,
                    artifact_committer=None) -> EngineFacade:
        coordinator = Coordinator(self.store, self.spec, executor, workspace_id=self.workspace_id,
                                  principal=self.principal, project=project, root=self.workspace_root,
                                  policy=policy, config=config, artifact_committer=artifact_committer)
        coordinator.claim()
        self.facade.coordinator = coordinator
        self.mode = 'coordinator'
        self.facade.runtime = self
        return self.facade

    def close(self):
        coordinator = getattr(self.facade, 'coordinator', None) if self.facade else None
        if coordinator is not None:
            coordinator.stop()
        if self.store is not None:
            self.store.close()

    def status(self) -> dict:
        if self.store is None:
            return {'mode': self.mode, 'error': self.error, 'available': False}
        return {'mode': self.mode, 'available': True, 'pool': self.spec.to_json(), 'epoch': self.epoch,
                'workspace_id': self.workspace_id, 'principal': self.principal,
                'pool_owner': self.spec.principal,
                'journal': self.store.operational_snapshot(),
                'facade': self.facade.diagnostics() if self.facade else None}
