"""Same-host control wiring fixtures; synthetic receipts are not remote E2E."""
from contextlib import contextmanager
from dataclasses import replace
import json
from types import SimpleNamespace

import pytest

from operon.cluster.executors.ssh_pool import CAPABILITY, SSHPoolExecutor
from operon.cluster.invocation import (CAPABILITY as INVOCATION_CAPABILITY, CONSUMER_CAPABILITY,
    ConsumerIntent, ConsumerTemplate, consumer_intent)
from operon.cluster.receipts import Dispatch
from operon.cluster.scheduler import ClusterController
from operon.cluster.host import HostControllerEndpoint
from operon.cluster.invocation import project_unit
from operon.contracts.base import ContractError, sha256_hex
from operon.contracts.run_plan import RunPlan
from test_cluster_invocation import binding, source_plan
from test_cluster_artifact_bindings import producer


def template(*, workspace='/work/alice', host='host-pool', node='node'):
    raw = source_plan(inputs={'data': 'artifact:parent/result'}, dependent=True).model_dump(mode='json')
    raw['edges'] = [{'source': 'parent', 'target': 'unit', 'source_handle': 'result', 'target_handle': 'data'}]
    source = RunPlan.model_validate(raw).with_identity()
    return ConsumerTemplate(workspace=workspace, source_plan=source, source_unit_id='unit', binding=binding(),
                            target_node_id=node, target_host_identity=host)


def producer_row(value=None):
    value = value or template()
    result = {'principal': 'alice', 'run_id': 'cluster-run', 'plan_id': value.source_plan.plan_id,
        'unit_id': 'parent', 'spec': value.source_plan.units[0].model_dump(mode='json'),
        'controller_id': 'controller', 'node_id': value.target_node_id, 'executor': 'ssh',
        'request_key': 'producer-key', 'command_id': 'producer-command', 'attempt_id': 'producer-attempt',
        'external_handle': 'host-run', 'host_fence': 17, 'state': 'succeeded', 'unit_state': 'succeeded'}
    result['evidence'] = {'principal': 'alice', 'request_key': 'producer-key', 'command_id': 'producer-command',
        'cluster_run_id': 'cluster-run', 'cluster_unit_id': 'parent', 'cluster_attempt_id': 'producer-attempt',
        'host_identity': value.target_host_identity, 'host_run_id': 'host-run', 'host_unit_id': 'host-unit',
        'host_attempt_id': 'host-attempt', 'host_fence': 17, 'submission_kind': 'plan', 'state': 'succeeded',
        'tree_exited': True, 'resources_released': True, 'artifact_committed': True,
        'artifact': {'artifact_id': 'artifact', 'digest': 'd' * 64}}
    return result


def intent(value=None, rows=None, *, epoch=7):
    value = value or template()
    return consumer_intent(value, [producer_row(value)] if rows is None else rows,
        principal='alice', cluster_run_id='cluster-run', controller_id='controller', controller_epoch=epoch)


def test_intent_contains_owned_producer_identities_and_no_materialized_paths():
    prepared = intent()
    producer = prepared.producers['artifact:parent/result']
    assert producer.cluster_run_id == prepared.cluster_run_id
    assert producer.host_attempt_id == 'host-attempt' and producer.host_fence == 17
    assert producer.artifact_id == 'artifact' and producer.output_port == 'result'
    assert prepared.binding.inputs == {} and prepared.materialized_inputs == {}
    assert 'path' not in type(producer).model_fields
    assert intent(epoch=8).identity_payload() == prepared.identity_payload()


@pytest.mark.parametrize('field,value,code', [
    ('node_id', 'other-host', 'cross_host_artifact_unavailable'),
    ('executor', 'slurm', 'cross_host_artifact_unavailable'),
    ('run_id', 'other-run', 'unverified_artifact_provenance'),
    ('principal', 'bob', 'unverified_artifact_provenance'),
    ('plan_id', 'e' * 64, 'unverified_artifact_provenance'),
    ('controller_id', 'other-controller', 'unverified_artifact_provenance'),
    ('unit_state', 'running', 'producer_not_committed'),
])
def test_consumer_rejects_cross_host_or_other_run_receipts(field, value, code):
    row = producer_row()
    row[field] = value
    with pytest.raises(ContractError) as failure:
        intent(rows=[row])
    assert failure.value.code == code


@pytest.mark.parametrize('field,value', [
    ('host_identity', 'different-pool'), ('host_fence', 18), ('tree_exited', False),
    ('resources_released', False), ('artifact_committed', False), ('state', 'running'),
    ('cluster_attempt_id', 'other-attempt'),
])
def test_consumer_requires_current_complete_host_receipt(field, value):
    row = producer_row()
    row['evidence'][field] = value
    with pytest.raises(ContractError) as failure:
        intent(rows=[row])
    assert failure.value.code == 'producer_not_committed'


def test_consumer_cannot_substitute_another_named_port_or_static_input():
    raw = intent().model_dump(mode='json')
    raw['producers']['artifact:parent/result']['output_port'] = 'other'
    with pytest.raises(ValueError, match='frozen port'):
        ConsumerIntent.model_validate(raw)
    raw = template().model_dump(mode='json')
    raw['materialized_inputs'] = {'artifact:parent/result': {'representation': 'json',
        'path': 'client-local/value.json', 'size_bytes': 2, 'sha256': 'a' * 64}}
    with pytest.raises(ValueError, match='Static paths'):
        ConsumerTemplate.model_validate(raw)


def test_missing_or_ambiguous_producers_never_prepare_dispatch():
    for rows in ([], [producer_row(), producer_row()]):
        with pytest.raises(ContractError) as failure:
            intent(rows=rows)
        assert failure.value.code == 'producer_not_committed'


def test_scheduler_enriches_after_ranking_without_remote_work():
    value, calls = template(), []
    repository = SimpleNamespace(producer_receipts=lambda *args: calls.append(args) or [producer_row(value)])
    controller = ClusterController.__new__(ClusterController)
    controller.repository, controller.leadership = repository, SimpleNamespace(epoch=7)
    controller._db = lambda function, *args, **kwargs: function(*args, **kwargs)
    args = {'run_id': 'cluster-run', 'unit_id': 'unit', 'node_id': 'node', 'controller_id': 'controller',
            'payload': value.model_dump(mode='json'), 'binding_id': 'env-binding'}
    ready = [{'run_id': 'cluster-run', 'unit_id': 'unit', 'principal': 'alice', 'plan_id': value.source_plan.plan_id}]
    enriched = controller._prepared_arguments(args, ready)
    assert args['payload']['format'] == 'operon.cluster-consumer-template'
    assert enriched['payload']['format'] == 'operon.cluster-consumer-intent'
    assert enriched['binding_id'] == 'env-binding'
    assert calls == [('alice', 'cluster-run', {'parent'})]


def test_unsupported_consumer_does_not_starve_other_pending_dispatches():
    controller = ClusterController.__new__(ClusterController)
    claimed, launched = [], []
    pending = SimpleNamespace(command_id='good-command')
    controller.leadership = SimpleNamespace(epoch=7, assert_current=lambda **kw: None)
    controller._pending, controller._next_poll, controller._recovery = {}, {}, False
    controller._collect = lambda: None
    controller._db = lambda function, *args, **kwargs: function(*args, **kwargs)
    controller.repository = SimpleNamespace(cancellations=lambda: (), ready=lambda: [], nodes=lambda: [],
        dispatches=lambda **kw: [pending] if kw.get('pending') else (),
        prepare_dispatch=lambda **kw: claimed.append(kw), claim_dispatch=lambda *a, **kw: pending)
    bad, good = ({'run_id': 'run', 'unit_id': unit, 'payload': {}} for unit in ('bad', 'good'))
    controller.planner = lambda *_: [bad, good]
    def prepare(arguments, ready):
        if arguments['unit_id'] == 'bad':
            raise ContractError('Transfer is unsupported', code='cross_host_artifact_unavailable')
        return arguments
    controller._prepared_arguments = prepare
    controller._launch = lambda dispatch, operation: launched.append((dispatch, operation))
    controller.step()
    assert [value['unit_id'] for value in claimed] == ['good']
    assert launched == [(pending, 'launch')]
    assert controller.preparation_errors[('run', 'bad')]['code'] == 'cross_host_artifact_unavailable'


def consumer_dispatch():
    return Dispatch('consumer-command', 'consumer-attempt', 'cluster-run', 'unit', 'node', 'ssh',
        'consumer-key', 'alice', 'controller', 7, json.dumps(intent().model_dump(mode='json')))


class ConsumerHost:
    def __init__(self): self.calls = []
    def supports(self, capability): return capability in (CAPABILITY, INVOCATION_CAPABILITY, CONSUMER_CAPABILITY)
    def call(self, method, params):
        self.calls.append((method, params))
        if method == 'cluster.plan.submit':
            assert 'preparation' in params and 'plan' not in params and 'graph' not in params
            raise TimeoutError('Reply dropped after host acceptance')
        return {'submission_kind': 'plan', 'request_key': params['request_key'], 'command_id': params['command_id'],
            'cluster_attempt_id': params['cluster_attempt_id'], 'host_identity': 'host-pool',
            'host_run_id': 'consumer-host-run', 'host_attempt_id': 'consumer-host-attempt', 'lease_id': 'lease',
            'host_fence': 81, 'state': 'running'}


def test_consumer_lost_response_lookup_and_cancel_keep_one_host_key():
    host, leases = ConsumerHost(), []
    @contextmanager
    def lease(node_id, lane):
        leases.append((node_id, lane))
        yield host
    executor = SSHPoolExecutor(lease, controller_epoch=lambda: 8, expected_host_identity=lambda _: 'host-pool')
    dispatch = consumer_dispatch()
    assert executor.launch(dispatch).state == 'recovery_required'
    observed = executor.reconcile(dispatch)
    assert observed.state == 'running'
    owned = replace(dispatch, external_handle=observed.external_handle, host_fence=observed.host_fence)
    assert executor.cancel(owned).state == 'running'
    assert [call[0] for call in host.calls] == ['cluster.plan.submit', 'cluster.plan.lookup', 'cluster.plan.cancel']
    assert {call[1]['request_key'] for call in host.calls} == {'consumer-key'}
    assert {call[1]['controller_epoch'] for call in host.calls} == {8}
    assert {node for node, _ in leases} == {'node'}
    assert host.calls[-1][1]['host_run_id'] == 'consumer-host-run'


def test_missing_consumer_capability_never_falls_back_to_raw_plan_or_graph():
    host = ConsumerHost()
    host.supports = lambda value: value in (CAPABILITY, INVOCATION_CAPABILITY)
    @contextmanager
    def lease(*_): yield host
    executor = SSHPoolExecutor(lease, controller_epoch=lambda: 7, expected_host_identity=lambda _: 'host-pool')
    assert executor.launch(consumer_dispatch()).state == 'recovery_required'
    assert not host.calls


@pytest.fixture
def consumer_host(producer):
    """Real journals, artifact hashing and preparation; no scientific execution."""
    p, submissions, cancellations = producer, [], []
    raw = template().source_plan.model_dump(mode='json')
    raw['units'][0].update(unit_id='producer', node_ids=['producer'],
        output_contracts=[{'name': 'result', 'representation': 'table'}],
        payload={'outputs': {'result': {'path': 'table.csv', 'representation': 'table'}}})
    raw['units'][1]['input_bindings'] = {'data': 'artifact:producer/result'}
    raw['edges'][0]['source'] = 'producer'
    source = RunPlan.model_validate(raw).with_identity()
    projected = project_unit(source, unit_id='producer', workspace=str(p['workspace']), binding=binding())
    run = p['store'].run(p['request']['host_run_id'])
    saved = {**run['plan'], 'graph': projected.plan.model_dump(mode='json')}
    # Bring the existing committed-file fixture under this exact source plan.
    # Its synthetic process evidence remains explicitly a module fixture.
    with p['store'].transaction():
        p['store'].connection.execute('UPDATE runs SET plan_json=? WHERE id=?', (json.dumps(saved), run['id']))
    workspace = SimpleNamespace(root=p['workspace'], directory=p['workspace'],
                                engine=SimpleNamespace(workspace_id='workspace'))

    def submit(workspace_root, plan, bound, *, request_id, principal, run_id):
        submissions.append(dict(plan=plan, binding=bound, request_id=request_id, run_id=run_id))
        p['store'].claim_submission(principal=principal, key='plan:' + request_id,
            digest=sha256_hex({'plan': plan, 'binding': bound}), operation='plan',
            run={'id': run_id, 'workspace_id': 'workspace', 'project': 'project', 'plan_key': plan['plan_id'],
                 'plan_digest': plan['plan_id'], 'plan': {'graph': plan, 'execution': {'invocation_binding': bound}}},
            units=[{'unit_id': 'unit', 'node_ids': ['unit'], 'depends_on': [],
                    'requirement': {'process_reservation_bytes': 1024, 'cpu_threads': 1}}])
        raise TimeoutError('Dropped acceptance response after durable host admission')

    def cancel(workspace_root, run_id, *, principal):
        cancellations.append(run_id)
        return p['store'].request_cancel(run_id)

    pool = SimpleNamespace(resolve=lambda _: workspace, _authorize=lambda _, principal: principal,
        engine=SimpleNamespace(store=p['store'], spec=SimpleNamespace(pool_id='host-pool', capacity_domain='fixture')),
        coordinator=SimpleNamespace(epoch=2), submit_plan=submit, plan_cancel=cancel,
        plan_details=lambda _, run_id, **kwargs: p['store'].run(run_id))
    endpoint = HostControllerEndpoint(pool, authenticated_controller_id='controller')
    consumer = ConsumerTemplate(workspace=str(p['workspace']), source_plan=source, source_unit_id='unit',
        binding=binding(), target_node_id='node', target_host_identity='host-pool')
    control = {'controller_id': 'controller', 'controller_epoch': 7, 'principal': 'alice',
        'workspace': str(p['workspace']), 'request_key': 'consumer-key', 'command_id': 'consumer-command',
        'cluster_run_id': 'cluster-run', 'cluster_unit_id': 'unit', 'cluster_attempt_id': 'consumer-attempt'}
    parent_control = {**control, **{key: p['request'][key] for key in ('request_key', 'command_id',
        'cluster_run_id', 'cluster_unit_id', 'cluster_attempt_id')}}
    receipt = endpoint.dispatch('cluster.plan.lookup', parent_control)
    row = dict(principal='alice', run_id='cluster-run', plan_id=source.plan_id, unit_id='producer',
        spec=source.units[0].model_dump(mode='json'), controller_id='controller', node_id='node', executor='ssh',
        request_key=p['request']['request_key'], command_id=p['request']['command_id'],
        attempt_id=p['request']['cluster_attempt_id'], external_handle=p['request']['host_run_id'],
        host_fence=p['request']['host_fence'], state='succeeded', unit_state='succeeded', evidence=receipt)
    prepared = consumer_intent(consumer, [row], principal='alice', cluster_run_id='cluster-run',
                              controller_id='controller', controller_epoch=7)
    return SimpleNamespace(endpoint=endpoint, control=control, intent=prepared, submissions=submissions,
                           cancellations=cancellations, producer=p)


def test_host_prepares_current_run_output_once_and_lost_reply_never_resubmits(consumer_host):
    case = consumer_host
    params = {**case.control, 'preparation': case.intent.model_dump(mode='json')}
    with pytest.raises(TimeoutError):
        case.endpoint.dispatch('cluster.plan.submit', params)
    found = case.endpoint.dispatch('cluster.plan.lookup', case.control)
    again = case.endpoint.dispatch('cluster.plan.submit', params)
    assert found['host_run_id'] == again['host_run_id'] == case.submissions[0]['run_id']
    assert len(case.submissions) == 1
    submitted = case.submissions[0]
    lineage = submitted['plan']['execution_policy']['cluster_projection']
    assert lineage['prepared_binding']['cluster_run_id'] == 'cluster-run'
    provenance = lineage['materialized_inputs']['artifact:producer/result']
    assert provenance['host_attempt_id'] == case.producer['attempt']['id']
    bound = submitted['binding']['inputs'][provenance['input_key']]
    assert bound['path'] == (case.producer['output'] / 'table.csv').relative_to(case.producer['workspace']).as_posix()
    assert bound['sha256'] == case.producer['resolver'].resolve(case.producer['request'], principal='alice').input.sha256
    newer = case.intent.model_dump(mode='json')
    for producer in newer['producers'].values():
        producer['controller_epoch'] = 8
    newer_control = {**case.control, 'controller_epoch': 8}
    replay = case.endpoint.dispatch('cluster.plan.submit', {**newer_control, 'preparation': newer})
    assert replay['host_run_id'] == found['host_run_id'] and len(case.submissions) == 1
    case.endpoint.dispatch('cluster.plan.cancel', {**newer_control, 'host_run_id': found['host_run_id'], 'host_fence': None})
    assert case.cancellations == [found['host_run_id']]


def test_raw_audited_projection_cannot_bypass_host_preparation(consumer_host):
    case = consumer_host
    with pytest.raises(TimeoutError):
        case.endpoint.dispatch('cluster.plan.submit', {**case.control, 'preparation': case.intent.model_dump(mode='json')})
    submitted = case.submissions[0]
    lineage = submitted['plan']['execution_policy']['cluster_projection']
    forged = {**case.control, 'request_key': 'forged-key', 'command_id': 'forged-command',
        'source_plan_id': lineage['source_plan_id'], 'source_unit_id': 'unit',
        'source_unit_digest': lineage['source_unit_digest'], 'plan': submitted['plan'], 'binding': submitted['binding']}
    with pytest.raises(ContractError) as failure:
        case.endpoint.dispatch('cluster.plan.submit', forged)
    assert failure.value.code == 'unverified_artifact_provenance'
    assert len(case.submissions) == 1


def test_producer_tree_proof_changed_before_submission_never_launches_consumer(consumer_host):
    case = consumer_host
    proof = json.loads(case.producer['proof'].read_text(encoding='utf-8'))
    proof['identity']['created'] += 1
    case.producer['proof'].write_text(json.dumps(proof), encoding='utf-8')
    params = {**case.control, 'preparation': case.intent.model_dump(mode='json')}
    with pytest.raises(ContractError) as failure:
        case.endpoint.dispatch('cluster.plan.submit', params)
    assert failure.value.code == 'producer_not_stopped'
    assert not case.submissions
    unknown = case.endpoint.dispatch('cluster.plan.lookup', case.control)
    assert unknown['state'] == 'recovery_required' and unknown['phase'] == 'submission_unknown'
    # A claimed request is reconciled; changing the proof never silently retries.
    case.endpoint.dispatch('cluster.plan.submit', params)
    assert not case.submissions
