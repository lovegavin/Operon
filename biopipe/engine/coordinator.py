"""Single-writer pool coordinator: durable queue, leases and launch outbox.

The coordinator never performs scientific work.  It writes short transactions,
launches through an executor outside those transactions and reconciles the
result.  Multiple workspaces and client connections share one pool; connections
do not create independent entitlements.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import os
from pathlib import Path
import queue
import threading
import time
import traceback
import uuid
from typing import Callable

from .contracts import (
    AttemptState, BusyError, PoolSpec, ResourceRequest, RunPlan, RunState, StaleAttemptError,
    StaleRevisionError, UnavailableStateError, UnitPlan,
)
from .events import EventStream
from .budget import ResizeCommand, ResizeController
from .executor import ExecutionContext, ExecutionResult, Executor
from .policy import Demand, FairnessPolicy, Usage, aggregate, select_ready
from .resources import PoolResources
from .state import StateStore, now_iso
from .supervisor import SupervisorError, boot_identity, identity_alive
from .telemetry import METRICS, span


def _parse_time(value: str | None) -> float:
    if not value:
        return time.time()
    try:
        return datetime.fromisoformat(value).timestamp()
    except (TypeError, ValueError):
        return time.time()


@dataclass(frozen=True)
class CoordinatorConfig:
    heartbeat_seconds: float = 2.0
    poll_seconds: float = 0.25
    launch_batch: int = 8
    dispatch_batch: int = 16
    cancel_timeout_seconds: float = 8.0
    event_retention: int = 20000


class Coordinator:
    def __init__(self, store: StateStore, spec: PoolSpec, executor: Executor, *,
                 workspace_id: str, principal: str, project: str = 'default',
                 root: str | Path = '.', policy: FairnessPolicy | None = None,
                 config: CoordinatorConfig | None = None,
                 artifact_committer: Callable[[dict, ExecutionResult], dict] | None = None,
                 owner_id: str | None = None):
        self.store, self.spec, self.executor = store, spec, executor
        self.principal, self.project = principal, project
        self.trusted_principals = {principal}
        self.workspace_id = workspace_id
        self.root = Path(root)
        self.policy = policy or FairnessPolicy()
        self.config = config or CoordinatorConfig()
        self.artifact_committer = artifact_committer
        self.owner_id = owner_id or uuid.uuid4().hex
        self.owner = {'pid': os.getpid(), 'created': None, 'boot_id': boot_identity(),
                      'service_id': self.owner_id}
        try:
            import psutil
            self.owner['created'] = psutil.Process().create_time()
        except Exception:  # noqa: BLE001 - identity is optional in restricted containers
            self.owner['created'] = None
        self.resources = PoolResources(store, spec, 0)
        self.events = EventStream(store)
        self.resize = ResizeController(self.resources, store)
        self.epoch = 0
        self.stop_event = threading.Event()
        self.wake = threading.Event()
        self.thread: threading.Thread | None = None
        self.diagnostics: list[dict] = []
        self.stopping = False
        self._last_heartbeat = 0.0
        self._commands: queue.Queue = queue.Queue()
        self._lock = threading.RLock()

    # -- lifecycle -----------------------------------------------------
    @property
    def pool_id(self) -> str:
        return self.spec.pool_id

    def claim(self) -> int:
        if self.epoch:
            return self.epoch
        self.epoch = self.store.claim_coordinator(
            self.pool_id, owner=self.owner, owner_id=self.owner_id,
            owner_alive=_owner_alive, stale_after=self.config.heartbeat_seconds * 10)
        self.resources = PoolResources(self.store, self.spec, self.epoch)
        self.store.register_workspace(self.workspace_id, self.pool_id, str(self.root.resolve()),
                                      self.principal, self.project)
        self.recover()
        return self.epoch

    def start(self):
        if self.thread is not None and self.thread.is_alive():
            return self
        self.claim()
        self.thread = threading.Thread(target=self._loop, name='operon-coordinator-' + self.pool_id[:8],
                                       daemon=True)
        self.thread.start()
        return self

    def _loop(self):
        while not self.stop_event.is_set():
            started = time.monotonic()
            try:
                self.run_once()
            except Exception as exc:  # keep the durable queue observable
                self._diagnose('loop_error', error=f'{type(exc).__name__}: {exc}',
                               traceback=''.join(traceback.format_exc())[-4000:])
            elapsed = time.monotonic() - started
            self.wake.wait(max(0.02, self.config.poll_seconds - elapsed))
            self.wake.clear()

    def stop(self, *, cancel_attempts=False, timeout=10.0):
        """Detach this coordinator.  Queued work stays durable for the next owner."""
        self.stop_event.set()
        self.wake.set()
        if self.thread is not None:
            self.thread.join(timeout=timeout)
            self.thread = None
        if cancel_attempts:
            self.cancel_all(reason='coordinator shutdown')
        self.store.release_coordinator(self.pool_id, self.owner_id)

    def close(self, *, cancel_attempts=False):
        self.stopping = True
        self.stop(cancel_attempts=cancel_attempts)

    # -- submission and commands ---------------------------------------
    def submit(self, *, key: str, digest: str, graph: dict, parameters: dict, execution: dict,
               units: list[dict], workspace_id: str | None = None, principal: str | None = None,
               project: str | None = None, operation: str = 'run',
               run_id: str | None = None) -> dict:
        principal = principal or self.principal
        if principal not in self.trusted_principals:
            from .contracts import UnauthorizedError
            raise UnauthorizedError('A coordinator pool accepts work only from a trusted scheduling principal')
        project = project or self.project
        workspace_id = workspace_id or self.workspace_id
        unit_models = tuple(UnitPlan(unit_id=item['unit_id'], node_ids=tuple(item.get('node_ids', ())),
                                     depends_on=tuple(item.get('depends_on', ())),
                                     target=dict(item.get('target') or {'kind': 'local'}),
                                     requirement=ResourceRequest.from_json(item.get('requirement')),
                                     capability=item.get('capability', 'legacy-sequential'),
                                     group=item.get('group'), retry_limit=int(item.get('retry_limit', 1)))
                            for item in units)
        run_id = run_id or 'run-' + uuid.uuid4().hex
        plan = RunPlan(run_id=run_id, workspace_id=workspace_id, principal=principal, project=project,
                       plan_key=digest, graph=graph, parameters=parameters, execution=execution,
                       units=unit_models, created_at=now_iso())
        run = {'id': run_id, 'workspace_id': workspace_id, 'project': project, 'plan_key': digest,
               'plan_digest': plan.digest, 'plan': plan.to_json()}
        claim = self.store.claim_submission(
            principal=principal, key=key, digest=digest, operation=operation, run=run,
            units=[dict(unit_id=unit.unit_id, node_ids=unit.node_ids, depends_on=unit.depends_on,
                        target=unit.target, requirement=unit.requirement.to_json(),
                        capability=unit.capability, group=unit.group, retry_limit=unit.retry_limit)
                   for unit in unit_models],
            owner=self.owner)
        self.wake.set()
        METRICS.increment('coordinator.submissions')
        return {'created': claim.created, 'reused': claim.reused, 'status': claim.status,
                'record': claim.record, 'run_id': claim.record.get('run_id')}

    def cancel(self, run_id: str, *, expected_revision: int | None = None, reason='client request',
               principal: str | None = None) -> dict:
        run = self.store.run(run_id)
        caller = principal or self.principal
        if caller not in self.trusted_principals or run['principal'] != caller:
            from .contracts import UnauthorizedError
            raise UnauthorizedError('This run belongs to a different authenticated principal',
                                    details={'run_id': run_id})
        value = self.store.request_cancel(run_id, expected_revision=expected_revision, reason=reason)
        self.wake.set()
        return value

    def cancel_all(self, *, reason='shutdown', timeout=30.0):
        errors = []
        for run in self.store.list_runs(states=[RunState.QUEUED.value, RunState.RUNNING.value,
                                                RunState.SUBMITTED.value, RunState.RECOVERY_REQUIRED.value],
                                       limit=1000):
            try:
                self.store.request_cancel(run['id'], reason=reason)
            except Exception as exc:  # noqa: BLE001 - report, never hide
                errors.append({'run_id': run['id'], 'error': str(exc)})
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            self.run_once()
            remaining = [run for run in self.store.list_runs(states=[RunState.QUEUED.value,
                                                                     RunState.RUNNING.value,
                                                                     RunState.SUBMITTED.value,
                                                                     RunState.RECOVERY_REQUIRED.value],
                                                             limit=1000) if run['cancel_requested']]
            if not remaining:
                break
            time.sleep(0.05)
        return errors

    # -- command loop --------------------------------------------------
    def run_once(self) -> dict:
        """One bounded scheduling cycle, safe to call directly in tests."""
        result = {'launched': 0, 'polled': 0, 'cancelled': 0, 'dispatched': 0, 'errors': []}
        with self._lock:
            if not self.epoch:
                self.claim()
            self._heartbeat()
            self.store.reconcile_transport_leases(self.pool_id)
            for item in self.store.pending_outbox(limit=self.config.launch_batch):
                if item['command'] != 'launch':
                    self.store.retry_outbox(item['id'], error='unsupported outbox command', delay=5)
                    continue
                try:
                    if self._launch_outbox(item):
                        result['launched'] += 1
                except Exception as exc:  # noqa: BLE001 - durable diagnostic
                    result['errors'].append({'outbox': item['id'], 'error': str(exc)})
                    self._diagnose('launch_error', outbox=item['id'],
                                   error=f'{type(exc).__name__}: {exc}')
            result['polled'] = self._poll_attempts()
            result['resized'] = self._poll_resizes()
            result['cancelled'] = self._handle_cancellations()
            self._settle_runs()
            self._refresh_ready()
            result['dispatched'] = self._dispatch()
            self._prune()
        return result

    def _heartbeat(self):
        now = time.monotonic()
        if now - self._last_heartbeat >= self.config.heartbeat_seconds:
            if not self.store.heartbeat_coordinator(self.pool_id, self.owner_id):
                raise BusyError('Another coordinator took ownership of this execution pool')
            self._last_heartbeat = now

    def _diagnose(self, kind: str, **fields):
        item = {'time': now_iso(), 'kind': kind, **fields}
        self.diagnostics.append(item)
        del self.diagnostics[:-200]
        METRICS.increment('coordinator.errors')

    # -- dispatch ------------------------------------------------------
    def _dispatch(self) -> int:
        snapshot = self.resources.snapshot()
        ready = self.store.ready_units(self.pool_id, limit=self.policy.scan_limit)
        if not ready:
            return 0
        now = time.time()
        demands = []
        for unit in ready:
            requirement = ResourceRequest.from_json(unit['requirement'])
            created = _parse_time(unit.get('run_created'))
            demands.append(Demand(key=unit['local_id'], principal=unit['principal'],
                                  project=unit['project'], requirement=requirement,
                                  age_seconds=max(0.0, now - created), submitted_at=created,
                                  run_id=unit['run_id'], unit_id=unit['id'],
                                  retry=int(unit.get('attempts', 0))))
        usage = aggregate([{'principal': lease.get('principal') or '',
                            'ram': lease['committed'].process_reservation_bytes,
                            'cpu': lease['committed'].cpu_threads,
                            'scratch': lease['committed'].scratch_reserved_bytes}
                           for lease in self.store.lease_details(self.pool_id)
                           if lease.get('principal')])
        selection = select_ready(demands, capacity=snapshot.capacity, free=snapshot.free,
                                 usage=usage, policy=self.policy, limit=self.config.dispatch_batch,
                                 cpu_capacity=self.spec.cpu_threads)
        for item in selection.infeasible:
            self._fail_infeasible(item, ready)
        dispatched = 0
        for demand in selection.chosen:
            if self.stopping:
                break
            attempt_id = self._admit_unit(demand)
            if attempt_id:
                dispatched += 1
        if selection.explanation:
            METRICS.increment('coordinator.dispatch_cycles')
        if selection.reservation:
            METRICS.gauge('coordinator.protected_reservation_bytes',
                          selection.reservation.get('required_bytes', 0))
        return dispatched

    def _admit_unit(self, demand: Demand) -> str | None:
        try:
            with self.store.transaction():
                unit = self.store.unit(demand.unit_id)
                run = self.store.run(unit['run_id'])
                if unit['state'] != AttemptState.READY.value or RunState(run['status']) in (
                        RunState.CANCELLED, RunState.COMPLETE, RunState.FAILED):
                    return None
                attempt = self.store.create_attempt(unit['id'], epoch=self.epoch)
                try:
                    lease = self.resources.admit(attempt_id=attempt['id'],
                                                 request=ResourceRequest.from_json(unit['requirement']),
                                                 owner=self.owner)
                except Exception:
                    raise
                self.store.add_outbox(outbox_id='launch:' + attempt['id'], command='launch',
                                      attempt_id=attempt['id'], run_id=unit['run_id'],
                                      payload={'attempt_id': attempt['id'], 'lease_id': lease['id']})
                attempt = self.store.transition_attempt(attempt['id'], AttemptState.STARTING,
                                                        expected_revision=attempt['revision'],
                                                        actor='coordinator')
                if RunState(run['status']) == RunState.QUEUED:
                    self.store.transition_run(run['id'], RunState.RUNNING, actor='coordinator')
            self.wake.set()
            # Launch outside the state transaction and immediately, so a
            # feasible unit does not wait for the next heartbeat.
            try:
                self._launch_outbox(self.store.outbox('launch:' + attempt['id']))
            except Exception as exc:  # noqa: BLE001 - recorded, retried by outbox
                self._diagnose('admission_launch_error', attempt_id=attempt['id'], error=str(exc))
            return attempt['id']
        except Exception as exc:
            # A capacity race or a stale unit is normal; record it and continue.
            if type(exc).__name__ in ('InfeasibleResourcesError', 'StaleAttemptError', 'StaleRevisionError'):
                METRICS.increment('coordinator.admission_races')
                return None
            self._diagnose('admission_error', demand=demand.key, error=f'{type(exc).__name__}: {exc}')
            return None

    def _launch_outbox(self, item: dict) -> bool:
        attempt = self.store.attempt(item['attempt_id'])
        if AttemptState(attempt['state']) in (AttemptState.RUNNING, AttemptState.COMMITTING,
                                              AttemptState.SUCCEEDED, AttemptState.FAILED,
                                              AttemptState.CANCELLED):
            self.store.ack_outbox(item['id'], result={'state': attempt['state']})
            return False
        if self.store.outbox(item['id'])['state'] == 'acked':
            return False
        self.store.claim_outbox(item['id'])
        unit = self.store.unit(attempt['unit_id'])
        run = self.store.run(unit['run_id'])
        plan = run['plan']
        context = ExecutionContext(run=run, unit=unit, attempt=self.store.attempt(attempt['id']),
                                   directory=self.root / 'runs' / run['id'],
                                   environment=dict(os.environ), plan=plan,
                                   lease=self.store.lease(attempt['id']))
        with span('coordinator.launch', run_id=run['id'], attempt_id=attempt['id']):
            try:
                result = self.executor.launch(context)
            except SupervisorError as exc:
                if exc.code == 'recovery_required':
                    self._transition(attempt['id'], AttemptState.RECOVERY_REQUIRED,
                                     error=str(exc), error_code=exc.code)
                    self.store.ack_outbox(item['id'], result={'state': 'recovery_required'})
                    self._diagnose('launch_quarantined', attempt_id=attempt['id'], error=str(exc))
                    return False
                self._fail_attempt(attempt['id'], result=None, error=str(exc), error_code=exc.code,
                                   release=True, retry=True)
                self.store.ack_outbox(item['id'], result={'state': 'failed', 'error': str(exc)})
                return False
            except Exception as exc:  # noqa: BLE001 - classification is explicit
                self._fail_attempt(attempt['id'], result=None, error=f'{type(exc).__name__}: {exc}',
                                   error_code='launch_failed', release=True, retry=False)
                self.store.ack_outbox(item['id'], result={'state': 'failed', 'error': str(exc)})
                return False
        fresh = self.store.attempt(attempt['id'])
        if result.state in ('failed', 'cancelled'):
            lease = self.store.lease(attempt['id'])
            self._fail_attempt(
                attempt['id'], result=result,
                error=result.error or f'launch returned {result.state}',
                error_code='launch_failed' if result.state == 'failed' else 'cancelled',
                release=True, retry=result.state == 'failed')
            self.store.ack_outbox(item['id'], result={'state': result.state})
            return False
        if AttemptState(fresh['state']) in (AttemptState.STARTING, AttemptState.ADMITTED):
            identity = result.identity
            if identity is not None and hasattr(identity, 'to_json'):
                identity = identity.to_json()
            self.store.transition_attempt(attempt['id'], AttemptState.RUNNING,
                                          expected_revision=fresh['revision'],
                                          process=identity or {},
                                          receipt={'state': result.state, 'detail': result.detail})
        self.store.ack_outbox(item['id'], result={'state': result.state})
        METRICS.increment('coordinator.launches')
        return True

    # -- completion and cancellation -----------------------------------
    def _poll_attempts(self) -> int:
        count = 0
        states = [AttemptState.RUNNING.value, AttemptState.COMMITTING.value, AttemptState.STARTING.value]
        for attempt in self.store.attempts_for_pool(self.pool_id, states=states):
            unit = self.store.unit(attempt['unit_id'])
            run = self.store.run(unit['run_id'])
            context = ExecutionContext(run=run, unit=unit, attempt=attempt,
                                       directory=self.root / 'runs' / run['id'],
                                       environment=dict(os.environ), plan=run['plan'])
            with span('coordinator.poll', run_id=run['id'], attempt_id=attempt['id']):
                try:
                    result = self.executor.poll(context)
                except Exception as exc:  # noqa: BLE001
                    self._diagnose('poll_error', attempt_id=attempt['id'],
                                   error=f'{type(exc).__name__}: {exc}')
                    continue
            count += 1
            if result.state == 'running':
                continue
            if result.state == 'committing':
                if AttemptState(attempt['state']) != AttemptState.COMMITTING:
                    self._transition(attempt['id'], AttemptState.COMMITTING,
                                     error=None)
                    self._diagnose('cleanup_lease_retained', attempt_id=attempt['id'],
                                   detail='output exists but owned descendants still run')
                continue
            if result.state in ('succeeded', 'failed', 'cancelled'):
                self._finalize(attempt, unit, run, result)
                continue
            if result.state in ('unknown', 'missing'):
                if AttemptState(attempt['state']) in (AttemptState.STARTING, AttemptState.ADMITTED):
                    self._fail_attempt(attempt['id'], result=None,
                                       error=result.error or 'Launch could not be verified',
                                       error_code='recovery_required', release=True, retry=False)
                else:
                    self._transition(attempt['id'], AttemptState.RECOVERY_REQUIRED,
                                     error=result.error or 'Process ownership is uncertain',
                                     error_code='recovery_required')
                    self._diagnose('attempt_quarantined', attempt_id=attempt['id'],
                                   detail=result.error or result.detail)
        return count

    def request_resize(self, attempt_id: str, *, managed_budget_bytes: int,
                       release_process_bytes: int = 0, resize_id: str | None = None) -> dict:
        """Propose a revisioned resize and deliver it at the next safe boundary."""
        attempt = self.store.attempt(attempt_id)
        unit = self.store.unit(attempt['unit_id'])
        run = self.store.run(unit['run_id'])
        proposal = self.resize.propose(attempt_id, managed_budget_bytes=managed_budget_bytes,
                                       release_process_bytes=release_process_bytes,
                                       resize_id=resize_id)
        payload = proposal.get('resize') or {}
        command = ResizeCommand(
            lease_id=proposal['id'], attempt_id=attempt_id, fence=int(attempt['fence']),
            resize_id=str(payload.get('resize_id')), revision=int(proposal['revision']),
            managed_budget_bytes=int(managed_budget_bytes),
            process_reservation_bytes=int(proposal['target'].process_reservation_bytes),
            release_process_bytes=int(release_process_bytes))
        writer = getattr(self.executor, 'write_resize', None)
        if callable(writer):
            context = ExecutionContext(run=run, unit=unit, attempt=attempt,
                                       directory=self.root / 'runs' / run['id'],
                                       environment=dict(os.environ), plan=run['plan'])
            writer(context, command)
        return proposal

    def _poll_resizes(self) -> int:
        count = 0
        reader = getattr(self.executor, 'read_resize_ack', None)
        if not callable(reader):
            return 0
        for lease in self.store.lease_details(self.pool_id):
            if lease['state'] != 'resize_pending':
                continue
            attempt = self.store.attempt(lease['attempt_id'])
            unit = self.store.unit(attempt['unit_id'])
            run = self.store.run(unit['run_id'])
            context = ExecutionContext(run=run, unit=unit, attempt=attempt,
                                       directory=self.root / 'runs' / run['id'],
                                       environment=dict(os.environ), plan=run['plan'])
            try:
                ack = reader(context)
            except Exception as exc:  # noqa: BLE001
                self._diagnose('resize_read_error', attempt_id=attempt['id'], error=str(exc))
                continue
            if not ack:
                continue
            proposal = lease.get('resize') or {}
            if ack.get('resize_id') != proposal.get('resize_id'):
                continue  # delayed/duplicate ack for an older proposal
            try:
                if ack.get('state') == 'acknowledged':
                    self.resize.acknowledge(attempt['id'], ack)
                else:
                    self.resize.reject(attempt['id'], resize_id=str(ack.get('resize_id')),
                                       reason=str(ack.get('error') or 'worker refused resize'))
                count += 1
            except Exception as exc:  # noqa: BLE001
                self._diagnose('resize_ack_error', attempt_id=attempt['id'], error=str(exc))
        return count

    def _finalize(self, attempt, unit, run, result: ExecutionResult):
        target = {'succeeded': AttemptState.SUCCEEDED, 'failed': AttemptState.FAILED,
                  'cancelled': AttemptState.CANCELLED}[result.state]
        fresh = self.store.attempt(attempt['id'])
        if AttemptState(fresh['state']) in (AttemptState.SUCCEEDED, AttemptState.FAILED,
                                            AttemptState.CANCELLED):
            return
        if target == AttemptState.SUCCEEDED and self.artifact_committer is not None:
            try:
                receipt = self.artifact_committer({**attempt, 'unit': unit, 'run': run}, result)
                self.store.transition_attempt(attempt['id'], AttemptState.COMMITTING,
                                              expected_revision=fresh['revision'], receipt=receipt or {})
                fresh = self.store.attempt(attempt['id'])
            except Exception as exc:  # noqa: BLE001 - publication failure is explicit
                target = AttemptState.FAILED
                result = ExecutionResult(state='failed', exit_code=result.exit_code,
                                         error=f'Artifact commit failed: {exc}', identity=result.identity)
        try:
            if AttemptState(fresh['state']) == AttemptState.RUNNING and target != AttemptState.RUNNING:
                self.store.transition_attempt(attempt['id'], AttemptState.COMMITTING,
                                              expected_revision=fresh['revision'], actor='coordinator')
                fresh = self.store.attempt(attempt['id'])
            if AttemptState(fresh['state']) != target:
                self.store.transition_attempt(attempt['id'], target, expected_revision=fresh['revision'],
                                              exit_code=result.exit_code, error=result.error,
                                              error_code=None if target == AttemptState.SUCCEEDED else 'execution_failed',
                                              receipt={'detail': result.detail})
        except (StaleAttemptError, StaleRevisionError):
            # A concurrent cancellation or a newer attempt already decided the
            # terminal state; the durable decision is authoritative.
            return
        lease = self.store.lease(attempt['id'])
        if lease and lease['state'] != 'released':
            # Only a confirmed exit of the owned tree returns process credits.
            self.resources.release(lease['id'], reason=f'attempt {target.value}',
                                   released_process_bytes=lease['committed'].process_reservation_bytes)
        if target == AttemptState.FAILED:
            retry = self._retry_allowed(unit, result)
            if retry:
                self.store.update_unit(unit['id'], state=AttemptState.READY.value)
                self._diagnose('attempt_retry', attempt_id=attempt['id'], unit=unit['local_id'])
            else:
                self.store.update_unit(unit['id'], state=AttemptState.FAILED.value)
        self.wake.set()

    def _retry_allowed(self, unit, result: ExecutionResult) -> bool:
        if int(unit.get('attempts', 0)) >= int(unit.get('retry_limit', 1)):
            return False
        # Only transient launch/ownership failures retry automatically.  A
        # scientific non-zero exit or a cancelled attempt is explicit.
        return result is not None and result.detail in ('launch_failed', 'recovery_required')

    def _fail_attempt(self, attempt_id: str, *, result: ExecutionResult | None, error: str,
                      error_code: str, release: bool, retry: bool):
        attempt = self.store.attempt(attempt_id)
        if AttemptState(attempt['state']) not in (AttemptState.SUCCEEDED, AttemptState.FAILED,
                                                 AttemptState.CANCELLED):
            self.store.transition_attempt(attempt_id, AttemptState.FAILED, error=error,
                                          error_code=error_code)
        lease = self.store.lease(attempt_id)
        if release and lease and lease['state'] != 'released':
            self.resources.release(lease['id'], reason='attempt failed: ' + error_code,
                                   released_process_bytes=lease['committed'].process_reservation_bytes)
        unit = self.store.unit(attempt['unit_id'])
        if retry and self._retry_allowed(unit, ExecutionResult(state='failed', detail='launch_failed')):
            self.store.update_unit(unit['id'], state=AttemptState.READY.value)
        else:
            self.store.update_unit(unit['id'], state=AttemptState.FAILED.value)
        self._settle_runs()
        self.wake.set()

    def _transition(self, attempt_id: str, state: AttemptState, **values):
        attempt = self.store.attempt(attempt_id)
        if attempt['state'] == state.value:
            return attempt
        return self.store.transition_attempt(attempt_id, state,
                                             expected_revision=attempt['revision'], **values)

    def _handle_cancellations(self) -> int:
        count = 0
        active_runs = [run for run in self.store.list_runs(states=[RunState.QUEUED.value,
                                                                  RunState.RUNNING.value,
                                                                  RunState.SUBMITTED.value,
                                                                  RunState.RECOVERY_REQUIRED.value],
                                                          limit=500)
                       if run['cancel_requested']]
        for run in active_runs:
            attempts = [item for item in self.store.attempts_for_pool(
                self.pool_id, states=[AttemptState.RUNNING.value, AttemptState.STARTING.value,
                                      AttemptState.ADMITTED.value, AttemptState.COMMITTING.value,
                                      AttemptState.RECOVERY_REQUIRED.value])
                if item['run_id'] == run['id']]
            confirmed = True
            for attempt in attempts:
                unit = self.store.unit(attempt['unit_id'])
                context = ExecutionContext(run=run, unit=unit, attempt=attempt,
                                           directory=self.root / 'runs' / run['id'],
                                           environment=dict(os.environ), plan=run['plan'])
                try:
                    result = self.executor.cancel(context, timeout=self.config.cancel_timeout_seconds)
                except Exception as exc:  # stop must be confirmed before release
                    confirmed = False
                    self.store.update_run_cancel_state(run['id'], 'stopping')
                    self._diagnose('cancel_unconfirmed', attempt_id=attempt['id'],
                                   error=f'{type(exc).__name__}: {exc}')
                    continue
                if result.tree_alive:
                    confirmed = False
                    self.store.update_run_cancel_state(run['id'], 'stopping')
                    continue
                self._finalize_cancelled(attempt, unit)
                count += 1
            if confirmed:
                if not attempts:
                    cancel_run = getattr(self.executor, 'cancel_run', None)
                    if callable(cancel_run):
                        try:
                            cancel_run(run['id'])
                        except Exception as exc:  # noqa: BLE001 - durable run still marked stopped
                            self._diagnose('queued_cancel_error', run_id=run['id'], error=str(exc))
                self.store.mark_cancel_stopped(run['id'], actor='coordinator')
            else:
                self.store.update_run_cancel_state(run['id'], 'stopping')
        return count

    def _finalize_cancelled(self, attempt, unit):
        fresh = self.store.attempt(attempt['id'])
        if AttemptState(fresh['state']) not in (AttemptState.SUCCEEDED, AttemptState.FAILED,
                                                AttemptState.CANCELLED):
            self.store.transition_attempt(attempt['id'], AttemptState.CANCELLED,
                                          expected_revision=fresh['revision'],
                                          error_code='cancelled', error='Cancelled by request')
        lease = self.store.lease(attempt['id'])
        if lease and lease['state'] != 'released':
            self.resources.release(lease['id'], reason='ancelled after confirmed stop',
                                   released_process_bytes=lease['committed'].process_reservation_bytes)
        self.store.update_unit(unit['id'], state=AttemptState.CANCELLED.value)

    def _fail_infeasible(self, item: dict, ready: list[dict]):
        unit = next((value for value in ready
                     if value['local_id'] == item['key'] and value['run_id'] == item['run_id']), None)
        if unit is None:
            return
        run = self.store.run(unit['run_id'])
        if RunState(run['status']) in (RunState.COMPLETE, RunState.FAILED, RunState.CANCELLED):
            return
        self.store.update_unit(unit['id'], state=AttemptState.FAILED.value)
        try:
            self.store.transition_run(run['id'], RunState.FAILED, actor='coordinator',
                                      reason='infeasible_resources',
                                      error='The unit minimum exceeds the frozen pool ceiling')
        except Exception:  # noqa: BLE001 - the durable state may already be terminal
            self._diagnose('infeasible_transition_failed', run_id=run['id'])
        self._diagnose('infeasible_unit', run_id=run['id'], unit=unit['local_id'],
                       message='The unit minimum exceeds the frozen pool ceiling')

    def _refresh_ready(self):
        for run in self.store.list_runs(states=[RunState.QUEUED.value, RunState.RUNNING.value,
                                                RunState.SUBMITTED.value], limit=200):
            self.store.set_unit_state_for_dependencies(run['id'])

    def _settle_runs(self):
        for run in self.store.list_runs(states=[RunState.QUEUED.value, RunState.RUNNING.value,
                                                RunState.SUBMITTED.value], limit=200):
            units = self.store.units(run['id'])
            if not units or any(unit['state'] not in (AttemptState.SUCCEEDED.value,
                                                     AttemptState.FAILED.value,
                                                     AttemptState.CANCELLED.value) for unit in units):
                continue
            if run['cancel_requested'] and any(unit['state'] != AttemptState.SUCCEEDED.value for unit in units):
                self.store.mark_cancel_stopped(run['id'], actor='coordinator')
                continue
            if all(unit['state'] == AttemptState.SUCCEEDED.value for unit in units):
                continue  # the state repository already published completion
            error = 'One or more execution units failed'
            self.store.transition_run(run['id'], RunState.FAILED, actor='coordinator',
                                      reason='unit failure', error=error)

    def _prune(self):
        try:
            if self.store.event_bounds()[1] > self.config.event_retention * 1.2:
                self.events.prune(self.config.event_retention)
        except Exception as exc:  # noqa: BLE001
            self._diagnose('prune_error', error=str(exc))

    # -- recovery ------------------------------------------------------
    def recover(self):
        """Reconcile every active attempt and outbox entry after a takeover."""
        recovered = {'adopted': 0, 'failed': 0, 'quarantined': 0, 'relaunched': 0}
        states = [AttemptState.ADMITTED.value, AttemptState.STARTING.value, AttemptState.RUNNING.value,
                  AttemptState.COMMITTING.value, AttemptState.RECOVERY_REQUIRED.value]
        for attempt in self.store.attempts_for_pool(self.pool_id, states=states):
            unit = self.store.unit(attempt['unit_id'])
            run = self.store.run(unit['run_id'])
            context = ExecutionContext(run=run, unit=unit, attempt=attempt,
                                       directory=self.root / 'runs' / run['id'],
                                       environment=dict(os.environ), plan=run['plan'])
            try:
                result = self.executor.reconcile(context)
            except Exception as exc:  # noqa: BLE001
                self._diagnose('recovery_error', attempt_id=attempt['id'], error=str(exc))
                result = ExecutionResult(state='unknown', detail='reconcile failed')
            state = AttemptState(attempt['state'])
            if result.state == 'running' and result.identity is not None:
                if state in (AttemptState.ADMITTED, AttemptState.STARTING, AttemptState.RECOVERY_REQUIRED):
                    self.store.transition_attempt(attempt['id'], AttemptState.RUNNING,
                                                  process=result.identity.to_json(),
                                                  receipt={'adopted': True})
                recovered['adopted'] += 1
                continue
            if result.state == 'dead':
                if run['cancel_requested']:
                    self._finalize_cancelled(attempt, unit)
                else:
                    self._fail_attempt(attempt['id'], result=result,
                                       error='The worker exited while the coordinator was absent; '
                                             'its scientific result is unknown',
                                       error_code='recovery_unknown', release=True, retry=False)
                recovered['failed'] += 1
                continue
            if result.state in ('missing', 'failed'):
                if state in (AttemptState.ADMITTED, AttemptState.STARTING):
                    pending = None
                    try:
                        pending = self.store.outbox('launch:' + attempt['id'])
                    except KeyError:
                        pending = None
                    if pending is not None and pending['state'] not in ('acked',):
                        # The durable launch command was never acknowledged;
                        # the normal outbox path launches it exactly once.
                        continue
                    self._fail_attempt(attempt['id'], result=result,
                                       error=result.error or 'The attempt was never launched',
                                       error_code='launch_failed', release=True, retry=True)
                    recovered['failed'] += 1
                else:
                    if state != AttemptState.RECOVERY_REQUIRED:
                        self._transition(attempt['id'], AttemptState.RECOVERY_REQUIRED,
                                         error='No verifiable launch receipt after coordinator restart')
                    recovered['quarantined'] += 1
                continue
            if state in (AttemptState.ADMITTED, AttemptState.STARTING):
                continue  # a pending launch outbox entry will launch it
            if state != AttemptState.RECOVERY_REQUIRED:
                self._transition(attempt['id'], AttemptState.RECOVERY_REQUIRED,
                                 error='Process ownership after restart is uncertain')
            recovered['quarantined'] += 1
        # Launch outbox entries that were recorded but never acknowledged.
        for item in self.store.pending_outbox(limit=500):
            if item['command'] != 'launch':
                continue
            attempt = self.store.attempt(item['attempt_id'])
            if AttemptState(attempt['state']) in (AttemptState.ADMITTED, AttemptState.STARTING):
                try:
                    if self._launch_outbox(item):
                        recovered['relaunched'] += 1
                except Exception as exc:  # noqa: BLE001
                    self._diagnose('recovery_launch_error', outbox=item['id'], error=str(exc))
        self._refresh_ready()
        self._settle_runs()
        self._diagnose('coordinator_recovered', epoch=self.epoch, **recovered)
        return recovered

    # -- read views ----------------------------------------------------
    def status(self) -> dict:
        snapshot = self.resources.snapshot()
        runs = self.store.list_runs(workspace_id=self.workspace_id, limit=100)
        return {'pool': snapshot.to_json(), 'epoch': self.epoch, 'owner_id': self.owner_id,
                'mode': self.spec.mode, 'runs': len(runs),
                'active_attempts': len(self.store.attempts_for_pool(
                    self.pool_id, states=[AttemptState.RUNNING.value, AttemptState.STARTING.value,
                                          AttemptState.ADMITTED.value, AttemptState.COMMITTING.value])),
                'pending_outbox': len(self.store.pending_outbox(limit=1000)),
                'diagnostics': self.diagnostics[-20:]}

    def details(self, run_id: str, *, principal: str | None = None) -> dict:
        run = self.store.run(run_id)
        caller = principal or self.principal
        if caller not in self.trusted_principals or run['principal'] != caller:
            from .contracts import UnauthorizedError
            raise UnauthorizedError('This run belongs to a different authenticated principal',
                                    details={'run_id': run_id})
        run['units'] = self.store.units(run_id)
        run['attempts'] = self.store.attempts(run_id)
        return run

    def events_page(self, cursor=0, **filters):
        return self.events.page(cursor, **filters)


def _owner_alive(owner: dict) -> bool:
    if not owner:
        return False
    if owner.get('boot_id') and owner['boot_id'] != boot_identity():
        return False
    if owner.get('created') is None:
        # Without a creation stamp, a live PID is not sufficient proof of the
        # same process; treat it as alive only while the heartbeat is fresh.
        return bool(owner.get('service_id'))
    return identity_alive({'pid': owner.get('pid'), 'created': owner.get('created'),
                           'boot_id': owner.get('boot_id')})
