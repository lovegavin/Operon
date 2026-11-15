"""Host-owned preparation of same-host, committed producer inputs.

The controller names producer attempts, never filesystem paths. This layer
authorizes the frozen edges, retains their artifacts, and projects one consumer
for the existing host pool. It allocates no capacity and performs no transfer.
Persisted preparations are audit records, not bearer capabilities: each reuse
rechecks the authenticated scope, producer provenance, pins and all file bytes.
"""
from __future__ import annotations

import json
import os
import re
from typing import Literal

from pydantic import Field, model_validator

from operon.bytecode import io_path
from operon.contracts.base import ContractError, ContractModel, canonical_json, sha256_hex
from operon.contracts.plan_operations import PlanExecutionBinding
from operon.contracts.run_plan import PlacementPolicy, RunPlan, UnitSpec
from operon.engine.contracts import UnauthorizedError
from operon.engine.fs import atomic_json
from operon.execution.unit_executor import unit_dependencies
from operon.planning.validation import validate_run_plan
from .artifact_bindings import ProducerArtifactRequest, SharedArtifactReceipt, _opened_matches, _same_path, _stamp


MAX_PREPARATION_BYTES = 8 * 1024 * 1024
MAX_AUDIT_BYTES = 64 * 1024
MAX_PRODUCERS = 128
OPERATION = 'cluster-consumer-binding-v1'


def _error(message, code='unverified_artifact_provenance', **details):
    return ContractError(message, code=code, details=details)


def _bounded(value, limit=MAX_PREPARATION_BYTES):
    if len(canonical_json(value).encode('utf-8')) > limit:
        raise _error('Consumer binding metadata exceeds its bounded allowance', 'binding_metadata_limit')


def _input_key(edge):
    return 'artifact-' + sha256_hex(edge)


class MaterializedInputAudit(ContractModel):
    input_key: str = Field(pattern=r'^artifact-[a-f0-9]{64}$')
    input_digest: str = Field(pattern=r'^[a-f0-9]{64}$')
    receipt_id: str = Field(pattern=r'^[a-f0-9]{64}$')
    publication_digest: str = Field(pattern=r'^[a-f0-9]{64}$')
    artifact_id: str = Field(min_length=1, max_length=200)
    artifact_digest: str = Field(pattern=r'^[a-f0-9]{64}$')
    producer_cluster_run_id: str = Field(min_length=1, max_length=200)
    producer_cluster_unit_id: str = Field(min_length=1, max_length=200)
    producer_cluster_attempt_id: str = Field(min_length=1, max_length=200)
    host_run_id: str = Field(min_length=1, max_length=200)
    host_unit_id: str = Field(min_length=1, max_length=512)
    host_attempt_id: str = Field(min_length=1, max_length=200)
    host_fence: int = Field(ge=0)
    reference_id: str = Field(min_length=1, max_length=200)
    output_port: str = Field(min_length=1, max_length=200)


class PreparationAudit(ContractModel):
    preparation_id: str = Field(pattern=r'^prep-[a-f0-9]{64}$')
    request_digest: str = Field(pattern=r'^[a-f0-9]{64}$')
    controller_id: str = Field(min_length=1, max_length=128)
    principal: str = Field(min_length=1, max_length=128)
    cluster_run_id: str = Field(min_length=1, max_length=200)
    target_node_id: str = Field(min_length=1, max_length=128)
    host_identity: str = Field(min_length=1, max_length=200)
    workspace_id: str = Field(min_length=1, max_length=200)


class ProjectionAudit(ContractModel):
    source_plan_id: str = Field(pattern=r'^[a-f0-9]{64}$')
    source_unit_id: str = Field(min_length=1, max_length=200)
    source_unit_digest: str = Field(pattern=r'^[a-f0-9]{64}$')
    source_placement: PlacementPolicy
    source_dependencies: tuple[str, ...] = Field(min_length=1, max_length=MAX_PRODUCERS)
    materialized_inputs: dict[str, MaterializedInputAudit] = Field(min_length=1, max_length=MAX_PRODUCERS)
    prepared_binding: PreparationAudit


def validate_prepared_projection(plan, *, source_plan_id, source_unit_id, source_unit_digest, binding) -> None:
    """Pure consistency audit, not authorization of an incoming wire dispatch.

    Host entry points must call SharedConsumerPreparer; a caller can recompute
    any public hash. Reconstructing the source unit here catches altered code,
    parameters, resources, placement, port remapping and input binding content.
    """
    plan = validate_run_plan(RunPlan.model_validate(plan))
    binding = PlanExecutionBinding.model_validate(binding)
    _bounded({'plan': plan, 'binding': binding})
    audit = ProjectionAudit.model_validate(plan.execution_policy.get('cluster_projection', {}))
    _bounded(audit, MAX_AUDIT_BYTES)
    if (audit.source_plan_id != source_plan_id or audit.source_unit_id != source_unit_id
            or audit.source_unit_digest != source_unit_digest or len(plan.units) != 1
            or plan.units[0].unit_id != source_unit_id):
        raise _error('Prepared projection differs from its frozen source identity')
    unit = plan.units[0]
    placement = audit.source_placement
    authority = audit.prepared_binding
    if (placement.executor != 'ssh' or placement.node_id not in (None, authority.target_node_id)
            or placement.pool_id not in (None, authority.host_identity)
            or unit.retry_policy.maximum_attempts != 1):
        raise _error('Prepared projection differs from its selected host or retry policy')
    expected_placement = placement.model_dump(mode='json')
    expected_placement.update(executor='local', node_id=None, pool_id=None)
    if unit.placement.model_dump(mode='json') != expected_placement:
        raise _error('Prepared projection changed the source target requirements')
    original = unit.model_dump(mode='json')
    original['placement'] = placement.model_dump(mode='json')
    replacements, parents = {}, set()
    for edge, item in audit.materialized_inputs.items():
        if not edge.startswith('artifact:'):
            raise _error('Prepared input lacks an artifact edge')
        parent, separator, port = edge[len('artifact:'):].partition('/')
        if (not separator or not port or parent == source_unit_id or item.input_key != _input_key(edge)
                or item.producer_cluster_unit_id != parent or item.output_port != port
                or item.producer_cluster_run_id != authority.cluster_run_id):
            raise _error('Prepared input differs from its current-run named producer')
        bound = binding.inputs.get(item.input_key)
        if bound is None or sha256_hex(bound) != item.input_digest:
            raise _error('Prepared input content changed after verification')
        replacements['input:' + item.input_key] = edge
        parents.add(parent)
    if tuple(sorted(parents)) != audit.source_dependencies:
        raise _error('Prepared projection omitted or added a source dependency')
    used = set()
    for name, source in original['input_bindings'].items():
        if source.startswith('artifact:'):
            raise _error('Prepared projection still contains an unresolved artifact input')
        if source in replacements:
            original['input_bindings'][name] = replacements[source]
            used.add(source)
        elif source.startswith('input:') and source[len('input:'):] not in binding.inputs:
            raise _error('Prepared projection lacks a bound external input')
    if used != set(replacements) or sha256_hex(UnitSpec.model_validate(original)) != source_unit_digest:
        raise _error('Prepared projection changed its frozen source unit')
    if unit.invocation.environment_ref not in binding.environments:
        raise _error('Prepared projection lacks its selected environment generation')
    nodes = set(unit.node_ids)
    if any(edge.get('source') not in nodes or edge.get('target') not in nodes for edge in plan.edges):
        raise _error('Prepared projection contains an unrepresented cross-unit dependency')


class ConsumerPreparationRequest(ContractModel):
    source_plan: RunPlan
    cluster_run_id: str = Field(min_length=1, max_length=200)
    consumer_unit_id: str = Field(min_length=1, max_length=200)
    binding: PlanExecutionBinding
    producers: dict[str, ProducerArtifactRequest] = Field(min_length=1, max_length=MAX_PRODUCERS)
    request_id: str = Field(min_length=1, max_length=512)
    principal: str = Field(min_length=1, max_length=128)
    controller_id: str = Field(min_length=1, max_length=128)
    target_node_id: str = Field(min_length=1, max_length=128)
    host_identity: str = Field(min_length=1, max_length=200)
    workspace_id: str = Field(min_length=1, max_length=200)
    workspace: str = Field(min_length=1, max_length=32768)

    def identity_payload(self):
        value = self.model_dump(mode='json')
        for producer in value['producers'].values():
            producer.pop('controller_epoch')
        return value


def _preparation_id(request):
    # Unit, target node, source plan and binding remain in the claim digest, so
    # changing any of them under the same request cannot create a second claim.
    return 'prep-' + sha256_hex({name: getattr(request, name) for name in
        ('controller_id', 'principal', 'host_identity', 'workspace_id', 'request_id')})


class PreparedConsumerBinding(ContractModel):
    format: Literal['operon.prepared-consumer-binding'] = 'operon.prepared-consumer-binding'
    schema_version: Literal[1] = 1
    preparation_id: str = Field(pattern=r'^prep-[a-f0-9]{64}$')
    request_digest: str = Field(pattern=r'^[a-f0-9]{64}$')
    request: ConsumerPreparationRequest
    plan: RunPlan
    binding: PlanExecutionBinding
    receipts: dict[str, SharedArtifactReceipt] = Field(min_length=1, max_length=MAX_PRODUCERS)
    payload_digest: str = Field(pattern=r'^[a-f0-9]{64}$')

    @property
    def workspace(self): return self.request.workspace

    @property
    def source_plan_id(self): return self.request.source_plan.plan_id

    @property
    def source_unit_id(self): return self.request.consumer_unit_id

    @property
    def source_unit_digest(self): return self.audit['source_unit_digest']

    @property
    def audit(self): return self.plan.execution_policy['cluster_projection']

    def dispatch_payload(self):
        return dict(workspace=self.workspace, source_plan_id=self.source_plan_id,
            source_unit_id=self.source_unit_id, source_unit_digest=self.source_unit_digest,
            plan=self.plan.model_dump(mode='json'), binding=self.binding.model_dump(mode='json'))

    @model_validator(mode='after')
    def _identity(self):
        _bounded(self)
        if (self.preparation_id != _preparation_id(self.request)
                or self.request_digest != sha256_hex(self.request.identity_payload())
                or self.payload_digest != sha256_hex(self.model_dump(mode='json', exclude={'payload_digest'}))):
            raise _error('Persisted preparation identity differs from its content', 'binding_integrity_error')
        validate_prepared_projection(self.plan, source_plan_id=self.source_plan_id,
            source_unit_id=self.source_unit_id, source_unit_digest=self.source_unit_digest, binding=self.binding)
        return self


class SharedConsumerPreparer:
    def __init__(self, resolver, *, target_node_id):
        if not isinstance(target_node_id, str) or not 1 <= len(target_node_id) <= 128:
            raise ValueError('A bounded selected node identity is required')
        self.resolver, self.store, self.target_node_id = resolver, resolver.store, target_node_id
        self.root = resolver.root / 'prepared-bindings'

    def _scope(self, request, principal):
        if (request.principal != principal or request.controller_id != self.resolver.controller_id
                or request.host_identity != self.resolver.host_identity
                or request.workspace_id != self.resolver.workspace_id or request.target_node_id != self.target_node_id
                or not _same_path(request.workspace, self.resolver.workspace)):
            raise UnauthorizedError('Prepared consumer belongs to another authenticated host scope')
        registered = self.store.workspace(self.resolver.workspace_id)
        if (registered['principal'] != principal or registered['pool_id'] != self.resolver.host_identity
                or not _same_path(registered['root'], self.resolver.workspace)):
            raise UnauthorizedError('Prepared consumer workspace is not owned by this principal')

    def _source(self, request):
        plan = validate_run_plan(request.source_plan)
        _bounded(request)
        units = {unit.unit_id: unit for unit in plan.units}
        source = units.get(request.consumer_unit_id)
        if source is None:
            raise _error('Consumer is absent from the frozen RunPlan', 'invalid_plan_edge')
        required = {value for value in source.input_bindings.values() if value.startswith('artifact:')}
        dependencies = unit_dependencies(plan)[source.unit_id]
        parents = {edge[len('artifact:'):].split('/', 1)[0] for edge in required}
        if dependencies != parents:
            raise _error('Control-only dependencies require an explicit supported binding', 'unsupported_control_dependency')
        if not required or len(required) > MAX_PRODUCERS or required != set(request.producers):
            raise _error('Producer identities do not match the frozen consumer inputs', 'invalid_plan_edge')
        owners = {node: unit.unit_id for unit in plan.units for node in unit.node_ids}
        for edge in plan.edges:
            parent, target = owners.get(edge.get('source')), owners.get(edge.get('target'))
            if target != source.unit_id or parent is None or parent == target:
                continue
            output, input_port = edge.get('source_handle'), edge.get('target_handle')
            if not isinstance(output, str) or not output or not isinstance(input_port, str) or not input_port:
                raise _error('Cross-unit control edges require explicit supported port bindings',
                             'unsupported_control_dependency')
            if source.input_bindings.get(input_port) != 'artifact:' + parent + '/' + output:
                raise _error('Explicit edge ports differ from the frozen consumer input binding', 'invalid_plan_edge')
        for unit in (source, *(units[parent] for parent in sorted(parents))):
            if unit.retry_policy.maximum_attempts != 1:
                raise _error('Same-host preparation requires single-attempt producer and consumer units',
                             'unsupported_retry_policy')
            if (unit.placement.executor != 'ssh' or unit.placement.node_id not in (None, self.target_node_id)
                    or unit.placement.pool_id not in (None, self.resolver.host_identity)):
                raise _error('Producer and consumer must select this same host', 'cross_host_artifact_unavailable')
        for edge in required:
            parent, port = edge[len('artifact:'):].split('/', 1)
            producer = request.producers[edge]
            if (producer.cluster_run_id != request.cluster_run_id or producer.cluster_unit_id != parent
                    or producer.output_port != port):
                raise _error('Producer identity differs from its current-run frozen edge')
            if not any(item.name == port for item in units[parent].output_contracts):
                raise _error('Producer port is absent from its frozen output contract', 'invalid_plan_edge')
            if _input_key(edge) in request.binding.inputs:
                raise _error('Caller input collides with a host-derived producer binding', 'binding_rebind_rejected')
        return source, units, dependencies

    def _producer_request(self, request, edge, preparation_id, controller_epoch=None):
        value = request.producers[edge].model_dump(mode='json')
        value['binding_key'] = preparation_id + ':' + sha256_hex(edge)
        if controller_epoch is not None:
            value['controller_epoch'] = controller_epoch
        return ProducerArtifactRequest.model_validate(value)

    def _receipts(self, request, preparation_id, *, cached=None, controller_epoch=None):
        _, units, _ = self._source(request)
        if cached is not None and set(cached) != set(request.producers):
            raise _error('Cached producer references changed', 'binding_integrity_error')
        result = {}
        for edge in sorted(request.producers):
            expected = self._producer_request(request, edge, preparation_id, controller_epoch)
            if cached is None:
                receipt = self.resolver.resolve(expected, principal=request.principal)
            else:
                saved = cached[edge]
                if saved.producer.model_dump(exclude={'controller_epoch'}) != expected.model_dump(exclude={'controller_epoch'}):
                    raise _error('Cached producer receipt changed its exact attempt or reference owner', 'binding_integrity_error')
                receipt = self.resolver.audit(saved, principal=request.principal, controller_epoch=controller_epoch)
            original = units[expected.cluster_unit_id]
            contract = next(item for item in original.output_contracts if item.name == expected.output_port)
            if (receipt.source_plan_id != request.source_plan.plan_id or receipt.source_unit_digest != sha256_hex(original)
                    or receipt.input.representation != contract.representation):
                raise _error('Committed producer does not belong to this frozen RunPlan and port')
            result[edge] = receipt
        return result

    def _build(self, request, preparation_id, receipts):
        original, _, dependencies = self._source(request)
        unit, bound = original.model_dump(mode='json'), request.binding.model_dump(mode='json')
        materialized = {}
        for edge, receipt in sorted(receipts.items()):
            producer = receipt.producer
            key = _input_key(edge)
            bound['inputs'][key] = receipt.input.model_dump(mode='json')
            materialized[edge] = dict(input_key=key, input_digest=sha256_hex(receipt.input),
                receipt_id=receipt.receipt_id, publication_digest=receipt.publication_digest,
                artifact_id=producer.artifact_id, artifact_digest=producer.artifact_digest,
                producer_cluster_run_id=producer.cluster_run_id, producer_cluster_unit_id=producer.cluster_unit_id,
                producer_cluster_attempt_id=producer.cluster_attempt_id, host_run_id=producer.host_run_id,
                host_unit_id=producer.host_unit_id, host_attempt_id=producer.host_attempt_id,
                host_fence=producer.host_fence, reference_id=receipt.reference_id, output_port=producer.output_port)
        unit['input_bindings'] = {name: 'input:' + _input_key(value) if value in receipts else value
                                  for name, value in unit['input_bindings'].items()}
        placement = dict(unit['placement'])
        unit['placement'].update(executor='local', node_id=None, pool_id=None)
        request_digest = sha256_hex(request.identity_payload())
        authority = {name: getattr(request, name) for name in ('controller_id', 'principal', 'cluster_run_id',
                                                             'target_node_id', 'host_identity', 'workspace_id')}
        audit = dict(source_plan_id=request.source_plan.plan_id, source_unit_id=original.unit_id,
            source_unit_digest=sha256_hex(original), source_placement=placement,
            source_dependencies=sorted(dependencies), materialized_inputs=materialized,
            prepared_binding=dict(preparation_id=preparation_id, request_digest=request_digest, **authority))
        _bounded(audit, MAX_AUDIT_BYTES)
        raw = request.source_plan.model_dump(mode='json')
        raw['units'] = [unit]
        nodes = set(unit['node_ids'])
        raw['edges'] = [edge for edge in raw['edges'] if edge.get('source') in nodes and edge.get('target') in nodes]
        raw['execution_policy']['cluster_projection'] = audit
        projected = RunPlan.model_validate(raw).with_identity()
        value = dict(format='operon.prepared-consumer-binding', schema_version=1,
            preparation_id=preparation_id, request_digest=request_digest, request=request.model_dump(mode='json'),
            plan=projected.model_dump(mode='json'), binding=PlanExecutionBinding.model_validate(bound).model_dump(mode='json'),
            receipts={edge: receipt.model_dump(mode='json') for edge, receipt in receipts.items()})
        return PreparedConsumerBinding(payload_digest=sha256_hex(value), **value)

    def _owner(self, preparation_id):
        return dict(controller_id=self.resolver.controller_id, host_identity=self.resolver.host_identity,
            workspace_id=self.resolver.workspace_id, target_node_id=self.target_node_id, preparation_id=preparation_id)

    def _claim(self, preparation_id, principal):
        if not isinstance(preparation_id, str) or not re.fullmatch(r'prep-[a-f0-9]{64}', preparation_id):
            raise _error('Invalid consumer preparation identifier', 'binding_not_found')
        record = self.store.request(principal, 'consumer-binding:' + preparation_id)
        if not record or record['operation'] != OPERATION or record['owner'] != self._owner(preparation_id):
            raise UnauthorizedError('Consumer preparation is not owned by this authenticated scope')
        if record['state'] != 'ready':
            raise _error('Consumer preparation needs explicit recovery; it will not be rebuilt',
                         'binding_recovery_required', preparation_id=preparation_id, state=record['state'])
        return record

    def prepare(self, source_plan, *, cluster_run_id, consumer_unit_id, binding, producers, request_id, principal):
        request = ConsumerPreparationRequest(source_plan=RunPlan.model_validate(source_plan),
            cluster_run_id=cluster_run_id, consumer_unit_id=consumer_unit_id,
            binding=PlanExecutionBinding.model_validate(binding), producers=producers,
            request_id=request_id, principal=principal, controller_id=self.resolver.controller_id,
            target_node_id=self.target_node_id, host_identity=self.resolver.host_identity,
            workspace_id=self.resolver.workspace_id, workspace=str(self.resolver.workspace))
        self._scope(request, principal)
        self._source(request)
        epochs = {producer.controller_epoch for producer in request.producers.values()}
        if len(epochs) != 1:
            raise _error('Producer observations must use one authenticated controller epoch')
        preparation_id = _preparation_id(request)
        request_digest = sha256_hex(request.identity_payload())
        claim = self.store.claim_request(principal=principal, key='consumer-binding:' + preparation_id,
            digest=request_digest, operation=OPERATION, owner=self._owner(preparation_id),
            receipt={'preparation_id': preparation_id, 'request_digest': request_digest})
        if not claim.created:
            return self.load(preparation_id, principal=principal, controller_epoch=next(iter(epochs)))
        # After this durable claim, any failure leaves an explicit nonready
        # record and any acquired references. Never auto-release or retry it.
        receipts = self._receipts(request, preparation_id)
        prepared = self._build(request, preparation_id, receipts)
        # atomic_json uses indented JSON; bound the actual persisted spelling as
        # well as canonical content so every accepted record can be read back.
        if len(json.dumps(prepared.model_dump(mode='json'), ensure_ascii=False,
                          indent=2, allow_nan=False).encode('utf-8')) > MAX_PREPARATION_BYTES:
            raise _error('Persisted preparation exceeds its bounded allowance', 'binding_metadata_limit')
        self.resolver._safe(self.resolver.root)
        io_path(self.root).mkdir(exist_ok=True)
        self.resolver._safe(self.root)
        path = self.root / (preparation_id + '.json')
        if io_path(path).exists():
            raise _error('Unclaimed preparation file already exists', 'binding_recovery_required')
        atomic_json(path, prepared.model_dump(mode='json'))
        self.resolver._safe(path)
        self.store.update_request(principal, 'consumer-binding:' + preparation_id, state='ready', receipt={
            'preparation_id': preparation_id, 'request_digest': request_digest, 'payload_digest': prepared.payload_digest})
        return prepared

    def load(self, preparation_id, *, principal, controller_epoch=None):
        try:
            return self._load(preparation_id, principal=principal, controller_epoch=controller_epoch)
        except (OSError, UnicodeError, ValueError, KeyError) as exc:
            if isinstance(exc, ContractError):
                raise
            raise _error('Persisted consumer preparation is missing or invalid', 'binding_integrity_error',
                         preparation_id=preparation_id, error=type(exc).__name__) from exc

    def _load(self, preparation_id, *, principal, controller_epoch=None):
        record = self._claim(preparation_id, principal)
        path = self.resolver._safe(self.root / (preparation_id + '.json'))
        before_info = io_path(path).stat()
        before = _stamp(before_info)
        with io_path(path).open('rb') as stream:
            opened = os.fstat(stream.fileno())
            if not _opened_matches(before_info, opened):
                raise _error('Preparation changed while opening it', 'binding_integrity_error')
            raw = stream.read(MAX_PREPARATION_BYTES + 1)
            after = _stamp(os.fstat(stream.fileno()))
        if (len(raw) > MAX_PREPARATION_BYTES or _stamp(opened) != after
                or before != _stamp(io_path(self.resolver._safe(path)).stat())):
            raise _error('Preparation is oversized or changed while reading it', 'binding_integrity_error')
        def unique(items):
            result = {}
            for key, value in items:
                if key in result:
                    raise _error('Duplicate preparation metadata field', 'binding_integrity_error')
                result[key] = value
            return result
        saved = PreparedConsumerBinding.model_validate(json.loads(raw.decode('utf-8'), object_pairs_hook=unique))
        self._scope(saved.request, principal)
        if (saved.preparation_id != preparation_id or record['digest'] != saved.request_digest
                or record['receipt'] != dict(preparation_id=preparation_id, request_digest=saved.request_digest,
                                            payload_digest=saved.payload_digest)):
            raise _error('Preparation does not match its durable claim', 'binding_integrity_error')
        receipts = self._receipts(saved.request, preparation_id, cached=saved.receipts, controller_epoch=controller_epoch)
        rebuilt = self._build(saved.request, preparation_id, receipts)
        if (rebuilt != saved or self._claim(preparation_id, principal) != record
                or _stamp(io_path(self.resolver._safe(path)).stat()) != before):
            raise _error('Cached preparation changed its verified payload or authority', 'binding_integrity_error')
        return saved

    def audit(self, prepared, *, principal, controller_epoch=None):
        supplied = PreparedConsumerBinding.model_validate(prepared)
        saved = self.load(supplied.preparation_id, principal=principal, controller_epoch=controller_epoch)
        if saved != supplied:
            raise _error('Supplied preparation differs from its durable host record', 'binding_integrity_error')
        return saved


__all__ = ['SharedConsumerPreparer', 'PreparedConsumerBinding', 'validate_prepared_projection']
