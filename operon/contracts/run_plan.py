"""Versioned RunPlan and invocation records.

The records carry *requirements and references*, not machine-local paths.  A
scheduler creates a separate binding record after choosing a host, environment
generation and input snapshot.
"""
from __future__ import annotations

from copy import deepcopy
from pathlib import PurePosixPath, PureWindowsPath
from typing import Annotated, Any, Literal

from pydantic import Field, field_validator, model_validator

from .base import ContractModel, ContractError, domain_digest, canonical_json, sha256_hex


def validate_relative_path(value: str) -> str:
    normalized = value.replace('\\', '/')
    if (PureWindowsPath(value).drive or PurePosixPath(normalized).is_absolute()
            or '..' in normalized.split('/') or '\x00' in value):
        raise ValueError('Expected a relative path inside its configured root')
    return value


class TargetSpec(ContractModel):
    os: str = Field(min_length=1, max_length=40)
    arch: str = Field(min_length=1, max_length=40)
    python_abi: str | None = Field(default=None, max_length=20)
    capabilities: tuple[str, ...] = ()

    @property
    def key(self) -> str:
        return f'{self.os}-{self.arch}'


NonNegativeInt = Annotated[int, Field(strict=True, ge=0)]


class ResourceRequestSpec(ContractModel):
    managed_budget_bytes: NonNegativeInt = 0
    process_reservation_bytes: NonNegativeInt = 0
    cpu_threads: NonNegativeInt = 1
    scratch_reserved_bytes: NonNegativeInt = 0
    transport_reserved_bytes: NonNegativeInt = 0
    shared_buffer_bytes: NonNegativeInt = 0
    devices: tuple[str, ...] = ()

    @model_validator(mode='after')
    def _budget_fits_reservation(self):
        if self.managed_budget_bytes and self.process_reservation_bytes < self.managed_budget_bytes:
            raise ValueError('process_reservation_bytes must cover managed_budget_bytes')
        return self

    @property
    def ram_bytes(self) -> int:
        return self.process_reservation_bytes + self.transport_reserved_bytes + self.shared_buffer_bytes

    def to_engine(self):
        from operon.engine.contracts import ResourceRequest
        return ResourceRequest(**self.model_dump(mode='json'))


class CodeRef(ContractModel):
    kind: Literal['package', 'file', 'inline', 'workflow', 'script']
    ref: str = ''
    digest: str | None = Field(default=None, pattern=r'^[a-f0-9]{64}$')
    version: str | None = None


class ParametersRef(ContractModel):
    kind: Literal['frozen-json', 'task-parameters', 'none'] = 'frozen-json'
    ref: str = ''
    digest: str | None = Field(default=None, pattern=r'^[a-f0-9]{64}$')


class EnvironmentRequirement(ContractModel):
    target: TargetSpec
    runtime: str = Field(min_length=1, max_length=120)
    dependency_lock: dict[str, Any] = Field(default_factory=dict)
    resources_manifest: dict[str, Any] = Field(default_factory=dict)
    required_capabilities: tuple[str, ...] = ()
    recipe_digest: str | None = Field(default=None, pattern=r'^[a-f0-9]{64}$')


class EnvironmentBinding(ContractModel):
    requirement_digest: str = Field(pattern=r'^[a-f0-9]{64}$')
    target: TargetSpec
    generation_id: str = Field(min_length=1, max_length=200)
    content_digest: str = Field(pattern=r'^[a-f0-9]{64}$')
    verification_receipt: dict[str, Any] = Field(default_factory=dict)


class StorageRef(ContractModel):
    storage_id: str = Field(min_length=1, max_length=160)
    relative_path: str = Field(min_length=1, max_length=2048)
    version: str | None = None
    digest: str | None = Field(default=None, pattern=r'^[a-f0-9]{64}$')

    _relative = field_validator('relative_path')(validate_relative_path)


class ArtifactRef(ContractModel):
    artifact_id: str = Field(min_length=1, max_length=200)
    representation: Literal['form', 'file', 'directory', 'npy', 'table', 'json', 'report', 'figure']
    locations: tuple[str, ...] = ()
    logical_metadata: dict[str, Any] = Field(default_factory=dict)
    size_bytes: NonNegativeInt = 0
    digest: str | None = Field(default=None, pattern=r'^[a-f0-9]{64}$')
    verification: dict[str, Any] = Field(default_factory=dict)
    owner: str = Field(min_length=1, max_length=200)
    lifetime: Literal['attempt', 'run', 'session', 'persistent'] = 'run'


class StorageBinding(ContractModel):
    storage_id: str = Field(min_length=1, max_length=160)
    relative_path: str = Field(min_length=1, max_length=2048)
    version: str | None = None
    digest: str | None = Field(default=None, pattern=r'^[a-f0-9]{64}$')
    access: Literal['read', 'write', 'read-write'] = 'read'

    _relative = field_validator('relative_path')(validate_relative_path)


class InvocationSpec(ContractModel):
    kind: Literal['native', 'python_script', 'r_script', 'command']
    entrypoint: str | None = Field(default=None, max_length=1000)
    argv: tuple[str, ...] = ()
    code_ref: CodeRef
    parameters_ref: ParametersRef = Field(default_factory=ParametersRef)
    environment_ref: str | None = Field(default=None, max_length=200)
    cwd_policy: Literal['attempt-root', 'attempt-root/outputs', 'package-root'] = 'attempt-root'
    event_protocol: Literal['jsonl-v1', 'none'] = 'jsonl-v1'
    output_manifest: str = Field(default='output_manifest.json', max_length=512)

    _relative = field_validator('output_manifest')(validate_relative_path)

    @model_validator(mode='after')
    def _has_command(self):
        if not self.entrypoint and not self.argv:
            raise ValueError('Invocation requires an entrypoint or a literal argv')
        if self.kind == 'command' and not self.argv:
            raise ValueError('A command invocation requires argv')
        return self


class PlacementPolicy(ContractModel):
    executor: Literal['local', 'ssh', 'slurm', 'standalone'] = 'local'
    target: TargetSpec
    node_id: str | None = None
    pool_id: str | None = None
    storage_affinity: tuple[str, ...] = ()


class RetryPolicy(ContractModel):
    maximum_attempts: int = Field(default=1, ge=1, le=100)
    retry_on: tuple[str, ...] = ('transient_infrastructure',)


class CacheContract(ContractModel):
    eligible: bool = False
    reason: str | None = Field(default=None, max_length=500)
    identity: str | None = Field(default=None, pattern=r'^[a-f0-9]{64}$')


class OutputContract(ContractModel):
    name: str = Field(min_length=1, max_length=200)
    representation: Literal['form', 'file', 'directory', 'npy', 'table', 'json', 'report', 'figure']
    required: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)


class UnitSpec(ContractModel):
    unit_id: str = Field(min_length=1, max_length=200)
    node_ids: tuple[str, ...] = Field(min_length=1)
    invocation: InvocationSpec
    input_bindings: dict[str, str] = Field(default_factory=dict)
    output_contracts: tuple[OutputContract, ...] = ()
    resource_request: ResourceRequestSpec
    placement: PlacementPolicy
    retry_policy: RetryPolicy = Field(default_factory=RetryPolicy)
    cache_contract: CacheContract = Field(default_factory=CacheContract)
    # Implementation payload consumed by the native compatibility adapter.  It
    # is hash-bound until K04/K05 replace it with explicit portable bindings.
    payload: dict[str, Any] = Field(default_factory=dict)


class RunPlan(ContractModel):
    format: Literal['operon.run-plan'] = 'operon.run-plan'
    schema_version: Literal[1] = 1
    plan_id: str = Field(min_length=1, max_length=64)
    workflow_revision: str = Field(pattern=r'^[a-f0-9]{64}$')
    units: tuple[UnitSpec, ...] = Field(min_length=1)
    edges: tuple[dict[str, Any], ...] = ()
    parameters_digest: str = Field(pattern=r'^[a-f0-9]{64}$')
    implementations: dict[str, dict[str, Any]] = Field(default_factory=dict)
    environment_requirements: tuple[EnvironmentRequirement, ...] = ()
    storage_bindings: tuple[StorageBinding, ...] = ()
    execution_policy: dict[str, Any] = Field(default_factory=dict)
    compiler_version: str = Field(min_length=1, max_length=80)
    diagnostics: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode='after')
    def _unique_units(self):
        ids = [unit.unit_id for unit in self.units]
        if len(set(ids)) != len(ids):
            raise ValueError('RunPlan unit ids must be unique')
        for unit in self.units:
            if not set(unit.node_ids):
                raise ValueError(f'Unit {unit.unit_id!r} has no node ids')
        return self

    def identity_payload(self) -> dict:
        """The part of the plan that determines execution identity.

        ``plan_id`` and diagnostics are presentation/audit fields.  The
        workflow revision, units, implementation references, environment
        requirements, storage references and execution policy are stable.
        """
        value = self.model_dump(mode='json')
        value.pop('plan_id', None)
        value.pop('diagnostics', None)
        # K02 has a compatibility payload, so bind all executed content until
        # locations are extracted into explicit immutable binding records.
        # Excluding it would allow task code/parameters to change undetected.
        return value

    def compute_id(self) -> str:
        return domain_digest('operon:run-plan:v1', self.identity_payload())

    def with_identity(self) -> 'RunPlan':
        return self.model_copy(update={'plan_id': self.compute_id()})

    def canonical_json(self) -> str:
        return canonical_json(self)


class AttemptReceipt(ContractModel):
    run_id: str = Field(min_length=1, max_length=200)
    unit_id: str = Field(min_length=1, max_length=200)
    attempt_id: str = Field(min_length=1, max_length=200)
    command_id: str = Field(min_length=1, max_length=200)
    executor_kind: Literal['local', 'ssh', 'slurm', 'standalone']
    external_handle: str | None = None
    host_identity: str | None = None
    fence: int = Field(default=0, ge=0)
    evidence_revision: int = Field(default=0, ge=0)

    def identity(self) -> str:
        return domain_digest('operon:attempt-receipt:v1', self.model_dump(mode='json'))


__all__ = [
    'ArtifactRef', 'AttemptReceipt', 'CacheContract', 'CodeRef', 'EnvironmentBinding',
    'EnvironmentRequirement', 'InvocationSpec', 'OutputContract', 'ParametersRef',
    'PlacementPolicy', 'ResourceRequestSpec', 'RetryPolicy', 'RunPlan',
    'StorageBinding', 'StorageRef', 'TargetSpec', 'UnitSpec',
]
