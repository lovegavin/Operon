"""RunPlan adapters under the existing coordinator, grants and process supervisor.

This executor never grants memory or launches outside ProcessExecutor. Binding
is deployment data (paths/generations), separate from the canonical plan.
"""
from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path

from operon.contracts.base import ContractError, sha256_hex
from operon.contracts.run_plan import RunPlan
from operon.engine.executor import ProcessExecutor, ExecutionResult
from operon.engine.supervisor import LaunchSpec
from operon.engine.fs import atomic_json
from operon.environment_store.verification import confined
from operon.environment_store.builders import isolated_environment
from operon.bytecode import io_path, executable_path
from .invocation import InvocationContext, ExitReceipt, PreparedInvocation
from .adapters.command import CommandInvocationAdapter
from .adapters.native import NativeInvocationAdapter


def unit_dependencies(plan):
    owners = {}
    for unit in plan.units:
        for node in unit.node_ids:
            if node in owners:
                raise ContractError('Node belongs to multiple execution units', code='invalid_plan_edge')
            owners[node] = unit.unit_id
    dependencies = {unit.unit_id: set() for unit in plan.units}
    for unit in plan.units:
        for binding in unit.input_bindings.values():
            if binding.startswith('artifact:'):
                parent, separator, port = binding[len('artifact:'):].partition('/')
                if not separator or not port or parent not in dependencies or parent == unit.unit_id:
                    raise ContractError('Artifact binding must name another execution unit and output', code='invalid_plan_edge')
                dependencies[unit.unit_id].add(parent)
    for edge in plan.edges:
        source, target = owners.get(edge['source']), owners.get(edge['target'])
        if source and target and source != target:
            dependencies[target].add(source)
    pending, complete = dict(dependencies), set()
    while pending:
        ready = {key for key, parents in pending.items() if parents <= complete}
        if not ready:
            raise ContractError('Execution-unit dependencies contain a cycle', code='invalid_plan_edge')
        complete.update(ready)
        pending = {key: value for key, value in pending.items() if key not in ready}
    return dependencies


def bind_paths(value, bindings, *, encoded_refs=()):
    """Resolve only explicit storage:// identifiers, never arbitrary strings."""
    if isinstance(value, str) and value.startswith('storage://'):
        from urllib.parse import unquote
        identifier, _, relative = value[len('storage://'):].partition('/')
        if value in encoded_refs:
            identifier, relative = unquote(identifier), unquote(relative)
        if identifier not in bindings:
            raise ContractError('Storage binding is missing: ' + identifier, code='missing_binding')
        return str(confined(bindings[identifier], relative))
    if isinstance(value, dict):
        return {key: bind_paths(item, bindings, encoded_refs=encoded_refs) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [bind_paths(item, bindings, encoded_refs=encoded_refs) for item in value]
    return value


class RunPlanExecutor(ProcessExecutor):
    capability = 'invocation-v1'

    def __init__(self, root, *, environment_store, package_root, bindings):
        self.environments = environment_store
        self.package_root = Path(package_root).resolve()
        self.bindings = bindings
        self.prepared = {}
        super().__init__(root, command_builder=self._command, environment_store=environment_store)

    def directory(self, context):
        # Unit labels are metadata, not directory components. Including a label
        # and a second 'nodes' level made CreateProcess's current directory
        # exceed Windows MAX_PATH even when every file used extended paths.
        # Keep the per-run partition and globally unique attempt identity.
        previous = super().directory(context)
        if io_path(previous / 'prepared.json').is_file():
            return previous  # Adopt an already prepared attempt without moving it.
        return io_path(confined(self.root / 'runs',
            context.run['id'] + '/attempts/' + context.attempt_id))

    def _prepare(self, context):
        plan = RunPlan.model_validate(context.plan['graph'])
        unit = next(item for item in plan.units if item.unit_id == context.unit['local_id'])
        ref = unit.invocation.environment_ref
        environment = self.bindings['environments'][ref]
        generation = environment['generation_id']
        binding = self.environments.binding(generation)
        requirements = {sha256_hex(item) for item in plan.environment_requirements}
        expected = plan.execution_policy.get('environment_refs', {}).get(ref)
        if expected is None and len(requirements) == 1:
            expected = next(iter(requirements))  # K02 single-chain compatibility
        if expected not in requirements or binding.requirement_digest != expected:
            raise ContractError('Bound generation does not satisfy frozen requirement', code='environment_unverified')
        from operon.contracts.storage import StorageInputRef, storage_input_path
        encoded_refs = {storage_input_path(StorageInputRef.model_validate(item))
                        for item in plan.execution_policy.get('storage_input_refs', ())}
        storage = {**self.bindings.get('storage', {}), '__code__': str(self.package_root)}
        for relative, expected_hash in plan.execution_policy.get('packaged_resources', {}).items():
            from operon.environment_store.verification import file_digest
            if file_digest(confined(self.package_root, relative)) != expected_hash:
                raise ContractError('Packaged resource changed', code='artifact_mismatch')
        payload = bind_paths(unit.model_dump(mode='json')['payload'], storage,
                             encoded_refs=encoded_refs)
        if unit.invocation.kind == 'native':
            from operon.storage.inputs import prepare_plan_inputs
            prepare_plan_inputs(plan, payload['task_manifest'], self.bindings.get('storage', {}))
        payload.setdefault('executable', environment['executable'])
        payload.setdefault('inputs', {})
        for port, source in unit.input_bindings.items():
            if source.startswith('artifact:'):
                parent, output = source[len('artifact:'):].split('/', 1)
                index = confined(self.root / 'runs' / context.run['id'] / 'published', parent + '.json')
                payload['inputs'][port] = json.loads(index.read_text(encoding='utf-8'))['outputs'][output]
            elif source.startswith('input:'):
                payload['inputs'][port] = self.bindings['inputs'][source[len('input:'):]]
        if unit.invocation.kind == 'native':
            from .native_bootstrap import validate_native_descriptors
            lowered_environment = payload.get('native_environment_requirement_digest')
            if lowered_environment is not None and lowered_environment != expected:
                raise ContractError('Native environment lowering differs from bound requirement', code='environment_unverified')
            validate_native_descriptors(payload.get('native_descriptors', ()), plan.implementations,
                payload['task_manifest'], environment_requirement_digest=lowered_environment)
            payload['native_implementations'] = {item['id']: plan.model_dump(mode='json')['implementations'][item['id']]
                for item in payload['native_descriptors']}
            audit = plan.model_dump(mode='json')['diagnostics'].get('native_descriptor_audit', {})
            payload['native_descriptor_audit'] = {item['id']: audit[item['id']] for item in payload['native_descriptors']
                                                   if item['id'] in audit}
            for port, record in payload['inputs'].items():
                from .codecs import validate_reference
                path = validate_reference(record)
                payload['task_manifest']['sources'][port]['path'] = str(path)
                if record['representation'] == 'form':
                    runtime = payload['task_manifest'].setdefault('runtime', {})
                    runtime.setdefault('exchange_inputs', []).append(port)
        elif unit.resource_request.process_reservation_bytes <= 0:
            raise ContractError('Foreign runtime requires a declared full-process memory reservation',
                                code='invalid_resource')
        granted = context.lease['committed'] if context.lease else None
        allocation = granted if granted else unit.resource_request
        memory = (allocation.managed_budget_bytes if unit.invocation.kind == 'native'
                  else allocation.process_reservation_bytes)
        threads = granted.cpu_threads if granted else unit.resource_request.cpu_threads
        invocation_context = InvocationContext(self.directory(context), context.attempt_id, context.run['id'],
            unit.unit_id, context.fence, payload, memory_bytes=memory, threads=threads)
        if unit.invocation.kind == 'native':
            adapter = NativeInvocationAdapter()
        else:
            adapter = CommandInvocationAdapter(self.environments, generation, package_root=self.package_root)
        prepared = adapter.prepare(unit.invocation, invocation_context)
        if unit.invocation.kind == 'native':
            envroot = self.environments.root / 'generations' / generation / 'payload'
            python = confined(envroot, environment['executable'])
            if not io_path(python).is_file():
                raise ContractError('Locked executable is unavailable', code='environment_unverified')
            from operon.environment_store.closures import materialize, execution_environment
            closures = materialize(envroot, self.environments.root / 'runtime-caches',
                                   python=python)
            if closures['python']:
                python = Path(closures['python'])
            # CPython resolves junctions during getpath initialization; a short
            # junction to a long prefix can fail before importing any module.
            # Its native extended-path spelling supports the verified prefix.
            # Windows R validates its ordinary physical paths separately.
            # Standard Python boot with only bundle-owned code/package directories.
            bootstrap = prepared.context.attempt_root / 'bootstrap.py'
            native_paths = [str(io_path(self.package_root)), *[str(io_path(confined(envroot, name)))
                for name in payload.get('native_shared_targets', ())],
                *[str(io_path(p)) for p in closures['python_packages']], str(io_path(envroot / 'packages'))]
            bootstrap.write_text('import sys\nsys.path[:0] = ' + repr([
                *native_paths]) +
                '\nfrom operon.bytecode import enable_long_import_paths\nenable_long_import_paths()\n' +
                '\nfrom operon.execution.worker_main import main\nraise SystemExit(main())\n', encoding='utf-8')
            env = execution_environment(closures, isolated_environment(envroot))
            scratch = prepared.context.attempt_root / 'scratch'
            scratch.mkdir(exist_ok=True)
            # R's Windows CRT crashes on a gratuitous \\?\ TMP prefix. Native
            # Python I/O retains extended paths; tool-facing paths use Win32
            # spelling whenever it fits, without changing the scratch owner.
            scratch_name = executable_path(scratch)
            import os
            if os.name == 'nt' and (closures['r'] or 'Rscript' in closures['tools']):
                from .foreign_paths import r_scratch
                scratch_name = str(r_scratch(prepared.context.attempt_root))
            env.update(TMP=scratch_name, TEMP=scratch_name, TMPDIR=scratch_name,
                       OMP_NUM_THREADS=str(threads), OPENBLAS_NUM_THREADS=str(threads),
                       OPERON_BASE_PATHS=json.dumps(native_paths), OPERON_ENVIRONMENT_ROOT=str(envroot))
            for name, relative in payload.get('native_external_interpreters', {}).items():
                env['OPERON_ENV_' + name.upper()] = str(confined(envroot, relative))
            prepared = replace(prepared, command=(str(io_path(python)), '-I', '-B', str(io_path(bootstrap)),
                '--invocation', str(prepared.context.attempt_root / 'invocation.json')), environment=env)
            if payload.get('plugins_lock'):
                atomic_json(prepared.task_dir / 'plugins.lock.json', payload['plugins_lock'])
        self.prepared[context.attempt_id] = (adapter, prepared)
        atomic_json(prepared.context.attempt_root / 'prepared.json', {
            'format': 'operon.prepared-invocation', 'schema_version': 1,
            'plan_id': plan.plan_id, 'attempt_id': context.attempt_id, 'fence': context.fence,
            'run_id': context.run['id'], 'unit_id': unit.unit_id, 'generation_id': generation,
            'payload': payload, 'memory_bytes': memory, 'threads': threads,
            'task_dir': prepared.task_dir.relative_to(prepared.context.attempt_root).as_posix(),
            'task_manifest': prepared.task_manifest_path.relative_to(prepared.context.attempt_root).as_posix()})
        return generation, prepared

    def _restore(self, context):
        """Reattach read-only collection; never re-prepare or spawn on recovery."""
        if context.attempt_id in self.prepared:
            return self.prepared[context.attempt_id]
        root = self.directory(context)
        saved = json.loads((root / 'prepared.json').read_text(encoding='utf-8'))
        plan = RunPlan.model_validate(context.plan['graph'])
        unit = next(item for item in plan.units if item.unit_id == context.unit['local_id'])
        if (saved.get('format') != 'operon.prepared-invocation' or saved.get('schema_version') != 1
                or saved['plan_id'] != plan.plan_id or saved['attempt_id'] != context.attempt_id
                or saved['fence'] != context.fence or saved['run_id'] != context.run['id']
                or saved['unit_id'] != unit.unit_id):
            raise ContractError('Prepared invocation does not match attempt', code='recovery_required')
        selected = self.bindings['environments'][unit.invocation.environment_ref]
        if saved['generation_id'] != selected['generation_id']:
            raise ContractError('Prepared invocation environment differs', code='recovery_required')
        adapter = NativeInvocationAdapter() if unit.invocation.kind == 'native' else CommandInvocationAdapter(
            self.environments, saved['generation_id'], package_root=self.package_root)
        invocation_context = InvocationContext(root, context.attempt_id, context.run['id'], unit.unit_id,
            context.fence, saved['payload'], memory_bytes=saved['memory_bytes'], threads=saved['threads'])
        task_dir = root if saved['task_dir'] == '.' else confined(root, saved['task_dir'])
        prepared = PreparedInvocation(unit.invocation, invocation_context, task_dir,
            confined(root, saved['task_manifest']), root / 'outputs', (), {})
        self.prepared[context.attempt_id] = (adapter, prepared)
        return adapter, prepared

    def reconcile(self, context):
        result = super().reconcile(context)
        if result.state in ('running', 'dead'):
            try:
                self._restore(context)
            except (OSError, ValueError, KeyError, TypeError) as exc:
                return ExecutionResult('unknown', identity=result.identity, tree_alive=result.tree_alive,
                    error=str(exc), detail='recovery_required')
        if result.state == 'dead':
            return self.poll(context)
        return result

    def _command(self, context):
        from .windows_paths import attempt_launch_cwd
        generation, prepared = self._prepare(context)
        cwd = attempt_launch_cwd(self.root, prepared.context.attempt_root,
                                 run_id=context.run['id'], attempt_id=context.attempt_id)
        return LaunchSpec(prepared.command, str(cwd), prepared.environment,
                          str(prepared.context.attempt_root / 'logs' / 'worker.log'),
                          # The adapter selected the executable spelling for its runtime.
                          # Python needs its extended path even when only a loaded DLL
                          # exceeds MAX_PATH; R validates its ordinary physical spelling.
                          executable=prepared.command[0], generation_id=generation)

    def poll(self, context):
        result = super().poll(context)
        self._release_scratch(context, result)
        if result.state != 'succeeded':
            return result
        try:
            adapter, prepared = self._restore(context)
        except (OSError, ValueError, KeyError, TypeError) as exc:
            return ExecutionResult('unknown', error=str(exc), detail='recovery_required')
        outputs = adapter.collect(prepared, ExitReceipt(result.exit_code, 'succeeded', result.tree_alive))
        if outputs.status != 'complete':
            return replace(result, state='failed', error=outputs.error)
        return result

    def _release_scratch(self, context, result):
        if result.state in ('succeeded', 'failed', 'cancelled') and not result.tree_alive:
            from .foreign_paths import release_r_scratch
            try:
                release_r_scratch(self.directory(context))
            except (OSError, ValueError):
                pass  # Preserve receipt for cleanup; never mask scientific status.

    def cancel(self, context, *, timeout=10.0):
        result = super().cancel(context, timeout=timeout)
        self._release_scratch(context, result)
        return result

    def publish(self, attempt, result, committer):
        adapter, prepared = self.prepared[attempt['id']]
        files = [path.relative_to(prepared.output_dir).as_posix()
                 for path in prepared.output_dir.rglob('*') if path.is_file()]
        receipt = committer.commit_existing(attempt=attempt, unit=attempt['unit'], fence=attempt['fence'],
            source_root=prepared.output_dir, files=files, run_id=attempt['run']['id'], kind='invocation-output')
        manifest = json.loads((prepared.context.attempt_root / prepared.spec.output_manifest).read_text(encoding='utf-8'))
        if manifest.get('format') == 'operon.foreign-outputs':
            outputs = manifest['outputs']
        else:
            exchange = prepared.output_dir / 'exchange.json'
            raw = json.loads(exchange.read_text(encoding='utf-8')) if exchange.exists() else {}
            from .codecs import file_reference
            from operon.environment_store.verification import inventory
            outputs = {name: file_reference(value['path'], representation='form', metadata={
                'inventory': inventory(Path(value['path']).parent)}) for name, value in raw.items()}
        atomic_json(self.root / 'runs' / attempt['run']['id'] / 'published' /
                    (attempt['unit']['local_id'] + '.json'), {'receipt': receipt, 'outputs': outputs})
        return receipt
