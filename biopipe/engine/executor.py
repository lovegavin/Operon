"""Executor boundary: launch and observe units without granting resources.

Executors never reserve pool capacity; the coordinator owns grants.  A worker
cannot enlarge its allowance by changing a local setting.  Legacy services are
adapted behind this interface instead of becoming a second scheduler.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os
import time
from typing import Callable, Protocol

from .contracts import ProcessIdentity, ResourceRequest
from .supervisor import LaunchSpec, ProcessSupervisor, SupervisorError, identity_alive


@dataclass(frozen=True)
class ExecutionContext:
    run: dict
    unit: dict
    attempt: dict
    directory: Path
    environment: dict
    plan: dict
    lease: dict | None = None

    @property
    def attempt_id(self) -> str:
        return self.attempt['id']

    @property
    def fence(self) -> int:
        return int(self.attempt['fence'])


@dataclass(frozen=True)
class ExecutionResult:
    state: str
    exit_code: int | None = None
    error: str | None = None
    identity: ProcessIdentity | None = None
    tree_alive: bool = False
    detail: str = ''

    @property
    def terminal(self) -> bool:
        return self.state in ('succeeded', 'failed', 'cancelled')


class Executor(Protocol):
    capability: str
    resizable: bool

    def launch(self, context: ExecutionContext) -> ExecutionResult: ...

    def poll(self, context: ExecutionContext) -> ExecutionResult: ...

    def cancel(self, context: ExecutionContext, *, timeout: float = 10.0) -> ExecutionResult: ...

    def reconcile(self, context: ExecutionContext) -> ExecutionResult: ...


def attempt_directory(root, run_id: str, unit_label: str, attempt_id: str) -> Path:
    safe_run = str(run_id).replace('/', '_')
    safe_unit = str(unit_label).replace('/', '_')
    safe_attempt = str(attempt_id).replace('/', '_')
    return Path(root) / 'runs' / safe_run / 'nodes' / safe_unit / 'attempts' / safe_attempt


class ProcessExecutor:
    """Local process executor backed by :class:`ProcessSupervisor`."""

    capability = 'process-tree'
    resizable = False

    def __init__(self, root, *, command_builder: Callable[[ExecutionContext], LaunchSpec],
                 environment_builder: Callable[[ExecutionContext], dict] | None = None,
                 adopt_verified=True):
        self.root = Path(root)
        self.supervisor = ProcessSupervisor(self.root / 'supervisor', adopt_verified=adopt_verified)
        self.command_builder = command_builder
        self.environment_builder = environment_builder

    def directory(self, context: ExecutionContext) -> Path:
        return attempt_directory(self.root, context.run['id'], context.unit['local_id'], context.attempt_id)

    def launch(self, context: ExecutionContext) -> ExecutionResult:
        directory = self.directory(context)
        directory.mkdir(parents=True, exist_ok=True)
        spec = self.command_builder(context)
        environment = dict(spec.environment)
        if self.environment_builder:
            environment.update(self.environment_builder(context))
        environment.setdefault('BIOPIPE_ATTEMPT_ID', context.attempt_id)
        environment.setdefault('BIOPIPE_RUN_ID', context.run['id'])
        environment.setdefault('BIOPIPE_RESOURCE_FENCE', str(context.fence))
        adjusted = LaunchSpec(argv=spec.argv, cwd=spec.cwd, environment=environment,
                              stdout_path=str(directory / 'logs' / 'worker.log'),
                              executable=spec.executable, stdin_devnull=spec.stdin_devnull)
        receipt = self.supervisor.launch(context.attempt_id, fence=context.fence, spec=adjusted)
        return ExecutionResult(state='running', identity=receipt.identity, tree_alive=True,
                               detail='launch receipt ' + receipt.state)

    def _receipt(self, context):
        return self.supervisor.read_receipt(context.attempt_id)

    def poll(self, context: ExecutionContext) -> ExecutionResult:
        receipt = self._receipt(context)
        if receipt is None:
            return ExecutionResult(state='unknown', error='No launch receipt for this attempt',
                                   detail='recovery_required')
        if receipt.identity is None:
            return ExecutionResult(state='failed', error=receipt.error or 'The worker was never spawned',
                                   detail='no-identity')
        status, code = self.supervisor.poll_status(context.attempt_id)
        if status == 'running':
            return ExecutionResult(state='running', identity=receipt.identity, tree_alive=True)
        if status == 'stopped':
            return ExecutionResult(state='cancelled', identity=receipt.identity, exit_code=code)
        if status == 'exited':
            if self.tree_alive(receipt.identity):
                return ExecutionResult(state='committing', identity=receipt.identity, tree_alive=True,
                                       detail='root exited but owned descendants are still alive')
            return ExecutionResult(state='succeeded' if code == 0 else 'failed', exit_code=code,
                                   identity=receipt.identity, detail='process exited')
        if status == 'failed':
            return ExecutionResult(state='failed', error=receipt.error or 'The worker failed to start',
                                   identity=receipt.identity)
        if status == 'lost':
            return ExecutionResult(state='unknown', identity=receipt.identity,
                                   error='Process identity is no longer verifiable after a supervisor restart',
                                   detail='recovery_required')
        return ExecutionResult(state='unknown', error='No process status is available',
                               detail='recovery_required')

    @staticmethod
    def tree_alive(identity: ProcessIdentity | None) -> bool:
        if identity is None:
            return False
        import psutil
        try:
            root = psutil.Process(identity.pid)
            children = root.children(recursive=True)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            # A dead root can still leave reparented descendants; the receipt
            # records the tree only while stopping.  Without a live root we
            # conservatively say no owned tree remains.
            return False
        for child in children:
            try:
                if child.is_running() and child.status() != psutil.STATUS_ZOMBIE:
                    return True
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return False

    def reconcile(self, context: ExecutionContext) -> ExecutionResult:
        receipt = self._receipt(context)
        if receipt is None:
            return ExecutionResult(state='missing', detail='no receipt')
        if receipt.identity is None:
            return ExecutionResult(state='failed', error=receipt.error or 'No verifiable process identity',
                                   detail='no-identity')
        if identity_alive(receipt.identity):
            return ExecutionResult(state='running', identity=receipt.identity, tree_alive=True,
                                   detail='adopted')
        return ExecutionResult(state='dead', identity=receipt.identity, detail='identity dead')

    def write_resize(self, context: ExecutionContext, command) -> None:
        from .budget import write_command
        write_command(self.directory(context), command)

    def read_resize_ack(self, context: ExecutionContext):
        from .budget import read_ack
        return read_ack(self.directory(context))

    def cancel(self, context: ExecutionContext, *, timeout: float = 10.0) -> ExecutionResult:
        receipt = self.supervisor.stop(context.attempt_id, fence=context.fence, timeout=timeout)
        return ExecutionResult(state='cancelled', identity=receipt.identity,
                               tree_alive=not receipt.confirmed, detail=receipt.stop_method)


class LegacyServiceExecutor:
    """Adapter for an existing service and its sequential executor.

    Used in shadow mode only: it must never issue leases or launch while the
    legacy allocator remains authoritative.
    """
    capability = 'legacy-service'
    resizable = False

    def __init__(self, launch: Callable[[dict], dict], cancel: Callable[[str], dict],
                 details: Callable[[str], dict]):
        self._launch = launch
        self._cancel = cancel
        self._details = details

    def launch(self, context: ExecutionContext) -> ExecutionResult:
        raise SupervisorError('LegacyServiceExecutor is diagnostic-only in shadow mode',
                              code='capability_unavailable')

    def poll(self, context: ExecutionContext) -> ExecutionResult:
        value = self._details(context.attempt.get('external_id') or context.run['id'])
        return ExecutionResult(state={'complete': 'succeeded', 'failed': 'failed',
                                      'cancelled': 'cancelled'}.get(value.get('status'), 'running'),
                               detail=value.get('status', ''))

    def cancel(self, context: ExecutionContext, *, timeout: float = 10.0) -> ExecutionResult:
        self._cancel(context.attempt.get('external_id') or context.run['id'])
        return ExecutionResult(state='cancelled')

    def reconcile(self, context: ExecutionContext) -> ExecutionResult:
        return ExecutionResult(state='unknown', detail='legacy adapter cannot adopt workers')


class JobServiceExecutor:
    """Executor adapter that launches the existing scientific JobService.

    The coordinator owns the lease; this adapter never reserves capacity.  The
    JobService worker remains the single scientific implementation, including
    its Context, memory planner and emergency spill.
    """

    capability = 'legacy-job-service'
    resizable = False

    def __init__(self, service):
        self.service = service

    def _job_id(self, context: ExecutionContext) -> str:
        return str(context.run['id'])

    def _allocation(self, context: ExecutionContext):
        lease = context.lease
        if not lease:
            raise SupervisorError('The coordinator did not attach a lease to this launch',
                                  code='capability_unavailable')
        return lease['committed']

    def launch(self, context: ExecutionContext) -> ExecutionResult:
        committed = self._allocation(context)
        job_id = self._job_id(context)
        self.service._start_coordinated(job_id, context.attempt_id, committed)
        value = self.service.details(job_id)
        if value.get('status') == 'failed':
            return ExecutionResult(state='failed', identity=identity_for_job(self.service, job_id),
                                   error=value.get('error'))
        if value.get('status') == 'cancelled':
            return ExecutionResult(state='cancelled', identity=identity_for_job(self.service, job_id))
        return ExecutionResult(state='running',
                               identity=identity_for_job(self.service, job_id),
                               tree_alive=True)

    def poll(self, context: ExecutionContext) -> ExecutionResult:
        try:
            value = self.service.details(self._job_id(context))
        except (KeyError, ValueError) as exc:
            return ExecutionResult(state='unknown', error=str(exc), detail='job-record-unavailable')
        status = value.get('status')
        identity = identity_for_job(self.service, self._job_id(context))
        if value.get('tree_exited') is False and status in ('failed', 'cancelled', 'complete',
                                                            'recovery_required'):
            # Never acknowledge lease release for a worker tree that has not
            # been observed to exit.
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
        job_id = self._job_id(context)
        try:
            self.service._cancel_local(job_id, coordinated=True, timeout=timeout)
        except Exception as exc:  # noqa: BLE001 - coordinator records and keeps lease
            return ExecutionResult(state='cancelled', tree_alive=True,
                                   error=f'{type(exc).__name__}: {exc}')
        value = self.service.details(job_id)
        complete = bool(value.get('logs_complete'))
        return ExecutionResult(state='cancelled' if complete else 'running',
                               identity=identity_for_job(self.service, job_id),
                               tree_alive=not complete)

    def cancel_run(self, run_id: str) -> None:
        """Queued coordinated work has no attempt; make its public record terminal."""
        try:
            self.service._cancel_local(str(run_id), coordinated=True, timeout=5)
        except (KeyError, ValueError):
            pass

    def reconcile(self, context: ExecutionContext) -> ExecutionResult:
        try:
            value = self.service.details(self._job_id(context))
        except (KeyError, ValueError):
            return ExecutionResult(state='missing', detail='job-record-missing')
        status = value.get('status')
        identity = identity_for_job(self.service, self._job_id(context))
        if value.get('tree_exited') is False and status in ('failed', 'cancelled', 'complete',
                                                            'recovery_required'):
            return ExecutionResult(state='running', identity=identity, tree_alive=True,
                                   detail='recovery required: worker tree still alive')
        if status == 'queued' or status == 'preparing':
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


def identity_for_job(service, job_id: str):
    """Return the recorded worker identity without importing UI models."""
    try:
        value = service.require(job_id)
    except (KeyError, ValueError):
        return None
    return value.get('worker')
