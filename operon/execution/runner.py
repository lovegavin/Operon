"""RunPlan facade over the existing durable task and host-admission service.

This module must never spawn a scientific process. The pool/JobService owns
admission, environment exclusion, process trees, cancellation and recovery.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json
import re
import time
import uuid

from operon.contracts.base import ContractError
from operon.contracts.run_plan import RunPlan
from operon.planning.validation import validate_run_plan
from .adapters.native import NativeInvocationAdapter
from .invocation import ExitReceipt, InvocationContext, PreparedInvocation


@dataclass(frozen=True)
class RunReceipt:
    run_id: str
    unit_id: str
    attempt_id: str
    status: str
    exit_code: int | None
    output_dir: str
    output_manifest: str | None
    receipt_path: str
    log_path: str
    error: str | None = None
    fence: int = 0
    job_id: str | None = None
    tree_exited: bool = False
    resources_released: bool = False

    def to_json(self):
        return self.__dict__.copy()


def safe_id(value):
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,159}', value):
        raise ContractError('Run/attempt identifier must be a safe nonempty name', code='invalid_run_id')
    return value


class InvocationRunner:
    def __init__(self, root, *, application=None):
        self.root = Path(root).resolve()
        self.application = application

    def _unit(self, plan, unit_id=None):
        plan = RunPlan.model_validate(plan.model_dump(mode='json') if isinstance(plan, RunPlan) else plan)
        validate_run_plan(plan)
        if len(plan.units) != 1 or (unit_id is not None and plan.units[0].unit_id != unit_id):
            raise ContractError('K02 supports one native chain unit', code='unsupported_boundary')
        unit = plan.units[0]
        if unit.invocation.kind != 'native' or unit.placement.executor != 'local':
            raise ContractError('This adapter supports local native units only', code='unsupported_boundary')
        return plan, unit

    def prepare(self, plan, *, run_id, attempt_id='attempt-1', unit_id=None, fence=1, inputs=None):
        """File-only preparation for adapter verification; never grants resources."""
        plan, unit = self._unit(plan, unit_id)
        safe_id(run_id); safe_id(attempt_id); safe_id(unit.unit_id)
        if inputs:
            raise ContractError('Recompile changed input bindings before execution', code='recompile_required')
        attempt_root = self.root / 'runs' / run_id / 'nodes' / unit.unit_id / 'attempts' / attempt_id
        attempt_root.mkdir(parents=True, exist_ok=True)
        context = InvocationContext(attempt_root=attempt_root, run_id=run_id,
            attempt_id=attempt_id, unit_id=unit.unit_id, fence=fence,
            payload=unit.model_dump(mode='json')['payload'],
            memory_bytes=unit.resource_request.managed_budget_bytes,
            threads=unit.resource_request.cpu_threads)
        return unit, NativeInvocationAdapter().prepare(unit.invocation, context)

    def execute(self, plan, *, run_id=None, unit_id=None, inputs=None,
                timeout=1800.0, poll_seconds=0.1, stop_timeout=30.0):
        app = self.application
        if app is None:
            raise ContractError('An authoritative application/host pool is required; no direct launch fallback',
                                code='admission_required')
        plan, unit = self._unit(plan, unit_id)
        if inputs:
            raise ContractError('Recompile changed input bindings before execution', code='recompile_required')
        if timeout <= 0 or poll_seconds <= 0 or stop_timeout <= 0:
            raise ContractError('Timeouts and poll interval must be positive', code='invalid_timeout')
        run_id = safe_id(run_id or uuid.uuid4().hex)
        graph = unit.model_dump(mode='json')['payload']['graph']
        from operon.planning.graph_models import Graph
        from operon.planning.source_paths import remote_profile
        parsed = Graph.model_validate(graph)
        if remote_profile(parsed) or app.executions.applies(parsed):
            raise ContractError('Remote/staged RunPlan execution is not implemented in K02', code='unsupported_boundary')
        # A digest is integrity, not authority. Recompile with the selected live
        # catalog before accepting executable payload supplied by a caller.
        current = app.compile_plan(graph, require_files=True)
        if current.plan_id != plan.plan_id:
            raise ContractError('The frozen plan no longer matches the selected catalog/graph; recompile',
                                code='stale_plan_identity')
        graph.setdefault('runtime', {})['native_invocation'] = {
            'abi': 1, 'plan_id': plan.plan_id, 'implementations': plan.model_dump(mode='json')['implementations']}
        request_id = 'run-plan:' + run_id
        job = app.jobs.submit({'request_id': request_id, 'graph': graph})
        key = job['id']
        self.root.mkdir(parents=True, exist_ok=True)
        from operon.engine.fs import atomic_json
        from operon.bytecode import io_path
        receipt_path = io_path(self.root / (run_id + '.json'))
        atomic_json(receipt_path, {'format': 'operon.run-receipt', 'schema_version': 1,
                                  'plan_id': plan.plan_id, 'request_id': request_id,
                                  'receipt': {'status': job['status'], 'job_id': key}})
        deadline = time.monotonic() + timeout
        stop_deadline = None
        try:
            while True:
                job = app.jobs.details(key)
                lifecycle = job.get('lifecycle') or {}
                if lifecycle:
                    job = {**job, **{field: lifecycle[field] for field in
                           ('tree_exited', 'resources_released', 'artifact_committed') if field in lifecycle}}
                if job.get('logs_complete') and job['status'] in ('complete', 'failed', 'cancelled'):
                    if not job.get('coordinator_attempt') or job.get('resources_released'):
                        break
                if job['status'] == 'recovery_required':
                    break
                if time.monotonic() >= deadline and stop_deadline is None:
                    app.jobs.cancel(key)
                    stop_deadline = time.monotonic() + stop_timeout
                if stop_deadline is not None and time.monotonic() >= stop_deadline:
                    job = {**job, 'status': 'recovery_required',
                           'error': 'Cancellation is not confirmed; ownership and leases remain with the pool'}
                    break
                time.sleep(poll_seconds)
        except BaseException:
            # A disconnected/failed observer does not own the accepted job.
            # Its durable submission receipt allows later query/cancellation.
            raise
        directory = app.service.jobs_dir / key
        output_dir = Path(job.get('output_dir') or directory / 'output')
        status = {'complete': 'succeeded'}.get(job['status'], job['status'])
        error = job.get('error')
        if status == 'succeeded' and job.get('coordinator_attempt') and not job.get('artifact_committed'):
            status, error = 'failed', 'The authoritative pool did not commit the outputs'
        if status == 'succeeded':
            prepared = PreparedInvocation(unit.invocation,
                InvocationContext(directory, key, key, unit.unit_id, 0, {}),
                directory, directory / 'task.yaml', output_dir, (), {})
            result = NativeInvocationAdapter().collect(prepared, ExitReceipt(
                job.get('exit_code'), 'succeeded', not job.get('tree_exited', False)))
            if result.status != 'complete':
                status, error = 'failed', result.error
        if status in ('succeeded', 'cancelled') and not job.get('tree_exited'):
            status = 'recovery_required'
            error = 'Process-tree exit has not been confirmed by the authoritative service'
        receipt = RunReceipt(run_id, unit.unit_id, str(job.get('coordinator_attempt') or key),
            status, job.get('exit_code'), str(output_dir),
            str(directory / unit.invocation.output_manifest) if (directory / unit.invocation.output_manifest).is_file() else None,
            str(receipt_path), str(directory / 'console.log'), error,
            fence=int(job.get('coordinator_fence') or 0),
            job_id=key, tree_exited=bool(job.get('tree_exited')),
            resources_released=bool(job.get('resources_released')))
        atomic_json(receipt_path, {'format': 'operon.run-receipt', 'schema_version': 1,
                                  'plan_id': plan.plan_id, 'request_id': request_id,
                                  'receipt': receipt.to_json()})
        return receipt
