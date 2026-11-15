"""Real local files/StateStore; fixture containment evidence is not an SSH E2E."""
import json
import os
from pathlib import Path

import pytest

from operon.bytecode import io_path
from operon.cluster.artifact_bindings import CommittedArtifactResolver, ProducerArtifactRequest, MAX_METADATA_BYTES
from operon.cluster.host import stopped_attempt_proof
from operon.contracts.base import ContractError
from operon.engine.artifacts import ArtifactCommitter
from operon.engine.contracts import PoolSpec, ResourceRequest, UnauthorizedError
from operon.engine.fs import atomic_json
from operon.engine.state import StateStore
from operon.execution.codecs import file_reference


def test_confined_publication_metadata_beyond_windows_max_path(producer):
    # A genuine committed-tree layout may exceed MAX_PATH even when its
    # workspace and executable are short. Keep strict confinement checks.
    path = producer['workspace'] / ('deep-' + 'x' * 90) / ('part-' + 'y' * 90) / 'result.json'
    io_path(path).parent.mkdir(parents=True)
    io_path(path).write_text('{"ready":true}', encoding='utf-8')
    assert len(str(path)) > 260
    value, _ = producer['resolver']._json(path)
    assert value == {'ready': True}


@pytest.fixture
def producer(tmp_path):
    workspace = tmp_path.resolve()
    root = workspace / 'invocations'
    store = StateStore(workspace / 'state.sqlite3')
    store.ensure_pool(PoolSpec('host-pool', 'alice', 'machine', 64 * 1024**2, 4 * 1024**2, 2))
    store.register_workspace('workspace', 'host-pool', str(workspace), 'alice')
    envelope = {'request_key': 'source-request', 'command_id': 'source-command',
        'cluster_run_id': 'cluster-run', 'cluster_unit_id': 'producer', 'cluster_attempt_id': 'cluster-attempt',
        'workspace': str(workspace), 'principal': 'alice', 'submission_kind': 'plan'}
    _, claim = store.claim_cluster_request(controller_id='controller', epoch=7, principal='alice',
        request_key=envelope['request_key'], digest='source-payload', envelope=envelope)
    run_id = claim['host_run_id']
    graph = {'format': 'operon.run-plan', 'plan_id': 'a' * 64, 'units': [{
        'unit_id': 'producer', 'invocation': {'kind': 'command'}, 'payload': {'outputs': {
            'result': {'path': 'table.csv', 'representation': 'table'}}}}],
        'execution_policy': {'cluster_projection': {'source_plan_id': 'b' * 64,
            'source_unit_id': 'producer', 'source_unit_digest': 'c' * 64}}}
    store.claim_submission(principal='alice', key=claim['host_request_id'], digest='submitted', operation='run-plan',
        run={'id': run_id, 'workspace_id': 'workspace', 'project': 'project', 'plan_key': 'plan',
             'plan_digest': 'a' * 64, 'plan': {'graph': graph}},
        units=[{'unit_id': 'producer', 'node_ids': ['producer'], 'depends_on': [],
                'requirement': {'process_reservation_bytes': 1024, 'cpu_threads': 1}}])
    unit = store.units(run_id)[0]
    attempt = store.create_attempt(unit['id'], epoch=2)
    process = {'pid': 42, 'created': 123.0, 'boot_id': 'fixture-boot', 'host': 'fixture-host'}
    store.transition_attempt(attempt['id'], 'running', process=process)
    lease = store.acquire_lease(attempt_id=attempt['id'], pool_id='host-pool', owner=process,
                                request=ResourceRequest(process_reservation_bytes=1024, cpu_threads=1))
    committer = ArtifactCommitter(root, store)
    output = root / 'payloads' / attempt['id']
    io_path(output).mkdir(parents=True)
    io_path(output / 'table.csv').write_text('x,y\n1,2\n', encoding='utf-8')
    io_path(output / 'extra.txt').write_text('all output files are committed', encoding='utf-8')
    receipt = committer.commit_existing(attempt=attempt, unit=unit, fence=attempt['fence'], source_root=output,
        files=['table.csv', 'extra.txt'], run_id=run_id, kind='invocation-output')
    reference = file_reference(output / 'table.csv', representation='table')
    published = root / 'runs' / run_id / 'published' / 'producer.json'
    atomic_json(published, {'receipt': receipt, 'outputs': {'result': reference}})
    store.transition_attempt(attempt['id'], 'committing', receipt=receipt)
    store.transition_attempt(attempt['id'], 'succeeded', exit_code=0, receipt={**receipt, 'detail': ''})
    store.release_lease(lease['id'])
    proof = root / 'supervisor' / (attempt['id'] + '.tree-exit.json')
    launch = root / 'supervisor' / (attempt['id'] + '.launch.json')
    atomic_json(proof, {'attempt_id': attempt['id'], 'fence': attempt['fence'],
                       'tree_exited': True, 'method': 'windows-job', 'identity': process})
    atomic_json(launch, {'attempt_id': attempt['id'], 'fence': attempt['fence'], 'state': 'exited', **process})
    resolver = CommittedArtifactResolver(store, invocation_root=root, workspace_root=workspace,
        workspace_id='workspace', host_identity='host-pool', authenticated_controller_id='controller',
        verify_stopped=lambda run, unit, attempt, lease: stopped_attempt_proof(root, attempt))
    request = {key: envelope[key] for key in ('request_key', 'command_id', 'cluster_run_id',
                                             'cluster_unit_id', 'cluster_attempt_id')}
    request.update(controller_epoch=7, host_run_id=run_id, host_unit_id=unit['id'], host_attempt_id=attempt['id'],
                   host_fence=attempt['fence'], artifact_id=receipt['artifact_id'], artifact_digest=receipt['digest'],
                   output_port='result', binding_key='consumer-input')
    try:
        yield dict(store=store, resolver=resolver, request=request, output=output, published=published,
                   workspace=workspace, proof=proof, launch=launch, unit=unit, attempt=attempt, receipt=receipt,
                   baseline_references={ref['id'] for ref in store.references(receipt['artifact_id'])})
    finally:
        store.close()


def test_committed_named_port_is_derived_and_pinned_without_copy(producer):
    p = producer
    value = p['resolver'].resolve(p['request'], principal='alice')
    assert value.mode == 'same-host-visibility' and value.files_verified == 2
    assert value.input.path == (p['output'] / 'table.csv').relative_to(p['workspace']).as_posix()
    assert not Path(value.input.path).is_absolute()
    assert value.producer.host_attempt_id == p['attempt']['id']
    assert value.source_plan_id == 'b' * 64
    assert value.reference_id in {ref['id'] for ref in p['store'].references(p['receipt']['artifact_id'])}
    with StateStore(p['workspace'] / 'state.sqlite3') as reopened:
        assert value.reference_id in {ref['id'] for ref in reopened.references(p['receipt']['artifact_id'])}
    assert p['resolver'].resolve(p['request'], principal='alice') == value
    assert io_path(p['output'] / 'table.csv').read_text() == 'x,y\n1,2\n'


@pytest.mark.parametrize('field,value', [('host_run_id', 'other-run'), ('cluster_run_id', 'other-cluster-run'),
    ('command_id', 'other-command'), ('cluster_attempt_id', 'other-cluster-attempt')])
def test_wrong_controller_run_identity_cannot_resolve_producer(producer, field, value):
    request = {**producer['request'], field: value}
    with pytest.raises(UnauthorizedError): producer['resolver'].resolve(request, principal='alice')


def test_wrong_principal_is_rejected_before_publication_access(producer, monkeypatch):
    monkeypatch.setattr(producer['resolver'], '_json', lambda *a: pytest.fail('unauthorized metadata read'))
    with pytest.raises(UnauthorizedError): producer['resolver'].resolve(producer['request'], principal='mallory')


@pytest.mark.parametrize('field,value', [('host_fence', 999), ('artifact_digest', 'f' * 64),
                                        ('host_attempt_id', 'missing-attempt'), ('output_port', 'missing-port')])
def test_wrong_producer_evidence_or_port_is_rejected(producer, field, value):
    with pytest.raises(ContractError):
        producer['resolver'].resolve({**producer['request'], field: value}, principal='alice')


@pytest.mark.parametrize('change', ['selected', 'other', 'missing'])
def test_every_committed_file_is_verified_and_failed_verification_keeps_pin(producer, change):
    p = producer
    target = p['output'] / ('table.csv' if change == 'selected' else 'extra.txt')
    if change == 'missing': io_path(target).unlink()
    else: io_path(target).write_text('changed content', encoding='utf-8')
    with pytest.raises(ContractError) as error: p['resolver'].resolve(p['request'], principal='alice')
    assert error.value.details['reference_release_attempted'] is False
    assert error.value.details['reference_id'] in {ref['id'] for ref in p['store'].references(p['receipt']['artifact_id'])}


def test_port_remap_to_another_committed_file_is_not_accepted(producer):
    p = producer
    value = json.loads(io_path(p['published']).read_text())
    value['outputs']['result'] = file_reference(p['output'] / 'extra.txt', representation='table')
    atomic_json(p['published'], value)
    with pytest.raises(ContractError, match='frozen port'): p['resolver'].resolve(p['request'], principal='alice')


def test_mutation_during_verification_is_rejected_and_pin_retained(producer, monkeypatch):
    p = producer
    original = p['resolver'].committer.verify_existing
    def changed(*args, **kwargs):
        result = original(*args, **kwargs)
        io_path(p['output'] / 'extra.txt').write_text('changed after verification', encoding='utf-8')
        return result
    monkeypatch.setattr(p['resolver'].committer, 'verify_existing', changed)
    with pytest.raises(ContractError) as error: p['resolver'].resolve(p['request'], principal='alice')
    assert error.value.code == 'producer_changed'
    assert p['store'].references(p['receipt']['artifact_id'])


def test_missing_tree_exit_or_unreleased_lease_never_yields_binding(producer):
    p = producer
    io_path(p['proof']).unlink()
    with pytest.raises(ContractError) as error: p['resolver'].resolve(p['request'], principal='alice')
    assert error.value.code == 'producer_not_stopped'
    with p['store'].transaction():
        p['store'].connection.execute("UPDATE leases SET state='granted' WHERE attempt_id=?", (p['attempt']['id'],))
    with pytest.raises(ContractError) as error: p['resolver'].resolve(p['request'], principal='alice')
    assert error.value.code == 'producer_not_committed'


def test_oversized_publication_and_caller_paths_are_rejected(producer):
    p = producer
    with pytest.raises(ValueError): ProducerArtifactRequest.model_validate({**p['request'], 'path': '/caller/file'})
    io_path(p['published']).write_bytes(b' ' * (MAX_METADATA_BYTES + 1))
    with pytest.raises(ContractError) as error: p['resolver'].resolve(p['request'], principal='alice')
    assert error.value.code == 'artifact_metadata_limit'


def test_released_reference_is_not_silently_reactivated(producer):
    p = producer
    receipt = p['resolver'].resolve(p['request'], principal='alice')
    p['store'].release_reference(receipt.reference_id)
    with pytest.raises(ContractError) as error: p['resolver'].resolve(p['request'], principal='alice')
    assert error.value.code == 'artifact_reference_released'


def test_saved_receipt_is_reverified_and_epoch_refresh_keeps_reference(producer):
    p = producer
    saved = p['resolver'].resolve(p['request'], principal='alice')
    assert p['resolver'].audit(saved, principal='alice', controller_epoch=8) == saved
    assert {ref['id'] for ref in p['store'].references(p['receipt']['artifact_id'])} == (
        p['baseline_references'] | {saved.reference_id})
    io_path(p['output'] / 'extra.txt').write_text('changed after preparation', encoding='utf-8')
    with pytest.raises(ContractError): p['resolver'].audit(saved, principal='alice', controller_epoch=8)
    assert p['store'].references(p['receipt']['artifact_id'])


def test_receipt_cannot_supply_rehashed_input_as_authority(producer):
    from operon.contracts.base import sha256_hex
    p = producer
    saved = p['resolver'].resolve(p['request'], principal='alice').model_dump(mode='json')
    saved['input']['path'] = 'caller-chosen.txt'
    saved['receipt_id'] = sha256_hex({key: value for key, value in saved.items()
        if key not in ('format', 'schema_version', 'receipt_id', 'mode')})
    with pytest.raises(ContractError) as error: p['resolver'].audit(saved, principal='alice')
    assert error.value.code == 'producer_changed'
    assert error.value.details['reference_release_attempted'] is False


def test_publication_read_accepts_unchanged_file_with_distinct_creation_and_change_times(producer):
    p = producer
    # Force the file's change time away from creation on Windows. Path stat and
    # descriptor fstat can expose those two distinct clocks as st_ctime_ns.
    path = io_path(p['published'])
    info = path.stat()
    os.utime(path, ns=(info.st_atime_ns, info.st_mtime_ns + 2_000_000_000))
    expected = json.loads(path.read_text(encoding='utf-8'))
    value, _ = p['resolver']._json(p['published'])
    assert value == expected


def test_metadata_read_still_detects_handle_change_after_open(producer, monkeypatch):
    from types import SimpleNamespace
    p = producer
    fstat = os.fstat
    calls = []
    def changed(fd):
        result = fstat(fd)
        calls.append(fd)
        if len(calls) == 2:
            fields = {name: getattr(result, name) for name in dir(result) if name.startswith('st_')}
            fields['st_ctime_ns'] += 1
            return SimpleNamespace(**fields)
        return result
    monkeypatch.setattr('operon.cluster.artifact_bindings.os.fstat', changed)
    with pytest.raises(ContractError, match='changed while reading'):
        p['resolver']._json(p['published'])


def test_metadata_open_still_rejects_different_file_identity(producer, monkeypatch):
    from types import SimpleNamespace
    p = producer
    fstat = os.fstat
    def changed(fd):
        result = fstat(fd)
        fields = {name: getattr(result, name) for name in dir(result) if name.startswith('st_')}
        fields['st_ino'] += 1
        return SimpleNamespace(**fields)
    monkeypatch.setattr('operon.cluster.artifact_bindings.os.fstat', changed)
    with pytest.raises(ContractError, match='changed while opening'):
        p['resolver']._json(p['published'])


@pytest.mark.skipif(os.name != 'nt', reason='Win32 normal/extended filesystem spellings')
@pytest.mark.parametrize('artifact_extended,attempt_extended,publication_extended',
                         [(True, False, True), (False, True, False), (True, True, True)])
def test_mixed_windows_paths_resolve_same_committed_artifact(producer, artifact_extended,
                                                           attempt_extended, publication_extended):
    p = producer
    def spelling(path, extended):
        return str(io_path(path) if extended else path)
    p['store'].update_artifact(p['receipt']['artifact_id'], state='committed',
                              location=spelling(p['output'], artifact_extended))
    attempt = p['store'].attempt(p['attempt']['id'])
    p['store'].transition_attempt(attempt['id'], 'succeeded', receipt={
        **attempt['receipt'], 'location': spelling(p['output'], attempt_extended)})
    publication = json.loads(io_path(p['published']).read_text())
    publication['receipt']['location'] = spelling(p['output'], publication_extended)
    publication['outputs']['result']['path'] = spelling(p['output'] / 'table.csv', True)
    atomic_json(p['published'], publication)
    root = p['workspace'] / 'invocations'
    resolver = CommittedArtifactResolver(p['store'], invocation_root=io_path(root),
        workspace_root=io_path(p['workspace']) if attempt_extended else p['workspace'],
        workspace_id='workspace', host_identity='host-pool',
        authenticated_controller_id='controller',
        verify_stopped=lambda run, unit, attempt, lease: stopped_attempt_proof(root, attempt))
    result = resolver.resolve(p['request'], principal='alice')
    assert result.input.path == (p['output'] / 'table.csv').relative_to(p['workspace']).as_posix()
    assert result.files_verified == 2
    assert result.reference_id in {ref['id'] for ref in p['store'].references(p['receipt']['artifact_id'])}
    # Native spelling is not permission to reach another directory on the same
    # drive, or a device namespace. Check before any untrusted path is opened.
    with pytest.raises(ContractError) as error:
        resolver._safe(io_path(p['workspace'].parent / 'outside-payload'))
    assert error.value.code == 'path_escape'
    with pytest.raises(ContractError) as error:
        resolver._safe(r'\\?\GLOBALROOT\Device\HarddiskVolumeShadowCopy1\file')
    assert error.value.code == 'path_escape'


@pytest.mark.skipif(os.name != 'nt', reason='Win32 reparse-point confinement')
def test_extended_spelling_does_not_hide_linked_payload(producer):
    p = producer
    linked = p['workspace'] / 'payload-link'
    try:
        linked.symlink_to(p['output'], target_is_directory=True)
    except OSError:
        pytest.skip('Directory symlinks need developer mode or explicit privilege')
    with pytest.raises(ContractError) as error:
        p['resolver']._safe(io_path(linked / 'table.csv'))
    assert error.value.code == 'path_escape'
