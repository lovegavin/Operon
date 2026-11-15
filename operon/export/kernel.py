"""Bundle-local controller using the same coordinator, worker and memory engine."""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path
import time
import uuid

from operon.contracts.base import ContractError, sha256_hex
from operon.contracts.run_plan import RunPlan
from operon.engine.artifacts import ArtifactCommitter
from operon.engine.coordinator import Coordinator
from operon.engine.contracts import PoolSpec
from operon.engine.fs import FileLock, atomic_json
from operon.engine.state import StateStore
from operon.environment_store import EnvironmentStore
from operon.environment_store.verification import confined, file_digest, verify_inventory
from operon.execution.unit_executor import RunPlanExecutor, unit_dependencies
from operon.planning.validation import validate_run_plan
from operon.bytecode import io_path


def inspect_bundle(root):
    root = Path(root).resolve()
    manifest = json.loads((root / 'bundle.json').read_text(encoding='utf-8'))
    if manifest.get('format') != 'operon.portable' or manifest.get('status') != 'complete':
        raise ContractError('Bundle is not complete', code='incomplete_export')
    caches = manifest.get('managed_environment_caches', [])
    if caches:
        bindings = json.loads((root / 'payload/bindings.json').read_text())
        expected = sorted({'environments/generations/' + item['generation_id'] + '/payload'
                           for item in bindings['environments'].values()})
        if caches != expected:
            raise ContractError('Invalid managed cache boundaries', code='environment_corrupt')
        store = EnvironmentStore(root / 'payload/environments', create=False)
        from operon.environment_store.packages import verify
        for item in bindings['environments'].values():
            if not verify(store, item['generation_id']):
                raise ContractError('Missing environment packages', code='environment_corrupt')
    verify_inventory(root / 'payload', manifest['files'], excluded_roots=caches)
    for name, expected in manifest.get('launchers', {}).items():
        if name not in ('run.py', 'run.cmd', 'run.sh') or file_digest(root / name) != expected:
            raise ContractError('Bundle launcher changed after export', code='artifact_mismatch')
    return manifest


def _parameters(plan, values):
    """Editing a parameter file produces a NEW frozen plan; no live defaults."""
    raw = plan.model_dump(mode='json')
    known = {unit['unit_id'] for unit in raw['units']}
    if not isinstance(values, dict) or set(values) != known:
        raise ContractError('Parameter JSON must name exactly the exported execution units', code='invalid_parameters')
    for unit in raw['units']:
        payload = unit['payload']
        if unit['invocation']['kind'] == 'native':
            steps = payload['task_manifest']['steps']
            if not isinstance(values[unit['unit_id']], dict) or set(values[unit['unit_id']]) != set(unit['node_ids']):
                raise ContractError('Native parameter JSON differs from exported node IDs', code='invalid_parameters')
            for node, step in zip(unit['node_ids'], steps, strict=True):
                params = values[unit['unit_id']][node]
                if not isinstance(params, dict) or '_input_names' in params:
                    raise ContractError('Parameters must be objects without engine-owned _input_names', code='invalid_parameters')
                step['params'] = params
        else:
            if not isinstance(values[unit['unit_id']], dict):
                raise ContractError('Unit parameters must be an object', code='invalid_parameters')
            payload['parameters'] = values[unit['unit_id']]
            unit['invocation']['parameters_ref']['digest'] = sha256_hex(values[unit['unit_id']])
    raw['parameters_digest'] = sha256_hex(values)
    return RunPlan.model_validate(raw).with_identity()


def run_bundle(root, *, inputs=None, parameters=None, resume=False, work_dir=None, output_dir=None,
               memory=None, threads=None, check=False, prepare_only=False):
    root = Path(root).resolve()
    def progress(phase):
        if os.environ.get('OPERON_EXPORT_PROBE') == '1':
            print(f'[Operon portable probe] {phase}', file=sys.stderr, flush=True)
    progress('verify_bundle')
    manifest = inspect_bundle(root)
    plan = RunPlan.model_validate_json((root / 'payload' / 'plan.json').read_text(encoding='utf-8'))
    validate_run_plan(plan)
    if plan.plan_id != manifest['plan_id']:
        raise ContractError('Bundle manifest and plan identity differ', code='stale_plan_identity')
    plan = _parameters(plan, json.loads(Path(parameters or root / 'parameters.json').read_text(encoding='utf-8')))
    binding = json.loads((root / 'payload' / 'bindings.json').read_text(encoding='utf-8'))
    storage = {}
    identities = {}
    supplied = json.loads(Path(inputs or root / 'inputs.json').read_text(encoding='utf-8'))
    expected_inputs = {source[len('input:'):] if source.startswith('input:')
                       else source[len('storage://'):].split('/', 1)[0]
                       for unit in plan.units for source in unit.input_bindings.values()
                       if source.startswith(('input:', 'storage://'))}
    if 'required_inputs' in binding and set(binding['required_inputs']) != expected_inputs:
        raise ContractError('Input declaration differs from the frozen plan', code='missing_binding')
    if not isinstance(supplied, dict) or set(supplied) != expected_inputs:
        raise ContractError('Input JSON must contain exactly the exported input bindings', code='missing_binding')
    binding['inputs'] = {}
    for key, value in supplied.items():
        path = Path(value)
        path = path.resolve() if path.is_absolute() else (root / path).resolve()
        if not path.is_file():
            raise ContractError('Input file is missing: ' + key, code='input_missing')
        storage[key] = str(path.parent)
        identities[key] = {'sha256': file_digest(path), 'size': path.stat().st_size}
        from operon.execution.codecs import file_reference
        binding['inputs'][key] = file_reference(path, representation=binding.get('input_formats', {}).get(key, 'file'))
        # The binding basename may change: rewrite this explicit input reference
        # in the new frozen plan, never perform a global string substitution.
        raw = plan.model_dump(mode='json')
        for unit in raw['units']:
            for port, source in unit['input_bindings'].items():
                if source.startswith('storage://' + key + '/'):
                    unit['input_bindings'][port] = 'storage://' + key + '/' + path.name
            for source in unit['payload'].get('task_manifest', {}).get('sources', {}).values():
                if source['path'].startswith('storage://' + key + '/'):
                    source['path'] = 'storage://' + key + '/' + path.name
        plan = RunPlan.model_validate(raw).with_identity()
    binding['storage'] = storage
    store_root = root / 'payload' / 'environments'
    source_environments = EnvironmentStore(store_root, create=False)
    verified_generations = set()
    for value in binding['environments'].values():
        generation = value['generation_id']
        if generation not in verified_generations:
            progress('verify_source_environment')
            source_environments.binding(generation)
            verified_generations.add(generation)
    work = Path(work_dir or root / 'work').resolve()
    output = Path(output_dir or root / 'results').resolve()
    if work.is_relative_to((root / 'payload').resolve()) or output.is_relative_to((root / 'payload').resolve()):
        raise ContractError('Runtime output cannot modify immutable payload', code='invalid_output_path')
    identity = sha256_hex({'plan': plan.plan_id, 'inputs': identities,
                          'environments': binding['environments']})
    if check:
        missing = []
        for ref, value in binding['environments'].items():
            _, metadata, _ = source_environments._manifest(value['generation_id'])
            if metadata['identity']['builder'].get('fixups'):
                pointer = work / 'environments/references' / (metadata['requirement_digest'] + '.json')
                if not pointer.exists():
                    missing.append(ref)
                else:
                    target = EnvironmentStore(work/'environments', create=False)
                    deployed = target.binding(json.loads(pointer.read_text())['generation_id'])
                    value['generation_id'] = deployed.generation_id
        if missing:
            return {'status': 'preparation_required', 'environments': missing, 'network_resolution': False,
                    'next_action': '--prepare-only'}
        identity = sha256_hex({'plan': plan.plan_id, 'inputs': identities,
                              'environments': binding['environments']})
        return {'status': 'ready', 'plan_id': plan.plan_id, 'run_identity': identity,
                'units': len(plan.units), 'network_resolution': False}
    work.mkdir(parents=True, exist_ok=True)
    output.mkdir(parents=True, exist_ok=True)
    # One package instance owns this capacity domain. This is explicitly
    # standalone, not a second host-wide service started under Slurm/Studio.
    with FileLock(work / 'controller.lock', timeout=1):
        environments = EnvironmentStore(work / 'environments')
        deployed_generations = {}
        for value in binding['environments'].values():
            generation = value['generation_id']
            if generation in deployed_generations:
                value['generation_id'] = deployed_generations[generation]
                continue
            original, metadata, _ = source_environments._manifest(generation)
            if metadata['identity']['builder'].get('fixups'):
                from .environments import destination_binding
                deployed = destination_binding(source_environments, environments, generation)
                value['generation_id'] = deployed.generation_id
                deployed_generations[generation] = deployed.generation_id
                continue
            target = environments.root / 'generations' / generation
            if not target.exists():
                progress('copy_destination_environment')
                from operon.environment_store.packages import copy_generation, descriptor
                if descriptor(source_environments, generation) is not None:
                    copy_generation(source_environments, environments, generation)
                else:
                    # Old portable bundles are immutable input artifacts. Upgrade
                    # their working copy, never seal the original payload in place.
                    temporary = environments.root / 'staging' / uuid.uuid4().hex
                    shutil.copytree(io_path(original), io_path(temporary), symlinks=True)
                    os.replace(temporary, target)
            progress('verify_destination_environment')
            environments.binding(generation)
            deployed_generations[generation] = generation
        identity = sha256_hex({'plan': plan.plan_id, 'inputs': identities,
                              'environments': binding['environments']})
        if prepare_only:
            progress('preparation_complete')
            return {'status': 'ready', 'environments': binding['environments'],
                    'run_identity': identity, 'network_resolution': False}
        import psutil
        capacity = int(memory if memory is not None else psutil.virtual_memory().available * .9)
        cpu = int(threads if threads is not None else os.cpu_count() or 1)
        if capacity <= 0 or cpu < 1:
            raise ContractError('Memory and threads must be positive', code='invalid_resource')
        pool = PoolSpec('portable-' + sha256_hex(str(work))[:16], 'portable', 'standalone', capacity, 0, cpu,
                        scratch_bytes=int(psutil.disk_usage(str(work)).free), mode='coordinator')
        state = StateStore(work / 'engine.sqlite')
        state.ensure_pool(pool)
        executor = RunPlanExecutor(work, environment_store=environments, package_root=root / 'payload' / 'code', bindings=binding)
        committer = ArtifactCommitter(work, state)
        coordinator = Coordinator(state, pool, executor, workspace_id='bundle', principal='portable', root=work,
            artifact_committer=lambda attempt, result: executor.publish(attempt, result, committer))
        index_path = work / 'resume' / (identity + '.json')
        previous = json.loads(index_path.read_text(encoding='utf-8')) if resume and index_path.exists() else None
        key = previous['request_key'] if previous else 'portable:' + uuid.uuid4().hex
        parent_run_id = previous.get('parent_run_id') if previous else None
        if previous:
            prior = state.run(previous['run_id'])
            if prior['status'] in ('failed', 'cancelled'):
                parent_run_id = prior['id']
                key = 'portable-resume:' + sha256_hex({'parent': parent_run_id, 'identity': identity})
        dependencies = unit_dependencies(plan)
        units = [{'unit_id': unit.unit_id, 'node_ids': list(unit.node_ids), 'depends_on': sorted(dependencies[unit.unit_id]),
                  'requirement': unit.resource_request.model_dump(mode='json'), 'capability': 'invocation-v1',
                  'retry_limit': unit.retry_policy.maximum_attempts} for unit in plan.units]
        try:
            coordinator.claim()
            accepted = coordinator.submit(key=key, digest=identity, graph=plan.model_dump(mode='json'), parameters={},
                                          execution={'standalone': True, **({'resume_parent_run_id': parent_run_id}
                                                     if parent_run_id else {})}, units=units)
            run_id = accepted['run_id']
            if parent_run_id:
                from .resume import attach_verified_resume
                attach_verified_resume(state, root=work, parent_run_id=parent_run_id, run_id=run_id,
                    run_identity=identity, request_id=key, principal='portable', environment_store=environments)
            atomic_json(index_path, {'run_id': run_id, 'request_key': key, 'run_identity': identity,
                                    'parent_run_id': parent_run_id})
            atomic_json(output / 'run.json', {'run_id': run_id, 'run_identity': identity, 'work_dir': str(work)})
            while True:
                coordinator.run_once()
                record = state.run(run_id)
                if record['status'] in ('complete', 'failed', 'cancelled', 'recovery_required'):
                    break
                time.sleep(.05)
            # Verify committed results even when --resume reuses a completed run.
            for path in (work / 'runs' / run_id / 'published').glob('*.json'):
                published = json.loads(path.read_text(encoding='utf-8'))
                verification = committer.verify_existing(published['receipt'])
                if not verification['valid']:
                    raise ContractError('Committed output changed after publication', code='artifact_mismatch',
                                        details=verification)
            result = {'run_id': run_id, 'status': record['status'], 'reused': accepted['reused'],
                      'results': str(work / 'runs' / run_id / 'published'), 'work_dir': str(work)}
            atomic_json(output / 'run.json', result)
            return result
        except KeyboardInterrupt:
            if 'run_id' in locals():
                coordinator.cancel(run_id)
                coordinator.cancel_all(reason='bundle interrupted')
            raise
        finally:
            coordinator.stop()
            state.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle', type=Path, required=True)
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--prepare-only', action='store_true', help='Prepare destination bindings offline without starting a workflow')
    parser.add_argument('--inputs', type=Path)
    parser.add_argument('--parameters', type=Path)
    parser.add_argument('--resume', action='store_true')
    parser.add_argument('--work-dir', type=Path)
    parser.add_argument('--output-dir', type=Path)
    parser.add_argument('--memory', type=int, help='Process capacity in bytes')
    parser.add_argument('--threads', type=int)
    args = vars(parser.parse_args(argv))
    root = args.pop('bundle')
    result = run_bundle(root, **args)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result['status'] in ('ready', 'complete') else 1


if __name__ == '__main__':
    raise SystemExit(main())
