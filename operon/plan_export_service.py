"""Bounded application-owned export builds with durable idempotency receipts.

This queue owns package construction only. It never schedules scientific units
or shares a lock/database with the host pool's scientific admission ledger.
"""
from __future__ import annotations

from collections import deque
import hashlib
import json
import os
from pathlib import Path
import re
import threading

from .bytecode import io_path
from .contracts.base import ContractError, sha256_hex
from .contracts.plan_export import PlanExportRequest
from .engine.fs import FileLock, atomic_json
from .environment_store.verification import confined
from .planning.validation import validate_run_plan


class PlanExportService:
    def __init__(self, workspace, directory, *, builder_factory=None, max_waiting=4, max_receipts=1024):
        if type(max_waiting) is not int or not 0 <= max_waiting <= 4 or type(max_receipts) is not int or max_receipts < 1:
            raise ValueError('Invalid export queue/receipt limits')
        self.workspace = Path(workspace).resolve()
        self.directory = Path(directory).resolve()
        if not self.directory.is_relative_to(self.workspace):
            raise ValueError('Export receipts must remain under their workspace')
        self.builder_factory = builder_factory or self._builder
        self.max_waiting, self.max_receipts = max_waiting, max_receipts
        self._condition = threading.Condition(threading.RLock())
        self._pending = deque()
        self._active = None
        self._cancel = threading.Event()
        self._owner = None
        self._thread = None
        self._closing = False

    @staticmethod
    def _builder(source, environments, receipts):
        from .environment_store import EnvironmentStore
        from .export.service import ExportService
        return ExportService(source, EnvironmentStore(environments, create=False), receipts)

    @staticmethod
    def _id(request_id):
        if not isinstance(request_id, str) or not 1 <= len(request_id) <= 512:
            raise ContractError('Export lookup requires its stable request ID', code='invalid_request')
        return 'export-' + hashlib.sha256(request_id.encode()).hexdigest()

    def _path(self, identifier):
        if not isinstance(identifier, str) or not re.fullmatch(r'export-[a-f0-9]{64}', identifier):
            raise ContractError('Invalid export receipt ID', code='invalid_request')
        return self.directory / (identifier + '.json')

    def _read(self, identifier):
        try:
            return json.loads(io_path(self._path(identifier)).read_text(encoding='utf-8'))
        except FileNotFoundError as exc:
            if identifier not in self._index():
                raise ContractError('Export receipt was not found', code='export_not_found') from exc
            # The claim index is durable before a receipt can become visible or
            # any build can start. An interrupted receipt write is not permission
            # to reuse its key or output and launch another build.
            try:
                request = PlanExportRequest.model_validate(json.loads(io_path(
                    self.directory / (identifier + '.request.json')).read_text(encoding='utf-8')))
                if self._id(request.request_id) != identifier:
                    raise ValueError('Request identity differs from indexed claim')
            except (OSError, ValueError) as recovery_error:
                raise ContractError('Indexed export claim needs inspection before further builds',
                    code='export_recovery_required', details={'id': identifier},
                    next_actions=({'action': 'inspect_export', 'id': identifier},)) from recovery_error
            record = {'id': identifier, 'request_id': request.request_id, 'digest': sha256_hex(request),
                      'plan_id': request.plan.plan_id, 'output': request.output,
                      'status': 'unknown', 'phase': 'recovery_required',
                      'next_actions': [{'action': 'inspect_export', 'id': identifier}]}
            atomic_json(self._path(identifier), record)
            return record

    def _index(self):
        try:
            return json.loads(io_path(self.directory / 'index.json').read_text(encoding='utf-8'))
        except FileNotFoundError:
            return []

    def _acquire_owner(self):
        """One OS lease for this build queue, independent of pool ownership.

        A raw descriptor lock is intentionally transferable between the calling
        thread and its single build thread; FileLock is thread-reentrant instead.
        """
        io_path(self.directory).mkdir(parents=True, exist_ok=True)
        handle = io_path(self.directory / '.build-owner.lock').open('a+b')
        try:
            if not handle.seek(0, os.SEEK_END):
                handle.write(b'\0'); handle.flush()
            handle.seek(0)
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return handle
        except OSError:
            handle.close()
            return None
        except BaseException:
            handle.close()
            raise

    def _recover(self):
        # Called only while holding both the owner lease and short claim lock.
        # A previous queue's work is never silently replayed after restart.
        for identifier in self._index():
            record = self._read(identifier)
            if record['status'] in ('queued', 'building', 'cancelling'):
                record.update(status='unknown', phase='recovery_required',
                              next_actions=[{'action': 'inspect_export', 'id': identifier}])
                atomic_json(self._path(identifier), record)

    def _validate_paths(self, request):
        source = confined(self.workspace, request.source_root).resolve()
        environment = confined(self.workspace, request.environment_store).resolve()
        output = confined(self.workspace, request.output).resolve()
        if (output == self.workspace or source == output or source.is_relative_to(output)
                or output.is_relative_to(environment) or environment.is_relative_to(output)):
            raise ContractError('Export destination overlaps an owned source/environment root', code='path_escape')
        for manifest in [request.extra_files, *(item.files for item in request.implementations.values())]:
            for destination, record in manifest.items():
                confined(source, record.path)
                confined(output, destination)
        inputs = {name: str(confined(self.workspace, path).resolve())
                  for name, path in request.input_bindings.items()}
        from .export.planner import bindable_plan
        _, inferred = bindable_plan(request.plan)
        if not set(inferred) <= inputs.keys():
            raise ContractError('Export requires explicit confined bindings for every source input',
                                code='missing_binding', details={'inputs': sorted(set(inferred) - inputs.keys())})
        return source, environment, output, inputs

    def submit(self, value):
        request = PlanExportRequest.model_validate(value)
        validate_run_plan(request.plan)
        if request.plan.execution_policy.get('storage_input_refs'):
            raise ContractError('Selected storage versions cannot be relocated automatically. '
                                'Use the explicit portable input import/binding with verified content '
                                'instead of a machine-stat storage selection',
                                code='storage_route_unavailable')
        identifier, digest = self._id(request.request_id), sha256_hex(request)
        with self._condition:
            if self._closing:
                raise ContractError('Export service is closing', code='export_unavailable')
            io_path(self.directory).mkdir(parents=True, exist_ok=True)
            with FileLock(self.directory / '.claims.lock'):
                if io_path(self._path(identifier)).exists() or identifier in self._index():
                    record = self.details(identifier)
                    if record['digest'] != digest:
                        raise ContractError('Export request ID has different frozen content', code='idempotency_conflict')
                    return {**record, 'reused': True}
                self._validate_paths(request)
                acquired = False
                try:
                    if self._owner is None:
                        owner = self._acquire_owner()
                        if owner is None:
                            raise ContractError('Another application owns this profile export queue', code='export_busy')
                        self._owner, acquired = owner, True
                        self._recover()
                    index = self._index()
                    if len(index) >= self.max_receipts:
                        raise ContractError('Export receipt retention limit reached', code='export_queue_full',
                                            details={'max_receipts': self.max_receipts})
                    if len(self._pending) + int(self._active is not None) >= self.max_waiting + 1:
                        raise ContractError('Export queue is full', code='export_queue_full',
                                            details={'active': 1, 'max_waiting': self.max_waiting})
                    for previous in index:
                        record = self._read(previous)
                        same_output = os.path.normcase(str(confined(self.workspace, record['output']).resolve())) == os.path.normcase(str(confined(self.workspace, request.output).resolve()))
                        if same_output and record['status'] in ('queued', 'building', 'cancelling', 'unknown'):
                            raise ContractError('Export destination has an unresolved build', code='export_destination_busy')
                    record = {'id': identifier, 'request_id': request.request_id, 'digest': digest,
                              'plan_id': request.plan.plan_id, 'output': request.output,
                              'status': 'queued', 'phase': 'queued', 'next_actions': []}
                    atomic_json(self.directory / (identifier + '.request.json'), request.model_dump(mode='json'))
                    atomic_json(self.directory / 'index.json', [*index, identifier])
                    atomic_json(self._path(identifier), record)
                    self._pending.append(identifier)
                    if self._thread is None or not self._thread.is_alive():
                        self._thread = threading.Thread(target=self._work, name='plan-export-build', daemon=True)
                        self._thread.start()
                    self._condition.notify_all()
                    return record
                except BaseException:
                    if acquired and (self._thread is None or not self._thread.is_alive()):
                        self._pending.clear()
                        owner, self._owner = self._owner, None
                        if owner is not None:
                            owner.close()
                    raise

    def _update(self, identifier, **changes):
        with FileLock(self.directory / '.claims.lock'):
            record = self._read(identifier)
            if changes.get('status') == 'cancelling' and record['status'] in ('complete', 'failed', 'cancelled', 'unknown'):
                return record
            record.update(changes)
            atomic_json(self._path(identifier), record)
            return record

    def _work(self):
        try:
            while True:
                with self._condition:
                    self._condition.wait_for(lambda: self._pending or self._closing)
                    if self._closing:
                        return
                    identifier = self._pending.popleft()
                    self._active = identifier
                    self._cancel.clear()
                    self._update(identifier, status='building', phase='building')
                try:
                    request = PlanExportRequest.model_validate(json.loads(
                        io_path(self.directory / (identifier + '.request.json')).read_text(encoding='utf-8')))
                    source, environment, output, inputs = self._validate_paths(request)
                    builder = self.builder_factory(source, environment, self.directory / identifier / 'build')
                    value = request.model_dump(mode='json')
                    result = builder.build(request.plan, output, implementations=value['implementations'],
                        environments=value['environments'], extra_files=value['extra_files'],
                        management_environment=request.management_environment, input_bindings=inputs,
                        input_formats=value['input_formats'], cancel=self._cancel.is_set)
                    if (not isinstance(result, dict) or result.get('status') != 'complete'
                            or not re.fullmatch(r'[a-f0-9]{64}', str(result.get('bundle_identity', '')))):
                        raise ContractError('Builder did not return a verified completion receipt', code='export_receipt_invalid')
                    self._update(identifier, status='complete', phase=result.get('phase', 'complete'),
                                 build_receipt=result, next_actions=[])
                except InterruptedError as exc:
                    self._update(identifier, status='cancelled', phase='cancelled', error=str(exc))
                except Exception as exc:
                    self._update(identifier, status='failed', phase='failed',
                                 error={'code': getattr(exc, 'code', 'export_failed'), 'message': str(exc)})
                except BaseException:
                    self._update(identifier, status='unknown', phase='recovery_required',
                                 next_actions=[{'action': 'inspect_export', 'id': identifier}])
                    return
                finally:
                    with self._condition:
                        self._active = None
                        self._condition.notify_all()
        finally:
            with self._condition:
                # Unexpected worker exit cannot leave queued IDs available to a
                # later worker. Their durable records become unknown on recovery.
                self._pending.clear()
                self._active = None
                self._thread = None
                owner, self._owner = self._owner, None
                if owner is not None:
                    owner.close()
                self._condition.notify_all()

    def details(self, identifier=None, *, request_id=None):
        identifier = self._id(request_id) if request_id is not None else identifier
        with self._condition:
            if not io_path(self.directory).exists():
                raise ContractError('Export receipt was not found', code='export_not_found')
            with FileLock(self.directory / '.claims.lock'):
                unowned = False
                if self._owner is None:
                    owner = self._acquire_owner()
                    if owner is not None:
                        unowned = True
                        try:
                            self._recover()
                        finally:
                            owner.close()
                record = self._read(identifier)
                if (record['status'] in ('queued', 'building', 'cancelling') and (unowned
                        or self._owner is not None and identifier not in self._pending and identifier != self._active)):
                    record.update(status='unknown', phase='recovery_required',
                                  next_actions=[{'action': 'inspect_export', 'id': identifier}])
                    atomic_json(self._path(identifier), record)
                return record

    def cancel(self, identifier):
        with self._condition:
            record = self.details(identifier)
            if identifier == self._active:
                self._cancel.set()
                return self._update(identifier, status='cancelling', phase='cancelling')
            if identifier in self._pending:
                self._pending.remove(identifier)
                return self._update(identifier, status='cancelled', phase='cancelled')
            if record['status'] in ('queued', 'building', 'cancelling'):
                raise ContractError('Connect to the application owning this export to cancel it', code='export_owner_required')
            return record

    def close(self):
        with self._condition:
            self._closing = True
            self._cancel.set()
            for identifier in self._pending:
                self._update(identifier, status='cancelled', phase='application_shutdown')
            self._pending.clear()
            thread = self._thread
            self._condition.notify_all()
            if thread is None and self._owner is not None:
                self._owner.close()
                self._owner = None
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=2)
