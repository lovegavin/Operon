"""Adapter fault fixtures; these do NOT establish two-host K09 acceptance."""
from contextlib import contextmanager
from dataclasses import replace
import json

from operon.cluster.executors.ssh_pool import CAPABILITY, SSHPoolExecutor
from operon.cluster.invocation import CAPABILITY as INVOCATION_CAPABILITY
from operon.cluster.receipts import Dispatch
from test_cluster_invocation import prepared_payload


def dispatch():
    return Dispatch('command', 'attempt', 'run', 'unit', 'host1', 'ssh', 'operon-key',
                    'alice', 'controller', 4, json.dumps(prepared_payload()))


class Host:
    def __init__(self): self.calls = []
    def supports(self, capability): return capability in (CAPABILITY, INVOCATION_CAPABILITY)
    def call(self, method, params):
        self.calls.append((method, params))
        if method == 'cluster.plan.submit': raise TimeoutError('Reply lost after acceptance')
        return {'submission_kind': 'plan', 'request_key': params['request_key'], 'command_id': params['command_id'],
                'cluster_attempt_id': params['cluster_attempt_id'], 'host_identity': 'pool-physical1',
                'host_run_id': 'host-run', 'host_attempt_id': 'host-attempt', 'lease_id': 'lease',
                'host_fence': 71, 'state': 'running'}


def test_lost_reply_looks_up_same_key_on_same_host_without_resubmit():
    host, leases = Host(), []
    @contextmanager
    def lease(node_id, lane):
        leases.append((node_id, lane))
        yield host
    executor = SSHPoolExecutor(lease, controller_epoch=lambda: 5, expected_host_identity=lambda _: 'pool-physical1')
    attempt = dispatch()
    assert executor.launch(attempt).state == 'recovery_required'
    result = executor.reconcile(attempt)
    assert result.state == 'running' and result.host_fence == 71
    assert [item[0] for item in host.calls] == ['cluster.plan.submit', 'cluster.plan.lookup']
    assert {item[1]['request_key'] for item in host.calls} == {'operon-key'}
    assert {item[1]['controller_epoch'] for item in host.calls} == {5}
    assert {item[0] for item in leases} == {'host1'}
    assert leases[-1][1] == 'lifecycle'


def test_missing_capability_fails_closed_without_legacy_launch():
    host = Host()
    host.supports = lambda capability: capability == CAPABILITY
    @contextmanager
    def lease(*_): yield host
    executor = SSHPoolExecutor(lease, controller_epoch=lambda: 4, expected_host_identity=lambda _: 'pool-physical1')
    result = executor.launch(dispatch())
    assert result.state == 'recovery_required' and not host.calls


def test_legacy_graph_is_never_launched_by_new_ssh_adapter():
    host = Host()
    @contextmanager
    def lease(*_): yield host
    executor = SSHPoolExecutor(lease, controller_epoch=lambda: 4, expected_host_identity=lambda _: 'pool-physical1')
    legacy = replace(dispatch(), payload_json=json.dumps({'workspace': '/test', 'graph': {}}))
    assert executor.launch(legacy).state == 'recovery_required'
    assert host.calls == []


def test_cancel_without_owned_receipt_never_sends_remote_command():
    host = Host()
    @contextmanager
    def lease(*_): yield host
    executor = SSHPoolExecutor(lease, controller_epoch=lambda: 4, expected_host_identity=lambda _: 'pool-physical1')
    assert executor.cancel(dispatch()).phase == 'cancel_requires_owned_receipt'
    assert not host.calls


def test_receipt_from_other_physical_pool_is_not_adopted():
    host = Host()
    @contextmanager
    def lease(*_): yield host
    executor = SSHPoolExecutor(lease, controller_epoch=lambda: 4, expected_host_identity=lambda _: 'different-pool')
    assert executor.reconcile(dispatch()).state == 'recovery_required'
