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

from dataclasses import dataclass, field, asdict
import hmac
import hashlib
import json
import os
from pathlib import Path
import socket
import struct
import threading
import time
import uuid

from .engine.contracts import EngineError, UnauthorizedError, StaleRevisionError
from .engine.control import ControlLoop, ControlLimits, ControlError, limits_from_environment
from .engine.admission_limits import PrincipalLimiter
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
    input_roots: list[Path] | None = None
    worker_python: str | None = None
    manifest_only_registry: bool = False
    library_root: Path | None = None

    def to_json(self):
        return {'root': str(self.root), 'principal': self.principal,
                'data_dir': str(self.data_dir) if self.data_dir else None,
                'code_root': str(self.code_root) if self.code_root else None,
                'input_roots': [str(p) for p in self.input_roots] if self.input_roots else None,
                'worker_python': self.worker_python, 'manifest_only_registry': self.manifest_only_registry,
                'library_root': str(self.library_root) if self.library_root else None}


def bundled_catalog():
    from operon.packages import bundled_entries
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
        invocation = self.pool.invocation_executor(context.run)
        if invocation is not None:
            return invocation.launch(context)
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
        invocation = self.pool.invocation_executor(context.run)
        if invocation is not None:
            return invocation.poll(context)
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
        invocation = self.pool.invocation_executor(context.run)
        if invocation is not None:
            return invocation.cancel(context, timeout=timeout)
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
        invocation = self.pool.invocation_executor(context.run)
        if invocation is not None:
            return invocation.reconcile(context)
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


def _registration_binding(*, explicit_library, library_root, previous_library, requested_manifest):
    """Library binding and catalog policy a registration actually asks for.

    A client that omits the library keeps the binding the workspace already
    runs with: re-deriving it from the application directory made the policy
    look changed on every registration, which then failed any submit that
    arrived while a task was active.
    """
    if not explicit_library and previous_library is not None:
        library_root = previous_library
    return library_root, bool(requested_manifest and not library_root)


class PoolService:
    """One authoritative allocator for registered workspaces in one pool."""

    def __init__(self, *, root, admission_dir, workspaces=(), catalog=None,
                 code_root=None, capacity_bytes=None, cpu_threads=None,
                 environment_gate=None, start=True):
        self.root = _resolve(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.code_root = _resolve(code_root) if code_root else None
        self.owner = owner_identity()
        self._submission_lock = threading.Lock()
        self._pending_submissions = {}
        self._plan_executors = {}
        from src.web.admission import HostAdmission
        # A crashed daemon may leave live workers whose leases only exist in
        # the durable engine store. Do not rescan free RAM and redefine their
        # pool ceiling. Once all attempts drain, a cold start scans normally.
        from .engine.state import StateStore
        from .engine.facade import pool_id
        directory = Path(os.environ.get('OPERON_ENGINE_DIR') or Path(admission_dir) / 'engine').resolve()
        recovery = None
        if (directory / 'state.sqlite3').exists():
            previous = StateStore(directory / 'state.sqlite3', create=False)
            try:
                recovery = previous.recovery_pool(pool_id(scope=str(directory)))
            finally:
                previous.close()
        self.admission = HostAdmission(admission_dir, available_bytes=capacity_bytes,
                                       cpu_threads=cpu_threads, preserve_snapshot=recovery is not None)
        try:
            self.engine = EngineRuntime.open(workspace_root=self.root, admission=self.admission,
                                              mode='coordinator', principal=pool_owner(),
                                              ceiling_bytes=capacity_bytes if capacity_bytes is not None else
                                                (recovery.ceiling_bytes if recovery else None),
                                              cpu_threads=cpu_threads if cpu_threads is not None else
                                                (recovery.cpu_threads if recovery else None))
        except Exception:
            self.admission.close()
            raise
        if getattr(self.engine, 'store', None) is None:
            self.admission.close()
            raise PoolError(self.engine.error or 'The pool state store is unavailable')
        gate_path = environment_gate or os.environ.get('OPERON_ENVIRONMENT_GATE') or \
            (Path(self.admission.directory).parent / 'environment-gate.json')
        self.environment_guard = EnvironmentGuard(gate_path)
        self.catalog = catalog or bundled_catalog()
        self.services = {}
        self.workspaces = {}
        self._by_id = {}
        self.sessions = {}
        self._state_lock = threading.RLock()
        self._registration_lock = threading.RLock()
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
                                       data_dir=item.data_dir, code_root=item.code_root, input_roots=item.input_roots,
                                       worker_python=item.worker_python,
                                       manifest_only_registry=item.manifest_only_registry,
                                       library_root=item.library_root)
                else:
                    self.add_workspace(item['root'], principal=item.get('principal'),
                                       data_dir=item.get('data_dir'),
                                       code_root=item.get('code_root'), input_roots=item.get('input_roots'),
                                       worker_python=item.get('worker_python'),
                                       manifest_only_registry=item.get('manifest_only_registry', False),
                                       library_root=item.get('library_root'))
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
                for service in list(self.services.values())}

    def workspace_engine(self, root, principal):
        """Workspace facade sharing the pool store and frozen pool spec."""
        return EngineRuntime(self.engine.store, self.engine.spec, workspace_root=root,
                             mode='legacy', principal=principal or pool_owner())

    def _prune_dead_sessions(self, workspace_id):
        """Drop subscriptions left by a process that no longer exists."""
        removed = []
        with self._state_lock:
            for session_id, session in list(self.sessions.items()):
                if session.get('workspace_id') != workspace_id:
                    continue
                owner = session.get('owner')
                if not isinstance(owner, dict) or owner.get('created') is None:
                    continue
                if not identity_alive(owner):
                    self.sessions.pop(session_id, None)
                    removed.append(session_id)
        return removed

    def _close_workspace_sessions(self, workspace_id):
        """Close every client subscription for one workspace (force upgrade only)."""
        with self._state_lock:
            for session_id, session in list(self.sessions.items()):
                if session.get('workspace_id') == workspace_id:
                    self.sessions.pop(session_id, None)

    def add_workspace(self, root, *, principal=None, data_dir=None, code_root=None, input_roots=None,
                      worker_python=None, manifest_only_registry=False, library_root=None, force=False):
        with self._registration_lock:
            return self._add_workspace(root, principal=principal, data_dir=data_dir, code_root=code_root,
                                       input_roots=input_roots, worker_python=worker_python,
                                       manifest_only_registry=manifest_only_registry,
                                       library_root=library_root, force=force)

    def _add_workspace(self, root, *, principal=None, data_dir=None, code_root=None, input_roots=None,
                       worker_python=None, manifest_only_registry=False, library_root=None, force=False):
        from src.web.service import JobService, Settings
        root = _resolve(root)
        explicit_library = library_root is not None
        if library_root is None:
            from operon.installation import library_root as _infer_library_root
            library_root = _infer_library_root(code_root or self.code_root)
        requested_manifest = bool(manifest_only_registry)
        # The version-scoped library decides resolution; a manifest-only
        # registry cannot see its packages even when the client asked for it.
        manifest_only_registry = bool(requested_manifest and not library_root)
        if str(root) in self.workspaces:
            service = self.workspaces[str(root)]
            if data_dir is not None and service.directory != _resolve(data_dir):
                raise PoolError('This workspace is already registered with another data directory')
            self._authorize(service, principal)
            if input_roots:
                # Every path was authorized by this account's workspace client.
                # Preserve simultaneous clients' allowed roots rather than
                # silently narrowing an already-running task's input scope.
                service.settings.input_roots = list(dict.fromkeys([
                    *service.settings.input_roots, *map(_resolve, input_roots)]))
            changed_code = code_root is not None and _resolve(code_root) != _resolve(service.settings.code_root)
            previous_library = (_resolve(service.settings.library_root)
                                if getattr(service.settings, 'library_root', None) else None)
            library_root, manifest_only_registry = _registration_binding(
                explicit_library=explicit_library, library_root=library_root,
                previous_library=previous_library, requested_manifest=requested_manifest)
            changed_library = library_root is not None and _resolve(library_root) != previous_library
            selected_python = str(Path(worker_python).absolute()) if worker_python else service.plugins.python
            changed_policy = manifest_only_registry != service.settings.manifest_only_registry
            if changed_code or changed_library or selected_python != service.plugins.python or changed_policy:
                active = any(job.get('status') in ('queued', 'preparing', 'running', 'recovery_required')
                             or job.get('logs_complete') is False for job in service.jobs.values())
                if active:
                    raise PoolError('Finish tasks before changing its application, interpreter or catalog policy')
                if force:
                    self._close_workspace_sessions(service.engine.workspace_id)
                else:
                    self._prune_dead_sessions(service.engine.workspace_id)
                subscribed = any(s['workspace_id'] == service.engine.workspace_id
                                 for s in list(self.sessions.values()))
                if subscribed:
                    raise PoolError('Finish tasks and close workspace clients before changing its application, interpreter or catalog policy')
                if changed_code:
                    service.settings.code_root = _resolve(code_root)
                if changed_policy:
                    service.settings.manifest_only_registry = manifest_only_registry
                if changed_library:
                    service.settings.library_root = _resolve(library_root)
                    from operon.plugins import PluginManager
                    service.plugins = PluginManager(
                        service.directory,
                        manifest_only=service.settings.manifest_only_registry,
                        python=service.settings.worker_python,
                        library_root=service.settings.library_root)
                    service.dependencies.sync(service.plugins.state())
                service.settings.worker_python = service.plugins.python = selected_python
                service.settings.manifest_only_registry = service.plugins.manifest_only = manifest_only_registry
            return service
        if data_dir is None:
            data_dir = root / '.studio'
        data_dir = _resolve(data_dir)
        if not data_dir.is_relative_to(root):
            raise PoolError('Workspace data_dir must stay inside its workspace root')
        principal = principal or pool_owner()
        settings = Settings(root, data_dir, root / 'frontend/dist', testing=False,
                            code_root=_resolve(code_root or self.code_root or self.root),
                            admission_dir=self.admission.directory, engine_mode='legacy',
                            manifest_only_registry=manifest_only_registry,
                            input_roots=list(map(_resolve, input_roots)) if input_roots else None,
                            worker_python=worker_python,
                            library_root=_resolve(library_root) if library_root else None)
        service = JobService(settings, self.catalog, pool=self, principal=principal)
        wid = service.engine.workspace_id
        with self._state_lock:
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

    def open_session(self, workspace, *, principal=None, name=None, owner=None):
        if owner is not None and (not isinstance(owner, dict) or type(owner.get('pid')) is not int
                                  or owner['pid'] <= 0 or not isinstance(owner.get('created'), (int, float))):
            raise PoolError('A session owner needs a verified process identity')
        service = self.resolve(workspace)
        principal = self._authorize(service, principal)
        session_id = 'sess-' + uuid.uuid4().hex
        record = {'session_id': session_id,
                  'workspace_id': service.engine.workspace_id,
                  'workspace': str(service.root), 'principal': principal,
                  'name': name or '', 'created_at': time.time(), 'owner': owner}
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
        store = self.engine.store
        if request_id is not None and (not isinstance(request_id, str) or not request_id or len(request_id) > 512):
            raise ControlError('request_id must be a non-empty string of at most 512 characters')
        key = 'req-' + hashlib.sha256(request_id.encode('utf-8')).hexdigest()[:24] if request_id else None
        replay = key is not None and store.request(principal, key) is not None
        with self._submission_lock:
            if not replay:
                store.check_submission_capacity(principal, pending=sum(self._pending_submissions.values()),
                                                principal_pending=self._pending_submissions.get(principal, 0))
                if len(graph.model_dump_json().encode('utf-8')) > store.queue_limits.submission_bytes:
                    from .engine.contracts import BusyError
                    raise BusyError('Workflow exceeds submission size limit', code='queue_full')
            self._pending_submissions[principal] = self._pending_submissions.get(principal, 0) + 1
        try:
            return service.launch(graph, request_id=request_id, principal=principal)
        finally:
            with self._submission_lock:
                remaining = self._pending_submissions[principal] - 1
                if remaining:
                    self._pending_submissions[principal] = remaining
                else:
                    del self._pending_submissions[principal]

    def invocation_executor(self, run):
        execution = run.get('plan', {}).get('execution', {})
        binding = execution.get('invocation_binding')
        if binding is None:
            return None
        key = run['id']
        with self._state_lock:
            cached = self._plan_executors.get(key)
            if cached is not None:
                return cached
            from .environment_store import EnvironmentStore
            from .environment_store.verification import confined
            from .execution.unit_executor import RunPlanExecutor
            from .contracts.plan_operations import PlanExecutionBinding
            service = self.services[run['workspace_id']]
            binding = PlanExecutionBinding.model_validate(binding).model_dump(mode='json')
            package = confined(service.root, binding['package_root'])
            environment = confined(service.root, binding['environment_store'])
            binding['storage'] = {key: str(confined(service.root, value))
                                  for key, value in binding['storage'].items()}
            binding['inputs'] = {key: {**value, 'path': str(confined(service.root, value['path']))}
                                 for key, value in binding['inputs'].items()}
            executor = RunPlanExecutor(service.directory / 'invocations',
                environment_store=EnvironmentStore(environment), package_root=package, bindings=binding)
            self._plan_executors[key] = executor
            return executor

    def submit_plan(self, workspace, plan, binding, *, request_id, principal=None, session_id=None, run_id=None):
        from .contracts.run_plan import RunPlan
        from .contracts.base import sha256_hex
        from .planning.validation import validate_run_plan
        from .execution.unit_executor import unit_dependencies
        from .environment_store.verification import confined
        from .environment_store import EnvironmentStore
        from .contracts.plan_operations import PlanExecutionBinding
        service = self.resolve(workspace)
        if session_id is not None:
            principal = self._session(session_id, workspace=workspace, principal=principal)['principal']
        principal = self._authorize(service, principal)
        plan = RunPlan.model_validate(plan)
        validate_run_plan(plan)
        binding = PlanExecutionBinding.model_validate(binding).model_dump(mode='json')
        if not isinstance(request_id, str) or not request_id or len(request_id) > 512:
            raise ControlError('plan.submit requires a stable request_id')
        if run_id is not None:
            # Internal fenced-controller hook only: the public plan RPC never
            # accepts a caller-chosen run ID. Preserve its durable pre-send ID.
            from .contracts.plan_operations import PlanLookupControl
            from .engine.contracts import IdempotencyConflictError
            PlanLookupControl(workspace=str(service.root), run_id=run_id)
            claimed = self.engine.store.request(principal, 'plan:' + request_id)
            if claimed and (claimed['run_id'] != run_id or claimed['operation'] != 'run-plan'
                            or claimed['digest'] != sha256_hex({'plan': plan.plan_id, 'binding': binding})):
                raise IdempotencyConflictError('Internal plan ID differs from the original submission receipt')
            try:
                existing = self.engine.store.run(run_id)
            except KeyError:
                existing = None
            if existing and (not claimed or existing['principal'] != principal
                    or existing['workspace_id'] != service.engine.workspace_id
                    or existing['plan']['graph'].get('plan_id') != plan.plan_id
                    or existing['plan']['execution'].get('invocation_binding') != binding):
                raise IdempotencyConflictError('Internal plan ID is already bound to another execution')
        confined(service.root, binding['package_root'])
        for relative in binding['storage'].values():
            confined(service.root, relative)
        for value in binding['inputs'].values():
            from .execution.codecs import validate_reference
            validate_reference({**value, 'path': str(confined(service.root, value['path']))})
        store = EnvironmentStore(confined(service.root, binding['environment_store']), create=False)
        for unit in plan.units:
            if unit.placement.executor != 'local':
                raise PoolError('A host pool accepts only local units', code='unsupported_target')
            environment = binding['environments'][unit.invocation.environment_ref]
            resolved = store.binding(environment['generation_id'])
            expected = plan.execution_policy.get('environment_refs', {}).get(unit.invocation.environment_ref)
            if expected is None and len(plan.environment_requirements) == 1:
                expected = sha256_hex(plan.environment_requirements[0])
            if resolved.requirement_digest != expected:
                raise PoolError('Bound environment differs from the unit requirement', code='environment_unverified')
        parents = unit_dependencies(plan)
        return self.coordinator.submit(key='plan:' + request_id,
            digest=sha256_hex({'plan': plan.plan_id, 'binding': binding}),
            graph=plan.model_dump(mode='json'), parameters={}, execution={'invocation_binding': binding},
            units=[{'unit_id': unit.unit_id, 'node_ids': list(unit.node_ids), 'depends_on': sorted(parents[unit.unit_id]),
                    'requirement': unit.resource_request.model_dump(mode='json'), 'capability': 'invocation-v1',
                    'retry_limit': unit.retry_policy.maximum_attempts} for unit in plan.units],
            workspace_id=service.engine.workspace_id, principal=principal, operation='run-plan', run_id=run_id)

    def _plan_authorize(self, workspace, run_id, *, principal=None, session_id=None):
        from .contracts.plan_operations import PlanLookupControl
        PlanLookupControl(workspace=str(workspace), run_id=run_id, principal=principal, session_id=session_id)
        service = self.resolve(workspace)
        if session_id is not None:
            principal = self._session(session_id, workspace=workspace, principal=principal)['principal']
        principal = self._authorize(service, principal)
        try:
            run = self.engine.store.run(run_id)
        except KeyError as exc:
            raise PoolError('Plan was not found', code='plan_not_found', status=404) from exc
        if run['principal'] != principal or run['workspace_id'] != service.engine.workspace_id:
            raise PoolAuthError('This plan belongs to another workspace/principal')
        if not run['plan'].get('execution', {}).get('invocation_binding'):
            raise PoolError('This run is not an invocation plan')
        return service, run

    def plan_details(self, workspace, run_id, *, principal=None, session_id=None):
        service, run = self._plan_authorize(workspace, run_id, principal=principal, session_id=session_id)
        return {'run_id': run_id, 'state': run['status'], 'revision': run['revision'],
                'units': self.engine.store.units(run_id), 'attempts': self.engine.store.attempts(run_id),
                'results': str(service.directory / 'invocations' / 'runs' / run_id / 'published')}

    def _plan_read(self, operation, workspace, run_id, *, principal=None, session_id=None, **query):
        from .plan_results import PlanResults
        service, run = self._plan_authorize(workspace, run_id, principal=principal, session_id=session_id)
        return getattr(PlanResults(self.engine.store, service.directory, run), operation)(**query)

    def plan_events(self, workspace, run_id, **options):
        return self._plan_read('events', workspace, run_id, **options)

    def plan_attempts(self, workspace, run_id, **options):
        return self._plan_read('attempts', workspace, run_id, **options)

    def plan_artifacts(self, workspace, run_id, **options):
        return self._plan_read('artifacts', workspace, run_id, **options)

    def plan_logs(self, workspace, run_id, **options):
        return self._plan_read('logs', workspace, run_id, **options)

    def plan_artifact_files(self, workspace, run_id, **options):
        return self._plan_read('artifact_files', workspace, run_id, **options)

    def plan_artifact_preview(self, workspace, run_id, **options):
        return self._plan_read('artifact_preview', workspace, run_id, **options)

    def plan_artifact_file(self, workspace, run_id, **options):
        return self._plan_read('artifact_file', workspace, run_id, **options)

    def plan_cancel(self, workspace, run_id, *, principal=None, session_id=None):
        """Authorize against the existing plan owner before publishing cancel intent."""
        self.plan_details(workspace, run_id, principal=principal, session_id=session_id)
        service = self.resolve(workspace)
        if session_id is not None:
            principal = self._session(session_id, workspace=workspace, principal=principal)['principal']
        principal = self._authorize(service, principal)
        try:
            self.coordinator.cancel(run_id, principal=principal, reason='invocation plan cancellation')
        except StaleRevisionError:
            if self.engine.store.run(run_id)['status'] not in ('complete', 'failed', 'cancelled'):
                raise
        return self.plan_details(workspace, run_id, principal=principal, session_id=session_id)

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

    def cancel(self, workspace, run_id, *, principal=None, session_id=None, reason='client cancel', compact=False):
        service = self.resolve(workspace)
        if session_id is not None:
            session = self._session(session_id, workspace=workspace, principal=principal)
            principal = session['principal']
        principal = self._authorize(service, principal)
        job = service.require(run_id)
        if job.get('principal') and job['principal'] != principal:
            raise PoolAuthError('This run belongs to another scheduling principal')
        try:
            self.coordinator.cancel(run_id, principal=principal, reason=reason)
        except StaleRevisionError:
            # The scientific worker can finish between polling and cleanup.
            # Late cancellation acknowledges the durable terminal decision;
            # it must not overwrite it or strand the parent workflow.
            from .engine.contracts import RunState, TERMINAL_RUN_STATES
            if RunState(self.engine.store.run(run_id)['status']) not in TERMINAL_RUN_STATES:
                raise
            return self.run_status(workspace, run_id, principal=principal) if compact else self.details(workspace, run_id, principal=principal)
        with service.lock:
            current = service.jobs.get(run_id)
            if current is not None and current.get('status') in ('queued', 'running', 'preparing'):
                current['cancel_requested'] = True
                current['cancel_state'] = 'requesting'
                from src.web.service import write_json
                write_json(service.jobs_dir / run_id / 'job.json', current)
        return self.run_status(workspace, run_id, principal=principal) if compact else self.details(workspace, run_id, principal=principal)

    def run_status(self, workspace, run_id, *, principal=None, session_id=None):
        """Bounded lifecycle observation: no graph, file reads or historical logs."""
        service = self.resolve(workspace)
        if session_id is not None:
            principal = self._session(session_id, workspace=workspace, principal=principal)['principal']
        principal = self._authorize(service, principal)
        with service.lock:
            job = service.require(run_id)
            if job.get('principal') and job['principal'] != principal:
                raise PoolAuthError('This run belongs to another scheduling principal')
            return {key: job.get(key) for key in ('id', 'status', 'logs_complete', 'exit_code',
                'cancel_requested', 'compute_complete', 'tree_exited', 'resources_released', 'artifact_committed')}

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
                    for wid, service in list(self.services.items())],
            'trusted_principals': sorted(self._principals()),
            'sessions': len(self.sessions),
            'queue_limits': asdict(self.engine.store.queue_limits),
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
        invocation = self.invocation_executor(run)
        if invocation is not None:
            from .engine.artifacts import ArtifactCommitter
            return invocation.publish(payload, result, ArtifactCommitter(invocation.root, self.engine.store))
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
            except Exception:
                # A live stopping thread still owns state and admission. Preserve
                # every handle so shutdown can be retried without a second owner.
                self._closed = False
                raise
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

    def __init__(self, pool, *, token, host='127.0.0.1', port=0, limits=None, controller_id=None):
        if not token:
            raise ValueError('A non-empty pool token is required')
        self.pool, self.token = pool, token
        # A configured identity is authorized by this existing authenticated
        # endpoint; an arbitrary payload controller_id is never authority.
        configured_controller = controller_id or os.environ.get('OPERON_CLUSTER_CONTROLLER_ID')
        self.cluster_endpoint = None
        if configured_controller and pool is not None:
            from .cluster.host import HostControllerEndpoint
            self.cluster_endpoint = HostControllerEndpoint(pool, authenticated_controller_id=configured_controller)
        self.host = host
        self.listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.listener.bind((host, port))
        self.address = self.listener.getsockname()
        self.listener.listen(64)
        self.listener.settimeout(.25)
        self.loop = ControlLoop(self.dispatch, limits=limits or limits_from_environment())
        self.lifecycle_listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.lifecycle_listener.bind((host, 0))
        self.lifecycle_listener.listen(16)
        self.lifecycle_listener.settimeout(.25)
        self.lifecycle_address = self.lifecycle_listener.getsockname()
        self.lifecycle_loop = ControlLoop(self.dispatch_lifecycle, limits=ControlLimits(
            max_handlers=4, max_reject_handlers=1, max_frame_bytes=65536,
            max_response_bytes=65536, max_inflight_bytes=4 * 1024**2,
            inactivity_seconds=5, absolute_seconds=10, busy_response_seconds=.2))
        self.principal_limiter = PrincipalLimiter(
            rate=float(os.environ.get('OPERON_CONTROL_RATE', 20)),
            burst=int(os.environ.get('OPERON_CONTROL_BURST', 40)),
            concurrent=int(os.environ.get('OPERON_CONTROL_PRINCIPAL_HANDLERS', 8)))
        self._closed = threading.Event()
        self._thread = None

    def start(self):
        self._lifecycle_thread = threading.Thread(target=self._accept,
            args=(self.lifecycle_listener, self.lifecycle_loop), name='operon-pool-lifecycle', daemon=True)
        self._lifecycle_thread.start()
        self._thread = threading.Thread(target=self._accept, name='operon-pool-control', daemon=True)
        self._thread.start()
        return self

    def _accept(self, listener=None, loop=None):
        listener, loop = listener or self.listener, loop or self.loop
        while not self._closed.is_set():
            try:
                connection, peer = listener.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            loop.submit(connection, peer=f'{peer[0]}:{peer[1]}')

    def capabilities(self):
        value = {'control.lifecycle_lane.v1': {'address': list(self.lifecycle_address),
                                             'max_frame_bytes': 65536, 'handlers': 4}}
        if self.pool is not None and hasattr(self.pool, 'submit_plan'):
            value['execution.invocation.v1'] = {'schema_version': 1}
        if self.cluster_endpoint is not None:
            value['cluster.controller_fence.v1'] = {'controller_id': self.cluster_endpoint.controller_id}
            value['cluster.invocation.v1'] = {'controller_id': self.cluster_endpoint.controller_id,
                                              'schema_version': 1}
            value['cluster.same_host_artifacts.v1'] = {'schema_version': 1}
        return value

    def dispatch_lifecycle(self, method, params):
        self._check(params)
        if method not in ('pool.ping', 'run.status', 'run.cancel', 'session.close', 'workspace.close_session',
                          'cluster.lookup', 'cluster.status', 'cluster.cancel',
                          'cluster.plan.lookup', 'cluster.plan.status', 'cluster.plan.cancel'):
            if method not in ('plan.details', 'plan.cancel'):
                raise ControlError('This endpoint only accepts bounded lifecycle operations')
        return self.dispatch(method, {**params, '_compact': True})

    def _check(self, params):
        token = params.get('_token') if isinstance(params, dict) else None
        if not isinstance(token, str) or not hmac.compare_digest(token, self.token):
            raise PoolAuthError('Invalid pool control token')

    def dispatch(self, method, params):
        params = params or {}
        self._check(params)
        # A claimed principal is not an identity. Resolve it from an authorized
        # registered workspace/session, otherwise charge the authenticated pool
        # owner. Opening extra sessions cannot multiply a principal's allowance.
        principal = pool_owner()
        if params.get('session_id'):
            principal = self.pool._session(params['session_id'], workspace=params.get('workspace'),
                                           principal=params.get('principal'))['principal']
        elif params.get('workspace'):
            principal = self.pool._authorize(self.pool.resolve(params['workspace']), params.get('principal'))
        lane = 'lifecycle' if method in ('run.cancel', 'run.status', 'run.details', 'pool.ping', 'pool.status', 'session.close', 'workspace.close_session', 'workspace.stop', 'cluster.lookup', 'cluster.status', 'cluster.cancel', 'cluster.plan.lookup', 'cluster.plan.status', 'cluster.plan.cancel', 'plan.details', 'plan.cancel') else 'normal'
        with self.principal_limiter.admit(principal, lane=lane):
            return self._dispatch(method, params)

    def _dispatch(self, method, params):
        if method in ('plan.artifact_files', 'plan.artifact_preview', 'plan.artifact_file'):
            from .contracts.plan_artifacts import (PlanArtifactFilesControl, PlanArtifactPreviewControl,
                                                   PlanArtifactFileControl)
            model = {'plan.artifact_files': PlanArtifactFilesControl,
                     'plan.artifact_preview': PlanArtifactPreviewControl,
                     'plan.artifact_file': PlanArtifactFileControl}[method]
            request = model.model_validate({key: value for key, value in params.items()
                                            if key not in ('_token', '_compact')})
            arguments = request.model_dump(mode='json')
            workspace, run_id = arguments.pop('workspace'), arguments.pop('run_id')
            return getattr(self.pool, method.replace('.', '_'))(workspace, run_id, **arguments)
        if method in ('plan.events', 'plan.attempts', 'plan.artifacts', 'plan.logs'):
            from .contracts.plan_operations import PlanEventsControl, PlanPageControl, PlanLogsControl
            model = {'plan.events': PlanEventsControl, 'plan.logs': PlanLogsControl}.get(method, PlanPageControl)
            request = model.model_validate({key: value for key, value in params.items()
                                            if key not in ('_token', '_compact')})
            arguments = request.model_dump(mode='json')
            workspace, run_id = arguments.pop('workspace'), arguments.pop('run_id')
            return getattr(self.pool, method.replace('.', '_'))(workspace, run_id, **arguments)
        if method == 'plan.submit':
            from .contracts.plan_operations import PlanSubmitControl
            request = PlanSubmitControl.model_validate({key: value for key, value in params.items()
                                                       if key not in ('_token', '_compact')})
            return self.pool.submit_plan(request.workspace, request.plan, request.binding.model_dump(mode='json'),
                request_id=request.request_id, principal=request.principal, session_id=request.session_id)
        if method in ('plan.details', 'plan.cancel'):
            from .contracts.plan_operations import PlanLookupControl
            request = PlanLookupControl.model_validate({key: value for key, value in params.items()
                                                       if key not in ('_token', '_compact')})
            action = self.pool.plan_details if method == 'plan.details' else self.pool.plan_cancel
            value = action(request.workspace, request.run_id, principal=request.principal, session_id=request.session_id)
            if params.get('_compact'):
                # Reserved lane never serializes every unit/attempt or full plan.
                return {**{key: value[key] for key in ('run_id', 'state', 'results')}, 'revision': str(value['revision']),
                        'unit_count': len(value.get('units', ())), 'attempt_count': len(value.get('attempts', ()))}
            return value
        if method.startswith('cluster.'):
            if self.cluster_endpoint is None:
                raise PoolError('Controller access is not configured on this host', code='capability_unavailable')
            from src.web.models import Graph
            return self.cluster_endpoint.dispatch(method, params, graph_validator=Graph.model_validate)
        if method == 'pool.status':
            return {**self.pool.status(), 'capabilities': self.capabilities()}
        if method == 'pool.ping':
            return {'pool_id': self.pool.engine.spec.pool_id, 'closed': self.pool._closed,
                    'capacity_domain': self.pool.engine.spec.capacity_domain, 'capabilities': self.capabilities()}
        if method == 'run.status':
            return self.pool.run_status(params.get('workspace'), params.get('run_id'),
                principal=params.get('principal'), session_id=params.get('session_id'))
        if method == 'workspace.list':
            return [{'root': str(service.root), 'workspace_id': wid,
                     'principal': service._pool_principal or service.engine.principal}
                    for wid, service in self.pool.services.items()]
        if method == 'session.open':
            session = self.pool.open_session(params.get('workspace'),
                                          principal=params.get('principal'),
                                          name=params.get('name'), owner=params.get('owner'))
            return {**session, 'capabilities': self.capabilities()}
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
                                    reason=params.get('reason') or 'client cancel', compact=params.get('_compact') is True)
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
        self.lifecycle_listener.close()
        self.lifecycle_loop.close()
        for thread in (self._thread, getattr(self, '_lifecycle_thread', None)):
            if thread is not None and thread is not threading.current_thread():
                thread.join(timeout=1)


class PoolClientError(EngineError):
    code = 'pool_client_error'


class PoolClient:
    """Small reconnecting client; one request per connection."""

    def __init__(self, address, token, *, timeout=30.0, session_id=None, capabilities=None):
        self.address = tuple(address)
        self.token = token
        self.timeout = timeout
        self.session_id = session_id
        self._session_context = None
        self.lifecycle_address = None
        self.negotiate(capabilities or {})

    def negotiate(self, capabilities):
        self.capabilities = dict(capabilities)
        endpoint = (capabilities.get('control.lifecycle_lane.v1') or {}).get('address')
        if (isinstance(endpoint, (list, tuple)) and len(endpoint) == 2 and
                endpoint[0] == self.address[0] and type(endpoint[1]) is int and 0 < endpoint[1] < 65536):
            self.lifecycle_address = tuple(endpoint)

    def open_session(self, workspace, *, principal=None, name=None):
        value = self.request('session.open', {'workspace': str(workspace),
                                              'principal': principal, 'name': name,
                                              'owner': owner_identity()})
        self.session_id = value['session_id']
        self.negotiate(value.get('capabilities') or {})
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
            self._session_context = None
        return value

    def stop_workspace(self, workspace, *, principal=None):
        return self.request('workspace.stop', {'workspace': str(workspace),
                                               'principal': principal})

    def request(self, method, params=None, *, _retry_session=True):
        payload = dict(params or {})
        session_method = method in ('run.submit', 'run.status', 'run.details', 'run.cancel', 'events.page',
                                    'plan.submit', 'plan.details', 'plan.cancel', 'plan.events', 'plan.attempts',
                                    'plan.artifacts', 'plan.logs', 'plan.artifact_files', 'plan.artifact_preview',
                                    'plan.artifact_file')
        if session_method and self._session_context and self.session_id:
            payload['session_id'] = self.session_id
        payload['_token'] = self.token
        body = json.dumps({'id': uuid.uuid4().hex, 'method': method, 'params': payload},
                          ensure_ascii=False, allow_nan=False).encode('utf-8')
        address = (self.lifecycle_address if self.lifecycle_address and method in
            ('pool.ping', 'run.status', 'run.cancel', 'session.close', 'workspace.close_session',
             'cluster.lookup', 'cluster.status', 'cluster.cancel', 'cluster.plan.lookup', 'cluster.plan.status', 'cluster.plan.cancel', 'plan.details', 'plan.cancel') else self.address)
        with socket.create_connection(address, timeout=self.timeout) as connection:
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
                                  details=value.get('details'), retry_after=value.get('retry_after'))
        result = value.get('value')
        if method in ('pool.status', 'pool.ping') and isinstance(result, dict):
            self.negotiate(result.get('capabilities') or {})
        return result

    @staticmethod
    def _recv_exact(connection, size):
        chunks = []
        while size:
            try:
                block = connection.recv(min(size, 65536))
            except ConnectionResetError as exc:
                # Windows may reset a rejected oversized frame before its
                # error response drains. This is an unknown response, never
                # evidence that a submitted operation is safe to relaunch.
                raise PoolClientError('Pool connection reset before the response',
                                      code='response_unavailable') from exc
            if not block:
                raise PoolClientError('Pool connection closed before the response', code='response_unavailable')
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

    def submit_plan(self, workspace, plan, binding, *, request_id, principal=None):
        return self.request('plan.submit', {'workspace': str(workspace), 'plan': plan, 'binding': binding,
            'request_id': request_id, 'principal': principal, 'session_id': self.session_id})

    def plan_details(self, workspace, run_id, *, principal=None):
        return self.request('plan.details', {'workspace': str(workspace), 'run_id': run_id,
                                            'principal': principal, 'session_id': self.session_id})

    def cancel_plan(self, workspace, run_id, *, principal=None):
        return self.request('plan.cancel', {'workspace': str(workspace), 'run_id': run_id,
                                           'principal': principal, 'session_id': self.session_id})
