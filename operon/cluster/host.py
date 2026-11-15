"""Host endpoint glue; existing pool/StateStore retain all resource authority."""
from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
import platform
import sys

from pydantic import Field

from operon.contracts.base import ContractError, ContractModel, canonical_json
from operon.contracts.plan_operations import PlanExecutionBinding
from operon.contracts.run_plan import RunPlan
from operon.engine.contracts import BusyError, IdempotencyConflictError, UnauthorizedError
from operon.engine.supervisor import preparation_rejection_proof
from .invocation import ConsumerIntent, InvocationDispatch

CAPABILITY = 'cluster.controller_fence.v1'


def _read_evidence(path):
    try:
        with path.open('rb') as stream:
            raw = stream.read(65537)
        value = json.loads(raw) if len(raw) <= 65536 else None
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def _process_identity(value):
    if not isinstance(value, dict):
        return None
    pid, created = value.get('pid'), value.get('created')
    if (type(pid) is not int or pid <= 0 or type(created) not in (int, float)
            or not math.isfinite(created) or created <= 0):
        return None
    if any(value.get(key) is not None and not isinstance(value[key], str) for key in ('boot_id', 'host')):
        return None
    return {'pid': pid, 'created': float(created), 'boot_id': value.get('boot_id'), 'host': value.get('host')}


def stopped_attempt_proof(invocation_root, attempt):
    """Read-only containment proof; callers separately validate current state/lease.

    A crash may precede persistence of attempt.process, so the owned durable
    launch receipt remains the identity authority. A present process identity
    must match too. Neither a PID observation nor a caller boolean is proof.
    """
    if not attempt or attempt['state'] not in ('succeeded', 'failed', 'cancelled'):
        return False
    directory = Path(invocation_root) / 'supervisor'
    launch = _read_evidence(directory / (attempt['id'] + '.launch.json'))
    if launch.get('outcome') == 'rejected_before_launch':
        return (attempt['state'] in ('failed', 'cancelled') and not attempt.get('process')
                and preparation_rejection_proof(launch, attempt_id=attempt['id'], fence=attempt['fence'])
                and not any(os.path.lexists(directory / (attempt['id'] + suffix)) for suffix in
                            ('.environment.json', '.containment.json', '.ready.json', '.start', '.tree-exit.json')))
    proof = _read_evidence(directory / (attempt['id'] + '.tree-exit.json'))
    if any(value.get('attempt_id') != attempt['id'] or type(value.get('fence')) is not int
           or value['fence'] != attempt['fence'] for value in (proof, launch)):
        return False
    if proof.get('tree_exited') is not True:
        return False
    process = attempt.get('process') or {}
    if proof.get('method') == 'never-spawned':
        return (attempt['state'] in ('failed', 'cancelled') and not process and not proof.get('identity')
                and launch.get('state') == 'failed' and launch.get('pid') is None and launch.get('created') is None)
    if proof.get('method') not in ('windows-job', 'linux-subreaper') or launch.get('state') not in ('exited', 'stopped'):
        return False
    identity = _process_identity(launch)
    return bool(identity and _process_identity(proof.get('identity')) == identity
                and (not process or _process_identity(process) == identity))


class HostControl(ContractModel):
    controller_id: str = Field(min_length=1, max_length=128)
    controller_epoch: int = Field(strict=True, ge=1)
    request_key: str = Field(min_length=1, max_length=512)
    command_id: str = Field(min_length=1, max_length=200)
    cluster_run_id: str = Field(min_length=1, max_length=200)
    cluster_unit_id: str = Field(min_length=1, max_length=200)
    cluster_attempt_id: str = Field(min_length=1, max_length=200)
    workspace: str = Field(min_length=1, max_length=2048)
    principal: str = Field(min_length=1, max_length=128)


class HostSubmit(HostControl):
    graph: dict


class HostPlanSubmit(HostControl):
    source_plan_id: str = Field(min_length=1, max_length=64)
    source_unit_id: str = Field(min_length=1, max_length=200)
    source_unit_digest: str = Field(pattern=r'^[a-f0-9]{64}$')
    plan: RunPlan
    binding: PlanExecutionBinding


class HostConsumerSubmit(HostControl):
    preparation: ConsumerIntent


class HostCancel(HostControl):
    host_run_id: str = Field(min_length=1, max_length=200)
    host_fence: int | None = Field(default=None, strict=True, ge=0)
    timeout_seconds: int = Field(default=10, strict=True, ge=1, le=30)


class HostControllerEndpoint:
    """Configured controller identity is bound to the existing authenticated token."""

    def __init__(self, pool, *, authenticated_controller_id):
        if not authenticated_controller_id or len(authenticated_controller_id) > 128:
            raise ValueError('A configured controller identity is required')
        self.pool, self.controller_id = pool, authenticated_controller_id

    @staticmethod
    def _envelope(request, *, invocation=False):
        result = {name: getattr(request, name) for name in ('request_key', 'command_id',
                'cluster_run_id', 'cluster_unit_id', 'cluster_attempt_id', 'workspace', 'principal')}
        if invocation:
            result['submission_kind'] = 'plan'
        return result

    def dispatch(self, method, params, *, graph_validator=None):
        models = {'cluster.submit': HostSubmit, 'cluster.lookup': HostControl,
                  'cluster.status': HostControl, 'cluster.cancel': HostCancel,
                  'cluster.plan.submit': HostPlanSubmit, 'cluster.plan.lookup': HostControl,
                  'cluster.plan.status': HostControl, 'cluster.plan.cancel': HostCancel}
        if method not in models:
            raise ValueError('Unknown cluster host operation')
        # Transport/session metadata has already been authenticated by the server.
        values = {key: value for key, value in params.items() if key not in ('_token', '_compact', 'session_id')}
        model = HostConsumerSubmit if method == 'cluster.plan.submit' and 'preparation' in values else models[method]
        request = model.model_validate(values)
        if request.controller_id != self.controller_id:
            raise UnauthorizedError('Controller identity is not authorized by this authenticated host endpoint')
        workspace = self.pool.resolve(request.workspace)
        principal = self.pool._authorize(workspace, request.principal)
        invocation = method.startswith('cluster.plan.')
        envelope = self._envelope(request, invocation=invocation)
        # Normalize aliases so they cannot change the meaning of a replay.
        envelope['workspace'] = str(workspace.root)
        store = self.pool.engine.store
        identity = dict(controller_id=self.controller_id, epoch=request.controller_epoch,
                        principal=principal, request_key=request.request_key)
        if method in ('cluster.submit', 'cluster.plan.submit'):
            consumer = isinstance(request, HostConsumerSubmit)
            if consumer:
                intent = request.preparation
                if (intent.source_unit_id != request.cluster_unit_id or intent.cluster_run_id != request.cluster_run_id
                        or intent.target_host_identity != self.pool.engine.spec.pool_id
                        or self.pool.resolve(intent.workspace).root != workspace.root):
                    raise IdempotencyConflictError('Consumer preparation differs from its owned run, workspace or host')
                payload = intent.identity_payload()
            elif invocation:
                prepared = InvocationDispatch(workspace=request.workspace, source_plan_id=request.source_plan_id,
                    source_unit_id=request.source_unit_id, source_unit_digest=request.source_unit_digest,
                    plan=request.plan, binding=request.binding)
                if prepared.source_unit_id != request.cluster_unit_id:
                    raise IdempotencyConflictError('Host invocation names another cluster unit')
                lineage = prepared.plan.execution_policy.get('cluster_projection', {})
                if lineage.get('prepared_binding') or lineage.get('materialized_inputs') or lineage.get('source_dependencies'):
                    raise ContractError('Dependent invocations must be prepared from owned producer receipts on this host',
                                        code='unverified_artifact_provenance')
                payload = prepared.model_dump(mode='json')
            else:
                if graph_validator is None:
                    raise ValueError('Host graph validator is required')
                graph = graph_validator(request.graph)
                payload = {'graph': request.graph}
            digest = hashlib.sha256(canonical_json({'envelope': envelope, 'payload': payload} if invocation
                else {'envelope': envelope, 'graph': request.graph}).encode()).hexdigest()
            created, record = store.claim_cluster_request(**identity, digest=digest, envelope=envelope)
            if created:
                # No StateStore lock spans graph preparation. The actual existing
                # claim_submission transaction rechecks this epoch before admission.
                with store.controller_guard(self.controller_id, request.controller_epoch):
                    try:
                        if invocation:
                            if consumer:
                                prepared = self._prepare_consumer(request, record, workspace, principal)
                            self.pool.submit_plan(workspace.root, prepared.plan.model_dump(mode='json'),
                                prepared.binding.model_dump(mode='json'), request_id=record['host_request_id'],
                                principal=principal, run_id=record['host_run_id'])
                        else:
                            self.pool.launch(workspace.root, graph, request_id=record['host_request_id'], principal=principal)
                    except BusyError:
                        # Graph preparation and plan admission raise BusyError
                        # before acceptance. Commit uncertainty has a distinct
                        # error; this guard also refuses rejection if a run exists.
                        store.reject_cluster_request(**identity)
                        record = store.cluster_request(**identity)
        else:
            record = store.cluster_request(**identity)
        machine = platform.machine().lower()
        response = {**envelope, 'host_identity': self.pool.engine.spec.pool_id,
                    'host_pool_epoch': self.pool.coordinator.epoch,
                    'capacity_domain': self.pool.engine.spec.capacity_domain,
                    'target': {'os': platform.system().lower(),
                               'arch': {'amd64': 'x86_64', 'arm64': 'aarch64'}.get(machine, machine),
                               'python_abi': f'{sys.implementation.name}-{sys.version_info.major}.{sys.version_info.minor}'}}
        if record is None:
            return {**response, 'found': False, 'state': 'recovery_required', 'phase': 'submission_unknown'}
        if record['envelope'] != envelope:
            raise IdempotencyConflictError('Cluster request envelope does not match its immutable owner')
        if method in ('cluster.cancel', 'cluster.plan.cancel'):
            if record['host_run_id'] != request.host_run_id:
                raise UnauthorizedError('Cancellation does not own this host run')
            with store.controller_guard(self.controller_id, request.controller_epoch,
                    run_id=request.host_run_id, host_fence=request.host_fence, cancel=True):
                if invocation:
                    self.pool.plan_cancel(workspace.root, request.host_run_id, principal=principal)
                else:
                    self.pool.cancel(workspace.root, request.host_run_id, principal=principal,
                                     reason='cluster controller cancellation', compact=True)
        return self._receipt(record, response, workspace, principal)

    def _prepare_consumer(self, request, record, workspace, principal):
        from .artifact_bindings import CommittedArtifactResolver
        from .prepared_bindings import SharedConsumerPreparer

        intent = request.preparation
        root = workspace.directory / 'invocations'
        resolver = CommittedArtifactResolver(self.pool.engine.store, invocation_root=root,
            workspace_root=workspace.root, workspace_id=workspace.engine.workspace_id,
            host_identity=self.pool.engine.spec.pool_id, authenticated_controller_id=self.controller_id,
            verify_stopped=lambda run, unit, attempt, lease: stopped_attempt_proof(root, attempt))
        # Current controller authority may observe producers accepted by an old
        # epoch. Producer attempt/fence/artifact ownership remains unchanged.
        producers = {edge: value.model_copy(update={'controller_epoch': request.controller_epoch})
                     for edge, value in intent.producers.items()}
        preparation = SharedConsumerPreparer(resolver, target_node_id=intent.target_node_id).prepare(
            intent.source_plan, cluster_run_id=request.cluster_run_id, consumer_unit_id=request.cluster_unit_id,
            binding=intent.binding, producers=producers, request_id=record['host_request_id'], principal=principal)
        return InvocationDispatch.model_validate(preparation.dispatch_payload())

    def _receipt(self, record, response, workspace, principal):
        store = self.pool.engine.store
        if record['state'] == 'rejected':
            return {**response, 'accepted': False, 'non_acceptance_proven': True,
                    'state': 'admitted', 'phase': 'admission_rejected'}
        if record['envelope'].get('submission_kind') == 'plan':
            return self._plan_receipt(record, response, workspace, principal)
        try:
            run = store.run(record['host_run_id'])
        except KeyError:
            return {**response, 'found': True, 'state': 'recovery_required', 'phase': 'submission_unknown'}
        if run['principal'] != principal or run['workspace_id'] != workspace.engine.workspace_id:
            raise UnauthorizedError('Durable host run has a different owner')
        attempts = store.attempts(record['host_run_id'])
        attempt = attempts[-1] if attempts else None
        lease = store.lease(attempt['id']) if attempt else None
        status = self.pool.run_status(workspace.root, record['host_run_id'], principal=principal)
        state = attempt['state'] if attempt else 'admitted'
        if not attempt and run['status'] in ('cancelled', 'failed'):
            state = run['status']
        never_admitted = attempt is None and state in ('cancelled', 'failed')
        return {**response, 'accepted': True, 'found': True, 'host_run_id': record['host_run_id'],
                'host_attempt_id': attempt['id'] if attempt else None,
                'host_fence': attempt['fence'] if attempt else None,
                'lease_id': lease['id'] if lease else None, 'state': state,
                'phase': 'never_admitted' if never_admitted else ('host_receipt' if attempt else 'queued'),
                'compute_complete': status.get('compute_complete') is True,
                'tree_exited': never_admitted or status.get('tree_exited') is True,
                'resources_released': never_admitted or status.get('resources_released') is True,
                'artifact_committed': status.get('artifact_committed') is True,
                'logs_complete': status.get('logs_complete') is True,
                'evidence_revision': str(attempt['revision'] if attempt else run['revision'])}

    def _plan_snapshot(self, run_id):
        """Caller holds store.lock; no filesystem work occurs in this snapshot."""
        store = self.pool.engine.store
        run = store.run(run_id)
        units = store.units(run_id)
        unit = units[0] if len(units) == 1 else None
        attempts = store.attempts(run_id)
        attempt = max(attempts, key=lambda value: (value['ordinal'], value['created_at'], value['id'])) if attempts else None
        lease = store.lease(attempt['id']) if attempt else None
        return {'run': run, 'unit': unit, 'attempt': attempt, 'lease': lease}

    @staticmethod
    def _snapshot_signature(snapshot):
        run, unit, attempt, lease = (snapshot[key] for key in ('run', 'unit', 'attempt', 'lease'))
        return (run['id'], run['revision'], run['status'], run['cancel_requested'],
                None if unit is None else (unit['id'], unit['state'], unit['attempts'], unit['updated_at']),
                None if attempt is None else (attempt['id'], attempt['revision'], attempt['fence'], attempt['state']),
                None if lease is None else (lease['id'], lease['revision'], lease['state']))

    @staticmethod
    def _plan_response(response, snapshot, *, state='recovery_required', phase='host_receipt', **flags):
        run, attempt, lease = (snapshot[key] for key in ('run', 'attempt', 'lease'))
        return {**response, 'accepted': True, 'found': True, 'host_run_id': run['id'],
                'host_unit_id': snapshot['unit']['id'] if snapshot['unit'] else None,
                'host_attempt_id': attempt['id'] if attempt else None,
                'host_fence': attempt['fence'] if attempt else None,
                'lease_id': lease['id'] if lease else None, 'state': state, 'phase': phase,
                'compute_complete': False, 'tree_exited': False, 'resources_released': False,
                'artifact_committed': False, 'logs_complete': False, **flags,
                'evidence_revision': str(attempt['revision'] if attempt else run['revision'])}

    def _plan_receipt(self, record, response, workspace, principal):
        store = self.pool.engine.store
        try:
            with store.lock:
                before = self._plan_snapshot(record['host_run_id'])
        except KeyError:
            return {**response, 'found': True, 'state': 'recovery_required', 'phase': 'submission_unknown'}
        run, unit, attempt = (before[key] for key in ('run', 'unit', 'attempt'))
        if run['principal'] != principal or run['workspace_id'] != workspace.engine.workspace_id:
            raise UnauthorizedError('Durable host run has a different owner')
        self.pool.plan_details(workspace.root, run['id'], principal=principal)
        stopped = stopped_attempt_proof(workspace.directory / 'invocations', attempt)
        # Receipt IO never holds the writer lock. Recheck all lifecycle metadata
        # after IO so an old attempt cannot certify a new/active retry as stopped.
        with store.lock:
            current = self._plan_snapshot(run['id'])
            if self._snapshot_signature(current) != self._snapshot_signature(before):
                return self._plan_response(response, current, phase='host_receipt_changed')
            if unit is None or (attempt and attempt['unit_id'] != unit['id']):
                return self._plan_response(response, current, phase='host_unit_mismatch')
            if attempt is None:
                never_admitted = (unit['attempts'] == 0 and run['status'] in ('failed', 'cancelled')
                                  and unit['state'] == run['status'])
                return self._plan_response(response, current,
                    state=run['status'] if never_admitted else 'admitted',
                    phase='never_admitted' if never_admitted else 'queued',
                    tree_exited=never_admitted, resources_released=never_admitted)
            terminal = attempt['state'] in ('succeeded', 'failed', 'cancelled')
            if not terminal:
                return self._plan_response(response, current, state=attempt['state'])
            expected_run = {'succeeded': 'complete', 'failed': 'failed', 'cancelled': 'cancelled'}[attempt['state']]
            if unit['state'] != attempt['state'] or run['status'] != expected_run:
                return self._plan_response(response, current, phase='host_run_active')
            lease = current['lease']
            released = bool(lease and lease['attempt_id'] == attempt['id'] and lease['state'] == 'released')
            if not stopped or not released or (attempt['state'] == 'succeeded' and attempt['exit_code'] != 0):
                return self._plan_response(response, current, phase='host_stop_unproven')
            receipt = attempt.get('receipt', {})
            artifact = store.artifact(receipt.get('artifact_id')) if receipt.get('artifact_id') else None
            committed = bool(artifact and artifact['state'] == 'committed' and receipt.get('state') == 'committed'
                and receipt.get('run_id') == run['id'] and receipt.get('unit_id') == unit['id']
                and receipt.get('attempt_id') == artifact['attempt_id'] == attempt['id']
                and receipt.get('fence') == artifact['fence'] == attempt['fence']
                and receipt.get('digest') == artifact['digest'] and receipt.get('location') == artifact['location'])
            state = attempt['state']
            if state == 'succeeded' and not committed:
                return self._plan_response(response, current, phase='host_artifact_unproven',
                    compute_complete=True, tree_exited=True, resources_released=True, logs_complete=True)
            return self._plan_response(response, current, state=state, compute_complete=True,
                tree_exited=True, resources_released=True, artifact_committed=state == 'succeeded' and committed,
                logs_complete=True, artifact=({'artifact_id': artifact['id'], 'digest': artifact['digest']}
                    if state == 'succeeded' and committed else None))
