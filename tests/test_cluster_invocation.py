"""Invocation projection and real host-journal fixtures, not two-host E2E."""
import hashlib
import json
from types import SimpleNamespace

import pytest

from operon.cluster.invocation import InvocationDispatch, InvocationTemplate, project_unit
from operon.contracts.base import ContractError, sha256_hex
from operon.contracts.run_plan import RunPlan
from operon.pool_service import PoolClient, PoolClientError, PoolControlServer
from test_pool_service import pool


def source_plan(*, inputs=None, dependent=False):
    unit = {'unit_id': 'unit', 'node_ids': ['unit'], 'invocation': {
        'kind': 'command', 'argv': ['fixture-only'], 'code_ref': {'kind': 'file', 'ref': 'tool'},
        'parameters_ref': {'kind': 'none'}, 'environment_ref': 'runtime'},
        'input_bindings': inputs or {}, 'output_contracts': [{'name': 'result', 'representation': 'json'}],
        'resource_request': {'process_reservation_bytes': 1024, 'cpu_threads': 1},
        'placement': {'executor': 'ssh', 'target': {'os': 'linux', 'arch': 'x86_64'}}}
    units = [unit]
    if dependent:
        units = [{**unit, 'unit_id': 'parent', 'node_ids': ['parent'], 'input_bindings': {}}, unit]
    return RunPlan.model_validate({'plan_id': 'pending', 'workflow_revision': 'a' * 64,
        'parameters_digest': 'b' * 64, 'compiler_version': 'cluster-fixture', 'units': units,
        'execution_policy': {'environment_refs': {'runtime': 'c' * 64}}}).with_identity()


def binding(*, inputs=None):
    return {'package_root': 'package', 'environment_store': 'environments',
            'environments': {'runtime': {'generation_id': 'generation', 'executable': 'bin/tool'}},
            'storage': {}, 'inputs': inputs or {}}


def prepared_payload(workspace='/test'):
    return project_unit(source_plan(), unit_id='unit', workspace=workspace, binding=binding()).model_dump(mode='json')


def test_projection_is_deterministic_and_preserves_immutable_invocation_and_external_input():
    reference = {'representation': 'json', 'path': 'data/input.json', 'size_bytes': 2,
                 'sha256': hashlib.sha256(b'{}').hexdigest(), 'metadata': {}}
    source = source_plan(inputs={'data': 'input:data'})
    kwargs = dict(unit_id='unit', workspace='/work', binding=binding(inputs={'data': reference}))
    first, second = project_unit(source, **kwargs), project_unit(source, **kwargs)
    assert first == second and first.plan.plan_id != source.plan_id
    assert source.units[0].placement.executor == 'ssh'
    assert first.plan.units[0].placement.executor == 'local'
    assert first.plan.units[0].invocation == source.units[0].invocation
    assert first.plan.units[0].resource_request == source.units[0].resource_request
    assert first.plan.units[0].output_contracts == source.units[0].output_contracts
    assert first.binding.inputs['data'].sha256 == reference['sha256']
    assert first.source_unit_digest == sha256_hex(source.units[0])
    assert first.source_plan_id == source.plan_id and first.source_unit_id == 'unit'


def test_cross_unit_artifacts_cannot_be_replaced_by_static_expected_hashes():
    source = source_plan(inputs={'data': 'artifact:parent/result'}, dependent=True)
    with pytest.raises(ContractError) as missing:
        project_unit(source, unit_id='unit', workspace='/work', binding=binding())
    assert missing.value.code == 'unresolved_artifact_input'
    reference = {'representation': 'json', 'path': 'staged/result.json', 'size_bytes': 2,
                 'sha256': hashlib.sha256(b'{}').hexdigest(), 'metadata': {}}
    with pytest.raises(ContractError) as unverified:
        project_unit(source, unit_id='unit', workspace='/work', binding=binding(),
                     materialized_inputs={'artifact:parent/result': reference})
    assert unverified.value.code == 'unverified_artifact_provenance'


def test_typed_dispatch_rejects_legacy_graph_and_unresolved_artifact_input():
    with pytest.raises(ValueError):
        InvocationDispatch.model_validate({'workspace': '/work', 'graph': {}})
    payload = prepared_payload()
    raw = payload['plan']
    raw['units'][0]['input_bindings'] = {'data': 'artifact:parent/result'}
    payload['plan'] = RunPlan.model_validate(raw).with_identity().model_dump(mode='json')
    with pytest.raises(ValueError):
        InvocationDispatch.model_validate(payload)


def test_projected_host_retry_policy_is_rejected_without_rewriting():
    raw = source_plan().model_dump(mode='json')
    raw['units'][0]['retry_policy']['maximum_attempts'] = 2
    source = RunPlan.model_validate(raw).with_identity()
    with pytest.raises(ContractError) as failure:
        project_unit(source, unit_id='unit', workspace='/work', binding=binding())
    assert failure.value.code == 'unsupported_retry_policy'
    assert source.units[0].retry_policy.maximum_attempts == 2
    payload = prepared_payload()
    payload['plan']['units'][0]['retry_policy']['maximum_attempts'] = 2
    payload['plan'] = RunPlan.model_validate(payload['plan']).with_identity().model_dump(mode='json')
    with pytest.raises(ValueError, match='single host attempt'):
        InvocationDispatch.model_validate(payload)


def test_real_host_request_uses_stable_plan_id_and_no_graph_fallback(pool, monkeypatch):
    service, _, workspace, _ = pool
    # This is a durable admission fixture. Stop the scheduler, and stub only
    # generation metadata; no scientific worker or containment gate is claimed.
    service.coordinator.stop()
    monkeypatch.setattr('operon.environment_store.EnvironmentStore',
                        lambda *a, **kw: SimpleNamespace(binding=lambda _: SimpleNamespace(requirement_digest='c' * 64)))
    original = service.submit_plan
    calls = []
    def record(*args, **kwargs):
        calls.append(kwargs)
        return original(*args, **kwargs)
    monkeypatch.setattr(service, 'submit_plan', record)
    monkeypatch.setattr(service, 'launch', lambda *a, **k: pytest.fail('Invocation must never launch a legacy graph'))
    server = PoolControlServer(service, token='cluster-plan', controller_id='configured').start()
    client = PoolClient(server.address, 'cluster-plan', capabilities=server.capabilities())
    from test_cluster_host import envelope
    control = envelope(workspace, cluster_unit_id='unit')
    payload = prepared_payload(str(workspace))
    extra = {key: value for key, value in payload.items() if key not in ('workspace', 'format', 'schema_version')}
    try:
        assert 'cluster.invocation.v1' in server.capabilities()
        first = client.request('cluster.plan.submit', {**control, **extra})
        # Model a discarded response by looking up only the original stable key.
        found = client.request('cluster.plan.lookup', control)
        again = client.request('cluster.plan.submit', {**control, **extra})
        assert first['host_run_id'] == found['host_run_id'] == again['host_run_id']
        assert len(calls) == 1 and calls[0]['run_id'] == first['host_run_id']
        assert first['submission_kind'] == found['submission_kind'] == 'plan'
        saved = service.engine.store.cluster_request(controller_id='configured', epoch=4,
            principal='alice', request_key=control['request_key'])
        assert saved['envelope']['submission_kind'] == 'plan'
        claimed = service.engine.store.request('alice', 'plan:' + saved['host_request_id'])
        assert claimed['run_id'] == saved['host_run_id'] == first['host_run_id']
        assert service.engine.store.run(first['host_run_id'])['plan']['execution']['invocation_binding'] == binding()
        with pytest.raises(PoolClientError) as namespace:
            client.request('cluster.lookup', control)
        assert namespace.value.code == 'idempotency_conflict'
        with pytest.raises(Exception) as conflict:
            original(workspace, payload['plan'], payload['binding'], request_id='different-key',
                     principal='alice', run_id=first['host_run_id'])
        assert conflict.value.code == 'idempotency_conflict'
        client.request('cluster.plan.cancel', {**control, 'host_run_id': first['host_run_id'], 'host_fence': None})
    finally:
        server.close()
