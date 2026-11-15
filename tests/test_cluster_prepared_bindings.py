"""Real local producer bytes and durable host state; no SSH/second-host claim."""
import json
import os

import pytest

from operon.bytecode import io_path
from operon.cluster.artifact_bindings import CommittedArtifactResolver
from operon.cluster.invocation import InvocationDispatch, project_unit
from operon.cluster.prepared_bindings import SharedConsumerPreparer, validate_prepared_projection
from operon.contracts.base import ContractError, sha256_hex
from operon.contracts.run_plan import RunPlan
from operon.engine.contracts import IdempotencyConflictError, UnauthorizedError
from operon.engine.fs import atomic_json
from operon.engine.state import StateStore
from test_cluster_artifact_bindings import producer


@pytest.fixture
def consumer(producer):
    p = producer
    common = dict(invocation={'kind': 'command', 'argv': ['fixture-only'],
        'code_ref': {'kind': 'file', 'ref': 'tool'}, 'environment_ref': 'runtime'},
        output_contracts=[{'name': 'result', 'representation': 'table'}],
        resource_request={'process_reservation_bytes': 1024, 'cpu_threads': 1},
        placement={'executor': 'ssh', 'target': {'os': 'linux', 'arch': 'x86_64'},
                   'node_id': 'node-a', 'pool_id': 'host-pool'},
        payload={'outputs': {'result': {'path': 'table.csv', 'representation': 'table'}}})
    plan = RunPlan.model_validate(dict(plan_id='pending', workflow_revision='a' * 64,
        parameters_digest='b' * 64, compiler_version='shared-artifact-fixture', units=[
            dict(common, unit_id='producer', node_ids=['producer']),
            dict(common, unit_id='consumer', node_ids=['consumer'], input_bindings={'data': 'artifact:producer/result'})],
        edges=[{'source': 'producer', 'target': 'consumer', 'source_handle': 'result', 'target_handle': 'data'}],
        execution_policy={'environment_refs': {'runtime': 'c' * 64}})).with_identity()
    binding = dict(package_root='package', environment_store='environments',
                   environments={'runtime': {'generation_id': 'fixture', 'executable': 'bin/tool'}})
    # Replace only the fixture's synthetic producer graph with the exact source
    # projection. ArtifactCommitter's actual manifest/bytes/receipt stay intact.
    projected = project_unit(plan, unit_id='producer', workspace=str(p['workspace']), binding=binding)
    with p['store'].transaction():
        p['store'].connection.execute('UPDATE runs SET plan_json=? WHERE id=?',
            (json.dumps({'graph': projected.plan.model_dump(mode='json')}), p['request']['host_run_id']))
    preparer = SharedConsumerPreparer(p['resolver'], target_node_id='node-a')
    return dict(p, plan=plan, binding=binding, preparer=preparer,
                producers={'artifact:producer/result': dict(p['request'])})


def prepare(c, **changes):
    values = dict(cluster_run_id='cluster-run', consumer_unit_id='consumer', binding=c['binding'],
                  producers=c['producers'], request_id='consumer-request', principal='alice')
    values.update(changes)
    return c['preparer'].prepare(c['plan'], **values)


def consumer_references(c):
    current = c['store'].references(c['receipt']['artifact_id'])
    # ArtifactCommitter independently pins job outputs. Consumer checks must
    # preserve those refs and verify this preparation's additional ownership.
    assert c['baseline_references'] <= {ref['id'] for ref in current}
    return {ref['id'] for ref in current if ref['reason'] == 'shared-artifact-input'}


def test_frozen_edge_projects_verified_host_input_and_persists_reference(consumer):
    c = consumer
    prepared = prepare(c)
    dispatch = InvocationDispatch.model_validate(prepared.dispatch_payload())
    assert dispatch.plan.units[0].placement.executor == 'local'
    assert c['plan'].units[1].placement.executor == 'ssh'
    assert dispatch.source_plan_id == c['plan'].plan_id
    assert dispatch.source_unit_digest == sha256_hex(c['plan'].units[1])
    assert prepared.audit['source_dependencies'] == ('producer',)
    edge = 'artifact:producer/result'
    item = prepared.audit['materialized_inputs'][edge]
    actual = prepared.binding.inputs[item['input_key']]
    assert actual.path == (c['output'] / 'table.csv').relative_to(c['workspace']).as_posix()
    assert item['host_attempt_id'] == c['request']['host_attempt_id']
    assert item['host_fence'] == c['request']['host_fence']
    assert item['artifact_digest'] == c['receipt']['digest']
    assert prepared.plan.units[0].input_bindings['data'] == 'input:' + item['input_key']
    assert consumer_references(c) == {item['reference_id']}
    assert prepare(c) == prepared
    assert c['preparer'].audit(prepared, principal='alice') == prepared
    with StateStore(c['store'].path) as reopened:
        resolver = CommittedArtifactResolver(reopened, invocation_root=c['resolver'].root,
            workspace_root=c['workspace'], workspace_id='workspace', host_identity='host-pool',
            authenticated_controller_id='controller', verify_stopped=c['resolver'].verify_stopped)
        restarted = SharedConsumerPreparer(resolver, target_node_id='node-a')
        assert restarted.load(prepared.preparation_id, principal='alice') == prepared


def test_epoch_refresh_keeps_preparation_payload_and_same_retention_pin(consumer):
    c = consumer
    original = prepare(c)
    newer = {'artifact:producer/result': {**c['request'], 'controller_epoch': 8}}
    assert prepare(c, producers=newer) == original
    assert c['preparer'].load(original.preparation_id, principal='alice', controller_epoch=8) == original
    assert consumer_references(c) == {original.receipts['artifact:producer/result'].reference_id}
    pin = original.receipts['artifact:producer/result'].reference_id
    c['store'].release_reference(pin)
    with pytest.raises(ContractError) as caught:
        c['preparer'].load(original.preparation_id, principal='alice', controller_epoch=9)
    assert caught.value.code == 'artifact_reference_released'
    assert not consumer_references(c)


def test_cached_read_preserves_win32_path_and_handle_timestamp_views(consumer):
    c = consumer
    prepared = prepare(c)
    path = io_path(c['preparer'].root / (prepared.preparation_id + '.json'))
    info = path.stat()
    os.utime(path, ns=(info.st_atime_ns, info.st_mtime_ns + 2_000_000_000))
    assert c['preparer'].load(prepared.preparation_id, principal='alice') == prepared
    assert consumer_references(c) == {prepared.receipts['artifact:producer/result'].reference_id}


def test_wrong_principal_cannot_read_cached_metadata(consumer, monkeypatch):
    c = consumer
    prepared = prepare(c)
    monkeypatch.setattr(c['resolver'], '_safe', lambda *a, **kw: pytest.fail('unauthorized filesystem read'))
    with pytest.raises(UnauthorizedError): c['preparer'].load(prepared.preparation_id, principal='mallory')


@pytest.mark.parametrize('field,value', [('cluster_run_id', 'other-run'), ('cluster_unit_id', 'other-unit'),
    ('output_port', 'other-port'), ('host_fence', 999), ('artifact_digest', 'f' * 64)])
def test_exact_run_attempt_artifact_and_port_are_required(consumer, field, value):
    c = consumer
    changed = {'artifact:producer/result': {**c['request'], field: value}}
    with pytest.raises(ContractError): prepare(c, producers=changed)


def test_changed_binding_cannot_reuse_successful_request(consumer):
    c = consumer
    prepare(c)
    changed = {**c['binding'], 'package_root': 'a-different-package'}
    with pytest.raises(IdempotencyConflictError): prepare(c, binding=changed)
    assert len(consumer_references(c)) == 1


def test_same_unit_from_another_frozen_plan_is_not_accepted(consumer):
    c = consumer
    raw = c['plan'].model_dump(mode='json')
    raw['execution_policy']['unrelated_setting'] = 'different-plan'
    c['plan'] = RunPlan.model_validate(raw).with_identity()
    with pytest.raises(ContractError) as caught: prepare(c)
    assert caught.value.code == 'unverified_artifact_provenance'
    assert consumer_references(c)


def test_consumer_owns_generated_binding_names(consumer):
    c = consumer
    prepared = prepare(c)
    key = prepared.audit['materialized_inputs']['artifact:producer/result']['input_key']
    changed = {**c['binding'], 'inputs': {key: prepared.binding.inputs[key].model_dump(mode='json')}}
    with pytest.raises(ContractError) as caught: prepare(c, binding=changed, request_id='second')
    assert caught.value.code == 'binding_rebind_rejected'


@pytest.mark.parametrize('change', ['payload', 'missing', 'publication', 'proof'])
def test_cached_preparation_revalidates_producer_files_publication_and_exit(consumer, change):
    c = consumer
    prepared = prepare(c)
    if change == 'payload': io_path(c['output'] / 'extra.txt').write_text('corrupted')
    elif change == 'missing': io_path(c['output'] / 'table.csv').unlink()
    elif change == 'proof': io_path(c['proof']).unlink()
    else:
        publication = json.loads(io_path(c['published']).read_text())
        publication['outputs']['result']['metadata'] = {'changed': True}
        atomic_json(c['published'], publication)
    with pytest.raises(ContractError): c['preparer'].load(prepared.preparation_id, principal='alice')
    assert consumer_references(c)


def test_persisted_rehash_cannot_replace_durable_claim_digest(consumer):
    c = consumer
    prepared = prepare(c)
    path = c['preparer'].root / (prepared.preparation_id + '.json')
    raw = prepared.model_dump(mode='json')
    raw['request']['binding']['package_root'] = 'changed-package'
    raw['payload_digest'] = sha256_hex({key: value for key, value in raw.items() if key != 'payload_digest'})
    atomic_json(path, raw)
    with pytest.raises((ContractError, ValueError)):
        c['preparer'].load(prepared.preparation_id, principal='alice')
    assert consumer_references(c)


def test_cached_record_change_during_producer_audit_is_detected(consumer, monkeypatch):
    c = consumer
    prepared = prepare(c)
    path = c['preparer'].root / (prepared.preparation_id + '.json')
    audit = c['resolver'].audit
    def changed(*args, **kwargs):
        result = audit(*args, **kwargs)
        with io_path(path).open('ab') as stream: stream.write(b' ')
        return result
    monkeypatch.setattr(c['resolver'], 'audit', changed)
    with pytest.raises(ContractError) as caught:
        c['preparer'].load(prepared.preparation_id, principal='alice')
    assert caught.value.code == 'binding_integrity_error'


@pytest.mark.parametrize('missing', [True, False])
def test_missing_or_oversized_cached_record_is_not_rebuilt(consumer, monkeypatch, missing):
    c = consumer
    prepared = prepare(c)
    path = c['preparer'].root / (prepared.preparation_id + '.json')
    if missing: io_path(path).unlink()
    else:
        monkeypatch.setattr('operon.cluster.prepared_bindings.MAX_PREPARATION_BYTES', 128)
    with pytest.raises(ContractError) as caught: prepare(c)
    assert caught.value.code == 'binding_integrity_error'
    assert consumer_references(c)


def test_failed_persistence_keeps_pins_and_claim_without_hidden_retry(consumer, monkeypatch):
    c = consumer
    def failed_write(*args, **kwargs): raise OSError('fixture persistence failure')
    monkeypatch.setattr('operon.cluster.prepared_bindings.atomic_json', failed_write)
    with pytest.raises(OSError): prepare(c)
    assert consumer_references(c)
    monkeypatch.setattr(c['resolver'], 'resolve', lambda *a, **kw: pytest.fail('silent rebuild'))
    with pytest.raises(ContractError) as caught: prepare(c)
    assert caught.value.code == 'binding_recovery_required'


@pytest.mark.parametrize('field,value', [('source_handle', 'other-port'), ('target_handle', 'other-input'),
                                      ('source_handle', None), ('target_handle', None)])
def test_explicit_edge_handles_cannot_disagree_with_frozen_input_bindings(consumer, field, value):
    c = consumer
    raw = c['plan'].model_dump(mode='json')
    raw['edges'][0][field] = value
    c['plan'] = RunPlan.model_validate(raw).with_identity()
    with pytest.raises(ContractError) as caught: prepare(c)
    assert caught.value.code in ('invalid_plan_edge', 'unsupported_control_dependency')
    assert not consumer_references(c)


def test_pure_control_dependency_is_explicitly_unsupported(consumer):
    c = consumer
    raw = c['plan'].model_dump(mode='json')
    raw['units'].append({**raw['units'][0], 'unit_id': 'control', 'node_ids': ['control']})
    raw['edges'].append({'source': 'control', 'target': 'consumer'})
    c['plan'] = RunPlan.model_validate(raw).with_identity()
    with pytest.raises(ContractError) as caught: prepare(c)
    assert caught.value.code == 'unsupported_control_dependency'


@pytest.mark.parametrize('field,value', [('node_id', 'node-b'), ('pool_id', 'another-pool'), ('executor', 'slurm')])
def test_different_selected_host_never_falls_back_to_local_visibility(consumer, field, value):
    c = consumer
    raw = c['plan'].model_dump(mode='json')
    raw['units'][0]['placement'][field] = value
    c['plan'] = RunPlan.model_validate(raw).with_identity()
    with pytest.raises(ContractError) as caught: prepare(c)
    assert caught.value.code == 'cross_host_artifact_unavailable'


def test_pure_projection_validator_rejects_changed_code_or_bound_content(consumer):
    c = consumer
    prepared = prepare(c)
    options = dict(source_plan_id=prepared.source_plan_id, source_unit_id=prepared.source_unit_id,
                   source_unit_digest=prepared.source_unit_digest, binding=prepared.binding)
    raw = prepared.plan.model_dump(mode='json')
    raw['units'][0]['invocation']['argv'] = ['changed-code']
    with pytest.raises(ContractError):
        validate_prepared_projection(RunPlan.model_validate(raw).with_identity(), **options)
    changed = prepared.binding.model_dump(mode='json')
    next(iter(changed['inputs'].values()))['sha256'] = 'f' * 64
    with pytest.raises(ContractError):
        validate_prepared_projection(prepared.plan, **{**options, 'binding': changed})


def test_compact_projection_audit_has_an_independent_size_bound(consumer, monkeypatch):
    c = consumer
    monkeypatch.setattr('operon.cluster.prepared_bindings.MAX_AUDIT_BYTES', 128)
    with pytest.raises(ContractError) as caught: prepare(c)
    assert caught.value.code == 'binding_metadata_limit'
    assert consumer_references(c)
