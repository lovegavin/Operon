"""Automatic canvas-to-RunPlan preparation shared by GUI and headless clients.

Preparation never submits science or installs packages. The resulting immutable
body is persisted before submission, so a lost response is retried verbatim.
"""
from copy import deepcopy
import json
import os
from pathlib import Path
import shutil
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor

from .contracts.base import ContractError, sha256_hex
from .contracts.run_plan import RunPlan
from .contracts.plan_operations import PlanExecutionBinding
from .contracts.plan_export import PlanExportRequest
from .engine.fs import atomic_json, FileLock
from .environment_store.verification import file_digest, confined
from .bytecode import io_path


class CanvasPlans:
    def __init__(self, app):
        self.app = app
        self.root = app.service.root
        self.directory = app.service.directory / 'canvas-plans'
        self.directory.mkdir(exist_ok=True)
        self.pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix='canvas-prepare')
        self.slots = threading.BoundedSemaphore(2)
        self.closed = threading.Event()
        self._active = set()
        self._mutex = threading.Lock()

    @property
    def active(self):
        with self._mutex:
            return bool(self._active)

    def _path(self, key):
        return self.directory / (sha256_hex(key) + '.json')

    def start(self, graph, request_id):
        if not isinstance(request_id, str) or not 1 <= len(request_id) <= 200:
            raise ContractError('A stable request ID is required', code='invalid_request')
        digest = sha256_hex(graph)
        path = self._path(request_id)
        with FileLock(path.with_suffix('.lock'), timeout=5):
            if io_path(path).exists():
                record = json.loads(io_path(path).read_text(encoding='utf-8'))
                if record['graph_digest'] != digest:
                    raise ContractError('Preparation ID already names a different canvas', code='idempotency_conflict')
                return self._recover(record, path)
            if self.closed.is_set() or not self.slots.acquire(blocking=False):
                raise ContractError('Another canvas is being prepared; retry shortly', code='busy')
            from .engine.supervisor import identity_for_pid
            identity = identity_for_pid(os.getpid())
            record = {'request_id': request_id, 'graph_digest': digest, 'status': 'preparing', 'phase': 'validate',
                      'owner': identity.to_json() if identity else None}
            try:
                atomic_json(path, record)
                with self._mutex:
                    self._active.add(request_id)
                self.pool.submit(self._work, deepcopy(graph), record, path)
            except BaseException:
                with self._mutex:
                    self._active.discard(request_id)
                self.slots.release()
                raise
        return record

    def status(self, request_id):
        try:
            path = self._path(request_id)
            with FileLock(path.with_suffix('.lock'), timeout=5):
                return self._recover(json.loads(io_path(path).read_text(encoding='utf-8')), path)
        except FileNotFoundError as exc:
            raise ContractError('Preparation was not found', code='preparation_not_found') from exc

    def _recover(self, record, path):
        from .engine.supervisor import identity_alive
        if record['status'] == 'preparing' and not identity_alive(record.get('owner')):
            record.update(status='failed', phase='interrupted', code='preparation_interrupted',
                          error='Preparation owner stopped. Prepare again; no workflow was submitted.')
            atomic_json(path, record)
        return record

    def cancel(self, request_id):
        # Persist the request; a different connected client may request cancellation.
        record = self.status(request_id)
        if record['status'] == 'preparing':
            atomic_json(self._path(request_id).with_suffix('.cancel.json'), {'cancel': True})
        return record

    def _work(self, graph, record, path):
        record = deepcopy(record)
        from .plugins import process_context
        owner = self
        class Cancellation:
            def is_set(self):
                return owner.closed.is_set() or io_path(path.with_suffix('.cancel.json')).exists()
        cancellation = Cancellation()
        process_context.cancel = cancellation
        def progress(phase):
            if cancellation.is_set():
                raise InterruptedError('Preparation cancelled; no workflow was submitted')
            record['phase'] = phase
            atomic_json(path, record)
        try:
            result = self.prepare(graph, progress=progress)
            record.update(status='ready', phase='ready', prepared=result)
        except Exception as exc:
            record.update(status='cancelled' if isinstance(exc, InterruptedError) else 'failed', phase='failed', error=str(exc),
                          code=getattr(exc, 'code', 'preparation_failed'),
                          next_actions=getattr(exc, 'next_actions', ()))
        finally:
            try:
                atomic_json(path, record)
            finally:
                with self._mutex:
                    self._active.discard(record['request_id'])
                self.slots.release()
                process_context.cancel = None

    def prepare(self, graph, *, progress=lambda phase: None):
        from src.web.models import Graph
        from src.web.source_paths import remote_profile
        from .export.automatic import collect_canvas_code, provider_roots, bind_declared_resources
        from .environment_store.canvas import prepare_python
        prepared = self.app.prepare(graph)
        checked = self.app.validate(prepared, require_files=True)
        prepared = self.app._execution_binding(prepared, checked)
        prepared = self._placement(prepared, checked)
        if remote_profile(prepared):
            return self._remote(prepared, progress)
        plan = self.app.compile_plan(prepared, require_files=True)
        descriptors = plan.diagnostics.get('native_descriptor_audit', {})
        manager = self.app.service.plugins
        state = manager.snapshot(prepared)
        progress('environment')
        envroot = self.directory / 'environments'
        guard = self.app.service.execution_environment_guard()
        ticket = 'canvas-environment-' + uuid.uuid4().hex
        if guard:
            guard.acquire_job(ticket, service=self.app.service.owner, workspace=str(self.root),
                              environment=self.app.service.environment_identity())
        try:
            from .plugins import process_context
            cancellation = getattr(process_context, 'cancel', None) or self.closed
            environment = prepare_python(envroot, manager.python_for(state), state, list(descriptors.values()),
                                         cancel=cancellation.is_set, r_root=manager.directory.parent / 'runtimes/r')
        finally:
            if guard:
                guard.release_job(ticket)
        data = plan.model_dump(mode='json')
        resources = bind_declared_resources(data, workspace=self.root, base_dir=prepared.base_dir,
                                            input_roots=self.app.service.settings.input_roots)
        requirement = environment['requirement']
        digest = sha256_hex(requirement)
        data['environment_requirements'] = [requirement]
        data['execution_policy']['environment_refs'] = {'cpython': digest}
        data['execution_policy']['target'] = requirement['target']
        data['execution_policy'].pop('storage_input_refs', None)
        data['storage_bindings'] = []
        inputs = {}
        progress('inputs')
        for unit in data['units']:
            unit['placement']['target'] = requirement['target']
            unit['payload']['native_environment_requirement_digest'] = digest
            unit['payload']['native_shared_targets'] = environment['shared_targets']
            unit['payload']['native_external_interpreters'] = environment.get('external_interpreters', {})
            unit['payload']['native_isolation_targets'] = {
                key: [environment['target_paths'][str(confined(Path(state['_runtime_root']), value))]
                      for value in d['execution'].get('paths', [])]
                for key, d in descriptors.items() if (d.get('execution') or {}).get('mode') == 'isolated'}
            for name, source in unit['payload']['task_manifest'].get('sources', {}).items():
                original = Path(source['path'])
                if not original.is_absolute():
                    original = self.root / original
                source_digest = file_digest(original)
                # Outside-workspace inputs are copied into content-addressed groups;
                # inside inputs stay in place and are checked by the worker ABI.
                if not original.resolve().is_relative_to(self.root):
                    reader = descriptors.get(source.get('reader'), {})
                    group = self.app.executions._file_group({'kind': 'local'}, str(original),
                                                           prepared.base_dir, reader)
                    fingerprints = {item['name']: file_digest(Path(item['path'])) for item in group}
                    destination = self.directory / 'inputs' / sha256_hex(fingerprints) / original.name
                    io_path(destination.parent).mkdir(parents=True, exist_ok=True)
                    for item in group:
                        final = destination.parent / item['name']
                        if not io_path(final).exists():
                            temporary = final.with_name(final.name + '.' + uuid.uuid4().hex)
                            shutil.copyfile(io_path(item['path']), io_path(temporary))
                            if file_digest(temporary) != fingerprints[item['name']]:
                                io_path(temporary).unlink()
                                raise ContractError('Input changed during preparation', code='input_changed')
                            io_path(temporary).replace(io_path(final))
                    original = destination
                key = unit['unit_id'] + '-' + name
                inputs[key] = {'path': original.relative_to(self.root).as_posix(), 'representation': 'file',
                    'size_bytes': original.stat().st_size, 'sha256': source_digest, 'metadata': {}}
                unit['input_bindings'][name] = 'input:' + key
                source['path'] = 'input:' + key
        progress('code')
        app_root = self.app.service.settings.code_root or Path(__file__).resolve().parents[1]
        from .export.collector import kernel_files
        kernel = kernel_files(app_root)
        data['execution_policy']['kernel_digest'] = sha256_hex(kernel)
        plan = RunPlan.model_validate(data).with_identity()
        package = self.directory / 'code' / plan.plan_id
        roots = provider_roots(manager, state, app_root)
        # Atomic complete-code publication. Failed preparations do not publish a
        # usable package or replace code referenced by an accepted run.
        with FileLock(package.with_suffix('.lock'), timeout=600):
            receipt = package.parent / (package.name + '.manifest.json')
            if io_path(receipt).exists():
                implementations = json.loads(io_path(receipt).read_text(encoding='utf-8'))
            else:
                temporary = package.with_name(package.name + '.partial-' + uuid.uuid4().hex)
                implementations = collect_canvas_code(plan, temporary, application_root=app_root, roots=roots, kernel=kernel)
                from .export.collector import collect
                for relative, resource in resources.items():
                    source = Path(resource['source'])
                    collect(source.parent, temporary, {relative: {'path': source.name,
                        'sha256': resource['sha256'], 'role': 'resource'}})
                if io_path(package).exists():
                    raise ContractError('Incomplete code publication requires recovery', code='recovery_required')
                io_path(temporary).rename(io_path(package))
                atomic_json(receipt, implementations)
        binding = PlanExecutionBinding(package_root=package.relative_to(self.root).as_posix(),
            environment_store=envroot.relative_to(self.root).as_posix(),
            environments={'cpython': {key: environment[key] for key in ('generation_id', 'executable')}}, inputs=inputs)
        return {'plan': plan.model_dump(mode='json'), 'binding': binding.model_dump(mode='json'),
                'implementations': implementations, 'profile_id': None,
                'extra_files': {name: {'path': name, 'sha256': item['sha256'], 'role': 'resource'}
                                for name, item in resources.items()}}

    @staticmethod
    def _placement(graph, checked):
        """Respect existing placement decisions; never silently run on another host."""
        from src.web.execution_plan import settings, target, target_key, source_location
        config = settings(graph)
        targets = {target_key(unit['target']): target(unit['target'])
                   for unit in checked.get('execution_plan', {}).get('units', ())}
        if not targets:
            targets = {target_key(value): target(value) for value in config['node_targets'].values()}
            if not targets:
                targets = {target_key(config): target(config)}
        if len(targets) != 1:
            raise ContractError('This canvas spans execution hosts. Select one host for RunPlan execution/export.',
                code='multi_host_plan_required', next_actions=({'action': 'choose_execution_host'},))
        chosen = next(iter(targets.values()))
        if target_key(chosen) == target_key(config):
            return graph
        result = graph.model_copy(deep=True)
        # Keep data ownership independent of a new automatic compute placement.
        for node in result.nodes:
            if node.source and node.source.location is None:
                node.source.location = source_location(node, config)
            for name in node.params:
                config['file_locations'].setdefault(f'{node.id}.params.{name}', target(config))
        result.runtime['execution'] = {**config, **chosen, 'mode': 'manual', 'node_targets': {}}
        return result

    def export_request(self, prepared, request_id, output=None):
        if prepared.get('profile_id'):
            raise ContractError('Export on the execution host using its canvas API', code='remote_export_required')
        binding = prepared['binding']
        return PlanExportRequest(plan=prepared['plan'], request_id=request_id,
            source_root=binding['package_root'], environment_store=binding['environment_store'],
            environments=binding['environments'], implementations=prepared['implementations'],
            extra_files=prepared.get('extra_files', {}),
            management_environment='cpython', input_bindings={key: value['path'] for key, value in binding['inputs'].items()},
            input_formats={key: value['representation'] for key, value in binding['inputs'].items()},
            output=output or ('exports/route-' + sha256_hex(request_id)[:16]))

    def execute(self, preparation_id, *, action, request_id, output=None):
        record = self.status(preparation_id)
        if record['status'] != 'ready':
            raise ContractError('Canvas is not prepared', code='preparation_not_ready')
        prepared = record['prepared']
        if action not in ('run', 'export'):
            raise ContractError('Unknown canvas action', code='invalid_request')
        path = self.directory / ('action-' + sha256_hex(request_id) + '.json')
        body = {'preparation_id': preparation_id, 'action': action, 'request_id': request_id, 'output': output}
        with FileLock(path.with_suffix('.lock'), timeout=60):
            if io_path(path).exists():
                old = json.loads(io_path(path).read_text(encoding='utf-8'))
                if old['body'] != body:
                    raise ContractError('Action ID was already used', code='idempotency_conflict')
                if 'result' in old:
                    return old['result']
            atomic_json(path, {'body': body, 'status': 'pending'})
            if prepared.get('profile_id'):
                result = self.app.service.remotes.call(prepared['profile_id'], 'canvas.execute',
                    {**body, 'preparation_id': prepared['remote_preparation_id']})
                if action == 'run':
                    result = self._remember_remote(prepared['profile_id'], result)
            elif action == 'run':
                result = self.app.plans.submit({'plan': prepared['plan'], 'binding': prepared['binding'],
                                               'request_id': request_id})
            else:
                result = self.app.plan_exports.submit(self.export_request(prepared, request_id, output))
            atomic_json(path, {'body': body, 'status': 'accepted', 'result': result})
            return result

    def _remember_remote(self, profile, result):
        identifier = 'remote-plan-' + sha256_hex([profile, result['run_id']])
        atomic_json(self.directory / (identifier + '.json'), {'profile_id': profile, 'run_id': result['run_id']})
        return {**result, 'run_id': identifier}

    def remote_reference(self, identifier):
        import re
        if not re.fullmatch(r'remote-plan-[a-f0-9]{64}', identifier):
            raise ContractError('Invalid remote plan identifier', code='invalid_request')
        try:
            return json.loads((self.directory / (identifier + '.json')).read_text(encoding='utf-8'))
        except FileNotFoundError as exc:
            raise ContractError('Remote plan is not owned by this workspace', code='plan_not_found') from exc

    def history(self):
        paths = sorted(self.directory.glob('action-*.json'), key=lambda p: p.stat().st_mtime, reverse=True)[:100]
        return [json.loads(p.read_text(encoding='utf-8')) for p in paths]

    def outcome(self, request_id):
        path = self.directory / ('action-' + sha256_hex(request_id) + '.json')
        record = json.loads(path.read_text(encoding='utf-8'))
        if 'result' not in record:
            return record
        result = record['result']
        if record['body']['action'] == 'run':
            return self.app.plans.details(result['run_id'])
        preparation = self.status(record['body']['preparation_id'])['prepared']
        if preparation.get('profile_id'):
            return self.app.service.remotes.call(preparation['profile_id'], 'canvas.outcome', {'request_id': request_id})
        return self.app.plan_exports.details(result['id'])

    def _remote(self, graph, progress):
        from src.web.execution_plan import source_location, settings
        from src.web.source_paths import remote_profile
        from src.web.transfers import TransferClient
        from operon.engine.transport import transport_admission
        key = remote_profile(graph)
        remotes = self.app.service.remotes
        remotes.ensure(key)
        # Fail before transferring data to an older server.
        capabilities = remotes.call(key, 'canvas.capabilities', {})
        if capabilities.get('version') != 1:
            raise ContractError('Upgrade the server to use canvas RunPlans', code='remote_capability_required')
        client = TransferClient(lambda method, params=None: remotes.call(key, method, params or {}),
                                self.directory / 'transfers' / key)
        config = settings(graph)
        graph = graph.model_copy(deep=True)
        catalog = self.app.catalog_for(graph)
        readers = {r['id']: r for r in catalog['readers']}
        operators = {r['id']: r for r in catalog['operators']}
        # Reuse descriptor-driven companion discovery and the resumable transfer
        # protocol. The pool still accounts for the transport buffers.
        admission = transport_admission(self.app.service)
        ticket = 'canvas-' + uuid.uuid4().hex
        if not admission.reserve(ticket, {'kind': 'transport', 'reserved_bytes': client.buffer_budget_bytes,
                                          'cpu_threads': 0}):
            raise ContractError('Transfer memory is temporarily occupied', code='busy')
        try:
            def move(value, location, base, reader=None):
                if location['kind'] == 'ssh':
                    if location.get('profile_id') != key:
                        raise ContractError('Cross-server inputs require explicit storage bindings', code='unsupported_boundary')
                    return value
                files = self.app.executions._file_group(location, value, base, reader)
                references = []
                for item in files:
                    reference = client.upload(item['path'], cancel=self.closed.is_set,
                        progress=lambda state: progress('upload:' + str(state.get('percent', state.get('phase', '')))), name=item['name'])
                    references.append({'name': item['name'], 'reference': reference})
                materialized = client.materialize(references, cancel=self.closed.is_set)
                return materialized['paths'][files[0]['name']]
            for node in graph.nodes:
                if not node.source:
                    if node.kind == 'operator':
                        for name, schema in operators[node.operator]['parameters_schema'].get('properties', {}).items():
                            if schema.get('x-operon-path') and node.params.get(name):
                                location = config.get('file_locations', {}).get(f'{node.id}.params.{name}', config)
                                node.params[name] = move(node.params[name], location, graph.base_dir)
                    continue
                location = source_location(node, config)
                reader = readers.get(node.source.reader, {})
                for name, schema in reader.get('parameters_schema', {}).get('properties', {}).items():
                    if schema.get('x-operon-path') and node.source.args.get(name):
                        where = config.get('file_locations', {}).get(f'{node.id}.source.args.{name}', location)
                        node.source.args[name] = move(node.source.args[name], where, graph.base_dir)
                node.source.path = move(node.source.path, location, graph.base_dir, reader)
                node.source.location = None
        finally:
            admission.release(ticket)
        graph.runtime['execution'] = {'kind': 'local', 'mode': 'manual'}
        graph.base_dir = remotes.profile(key)['workspace']
        remote_key = 'canvas-' + uuid.uuid4().hex
        result = remotes.call(key, 'canvas.prepare', {'graph': graph.model_dump(mode='json'), 'request_id': remote_key})
        try:
            while result['status'] == 'preparing':
                progress('server:' + result.get('phase', 'prepare'))
                if self.closed.wait(.5):
                    raise InterruptedError('Application is closing; server preparation receipt retained')
                result = remotes.call(key, 'canvas.status', {'request_id': remote_key})
        except InterruptedError:
            try:
                remotes.call(key, 'canvas.cancel', {'request_id': remote_key})
            except Exception:
                pass  # No science was submitted; remote receipt remains queryable.
            raise
        if result['status'] != 'ready':
            raise ContractError(result.get('error', 'Server preparation failed'), code=result.get('code', 'preparation_failed'))
        return {**result['prepared'], 'profile_id': key, 'remote_preparation_id': remote_key}

    def close(self):
        self.closed.set()
        self.pool.shutdown(wait=False, cancel_futures=False)
