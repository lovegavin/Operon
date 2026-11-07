"""Dedicated multi-workspace resource-pool service.

The pool service is the only allocator for one physical capacity domain.  It
does not share a process-global working directory: every submitted job belongs
to a registered workspace and is executed by that workspace's existing
JobService worker contract.  Client sessions are observation/submission
channels; closing one never stops the pool or another workspace's work.

This is a product adapter around the tested engine coordinator, not a second
execution engine.  The scientific worker, task.yaml, frozen parameters and
memory planner remain exactly the existing implementation.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import hmac
import json
import os
from pathlib import Path
import socket
import struct
import threading
import time
import uuid

from .engine.contracts import EngineError, UnauthorizedError
from .engine.control import ControlLoop, ControlLimits, ControlError
from .engine.environment import EnvironmentBusy, EnvironmentGuard
from .engine.executor import ExecutionContext, ExecutionResult
from .engine.facade import EngineRuntime, owner_identity, pool_owner
from .engine.supervisor import SupervisorError, identity_alive


class PoolError(EngineError):
    code = 'pool_error'
    status = 409


class PoolAuthError(UnauthorizedError):
    code = 'unauthorized'


@dataclass(frozen=True)
class WorkspaceSpec:
    root: Path
    principal: str
    data_dir: Path | None = None
    code_root: Path | None = None

    def to_json(self):
        return {'root': str(self.root), 'principal': self.principal,
                'data_dir': str(self.data_dir) if self.data_dir else None,
                'code_root': str(self.code_root) if self.code_root else None}


def bundled_catalog():
    from biopipe.packages import bundled_entries
    from src.web.operator_catalog import catalog_from_descriptors
    descriptors = []
    for kind in ('operator', 'reader'):
        descriptors.extend(descriptor for _, descriptor in bundled_entries(kind))
    return catalog_from_descriptors(descriptors)


def _resolve(root):
    return Path(root).expanduser().resolve()


class MultiWorkspaceExecutor:
    """Executor protocol adapter resolving each run by its workspace id."""

    capability = 'multi-workspace-job-service'
    resizable = False

    def __init__(self, pool):
        self.pool = pool

    def _service(self, context: ExecutionContext):
        run = context.run
        workspace = run.get('workspace_id')
        service = self.pool.services.get(workspace)
        if service is None:
            raise SupervisorError(
                f'The run workspace is not registered: {workspace}',
                code='capability_unavailable')
        return service

    def launch(self, context: ExecutionContext) -> ExecutionResult:
        service = self._service(context)
        job_id = str(context.run['id'])
        committed = (context.lease or {}).get('committed')
        if not committed:
            raise SupervisorError('The coordinator did not attach a lease', code='capability_unavailable')
        service._start_coordinated(job_id, context.attempt_id, committed)
        value = service.details(job_id)
        from .engine.executor import identity_for_job
        identity = identity_for_job(service, job_id)
        if value.get('status') == 'failed':
            return ExecutionResult(state='failed', identity=identity, error=value.get('error'))
        if value.get('status') == 'cancelled':
            return ExecutionResult(state='cancelled', identity=identity)
        return ExecutionResult(state='running', identity=identity, tree_alive=True)

    def poll(self, context: ExecutionContext) -> ExecutionResult:
        service = self._service(context)
        from .engine.executor import identity_for_job
        job_id = str(context.run['id'])
        value = service.details(job_id)
        status = value.get('status')
        identity = identity_for_job(service, job_id)
        if value.get('tree_exited') is False and status in ('failed', 'cancelled', 'complete',
                                                            'recovery_required'):
            return ExecutionResult(state='running', identity=identity, tree_alive=True,
                                   detail='worker tree not confirmed exited')
        if status == 'complete':
            return ExecutionResult(state='succeeded' if value.get('logs_complete') else 'running',
                                   identity=identity, tree_alive=not value.get('logs_complete'))
        if status == 'failed':
            return ExecutionResult(state='failed' if value.get('logs_complete') else 'running',
                                   error=value.get('error'), identity=identity,
                                   tree_alive=not value.get('logs_complete'))
        if status == 'cancelled':
            return ExecutionResult(state='cancelled' if value.get('logs_complete') else 'running',
                                   identity=identity, tree_alive=not value.get('logs_complete'))
        return ExecutionResult(state='running', identity=identity, tree_alive=True)

    def cancel(self, context: ExecutionContext, *, timeout: float = 10.0) -> ExecutionResult:
        service = self._service(context)
        from .engine.executor import identity_for_job
        job_id = str(context.run['id'])
        try:
            service._cancel_local(job_id, coordinated=True, timeout=timeout)
        except Exception as exc:  # noqa: BLE001 - coordinator keeps lease
            return ExecutionResult(state='cancelled', tree_alive=True,
                                   error=f'{type(exc).__name__}: {exc}')
        value = service.details(job_id)
        return ExecutionResult(state='cancelled' if value.get('logs_complete') else 'running',
                               identity=identity_for_job(service, job_id),
                               tree_alive=not value.get('logs_complete'))

    def cancel_run(self, run_id: str) -> None:
        for service in self.pool.services.values():
            try:
                service._cancel_local(str(run_id), coordinated=True, timeout=5)
                return
            except (KeyError, ValueError):
                continue

    def reconcile(self, context: ExecutionContext) -> ExecutionResult:
        service = self._service(context)
        from .engine.executor import identity_for_job
        job_id = str(context.run['id'])
        value = service.details(job_id)
        status = value.get('status')
        identity = identity_for_job(service, job_id)
        if value.get('tree_exited') is False and status in ('failed', 'cancelled', 'complete',
                                                            'recovery_required'):
            return ExecutionResult(state='running', identity=identity, tree_alive=True,
                                   detail='recovery required: worker tree still alive')
        if status in ('queued', 'preparing'):
            return ExecutionResult(state='missing', identity=identity, detail='not-started')
        if status == 'running':
            if identity is not None and identity_alive(identity):
                return ExecutionResult(state='running', identity=identity, tree_alive=True)
            return ExecutionResult(state='unknown', identity=identity,
                                   error='The JobService worker identity is not verifiable')
        if status == 'complete':
            return ExecutionResult(state='succeeded', identity=identity)
        if status == 'failed':
            return ExecutionResult(state='failed', error=value.get('error'), identity=identity)
        if status == 'cancelled':
            return ExecutionResult(state='cancelled', identity=identity)
        return ExecutionResult(state='unknown', detail=f'job-status:{status}')


class PoolService:
    """One authoritative allocator for registered workspaces in one pool."""

    def __init__(self, *, root, admission_dir, workspaces=(), catalog=None,
                 code_root=None, capacity_bytes=None, cpu_threads=None,
                 environment_gate=None, start=True):
        self.root = _resolve(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.code_root = _resolve(code_root) if code_root else None
        self.owner = owner_identity()
        from src.web.admission import HostAdmission
        self.admission = HostAdmission(admission_dir, available_bytes=capacity_bytes,
                                       cpu_threads=cpu_threads)
        self.engine = EngineRuntime.open(workspace_root=self.root, admission=self.admission,
                                          mode='coordinator', principal=pool_owner(),
                                          ceiling_bytes=capacity_bytes, cpu_threads=cpu_threads)
        if getattr(self.engine, 'store', None) is None:
            self.admission.close()
            raise PoolError(self.engine.error or 'The pool state store is unavailable')
        gate_path = environment_gate or os.environ.get('BIOPIPE_ENVIRONMENT_GATE') or \
            (Path(self.admission.directory).parent / 'environment-gate.json')
        self.environment_guard = EnvironmentGuard(gate_path)
        self.catalog = catalog or bundled_catalog()
        self.services = {}
        self.workspaces = {}
        self._by_id = {}
        self.sessions = {}
        self._state_lock = threading.RLock()
        self._closed = False
        self._claimed = False
        self.coordinator = None
        self.executor = None
        try:
            self.admission.claim_coordinator(self.owner)
            self._claimed = True
            for item in workspaces:
                if isinstance(item, WorkspaceSpec):
                    self.add_workspace(item.root, principal=item.principal,
                                       data_dir=item.data_dir, code_root=item.code_root)
                else:
                    self.add_workspace(item['root'], principal=item.get('principal'),
                                       data_dir=item.get('data_dir'),
                                       code_root=item.get('code_root'))
            self.executor = MultiWorkspaceExecutor(self)
            self.coordinator = self.engine.coordinator(
                self.executor, project='default', artifact_committer=self._commit_artifacts).coordinator
            self.coordinator.trusted_principals.update(self._principals())
            if start:
                self.coordinator.start()
        except Exception:
            try:
                if self.coordinator is not None:
                    self.coordinator.stop(cancel_attempts=False)
            finally:
                if self._claimed:
                    self.admission.release_coordinator(self.owner)
                self.engine.close()
                self.admission.close()
            raise

    def _principals(self):
        return {service._pool_principal or service.engine.principal
                for service in self.services.values()}

    def workspace_engine(self, root, principal):
        """Workspace facade sharing the pool store and frozen pool spec."""
        return EngineRuntime(self.engine.store, self.engine.spec, workspace_root=root,
                             mode='legacy', principal=principal or pool_owner())

    def add_workspace(self, root, *, principal=None, data_dir=None, code_root=None):
        from src.web.service import JobService, Settings
        root = _resolve(root)
        if str(root) in self.workspaces:
            return self.workspaces[str(root)]
        if data_dir is None:
            data_dir = root / '.studio'
        data_dir = _resolve(data_dir)
        if not data_dir.is_relative_to(root):
            raise PoolError('Workspace data_dir must stay inside its workspace root')
        principal = principal or pool_owner()
        settings = Settings(root, data_dir, root / 'frontend/dist', testing=False,
                            code_root=code_root or self.code_root or self.root,
                            admission_dir=self.admission.directory, engine_mode='legacy')
        service = JobService(settings, self.catalog, pool=self, principal=principal)
        wid = service.engine.workspace_id
        self.services[wid] = service
        self.workspaces[str(root)] = service
        self._by_id[wid] = service
        if self.coordinator is not None:
            self.coordinator.trusted_principals.add(principal)
        service.admission.baseline_bytes = min(service.admission.capacity // 8,
                                                max(1 * 1024 ** 2,
                                                    service.admission.baseline_bytes))
        return service

    def resolve(self, workspace):
        value = str(workspace)
        if value in self.services:
            return self.services[value]
        if value in self.workspaces:
            return self.workspaces[value]
        root = str(_resolve(workspace))
        if root in self.workspaces:
            return self.workspaces[root]
        raise KeyError(f'Unknown workspace: {workspace}')

    def _authorize(self, service, principal):
        expected = service._pool_principal or service.engine.principal
        if principal and principal != expected:
            raise PoolAuthError('This workspace belongs to a different scheduling principal',
                                details={'workspace': str(service.root)})
        return expected

    def open_session(self, workspace, *, principal=None, name=None):
        service = self.resolve(workspace)
        principal = self._authorize(service, principal)
        session_id = 'sess-' + uuid.uuid4().hex
        record = {'session_id': session_id,
                  'workspace_id': service.engine.workspace_id,
                  'workspace': str(service.root), 'principal': principal,
                  'name': name or '', 'created_at': time.time()}
        with self._state_lock:
            self.sessions[session_id] = record
        return dict(record)

    def _session(self, session_id, *, workspace=None, principal=None):
        with self._state_lock:
            record = self.sessions.get(session_id)
        if record is None:
            raise PoolError('The pool session is not open', code='session_not_open',
                            details={'session_id': session_id})
        if workspace is not None:
            service = self.resolve(workspace)
            if record['workspace_id'] != service.engine.workspace_id:
                raise PoolAuthError('This session belongs to another workspace')
        if principal is not None and principal != record['principal']:
            raise PoolAuthError('This session belongs to another principal')
        return record

    def close_session(self, session_id, *, workspace=None, principal=None):
        """Remove only this subscription; never shut down the shared service."""
        record = self._session(session_id, workspace=workspace, principal=principal)
        with self._state_lock:
            self.sessions.pop(session_id, None)
        service = self.services.get(record['workspace_id'])
        running = 0
        if service is not None:
            running = sum(job.get('status') in ('running', 'preparing', 'queued')
                          for job in service.jobs.values())
        return {'session_id': session_id, 'closed': True, 'pool_closed': False,
                'running_jobs': running}

    def stop_workspace(self, workspace, *, principal=None):
        """Explicitly stop accepting work for one workspace; do not cancel work."""
        service = self.resolve(workspace)
        self._authorize(service, principal)
        service.shutdown(cancel_jobs=False)
        running = sum(job.get('status') in ('running', 'preparing', 'queued')
                      for job in service.jobs.values())
        return {'workspace': str(service.root), 'accepting': False,
                'pool_closed': False, 'running_jobs': running}

    def launch(self, workspace, graph, *, request_id=None, principal=None, session_id=None):
        service = self.resolve(workspace)
        if session_id is not None:
            session = self._session(session_id, workspace=workspace, principal=principal)
            principal = session['principal']
        principal = self._authorize(service, principal)
        return service.launch(graph, request_id=request_id, principal=principal)

    def submit_run(self, service, job, *, principal=None):
        """Register an already-prepared workspace job with the pool coordinator."""
        if self.coordinator is None:
            raise PoolError('The pool coordinator is not running')
        principal = self._authorize(service, principal or job.get('principal'))
        job_id = job['id']
        parameters = {}
        try:
            parameters = json.loads((service.jobs_dir / job_id / 'parameters.json').read_text(encoding='utf-8'))
        except (OSError, ValueError):
            pass
        digest = job.get('request_digest')
        if not digest:
            import hashlib
            digest = hashlib.sha256(json.dumps(
                {'graph': job.get('graph'), 'parameters': parameters},
                sort_keys=True, separators=(',', ':')).encode('utf-8')).hexdigest()
        allocation = job.get('allocation') or {}
        return self.coordinator.submit(
            key=job_id, digest=digest, graph=job.get('graph') or {},
            parameters=parameters, execution=(job.get('graph', {}).get('runtime', {})
                                              .get('execution') or {}),
            units=[{'unit_id': 'main', 'node_ids': list(job.get('order') or []),
                    'depends_on': [], 'target': {'kind': 'local'},
                    'requirement': {
                        'managed_budget_bytes': int(allocation.get('budget_bytes', 0)),
                        'process_reservation_bytes': int(allocation.get('reserved_bytes', 0)),
                        'cpu_threads': max(1, int(allocation.get('cpu_threads', 1))),
                        'scratch_reserved_bytes': 0},
                    'capability': 'legacy-sequential', 'retry_limit': 1}],
            workspace_id=service.engine.workspace_id, principal=principal,
            run_id=job_id, operation='job')

    def details(self, workspace, run_id, *, principal=None, session_id=None):
        service = self.resolve(workspace)
        if session_id is not None:
            session = self._session(session_id, workspace=workspace, principal=principal)
            principal = session['principal']
        principal = self._authorize(service, principal)
        job = service.details(run_id)
        if job.get('principal') and job['principal'] != principal:
            raise PoolAuthError('This run belongs to another scheduling principal')
        run = None
        attempt = None
        lease = None
        try:
            run = self.engine.store.run(run_id)
            attempts = self.engine.store.attempts(run_id)
            attempt = attempts[-1] if attempts else None
            if attempt:
                lease = self.engine.store.lease(attempt['id'])
        except Exception:  # noqa: BLE001 - adopt a legacy/uncoordinated job record too
            pass
        if lease is not None:
            lease = dict(lease)
            for field in ('committed', 'request', 'target'):
                value = lease.get(field)
                if value is not None and hasattr(value, 'to_json'):
                    lease[field] = value.to_json()
        if attempt is not None:
            attempt = dict(attempt)
        if run is not None:
            run = dict(run)
        job['pool'] = {
            'workspace_id': service.engine.workspace_id,
            'workspace': str(service.root),
            'principal': principal,
            'run': run,
            'attempt': attempt,
            'lease': lease,
            'lifecycle': job.get('lifecycle'),
        }
        return job

    def cancel(self, workspace, run_id, *, principal=None, session_id=None, reason='client cancel'):
        service = self.resolve(workspace)
        if session_id is not None:
            session = self._session(session_id, workspace=workspace, principal=principal)
            principal = session['principal']
        principal = self._authorize(service, principal)
        job = service.require(run_id)
        if job.get('principal') and job['principal'] != principal:
            raise PoolAuthError('This run belongs to another scheduling principal')
        value = self.coordinator.cancel(run_id, principal=principal, reason=reason)
        with service.lock:
            current = service.jobs.get(run_id)
            if current is not None and current.get('status') in ('queued', 'running', 'preparing'):
                current['cancel_requested'] = True
                current['cancel_state'] = 'requesting'
                from src.web.service import write_json
                write_json(service.jobs_dir / run_id / 'job.json', current)
        return self.details(workspace, run_id, principal=principal)

    def events(self, workspace, *, after=0, limit=200, principal=None, session_id=None):
        service = self.resolve(workspace)
        if session_id is not None:
            session = self._session(session_id, workspace=workspace, principal=principal)
            principal = session['principal']
        principal = self._authorize(service, principal)
        if service._engine_journal is None:
            return {'events': [], 'cursor': after, 'next_cursor': after}
        page = service._engine_journal.page(after, limit=limit)
        return page.to_json()

    def status(self):
        coordinator = self.coordinator
        return {
            'schema_version': 1,
            'pool': self.engine.spec.to_json(),
            'owner': self.owner,
            'coordinator': coordinator.status() if coordinator else {'running': False},
            'admission': self.admission.resources(),
            'environment_gate': self.environment_guard.status(),
            'workspaces': [
                {'workspace_id': wid, 'root': str(service.root),
                 'principal': service._pool_principal or service.engine.principal,
                 'jobs': len(service.jobs),
                 'running': sum(job.get('status') in ('running', 'preparing')
                                for job in service.jobs.values())}
                for wid, service in self.services.items()],
            'trusted_principals': sorted(self._principals()),
            'sessions': len(self.sessions),
            'capacity_domain': self.engine.spec.capacity_domain,
            'closed': self._closed,
        }

    def close_workspace(self, workspace):
        service = self.resolve(workspace)
        active = [job['id'] for job in service.jobs.values()
                  if job.get('status') in ('queued', 'preparing', 'running')]
        if active:
            raise PoolError('A workspace with active jobs cannot be removed from the pool',
                            details={'jobs': active[:10]})
        wid = service.engine.workspace_id
        with self._state_lock:
            for session_id, record in list(self.sessions.items()):
                if record['workspace_id'] == wid:
                    self.sessions.pop(session_id, None)
        self.services.pop(wid, None)
        self.workspaces.pop(str(service.root), None)
        self._by_id.pop(wid, None)
        service.shutdown(cancel_jobs=False)
        return {'removed': str(service.root)}

    def _commit_artifacts(self, payload, result):
        run = payload.get('run') or {}
        workspace = run.get('workspace_id')
        service = self.services.get(workspace)
        if service is None:
            raise PoolError(f'Cannot commit artifacts for unregistered workspace: {workspace}')
        return service._commit_job_artifacts(payload, result)

    def restart(self, *, stop=True):
        """Stop coordinator authority but leave workers for adoption (test/recovery)."""
        if stop and self.coordinator is not None:
            self.coordinator.stop(cancel_attempts=False)
        if self._claimed:
            self.admission.release_coordinator(self.owner)
            self._claimed = False
        if self.engine is not None:
            self.engine.close()
        self._closed = True

    def shutdown(self):
        if self._closed:
            return
        self._closed = True
        with self._state_lock:
            self.sessions.clear()
        if self.coordinator is not None:
            try:
                self.coordinator.stop(cancel_attempts=True)
            finally:
                self.coordinator = None
        for service in list(self.services.values()):
            try:
                service.shutdown(cancel_jobs=True)
            except Exception:  # noqa: BLE001 - close remaining workspaces
                pass
        if self._claimed:
            try:
                self.admission.release_coordinator(self.owner)
            except Exception:  # noqa: BLE001 - process identity reconciles
                pass
            self._claimed = False
        try:
            self.engine.close()
        finally:
            self.admission.close()


class PoolControlServer:
    """Loopback framed control channel for pool clients; not a second scheduler."""

    def __init__(self, pool, *, token, host='127.0.0.1', port=0, limits=None):
        if not token:
            raise ValueError('A non-empty pool token is required')
        self.pool, self.token = pool, token
        self.host = host
        self.listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.listener.bind((host, port))
        self.address = self.listener.getsockname()
        self.listener.listen(64)
        self.loop = ControlLoop(self.dispatch, limits=limits or ControlLimits())
        self._closed = threading.Event()
        self._thread = None

    def start(self):
        self._thread = threading.Thread(target=self._accept, name='operon-pool-control', daemon=True)
        self._thread.start()
        return self

    def _accept(self):
        while not self._closed.is_set():
            try:
                connection, peer = self.listener.accept()
            except OSError:
                break
            self.loop.submit(connection, peer=f'{peer[0]}:{peer[1]}')

    def _check(self, params):
        token = params.get('_token') if isinstance(params, dict) else None
        if not isinstance(token, str) or not hmac.compare_digest(token, self.token):
            raise PoolAuthError('Invalid pool control token')

    def dispatch(self, method, params):
        params = params or {}
        self._check(params)
        if method == 'pool.status':
            return self.pool.status()
        if method == 'workspace.list':
            return [{'root': str(service.root), 'workspace_id': wid,
                     'principal': service._pool_principal or service.engine.principal}
                    for wid, service in self.pool.services.items()]
        if method == 'session.open':
            return self.pool.open_session(params.get('workspace'),
                                          principal=params.get('principal'),
                                          name=params.get('name'))
        if method == 'session.close':
            session_id = params.get('session_id')
            if not isinstance(session_id, str) or not session_id:
                raise ControlError('session.close requires session_id')
            return self.pool.close_session(session_id,
                                           workspace=params.get('workspace'),
                                           principal=params.get('principal'))
        if method == 'workspace.stop':
            return self.pool.stop_workspace(params.get('workspace'),
                                            principal=params.get('principal'))
        if method == 'environment.fingerprint':
            from .engine.cache_environment import fingerprint
            from src.web.models import Graph
            service = self.pool.resolve(params['workspace'])
            self.pool._authorize(service, params.get('principal'))
            return fingerprint(service, Graph.model_validate(params['graph']))
        if method == 'transport.capacity':
            spec = self.pool.engine.spec
            return {'bytes': min(spec.schedulable_bytes, spec.transport_reserve_bytes or spec.schedulable_bytes)}
        if method == 'transport.lease':
            import re
            if not re.fullmatch(r'transport-[a-f0-9]{64}', params.get('lease_id', '')):
                raise ControlError('Invalid transport lease id')
            if not isinstance(params.get('owner'), dict) or not params['owner'].get('service_id'):
                raise ControlError('Transport lease requires a process owner')
            return {'reserved': self.pool.engine.store.transport_lease(
                pool_id=self.pool.engine.spec.pool_id, lease_id=params['lease_id'], owner=params['owner'],
                size=params.get('size'), release=params.get('release') is True)}
        if method == 'run.submit':
            graph = params.get('graph')
            if not isinstance(graph, dict):
                raise ControlError('run.submit requires a graph object')
            from src.web.models import Graph
            value = self.pool.launch(params.get('workspace'), Graph.model_validate(graph),
                                     request_id=params.get('request_id'),
                                     principal=params.get('principal'),
                                     session_id=params.get('session_id'))
            return value
        if method == 'run.details':
            return self.pool.details(params.get('workspace'), params.get('run_id'),
                                     principal=params.get('principal'),
                                     session_id=params.get('session_id'))
        if method == 'run.cancel':
            return self.pool.cancel(params.get('workspace'), params.get('run_id'),
                                    principal=params.get('principal'),
                                    session_id=params.get('session_id'),
                                    reason=params.get('reason') or 'client cancel')
        if method == 'events.page':
            return self.pool.events(params.get('workspace'), after=int(params.get('after', 0)),
                                    limit=int(params.get('limit', 200)),
                                    principal=params.get('principal'),
                                    session_id=params.get('session_id'))
        if method == 'workspace.close_session':
            session_id = params.get('session_id')
            if not isinstance(session_id, str) or not session_id:
                raise ControlError('workspace.close_session requires session_id')
            return self.pool.close_session(session_id,
                                           workspace=params.get('workspace'),
                                           principal=params.get('principal'))
        raise ControlError(f'Unknown pool method: {method}')

    def close(self):
        self._closed.set()
        try:
            self.listener.close()
        except OSError:
            pass
        self.loop.close()


class PoolClientError(EngineError):
    code = 'pool_client_error'


class PoolClient:
    """Small reconnecting client; one request per connection."""

    def __init__(self, address, token, *, timeout=30.0, session_id=None):
        self.address = tuple(address)
        self.token = token
        self.timeout = timeout
        self.session_id = session_id
        self._session_context = None

    def open_session(self, workspace, *, principal=None, name=None):
        value = self.request('session.open', {'workspace': str(workspace),
                                              'principal': principal, 'name': name})
        self.session_id = value['session_id']
        self._session_context = {'workspace': str(workspace), 'principal': principal, 'name': name}
        return value

    def close_session(self, session_id=None, *, workspace=None, principal=None):
        session_id = session_id or self.session_id
        if not session_id:
            raise PoolClientError('No open pool session', code='session_not_open')
        value = self.request('session.close', {'session_id': session_id,
                                               'workspace': str(workspace) if workspace else None,
                                               'principal': principal})
        if self.session_id == session_id:
            self.session_id = None
        return value

    def stop_workspace(self, workspace, *, principal=None):
        return self.request('workspace.stop', {'workspace': str(workspace),
                                               'principal': principal})

    def request(self, method, params=None, *, _retry_session=True):
        payload = dict(params or {})
        session_method = method in ('run.submit', 'run.details', 'run.cancel', 'events.page')
        if session_method and self._session_context and self.session_id:
            payload['session_id'] = self.session_id
        payload['_token'] = self.token
        body = json.dumps({'id': uuid.uuid4().hex, 'method': method, 'params': payload},
                          ensure_ascii=False, allow_nan=False).encode('utf-8')
        with socket.create_connection(self.address, timeout=self.timeout) as connection:
            connection.settimeout(self.timeout)
            connection.sendall(struct.pack('!Q', len(body)) + body)
            header = self._recv_exact(connection, 8)
            size = struct.unpack('!Q', header)[0]
            value = json.loads(self._recv_exact(connection, size))
        if not value.get('ok'):
            if (value.get('code') == 'session_not_open' and session_method
                    and self._session_context and _retry_session):
                # A restarted pool loses subscriptions, not durable run keys.
                # Rejection happens before dispatch, so retrying this same
                # request after reopening the subscription cannot double-launch.
                self.open_session(**self._session_context)
                payload['session_id'] = self.session_id
                return self.request(method, payload, _retry_session=False)
            raise PoolClientError(value.get('error') or 'Pool request failed',
                                  code=value.get('code') or 'pool_error',
                                  details=value.get('details'))
        return value.get('value')

    @staticmethod
    def _recv_exact(connection, size):
        chunks = []
        while size:
            block = connection.recv(min(size, 65536))
            if not block:
                raise PoolClientError('Pool connection closed before the response')
            chunks.append(block)
            size -= len(block)
        return b''.join(chunks)

    def status(self):
        return self.request('pool.status')

    def submit(self, workspace, graph, *, request_id=None, principal=None):
        return self.request('run.submit', {'workspace': str(workspace), 'graph': graph,
                                           'request_id': request_id, 'principal': principal,
                                           'session_id': self.session_id})

    def details(self, workspace, run_id, *, principal=None):
        return self.request('run.details', {'workspace': str(workspace), 'run_id': run_id,
                                            'principal': principal,
                                            'session_id': self.session_id})

    def cancel(self, workspace, run_id, *, principal=None):
        return self.request('run.cancel', {'workspace': str(workspace), 'run_id': run_id,
                                           'principal': principal,
                                           'session_id': self.session_id})
