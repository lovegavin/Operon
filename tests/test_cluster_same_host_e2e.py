"""Actual one-host native/Form/Python invocation and owned cancellation gate.

Opt in with the existing OPERON_ACCEPTANCE_ENV_STORE/GENERATION variables.
Uses real PoolService TCP RPC, immutable runtime bytes, worker processes,
supervisor containment and artifact publication. This does not claim SSH,
multiple hosts or the PostgreSQL controller's end-to-end acceptance.
"""
from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import shutil
import time
import uuid

from operon.bytecode import io_path
from operon.cluster.executors.ssh_pool import SSHPoolExecutor
from operon.cluster.host import stopped_attempt_proof
from operon.cluster.invocation import CONSUMER_CAPABILITY, ConsumerTemplate, consumer_intent, project_unit
from operon.cluster.receipts import Dispatch
from operon.contracts.base import sha256_hex
from operon.contracts.run_plan import (CodeRef, InvocationSpec, OutputContract, ParametersRef,
    PlacementPolicy, ResourceRequestSpec, RunPlan, UnitSpec)
from operon.engine.artifacts import ArtifactCommitter
from operon.engine.fs import atomic_json
from operon.environment_store import EnvironmentStore
from operon.export.collector import collect, kernel_files
from operon.planning.authoring_v2 import normalize
from operon.pool_service import PoolClient, PoolControlServer, PoolService

from test_native_runtime_snapshot import provider
from test_run_plan_portable_e2e import target_store
from test_run_plan_portable_native_e2e import _document, CONSUMER


ROOT = Path(__file__).resolve().parents[1]
MIB = 1024**2


def _wait(executor, dispatch, *, terminal=True, timeout=120):
    deadline, last = time.monotonic() + timeout, None
    while time.monotonic() < deadline:
        last = executor.reconcile(dispatch)
        if last.state in ('succeeded', 'failed', 'cancelled'):
            return last
        if not terminal and last.state == 'running':
            return last
        time.sleep(.1)
    raise AssertionError(f'Host did not reach the requested state: {last}')


def _dispatch(payload, *, run_id, unit_id):
    token = uuid.uuid4().hex
    return Dispatch('command-' + token, 'cluster-attempt-' + token, run_id, unit_id, 'node', 'ssh',
        'request-' + token, 'alice', 'controller', 7, json.dumps(payload))


def _actual_producer_row(plan, dispatch, observation):
    return dict(principal='alice', run_id=dispatch.run_id, plan_id=plan.plan_id, unit_id=dispatch.unit_id,
        spec=next(unit.model_dump(mode='json') for unit in plan.units if unit.unit_id == dispatch.unit_id),
        controller_id=dispatch.controller_id, node_id=dispatch.node_id, executor=dispatch.executor,
        request_key=dispatch.request_key, command_id=dispatch.command_id, attempt_id=dispatch.attempt_id,
        external_handle=observation.external_handle, host_fence=observation.host_fence,
        state=observation.state, unit_state=observation.state, evidence=observation.evidence)


def _check_terminal(pool, workspace, receipt, expected):
    store = pool.engine.store
    run = store.run(receipt.external_handle)
    attempts = store.attempts(run['id'])
    assert len(attempts) == 1, 'One cluster dispatch must never create duplicate host attempts'
    attempt = attempts[0]
    assert attempt['state'] == expected
    assert store.lease(attempt['id'])['state'] == 'released'
    assert stopped_attempt_proof(workspace / 'd' / 'invocations', attempt)
    assert attempt['process']['pid'] > 0
    if expected == 'succeeded':
        artifact = store.artifact(attempt['receipt']['artifact_id'])
        assert ArtifactCommitter(workspace / 'd' / 'invocations', store).verify_existing(
            attempt['receipt'], manifest=artifact['manifest'])['valid']
        assert receipt.evidence['artifact_committed'] is True
    return {'run_id': run['id'], 'attempt_id': attempt['id'], 'fence': attempt['fence'],
            'process': attempt['process'], 'receipt': attempt['receipt'], 'state': attempt['state']}


def test_actual_same_host_native_form_to_python_and_owned_cancel(target_store, provider, tmp_path_factory):
    fixture_root, catalog = provider
    original_store, generation, requirement, executable = target_store
    workspace = tmp_path_factory.mktemp('host')
    package, environment_root = workspace / 'code', workspace / 'env'
    collect(ROOT, package, kernel_files(ROOT))
    shutil.copytree(fixture_root / 'owned_native_provider', package / 'owned_native_provider')
    source_generation, _, _ = original_store._manifest(generation)
    destination = environment_root / 'generations' / generation
    shutil.copytree(io_path(source_generation), io_path(destination), symlinks=True)
    deployed = EnvironmentStore(environment_root)
    verified = deployed.binding(generation)
    source = workspace / 'numbers.owned'
    source.write_text('1 2 3', encoding='utf-8')
    # The native fixture exports the actual Form under the explicit result port.
    # Build the consumer edge directly instead of guessing compiler alias names.
    document = normalize(_document(source, consumer=False), workspace, initial=True,
        parameters={'params': {}}, environments={'locked': {
            'requirement': requirement.model_dump(mode='json'), 'executable': executable}}, catalog=None)
    native_plan = document.compile(deepcopy(catalog), require_files=True)
    native = next(unit for unit in native_plan.units if unit.invocation.kind == 'native')
    script_hash = hashlib.sha256(CONSUMER.encode()).hexdigest()
    script_path = 'scripts/consume.py'
    (package / 'scripts').mkdir(exist_ok=True)
    (package / script_path).write_bytes(CONSUMER.encode('utf-8'))
    cancel_script = 'import time\nprint("owned cancellation target", flush=True)\ntime.sleep(120)\n'
    (package / 'scripts/cancel.py').write_bytes(cancel_script.encode('utf-8'))
    binding = {'package_root': 'code', 'environment_store': 'env', 'environments': {
        'locked': {'generation_id': generation, 'executable': executable}}, 'storage': {}, 'inputs': {}}
    pool = PoolService(root=workspace / 'pool', admission_dir=workspace / 'admission',
        workspaces=[{'root': workspace, 'principal': 'alice', 'data_dir': workspace / 'd'}],
        code_root=ROOT, catalog=catalog, capacity_bytes=768*MIB, cpu_threads=2)
    server = PoolControlServer(pool, token='test-owned-cluster-token', controller_id='controller').start()
    host_identity = pool.engine.spec.pool_id
    calls, submitted, completed = [], [], []
    @contextmanager
    def lease(node_id, lane):
        assert node_id == 'node'
        client = PoolClient(server.address, 'test-owned-cluster-token', timeout=90,
                            capabilities=server.capabilities())
        assert CONSUMER_CAPABILITY in client.capabilities
        calls.append({'node': node_id, 'lane': lane})
        yield client
    executor = SSHPoolExecutor(lease, controller_epoch=lambda: 7, expected_host_identity=lambda _: host_identity)
    try:
        placement = PlacementPolicy(executor='ssh', node_id='node', pool_id=host_identity, target=requirement.target)
        native = native.model_copy(update={'placement': placement,
            'output_contracts': (OutputContract(name='result', representation='form'),)})
        consumer = UnitSpec(unit_id='consume', node_ids=('consume',),
            invocation=InvocationSpec(kind='python_script', entrypoint='script', environment_ref='locked',
                code_ref=CodeRef(kind='script', ref=script_path, digest=script_hash),
                parameters_ref=ParametersRef(digest=sha256_hex({}))),
            input_bindings={'data': f'artifact:{native.unit_id}/result'},
            output_contracts=(OutputContract(name='report', representation='json'),),
            resource_request=ResourceRequestSpec(process_reservation_bytes=192*MIB, cpu_threads=1),
            placement=placement, payload={'parameters': {}, 'executable': executable,
                'arguments': ['--in-data', {'input': 'data'}, '--out-report', {'output': 'report'}],
                'outputs': {'report': {'path': 'report.json', 'representation': 'json'}}})
        raw = native_plan.model_dump(mode='json')
        raw['units'] = [native.model_dump(mode='json'), consumer.model_dump(mode='json')]
        raw['edges'].append({'source': native.node_ids[-1], 'target': 'consume',
                             'source_handle': 'result', 'target_handle': 'data'})
        plan = RunPlan.model_validate(raw).with_identity()
        cluster_run = 'cluster-real-' + uuid.uuid4().hex
        first = _dispatch(project_unit(plan, unit_id=native.unit_id, workspace=str(workspace),
            binding=binding).model_dump(mode='json'), run_id=cluster_run, unit_id=native.unit_id)
        atomic_json(workspace / 'producer-dispatch.json', first.__dict__)
        submitted.append(first)
        initial = executor.launch(first)
        assert initial.state not in ('failed', 'cancelled'), initial
        produced = _wait(executor, first)
        assert produced.state == 'succeeded', produced.evidence
        completed.append(_check_terminal(pool, workspace, produced, 'succeeded'))
        intent = consumer_intent(ConsumerTemplate(workspace=str(workspace), source_plan=plan,
            source_unit_id='consume', binding=binding, target_node_id='node', target_host_identity=host_identity),
            [_actual_producer_row(plan, first, produced)], principal='alice', cluster_run_id=cluster_run,
            controller_id='controller', controller_epoch=7)
        second = _dispatch(intent.model_dump(mode='json'), run_id=cluster_run, unit_id='consume')
        atomic_json(workspace / 'consumer-dispatch.json', second.__dict__)
        submitted.append(second)
        accepted = executor.launch(second)
        assert accepted.state not in ('failed', 'cancelled'), accepted
        consumed = _wait(executor, second)
        assert consumed.state == 'succeeded', consumed.evidence
        completed.append(_check_terminal(pool, workspace, consumed, 'succeeded'))
        result_path = workspace / 'd/invocations/runs' / consumed.external_handle / 'published/consume.json'
        publication = json.loads(io_path(result_path).read_text(encoding='utf-8'))
        result = json.loads(io_path(publication['outputs']['report']['path']).read_text(encoding='utf-8'))
        assert result == {'sum': 6.0, 'shape': [3, 1], 'dims': ['sample', 'feature'],
                          'labels': {'sample': {'0': 0, '1': 1, '2': 2}, 'feature': {'value': 0}}}
        # A replay reaches the existing host key and retains exactly one attempt.
        replay = executor.launch(second)
        assert replay.external_handle == consumed.external_handle
        assert len(pool.engine.store.attempts(consumed.external_handle)) == 1
        consumer_run = pool.engine.store.run(consumed.external_handle)
        audit = consumer_run['plan']['graph']['execution_policy']['cluster_projection']
        provenance = audit['materialized_inputs'][f'artifact:{native.unit_id}/result']
        assert provenance['host_attempt_id'] == produced.evidence['host_attempt_id']
        assert any(ref['id'] == provenance['reference_id'] for ref in
                   pool.engine.store.references(produced.evidence['artifact']['artifact_id']))
        # Cancellation uses the same configured host authority and a real worker.
        cancelling = consumer.model_copy(update={'unit_id': 'cancel', 'node_ids': ('cancel',),
            'input_bindings': {}, 'invocation': consumer.invocation.model_copy(update={
                'code_ref': CodeRef(kind='script', ref='scripts/cancel.py',
                                   digest=hashlib.sha256(cancel_script.encode()).hexdigest())}),
            'payload': {'parameters': {}, 'executable': executable, 'arguments': [],
                        'outputs': {'report': {'path': 'unused.json', 'representation': 'json'}}}})
        cancel_plan = plan.model_copy(update={'units': (cancelling,), 'edges': ()}).with_identity()
        third = _dispatch(project_unit(cancel_plan, unit_id='cancel', workspace=str(workspace),
            binding=binding).model_dump(mode='json'), run_id='cancel-' + uuid.uuid4().hex, unit_id='cancel')
        submitted.append(third)
        executor.launch(third)
        running = _wait(executor, third, terminal=False)
        assert running.state == 'running', running.evidence
        owned = replace(third, external_handle=running.external_handle, host_fence=running.host_fence)
        executor.cancel(owned)
        cancelled = _wait(executor, owned)
        assert cancelled.state == 'cancelled', cancelled.evidence
        completed.append(_check_terminal(pool, workspace, cancelled, 'cancelled'))
        leases = [json.loads(path.read_text(encoding='utf-8')) for path in (environment_root / 'leases').glob('*.json')]
        assert len(leases) == 3 and all(value['state'] == 'released' for value in leases)
        assert deployed.binding(generation) == verified
        assert pool.coordinator.resources.snapshot().active == 0
        atomic_json(workspace / 'evidence.json', {'kind': 'actual-one-host-pool-rpc-native-form-python',
            'status': 'passed', 'host_identity': host_identity, 'plan_id': plan.plan_id,
            'generation': verified.model_dump(mode='json'), 'result': result, 'attempts': completed,
            'environment_leases': leases, 'calls': calls, 'native_provider': 'test-owned fixture',
            'source_sha256': {path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest() for path in (
                'tests/test_cluster_same_host_e2e.py', 'operon/cluster/host.py', 'operon/cluster/invocation.py',
                'operon/cluster/artifact_bindings.py', 'operon/cluster/prepared_bindings.py',
                'operon/execution/unit_executor.py', 'operon/engine/supervisor.py')},
            'limits': ['Local TCP transport, not SSH', 'No PostgreSQL controller in this gate', 'One physical host']})
    finally:
        for dispatch in submitted:
            observed = executor.reconcile(dispatch)
            if observed.state not in ('succeeded', 'failed', 'cancelled') and observed.external_handle:
                executor.cancel(replace(dispatch, external_handle=observed.external_handle,
                                        host_fence=observed.host_fence))
        server.close()
        pool.shutdown()
