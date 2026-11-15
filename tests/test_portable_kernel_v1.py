"""Portable metadata and check-mode gates, not real offline runtime acceptance.

The synthetic generation below has deliberately non-executable fixture bytes.
These tests never launch it; target runtime/relocation acceptance is separate.
"""
from copy import deepcopy
import json
import platform
from pathlib import Path

import pytest

from operon.contracts.base import ContractError, sha256_hex
from operon.contracts.run_plan import (
    CodeRef, EnvironmentRequirement, InvocationSpec, PlacementPolicy, ResourceRequestSpec,
    RunPlan, TargetSpec, UnitSpec,
)
from operon.environment_store import EnvironmentStore
from operon.environment_store.verification import inventory
from operon.export.collector import collect, kernel_files, validate_coverage
from operon.export.kernel import _parameters, inspect_bundle, run_bundle
from operon.export.planner import bindable_plan
from operon.planning.validation import validate_run_plan
from operon.bytecode import io_path


def _write(path, value):
    path = io_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')


def test_explicit_kernel_manifest_contains_lazy_native_public_api():
    files = kernel_files(Path(__file__).resolve().parents[1])
    for module in ('src/task/context/__init__.py', 'src/task/context/base.py',
                   'src/task/manifest.py', 'src/task/runner.py', 'src/task/step/base.py',
                   'operon_sdk/resources.py', 'operon_sdk/figures.py',
                   'operon/execution/containment.py'):
        assert module in files
    assert not any(name.startswith(('frontend/', 'library/')) for name in files)


def plan_for(path):
    target = TargetSpec(os=platform.system().lower(), arch=platform.machine().lower())
    requirement = EnvironmentRequirement(target=target, runtime='synthetic-test-only')
    params = {'threshold': 0, 'flag': False, 'optional': None, 'empty': []}
    unit = UnitSpec(
        unit_id='native-chain', node_ids=('transform',),
        invocation=InvocationSpec(kind='native', entrypoint='operon.execution.worker_main',
                                  code_ref=CodeRef(kind='workflow', ref='fixture'), environment_ref='cpython'),
        input_bindings={'matrix': str(path)},
        resource_request=ResourceRequestSpec(managed_budget_bytes=16, process_reservation_bytes=32),
        placement=PlacementPolicy(target=target),
        payload={'task_manifest': {'name': 'Fixture', 'sources': {
            'matrix': {'path': str(path), 'dims': ['sample', 'feature'], 'labels': {}, 'args': {'flag': False}}},
            'steps': [{'name': 'synthetic', 'inputs': ['matrix'], 'params': params}],
            'params': {'global': False}, 'runtime': {'memory': {'enabled': True, 'budget_mb': 1}}},
            'step_ids': ['transform'], 'graph': {'nodes': [], 'edges': []}},
    )
    return RunPlan(plan_id='pending', workflow_revision='a' * 64, units=(unit,),
                   parameters_digest='b' * 64, environment_requirements=(requirement,),
                   execution_policy={'environment_refs': {'cpython': sha256_hex(requirement)}},
                   compiler_version='synthetic-test/1').with_identity()


def bundle_at(root, source):
    """An intact synthetic bundle for read-only inspect/check testing only."""
    root.mkdir(parents=True)
    plan, inputs = bindable_plan(plan_for(source))
    store = EnvironmentStore(root / 'payload' / 'environments')
    requirement = plan.environment_requirements[0]
    # Stable content identity independent of the fixture directory.
    temporary = root / 'generation-fixture'
    (temporary / 'runtime').mkdir(parents=True)
    (temporary / 'runtime' / 'python').write_bytes(b'NOT EXECUTABLE: metadata fixture only\n')
    files = inventory(temporary)
    identity = {'requirement_digest': sha256_hex(requirement), 'content_digest': sha256_hex(files),
                'builder': {'fixture': True}, 'target': requirement.target.model_dump(mode='json')}
    generation = sha256_hex(identity)
    directory = store.root / 'generations' / generation
    directory.mkdir()
    temporary.rename(directory / 'payload')
    _write(directory / 'manifest.json', {'format': 'operon.environment-generation', 'schema_version': 1,
        'generation_id': generation, 'identity': identity, 'files': files,
        'requirement_digest': sha256_hex(requirement), 'requirement': requirement.model_dump(mode='json'),
        'content_digest': sha256_hex(files)})
    _write(directory / 'verification.json', {'status': 'passed', 'relocation': 'passed',
                                            'content_digest': sha256_hex(files)})
    _write(root / 'payload' / 'plan.json', plan.model_dump(mode='json'))
    _write(root / 'payload' / 'bindings.json', {'environments': {'cpython': {
        'generation_id': generation, 'executable': 'runtime/python'}}, 'inputs': {}})
    _write(root / 'inputs.json', inputs)
    _write(root / 'parameters.json', {'native-chain': {'transform': dict(plan.units[0].payload['task_manifest']['steps'][0]['params'])}})
    refresh_inventory(root, plan)
    return plan


def refresh_inventory(root, plan):
    _write(root / 'bundle.json', {'format': 'operon.portable', 'schema_version': 1,
                                'status': 'complete', 'plan_id': plan.plan_id,
                                'files': inventory(root / 'payload'), 'network_resolution': False})


def test_export_uses_measured_scan_budget_and_retains_failure_receipt(tmp_path, monkeypatch):
    import operon.export.service as service
    source = tmp_path / 'data.fixture'; source.write_bytes(b'synthetic')
    fixture = tmp_path / 'fixture'; plan = bundle_at(fixture, source)
    binding = json.loads((fixture / 'payload/bindings.json').read_text())['environments']
    store = EnvironmentStore(fixture / 'payload/environments', create=False)
    monkeypatch.setattr(service, '_inventory_with_duration', lambda path, **kwargs: (inventory(path, **kwargs), 300.0))
    observed = []
    def timeout_probe(root, argv, **kwargs):
        observed.append(kwargs)
        raise TimeoutError('Synthetic stalled probe')
    monkeypatch.setattr(service, 'probe', timeout_probe)
    cancelled = lambda: False
    export = service.ExportService(Path(__file__).resolve().parents[1], store, tmp_path / 'receipts')
    with pytest.raises(TimeoutError, match='stalled'):
        export.build(plan, tmp_path / 'output', implementations={}, environments=binding, cancel=cancelled)
    assert len(observed) == 1
    assert observed[0]['timeout'] == 1260
    assert observed[0]['cancel'] is cancelled
    receipt = json.loads(next((tmp_path / 'receipts').glob('*.json')).read_text())
    assert receipt['status'] == 'failed' and receipt['phase'] == 'relocation_probe'
    assert receipt['verification']['inventory_seconds'] == 300.0
    assert receipt['verification']['probe_timeout_seconds'] == 1260
    assert not (tmp_path / 'output').exists()


def test_relocation_budget_remains_bounded_and_rejects_invalid_measurements():
    from operon.export.service import _relocation_probe_timeout
    assert _relocation_probe_timeout(0) == 180
    assert _relocation_probe_timeout(0, prepare=True) == 600
    assert _relocation_probe_timeout(300, prepare=True) == 1920
    assert _relocation_probe_timeout(100000) == 7200
    for invalid in [-1, float('inf'), float('nan')]:
        with pytest.raises(ValueError):
            _relocation_probe_timeout(invalid)


def test_legacy_launch_upgrades_working_copy_without_mutating_bundle(tmp_path, monkeypatch):
    import operon.export.kernel as kernel
    source = tmp_path / 'data.fixture'; source.write_bytes(b'synthetic')
    root = tmp_path / 'legacy'; bundle_at(root, source)
    before = inventory(root / 'payload')
    class ReachedCoordinator(Exception): pass
    def stop_before_scientific_launch(*args, **kwargs): raise ReachedCoordinator()
    monkeypatch.setattr(kernel, 'Coordinator', stop_before_scientific_launch)
    with pytest.raises(ReachedCoordinator):
        run_bundle(root, memory=64*1024**2, threads=1)
    assert inventory(root / 'payload') == before
    assert list((root / 'work/environments/generations').glob('*/packages.json'))
    assert not list((root / 'payload/environments/generations').glob('*/packages.json'))


def test_bindable_plan_preserves_values_and_lifts_only_explicit_source_paths(tmp_path):
    path = tmp_path / 'data.fixture'
    original = plan_for(path)
    before = original.canonical_json()
    portable, inputs = bindable_plan(original)
    assert original.canonical_json() == before
    assert inputs == {'native-chain-matrix': str(path)}
    assert portable.units[0].payload['task_manifest']['sources']['matrix']['path'] == 'storage://native-chain-matrix/data.fixture'
    assert portable.units[0].input_bindings['matrix'] == 'storage://native-chain-matrix/data.fixture'
    assert portable.units[0].payload['task_manifest']['steps'][0]['params']['threshold'] == 0
    assert portable.units[0].payload['task_manifest']['sources']['matrix']['args']['flag'] is False
    assert 'graph' not in portable.units[0].payload
    assert portable.units[0].placement.executor == 'standalone'
    assert validate_run_plan(portable) == portable


def test_native_cross_unit_artifact_binding_is_not_rewritten_as_external_input(tmp_path):
    original = plan_for(tmp_path / 'data.fixture')
    raw = original.model_dump(mode='json')
    consumer = deepcopy(raw['units'][0])
    consumer.update(unit_id='consumer', node_ids=['consume'], input_bindings={'matrix': 'artifact:native-chain/result'})
    consumer['payload']['task_manifest']['sources']['matrix']['path'] = 'pending-parent.fixture'
    consumer['payload']['task_manifest']['steps'][0]['inputs'] = ['matrix']
    consumer['payload']['step_ids'] = ['consume']
    raw['units'].append(consumer)
    raw['edges'] = [{'id': 'parent-child', 'source': 'transform', 'target': 'consume',
                     'source_handle': 'out', 'target_handle': 'in-0'}]
    mixed = RunPlan.model_validate(raw).with_identity()
    portable, inputs = bindable_plan(mixed)
    assert portable.units[1].input_bindings['matrix'] == 'artifact:native-chain/result'
    assert 'consumer-matrix' not in inputs


def test_planner_refuses_stale_plan_identity_and_remote_only_targets(tmp_path):
    raw = plan_for(tmp_path / 'data.fixture').model_dump(mode='json')
    raw['units'][0]['payload']['task_manifest']['steps'][0]['params']['threshold'] = 10
    with pytest.raises(ContractError) as caught:
        bindable_plan(RunPlan.model_validate(raw))
    assert caught.value.code == 'stale_plan_identity'
    changed = RunPlan.model_validate(raw).with_identity().model_dump(mode='json')
    changed['units'][0]['placement']['executor'] = 'ssh'
    with pytest.raises(ContractError) as caught:
        bindable_plan(RunPlan.model_validate(changed).with_identity())
    assert caught.value.code == 'unsupported_target'


def test_runtime_parameters_create_new_identity_preserve_frozen_values_without_defaults(tmp_path):
    original = plan_for(tmp_path / 'data.fixture')
    before = original.canonical_json()
    values = {'native-chain': {'transform': {'threshold': 7, 'flag': False, 'optional': None, 'empty': []}}}
    updated = _parameters(original, values)
    assert original.canonical_json() == before
    assert updated.plan_id != original.plan_id
    params = updated.units[0].payload['task_manifest']['steps'][0]['params']
    assert params == {'threshold': 7, 'flag': False, 'optional': None, 'empty': ()}
    assert updated.parameters_digest == sha256_hex(values)
    assert updated.units[0].payload['task_manifest']['sources']['matrix']['args']['flag'] is False
    assert validate_run_plan(updated) == updated


@pytest.mark.parametrize('values', [{}, {'unknown': {}}, {'native-chain': {}},
                                   {'native-chain': {'wrong-node': {}}}])
def test_runtime_parameter_snapshot_requires_exact_units_and_nodes(tmp_path, values):
    with pytest.raises(ContractError):
        _parameters(plan_for(tmp_path / 'data.fixture'), values)


def test_runtime_parameters_reject_engine_owned_names(tmp_path):
    with pytest.raises(ContractError):
        _parameters(plan_for(tmp_path / 'data.fixture'), {'native-chain': {'transform': {'_input_names': ['override']}}})


def test_check_mode_is_read_only_for_immutable_payload_and_bundle(tmp_path):
    source = tmp_path / 'data.fixture'
    source.write_bytes(b'synthetic input')
    root = tmp_path / 'bundle'
    bundle_at(root, source)
    before = inventory(root)
    checked = run_bundle(root, check=True)
    assert checked['status'] == 'ready'
    assert checked['network_resolution'] is False
    assert inventory(root) == before
    assert not (root / 'work').exists()
    assert not (root / 'results').exists()


@pytest.mark.parametrize('change', ['missing', 'unknown'])
def test_check_requires_exact_external_input_bindings(tmp_path, change):
    source = tmp_path / 'data.fixture'
    source.write_bytes(b'synthetic input')
    root = tmp_path / 'bundle'
    bundle_at(root, source)
    supplied = {} if change == 'missing' else {'native-chain-matrix': str(source), 'unused': str(source)}
    override = tmp_path / 'inputs-override.json'
    _write(override, supplied)
    with pytest.raises(ContractError):
        run_bundle(root, inputs=override, check=True)


def test_renamed_runtime_input_rebinds_payload_and_unit_identity_consistently(tmp_path):
    first = tmp_path / 'original.fixture'
    second = tmp_path / 'renamed.fixture'
    first.write_bytes(b'same input content')
    second.write_bytes(first.read_bytes())
    root_a, root_b = tmp_path / 'bundle-a', tmp_path / 'bundle-b'
    bundle_at(root_a, first)
    bundle_at(root_b, second)
    override = tmp_path / 'renamed-input.json'
    _write(override, {'native-chain-matrix': str(second)})
    rebound = run_bundle(root_a, inputs=override, check=True)
    independently_bound = run_bundle(root_b, check=True)
    assert rebound['plan_id'] == independently_bound['plan_id']
    assert rebound['run_identity'] == independently_bound['run_identity']


@pytest.mark.parametrize('change', ['identity', 'manifest_identity'])
def test_kernel_rejects_stale_stored_plan_identity_before_parameter_changes(tmp_path, change):
    source = tmp_path / 'data.fixture'
    source.write_bytes(b'synthetic input')
    root = tmp_path / 'bundle'
    plan = bundle_at(root, source)
    if change == 'identity':
        path = root / 'payload' / 'plan.json'
        raw = json.loads(path.read_text(encoding='utf-8'))
        raw['plan_id'] = 'f' * 64
        _write(path, raw)
        # Isolate the plan-identity gate from the outer file-integrity gate.
        refresh_inventory(root, plan)
    else:
        path = root / 'bundle.json'
        raw = json.loads(path.read_text(encoding='utf-8'))
        raw['plan_id'] = 'f' * 64
        _write(path, raw)
    with pytest.raises(ContractError):
        run_bundle(root, check=True)


def test_payload_corruption_and_missing_implementation_coverage_block_export(tmp_path):
    source = tmp_path / 'data.fixture'
    source.write_bytes(b'synthetic input')
    root = tmp_path / 'bundle'
    plan = bundle_at(root, source)
    (root / 'payload' / 'plan.json').write_text('{}')
    with pytest.raises(ContractError):
        inspect_bundle(root)
    raw = plan.model_dump(mode='json')
    raw['implementations'] = {'synthetic': {'kind': 'operator', 'implementation': {'code_sha': 'c' * 64}}}
    selected = RunPlan.model_validate(raw).with_identity()
    with pytest.raises(ContractError) as caught:
        validate_coverage(selected, {})
    assert caught.value.code == 'export_missing_resource'
    with pytest.raises(ContractError):
        validate_coverage(selected, {'synthetic': {'implementation': {'code_sha': 'd' * 64},
                                                'files': {'wrong.py': {'path': 'wrong.py', 'sha256': 'e' * 64}}}})


def test_collector_rejects_missing_explicit_kernel_roots_and_changed_files(tmp_path):
    with pytest.raises(ContractError):
        kernel_files(tmp_path, modules=('operon.missing_required_kernel',))
    source = tmp_path / 'source'
    source.mkdir()
    (source / 'operator.py').write_text('saved implementation')
    with pytest.raises(ContractError) as caught:
        collect(source, tmp_path / 'output', {'operator.py': {'path': 'operator.py', 'sha256': 'f' * 64}})
    assert caught.value.code == 'export_missing_resource'


def test_work_and_output_directories_cannot_modify_immutable_payload(tmp_path):
    source = tmp_path / 'data.fixture'
    source.write_bytes(b'synthetic input')
    root = tmp_path / 'bundle'
    bundle_at(root, source)
    before = inventory(root / 'payload')
    for options in ({'work_dir': root / 'payload' / 'work'}, {'output_dir': root / 'payload' / 'results'}):
        with pytest.raises(ContractError) as caught:
            run_bundle(root, **options)
        assert caught.value.code == 'invalid_output_path'
    assert inventory(root / 'payload') == before


def test_collector_does_not_mistake_imported_attributes_for_modules(tmp_path):
    package = tmp_path / 'operon'
    (package / 'context').mkdir(parents=True)
    (package / '__init__.py').write_text('from .context import Context\n')
    (package / 'context/__init__.py').write_text('class Context: pass\n')
    from operon.export.collector import module_file
    assert module_file(tmp_path, 'operon.Context') is None
    assert module_file(tmp_path, 'operon.context') == package / 'context/__init__.py'
    assert set(kernel_files(tmp_path, modules=('operon',))) == {'operon/__init__.py', 'operon/context/__init__.py'}
