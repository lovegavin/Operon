"""Deterministic single-unit projection onto the existing invocation host pool."""
from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from operon.contracts.base import ContractError, ContractModel, sha256_hex
from operon.contracts.plan_operations import BoundInput, PlanExecutionBinding
from operon.contracts.run_plan import RunPlan
from operon.planning.validation import validate_run_plan
from operon.execution.unit_executor import unit_dependencies
from .artifact_bindings import ProducerArtifactRequest

CAPABILITY = 'cluster.invocation.v1'
CONSUMER_CAPABILITY = 'cluster.same_host_artifacts.v1'


class InvocationDispatch(ContractModel):
    format: Literal['operon.cluster-invocation-dispatch'] = 'operon.cluster-invocation-dispatch'
    schema_version: Literal[1] = 1
    workspace: str = Field(min_length=1, max_length=2048)
    source_plan_id: str = Field(min_length=1, max_length=64)
    source_unit_id: str = Field(min_length=1, max_length=200)
    source_unit_digest: str = Field(pattern=r'^[a-f0-9]{64}$')
    plan: RunPlan
    binding: PlanExecutionBinding

    @model_validator(mode='after')
    def _projected_unit(self):
        validate_run_plan(self.plan)
        if len(self.plan.units) != 1 or self.plan.units[0].unit_id != self.source_unit_id:
            raise ValueError('Cluster invocation must contain exactly its selected source unit')
        unit = self.plan.units[0]
        if unit.retry_policy.maximum_attempts != 1:
            raise ContractError('Projected cluster invocations require a single host attempt until retry lineage is supported',
                                code='unsupported_retry_policy')
        if unit.placement.executor != 'local' or any(source.startswith('artifact:') for source in unit.input_bindings.values()):
            raise ValueError('Projected invocation must be local with every artifact input materialized')
        source = self.plan.execution_policy.get('cluster_projection', {})
        if any(source.get(key) != getattr(self, key) for key in ('source_plan_id', 'source_unit_id', 'source_unit_digest')):
            raise ValueError('Projected invocation lacks its immutable source lineage')
        if source.get('prepared_binding'):
            from .prepared_bindings import validate_prepared_projection
            validate_prepared_projection(self.plan, source_plan_id=self.source_plan_id,
                source_unit_id=self.source_unit_id, source_unit_digest=self.source_unit_digest, binding=self.binding)
        elif source.get('materialized_inputs') or source.get('source_dependencies'):
            raise ContractError('Cross-unit inputs require this run\'s committed producer evidence',
                                code='unverified_artifact_provenance')
        required_inputs = {source[len('input:'):] for source in unit.input_bindings.values() if source.startswith('input:')}
        if not required_inputs.issubset(self.binding.inputs):
            raise ValueError('Projected invocation lacks a bound input')
        if unit.invocation.environment_ref not in self.binding.environments:
            raise ValueError('Projected invocation lacks its environment generation')
        return self


class InvocationTemplate(ContractModel):
    format: Literal['operon.cluster-invocation-template'] = 'operon.cluster-invocation-template'
    schema_version: Literal[1] = 1
    workspace: str = Field(min_length=1, max_length=2048)
    source_plan: RunPlan
    source_unit_id: str = Field(min_length=1, max_length=200)
    binding: PlanExecutionBinding
    # Reserved explicit declarations are rejected until this run's committed
    # producer provenance is connected. Static hashes never replace DAG edges.
    materialized_inputs: dict[str, BoundInput] = Field(default_factory=dict, max_length=128)

    def project(self) -> InvocationDispatch:
        return project_unit(self.source_plan, unit_id=self.source_unit_id, workspace=self.workspace,
                            binding=self.binding, materialized_inputs=self.materialized_inputs)


class ConsumerTemplate(InvocationTemplate):
    """Frozen deployment metadata; downstream bytes are resolved only by the host."""
    format: Literal['operon.cluster-consumer-template'] = 'operon.cluster-consumer-template'
    target_node_id: str = Field(min_length=1, max_length=128)
    target_host_identity: str = Field(min_length=1, max_length=200)

    @model_validator(mode='after')
    def _consumer(self):
        validate_run_plan(self.source_plan)
        source = next((unit for unit in self.source_plan.units if unit.unit_id == self.source_unit_id), None)
        if source is None or source.placement.executor != 'ssh':
            raise ContractError('Consumer template must name a frozen SSH unit', code='unsupported_target')
        if source.retry_policy.maximum_attempts != 1:
            raise ContractError('Projected cluster invocations require a single host attempt until retry lineage is supported',
                                code='unsupported_retry_policy')
        if source.placement.node_id not in (None, self.target_node_id):
            raise ContractError('Consumer template differs from its explicit node', code='unsupported_target')
        if self.materialized_inputs:
            raise ContractError('Static paths cannot substitute for committed producer evidence',
                                code='unverified_artifact_provenance')
        references = {value for value in source.input_bindings.values() if value.startswith('artifact:')}
        parents = {value[len('artifact:'):].split('/', 1)[0] for value in references}
        if not references or len(references) > 128:
            raise ContractError('Consumer templates require 1..128 declared artifact inputs', code='invalid_plan_edge')
        if unit_dependencies(self.source_plan)[source.unit_id] != parents:
            raise ContractError('Control-only cross-unit dependencies are not supported by same-host materialization',
                                code='unsupported_control_dependency')
        return self


class ConsumerIntent(ConsumerTemplate):
    """Durable dispatch input contains identities, never producer filesystem paths."""
    format: Literal['operon.cluster-consumer-intent'] = 'operon.cluster-consumer-intent'
    cluster_run_id: str = Field(min_length=1, max_length=200)
    producers: dict[str, ProducerArtifactRequest] = Field(min_length=1, max_length=128)

    @model_validator(mode='after')
    def _producer_scope(self):
        unit = next(unit for unit in self.source_plan.units if unit.unit_id == self.source_unit_id)
        required = {value for value in unit.input_bindings.values() if value.startswith('artifact:')}
        if set(self.producers) != required:
            raise ContractError('Producer receipts do not match the frozen consumer inputs', code='invalid_plan_edge')
        for edge, producer in self.producers.items():
            unit_id, output_port = edge[len('artifact:'):].split('/', 1)
            if (producer.cluster_run_id != self.cluster_run_id or producer.cluster_unit_id != unit_id
                    or producer.output_port != output_port):
                raise ContractError('Producer identity belongs to another run or frozen port',
                                    code='unverified_artifact_provenance')
        return self

    def identity_payload(self):
        value = self.model_dump(mode='json')
        # An epoch refresh authorizes observation of the same owned producer;
        # it does not change the immutable submission or preparation identity.
        for producer in value['producers'].values():
            producer.pop('controller_epoch')
        return value


def consumer_intent(template, rows, *, principal, cluster_run_id, controller_id, controller_epoch):
    """Bind a template to committed controller receipts outside the placement pass.

    The host re-verifies all evidence; these records only identify its producer.
    Every parent must already be on the selected node and capacity authority.
    """
    template = ConsumerTemplate.model_validate(template)
    source = next(unit for unit in template.source_plan.units if unit.unit_id == template.source_unit_id)
    references = {value for value in source.input_bindings.values() if value.startswith('artifact:')}
    sources = {unit.unit_id: unit for unit in template.source_plan.units}
    by_unit = {}
    for row in rows:
        unit_id = row['unit_id']
        if unit_id in by_unit:
            raise ContractError('Producer has ambiguous committed placements', code='producer_not_committed')
        by_unit[unit_id] = row
    producers = {}
    for edge in sorted(references):
        parent, port = edge[len('artifact:'):].split('/', 1)
        row = by_unit.get(parent)
        if row is None:
            raise ContractError('Producer has no durable committed placement', code='producer_not_committed')
        if (row['run_id'] != cluster_run_id or row['principal'] != principal
                or row['plan_id'] != template.source_plan.plan_id or row['controller_id'] != controller_id
                or sha256_hex(row['spec']) != sha256_hex(sources[parent])):
            raise ContractError('Producer receipt differs from the frozen run identity', code='unverified_artifact_provenance')
        if row['executor'] != 'ssh' or row['node_id'] != template.target_node_id:
            raise ContractError('Cross-host artifact transfer is not configured', code='cross_host_artifact_unavailable')
        evidence = row['evidence']
        expected = {'request_key': row['request_key'], 'command_id': row['command_id'],
            'cluster_run_id': cluster_run_id, 'cluster_unit_id': parent, 'cluster_attempt_id': row['attempt_id'],
            'host_identity': template.target_host_identity, 'host_run_id': row['external_handle'],
            'host_fence': row['host_fence'], 'principal': principal, 'submission_kind': 'plan', 'state': 'succeeded'}
        if (row['state'] != 'succeeded' or row['unit_state'] != 'succeeded'
                or any(evidence.get(key) != value for key, value in expected.items())
                or any(evidence.get(flag) is not True for flag in ('tree_exited', 'resources_released', 'artifact_committed'))):
            raise ContractError('Producer completion receipt is incomplete or inconsistent', code='producer_not_committed')
        artifact = evidence.get('artifact', {})
        producers[edge] = ProducerArtifactRequest(controller_epoch=controller_epoch,
            request_key=row['request_key'], command_id=row['command_id'], cluster_run_id=cluster_run_id,
            cluster_unit_id=parent, cluster_attempt_id=row['attempt_id'], host_run_id=row['external_handle'],
            host_unit_id=evidence.get('host_unit_id'), host_attempt_id=evidence.get('host_attempt_id'),
            host_fence=row['host_fence'], artifact_id=artifact.get('artifact_id'), artifact_digest=artifact.get('digest'),
            output_port=port, binding_key='consumer:' + sha256_hex({'run': cluster_run_id,
                'unit': template.source_unit_id, 'edge': edge}))
    raw = template.model_dump(mode='json')
    raw.update(format='operon.cluster-consumer-intent', cluster_run_id=cluster_run_id, producers=producers)
    return ConsumerIntent.model_validate(raw)


def project_unit(source_plan, *, unit_id, workspace, binding, materialized_inputs=None):
    source_plan = validate_run_plan(RunPlan.model_validate(source_plan))
    binding = PlanExecutionBinding.model_validate(binding)
    sources = {unit.unit_id: unit for unit in source_plan.units}
    if unit_id not in sources:
        raise ContractError('Source unit is absent from the frozen RunPlan', code='invalid_plan_edge')
    original = sources[unit_id]
    if original.retry_policy.maximum_attempts != 1:
        raise ContractError('Projected cluster invocations require a single host attempt until retry lineage is supported',
                            code='unsupported_retry_policy')
    if original.placement.executor != 'ssh':
        raise ContractError('SSH projection requires an explicit SSH unit', code='unsupported_target')
    supplied = {key: BoundInput.model_validate(value).model_dump(mode='json')
                for key, value in (materialized_inputs or {}).items()}
    needed = {value for value in original.input_bindings.values() if value.startswith('artifact:')}
    if needed != set(supplied):
        raise ContractError('Cross-unit artifacts must be explicitly materialized before dispatch',
                            code='unresolved_artifact_input', details={'missing': sorted(needed - set(supplied)),
                                                                     'unexpected': sorted(set(supplied) - needed)})
    dependencies = unit_dependencies(source_plan)[unit_id]
    if needed or dependencies:
        raise ContractError('Cross-unit inputs require this run\'s committed producer evidence',
                            code='unverified_artifact_provenance')
    unit = original.model_dump(mode='json')
    bound = binding.model_dump(mode='json')
    source_placement = dict(unit['placement'])
    unit['placement'] = {**source_placement, 'executor': 'local', 'node_id': None, 'pool_id': None}
    raw = source_plan.model_dump(mode='json')
    raw['units'] = [unit]
    nodes = set(unit['node_ids'])
    raw['edges'] = [edge for edge in raw['edges'] if edge.get('source') in nodes and edge.get('target') in nodes]
    lineage = {'source_plan_id': source_plan.plan_id, 'source_unit_id': unit_id,
               'source_unit_digest': sha256_hex(original), 'source_placement': source_placement,
               'materialized_inputs': {}, 'source_dependencies': []}
    raw['execution_policy'] = {**raw['execution_policy'], 'cluster_projection': lineage}
    projected = RunPlan.model_validate(raw).with_identity()
    return InvocationDispatch(workspace=workspace, source_plan_id=source_plan.plan_id,
        source_unit_id=unit_id, source_unit_digest=lineage['source_unit_digest'], plan=projected,
        binding=PlanExecutionBinding.model_validate(bound))


__all__ = ['CAPABILITY', 'CONSUMER_CAPABILITY', 'InvocationDispatch', 'InvocationTemplate',
           'ConsumerTemplate', 'ConsumerIntent', 'consumer_intent', 'project_unit']
