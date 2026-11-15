"""Compile and submit RunPlans through the one existing host-pool authority."""
from __future__ import annotations

from operon.contracts.base import ContractError
from operon.contracts.plan_operations import (PlanCompileRequest, PlanLookupControl, PlanSubmitRequest,
                                              PlanEventsQuery, PlanPageQuery, PlanLogsQuery)
from operon.engine.contracts import EngineError
from operon.planning.validation import validate_run_plan


class PlanOperationError(ContractError):
    """Preserve pool operation codes and evidence at application boundaries."""


class PlanService:
    def __init__(self, application):
        self.app = application

    def compile(self, request):
        request = PlanCompileRequest.model_validate(request)
        wire = request.model_dump(mode='json')
        if request.kind == 'graph':
            plan = self.app.compile_plan(wire['workflow'], request.values,
                                         require_files=request.require_files)
        else:
            from .planning.authoring_v2 import normalize
            from .planning import WorkflowCompiler
            from .environment_store.verification import confined
            directory = confined(self.app.service.root, request.directory)
            normalized = normalize(wire['workflow'], directory,
                parameters=wire['parameters'], inputs=wire['inputs'] or {},
                environments=wire['environments'] or {}, profile=request.profile,
                initial=request.initial, catalog=self.app.service.catalog)
            plan = WorkflowCompiler().compile_authoring(normalized, self.app.service.catalog,
                                                        root=directory, require_files=request.require_files)
        return validate_run_plan(plan)

    def _call(self, operation, *, run_id=None, submission=None, query=None):
        service = self.app.service
        if run_id and run_id.startswith('remote-plan-'):
            reference = self.app.canvas_plans.remote_reference(run_id)
            result = service.remotes.call(reference['profile_id'], 'plan.read', {
                'run_id': reference['run_id'], 'operation': operation, 'query': query or {}})
            return {**result, 'run_id': run_id} if 'run_id' in result else result
        try:
            if getattr(service, 'pool_remote', False):
                try:
                    service._ensure_pool_session()
                except Exception as exc:
                    # Session establishment precedes submit; its failure is not
                    # evidence that a scientific attempt was accepted.
                    raise PlanOperationError(str(exc), code=getattr(exc, 'code', 'engine_unavailable'),
                                             details=getattr(exc, 'details', None)) from exc
                payload = {'workspace': str(service.root), 'principal': service.pool_principal,
                           'session_id': service.pool_session_id}
                if submission is not None:
                    payload.update(submission.model_dump(mode='json'))
                else:
                    payload['run_id'] = run_id
                    payload.update(query or {})
                return service.pool_client.request('plan.' + operation, payload)
            pool = getattr(service, 'pool', None)
            if pool is None:
                raise PlanOperationError('RunPlan execution requires the existing shared host pool',
                                         code='engine_unavailable', next_actions=(
                                             {'action': 'connect_shared_pool'},))
            principal = getattr(service, '_pool_principal', None) or getattr(service.engine, 'principal', None)
            if submission is not None:
                return pool.submit_plan(service.root, submission.plan.model_dump(mode='json'),
                    submission.binding.model_dump(mode='json'), request_id=submission.request_id,
                    principal=principal)
            method = getattr(pool, 'plan_' + operation)
            return method(service.root, run_id, principal=principal, **(query or {}))
        except EngineError as exc:
            if submission is not None and exc.code == 'response_unavailable':
                raise PlanOperationError('The submission response is unavailable; acceptance is unknown',
                    code='submission_unknown', details={'request_id': submission.request_id},
                    next_actions=({'action': 'retry_same_request', 'request_id': submission.request_id},)) from exc
            error = PlanOperationError(str(exc), code=exc.code, details=exc.details)
            error.status = exc.status
            error.retry_after = exc.retry_after
            raise error from exc
        except (OSError, EOFError) as exc:
            if submission is not None:
                raise PlanOperationError('The submission response is unavailable; acceptance is unknown',
                    code='submission_unknown', details={'request_id': submission.request_id},
                    next_actions=({'action': 'retry_same_request', 'request_id': submission.request_id},)) from exc
            raise PlanOperationError('The shared pool is unavailable', code='engine_unavailable') from exc

    def submit(self, request):
        request = PlanSubmitRequest.model_validate(request)
        validate_run_plan(request.plan)
        if request.plan.execution_policy.get('storage_input_refs'):
            self.app.storage_inputs.validate_plan(request.plan, request.binding)
        missing_environments = {unit.invocation.environment_ref for unit in request.plan.units
                                if unit.invocation.environment_ref not in request.binding.environments}
        missing_storage = {item.storage_id for item in request.plan.storage_bindings
                           if item.storage_id not in request.binding.storage}
        missing_inputs = {value[len('input:'):] for unit in request.plan.units
                          for value in unit.input_bindings.values() if value.startswith('input:')
                          and value[len('input:'):] not in request.binding.inputs}
        if missing_environments or missing_storage or missing_inputs:
            raise PlanOperationError('Execution binding does not cover the frozen plan', code='missing_binding',
                details={'environments': sorted(str(item) for item in missing_environments),
                         'storage': sorted(missing_storage), 'inputs': sorted(missing_inputs)})
        if self.app.stopping:
            raise PlanOperationError('Application is closing; no plan was submitted', code='engine_unavailable')
        return self._call('submit', submission=request)

    def details(self, run_id):
        PlanLookupControl(workspace=str(self.app.service.root), run_id=run_id)
        return self._brief(self._call('details', run_id=run_id))

    def cancel(self, run_id):
        PlanLookupControl(workspace=str(self.app.service.root), run_id=run_id)
        # The host authorizes ownership and the existing coordinator cancels.
        return self._brief(self._call('cancel', run_id=run_id))

    def _read(self, operation, run_id, model, query):
        PlanLookupControl(workspace=str(self.app.service.root), run_id=run_id)
        request = model.model_validate(query)
        return self._call(operation, run_id=run_id, query=request.model_dump(mode='json'))

    def events(self, run_id, **query):
        return self._read('events', run_id, PlanEventsQuery, query)

    def attempts(self, run_id, **query):
        return self._read('attempts', run_id, PlanPageQuery, query)

    def artifacts(self, run_id, **query):
        return self._read('artifacts', run_id, PlanPageQuery, query)

    def logs(self, run_id, **query):
        return self._read('logs', run_id, PlanLogsQuery, query)

    def artifact_files(self, run_id, **query):
        from .contracts.plan_artifacts import PlanArtifactFilesQuery
        return self._read('artifact_files', run_id, PlanArtifactFilesQuery, query)

    def artifact_preview(self, run_id, **query):
        from .contracts.plan_artifacts import PlanArtifactPreviewQuery
        return self._read('artifact_preview', run_id, PlanArtifactPreviewQuery, query)

    def open_artifact(self, run_id, **query):
        from .contracts.plan_artifacts import PlanArtifactFileQuery
        from .plan_artifacts import OpenedPlanResult
        service = self.app.service
        if run_id.startswith('remote-plan-'):
            from src.web.transfers import TransferClient
            from .engine.transport import transport_admission
            import uuid
            reference = self.app.canvas_plans.remote_reference(run_id)
            result = self._read('artifact_file', run_id, PlanArtifactFileQuery, query)
            client = TransferClient(lambda method, params=None: service.remotes.call(
                reference['profile_id'], method, params or {}), self.app.canvas_plans.directory / 'results')
            remote = result['transfer']
            from .environment_store.verification import confined
            from .contracts.base import ContractError
            import re
            if not re.fullmatch('[a-f0-9]{64}', remote['sha256']):
                raise ContractError('Invalid result content identity', code='invalid_artifact')
            destination = confined(client.cache_dir / remote['sha256'], result['descriptor']['name'])
            admission = transport_admission(service)
            ticket = 'plan-result-' + uuid.uuid4().hex
            if not admission.reserve(ticket, {'kind': 'transport', 'reserved_bytes': client.buffer_budget_bytes,
                                              'cpu_threads': 0}):
                raise PlanOperationError('Result transfer memory is temporarily occupied', code='busy')
            try:
                client.download(remote, destination)
            finally:
                admission.release(ticket)
            descriptor = {**result['descriptor'], 'relative_path': destination.relative_to(service.directory).as_posix()}
            return OpenedPlanResult(service.directory, descriptor)
        if getattr(service, 'pool_remote', False) and not getattr(service, 'pool_managed', False):
            raise PlanOperationError('Opening this file requires an explicit transfer from its host',
                code='artifact_transfer_required', next_actions=({'action': 'configure_artifact_transfer'},))
        descriptor = self._read('artifact_file', run_id, PlanArtifactFileQuery, query)
        try:
            return OpenedPlanResult(service.directory, descriptor)
        except EngineError as exc:
            error = PlanOperationError(str(exc), code=exc.code, details=exc.details)
            error.status = exc.status
            raise error from exc

    @staticmethod
    def _brief(result):
        value = {key: result[key] for key in ('run_id', 'state', 'revision', 'results',
                                             'unit_count', 'attempt_count') if key in result}
        for key in ('units', 'attempts'):
            if key in result:
                value[{'units': 'unit_count', 'attempts': 'attempt_count'}[key]] = len(result[key])
        return value
