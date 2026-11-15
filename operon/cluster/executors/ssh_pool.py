"""Host pool RPCs over a leased existing framed transport.

The lease factory can supply SSHConnection.call or a tunneled PoolClient.request.
It MUST lease a distinct connection for the duration, including lifecycle work.
"""
from __future__ import annotations

import json

from ..receipts import ClusterError, Observation
from ..invocation import ConsumerIntent, InvocationDispatch, CAPABILITY as INVOCATION_CAPABILITY, CONSUMER_CAPABILITY

CAPABILITY = 'cluster.controller_fence.v1'
_PLAN_FORMATS = ('operon.cluster-invocation-dispatch', 'operon.cluster-consumer-intent')


class SSHPoolExecutor:
    capability = CAPABILITY
    resizable = False
    poll_interval = 10.0

    def __init__(self, lease, *, controller_epoch, expected_host_identity):
        self.lease = lease
        self.controller_epoch = controller_epoch
        self.expected_host_identity = expected_host_identity

    def _params(self, dispatch):
        payload = dispatch.payload
        return {'controller_id': dispatch.controller_id, 'controller_epoch': self.controller_epoch(),
                'request_key': dispatch.request_key, 'command_id': dispatch.command_id,
                'cluster_run_id': dispatch.run_id, 'cluster_unit_id': dispatch.unit_id,
                'cluster_attempt_id': dispatch.attempt_id, 'workspace': payload['workspace'],
                'principal': dispatch.principal}

    def _call(self, dispatch, method, extra=None, *, lifecycle=False):
        params = {**self._params(dispatch), **(extra or {})}
        with self.lease(dispatch.node_id, 'lifecycle' if lifecycle else 'control') as connection:
            required = (CAPABILITY, INVOCATION_CAPABILITY) if method.startswith('cluster.plan.') else (CAPABILITY,)
            if dispatch.payload.get('format') == 'operon.cluster-consumer-intent':
                required += (CONSUMER_CAPABILITY,)
            for capability in required:
                supported = (connection.supports(capability) if hasattr(connection, 'supports')
                             else capability in getattr(connection, 'capabilities', ()))
                if not supported:
                    raise ClusterError('Host lacks the required fenced invocation capability',
                                       code='capability_unavailable')
            call = getattr(connection, 'call', None) or connection.request
            return call(method, params)

    def _observation(self, dispatch, value):
        if not isinstance(value, dict):
            raise ClusterError('Malformed host receipt', code='receipt_identity_mismatch')
        for key, expected in (('request_key', dispatch.request_key), ('command_id', dispatch.command_id),
                              ('cluster_attempt_id', dispatch.attempt_id),
                              ('host_identity', self.expected_host_identity(dispatch.node_id))):
            if value.get(key) != expected:
                raise ClusterError('Host receipt identity does not match dispatch',
                                   code='receipt_identity_mismatch', details={'field': key})
        evidence = json.dumps(value, sort_keys=True, allow_nan=False)
        if dispatch.payload.get('format') in _PLAN_FORMATS and value.get('submission_kind') != 'plan':
            raise ClusterError('Host receipt belongs to another submission namespace', code='receipt_identity_mismatch')
        if value.get('accepted') is False and value.get('non_acceptance_proven') is True:
            return Observation('admitted', 'admission_rejected', evidence_json=evidence,
                               admission_rejected=True, stop_confirmed=True)
        if value.get('found') is False:
            return Observation('recovery_required', 'submission_unknown', evidence_json=evidence)
        handle, fence = value.get('host_run_id'), value.get('host_fence')
        if (isinstance(handle, str) and handle and fence is None and value.get('host_attempt_id') is None
                and value.get('lease_id') is None and value.get('phase') in ('queued', 'never_admitted')):
            state = value.get('state', 'admitted')
            stopped = value.get('tree_exited') is True and value.get('resources_released') is True
            if state not in ('admitted', 'failed', 'cancelled') or (state != 'admitted' and not stopped):
                state = 'recovery_required'
            return Observation(state, value['phase'], handle, None, evidence, stop_confirmed=stopped)
        if not isinstance(handle, str) or not handle or type(fence) is not int or fence < 0:
            raise ClusterError('Accepted host receipt is missing run identity/fence', code='receipt_identity_mismatch')
        if not value.get('host_attempt_id') or not value.get('lease_id'):
            raise ClusterError('Host admission receipt is incomplete', code='receipt_identity_mismatch')
        state = value.get('state', 'recovery_required')
        if state not in ('admitted', 'starting', 'running', 'committing', 'succeeded', 'failed', 'cancelled', 'recovery_required'):
            state = 'recovery_required'
        stop = value.get('tree_exited') is True and value.get('resources_released') is True
        if state in ('succeeded', 'failed', 'cancelled') and not stop:
            state = 'recovery_required'
        if state == 'succeeded' and value.get('artifact_committed') is not True:
            state = 'committing'
        return Observation(state, value.get('phase', 'host_receipt'), handle, fence, evidence, stop_confirmed=stop)

    def launch(self, dispatch):
        # Called exactly once after claim_dispatch commits. Exceptions are unknown.
        try:
            if dispatch.payload.get('format') == 'operon.cluster-consumer-intent':
                prepared = ConsumerIntent.model_validate(dispatch.payload)
                if (prepared.cluster_run_id != dispatch.run_id or prepared.target_node_id != dispatch.node_id
                        or prepared.target_host_identity != self.expected_host_identity(dispatch.node_id)):
                    raise ValueError('Prepared consumer intent differs from its owned run or host')
                extra = {'preparation': prepared.model_dump(mode='json')}
            else:
                prepared = InvocationDispatch.model_validate(dispatch.payload)
                extra = prepared.model_dump(mode='json', exclude={'format', 'schema_version', 'workspace'})
            if prepared.source_unit_id != dispatch.unit_id:
                raise ValueError('Prepared invocation names another cluster unit')
            return self._observation(dispatch, self._call(dispatch, 'cluster.plan.submit', extra))
        except Exception as exc:
            return Observation('recovery_required', 'submission_unknown',
                               evidence_json=json.dumps({'error': type(exc).__name__,
                                                         'code': getattr(exc, 'code', 'remote_unavailable')}))

    def reconcile(self, dispatch):
        try:
            method = 'cluster.plan.lookup' if dispatch.payload.get('format') in _PLAN_FORMATS else 'cluster.lookup'
            return self._observation(dispatch, self._call(dispatch, method, lifecycle=True))
        except Exception as exc:
            return Observation('recovery_required', 'reconciliation_unavailable', dispatch.external_handle,
                               dispatch.host_fence, json.dumps({'error': type(exc).__name__}))

    def poll(self, dispatch):
        return self.reconcile(dispatch)

    def cancel(self, dispatch, *, timeout=10.0):
        if not dispatch.external_handle:
            return Observation('recovery_required', 'cancel_requires_owned_receipt')
        try:
            method = 'cluster.plan.cancel' if dispatch.payload.get('format') in _PLAN_FORMATS else 'cluster.cancel'
            return self._observation(dispatch, self._call(dispatch, method,
                {'host_run_id': dispatch.external_handle, 'host_fence': dispatch.host_fence,
                 'timeout_seconds': max(1, min(int(timeout), 30))}, lifecycle=True))
        except Exception as exc:
            return Observation('recovery_required', 'cancellation_unconfirmed', dispatch.external_handle,
                               dispatch.host_fence, json.dumps({'error': type(exc).__name__}))
