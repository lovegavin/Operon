"""Strict plan operation/binding records shared by service, HTTP and pool RPC."""
from __future__ import annotations

from pathlib import PurePosixPath
from typing import Any, Literal

from pydantic import Field, field_validator, model_validator

from .base import ContractModel
from .run_plan import RunPlan, validate_relative_path
from .workflow import FrozenParameters


def binding_path(value):
    validate_relative_path(value)
    if ':' in value or not value:
        raise ValueError('Binding paths must be portable workspace-relative paths')
    return str(PurePosixPath(value.replace('\\', '/')))


class BoundEnvironment(ContractModel):
    generation_id: str = Field(min_length=1, max_length=200, pattern=r'^[A-Za-z0-9_.-]+$')
    executable: str = Field(min_length=1, max_length=2048)
    _path = field_validator('executable')(binding_path)


class BoundInput(ContractModel):
    representation: Literal['form', 'file', 'table', 'json', 'npy', 'report', 'figure']
    path: str = Field(min_length=1, max_length=2048)
    size_bytes: int = Field(ge=0)
    sha256: str = Field(pattern=r'^[a-f0-9]{64}$')
    metadata: dict[str, Any] = Field(default_factory=dict)
    _path = field_validator('path')(binding_path)


class PlanExecutionBinding(ContractModel):
    package_root: str = Field(min_length=1, max_length=2048)
    environment_store: str = Field(min_length=1, max_length=2048)
    environments: dict[str, BoundEnvironment] = Field(min_length=1, max_length=128)
    storage: dict[str, str] = Field(default_factory=dict, max_length=128)
    inputs: dict[str, BoundInput] = Field(default_factory=dict, max_length=128)
    _paths = field_validator('package_root', 'environment_store')(binding_path)

    @field_validator('storage')
    @classmethod
    def storage_paths(cls, value):
        return {key: binding_path(path) for key, path in value.items()}

    @model_validator(mode='after')
    def identifiers(self):
        for mapping in (self.environments, self.storage, self.inputs):
            if any(not key or len(key) > 200 or '\x00' in key for key in mapping):
                raise ValueError('Binding identifiers must be nonempty bounded strings')
        return self


class PlanCompileRequest(ContractModel):
    kind: Literal['graph', 'authoring-v2'] = 'graph'
    workflow: dict[str, Any]
    directory: str = Field(default='.', min_length=1, max_length=2048)
    values: FrozenParameters | None = None
    parameters: dict[str, Any] | None = None
    inputs: dict[str, Any] | None = None
    environments: dict[str, Any] | None = None
    profile: str | None = Field(default=None, min_length=1, max_length=160)
    initial: bool = False
    require_files: bool = False
    _directory = field_validator('directory')(binding_path)

    @model_validator(mode='after')
    def source_fields(self):
        if self.kind == 'graph' and (self.directory != '.' or self.parameters is not None or self.inputs is not None
                or self.environments is not None or self.profile is not None or self.initial):
            raise ValueError('Authoring directory/sidecars/profile/initial are only valid for authoring-v2')
        if self.kind == 'authoring-v2' and self.values is not None:
            raise ValueError('Authoring v2 uses its frozen parameters sidecar, not graph values')
        if self.kind == 'authoring-v2' and self.parameters is None:
            raise ValueError('Authoring v2 compile requires an explicit parameters sidecar')
        return self


class PlanSubmitRequest(ContractModel):
    plan: RunPlan
    binding: PlanExecutionBinding
    request_id: str = Field(min_length=1, max_length=512)


class PlanControlScope(ContractModel):
    workspace: str = Field(min_length=1, max_length=32768)
    principal: str | None = Field(default=None, min_length=1, max_length=128)
    session_id: str | None = Field(default=None, min_length=1, max_length=200)


class PlanSubmitControl(PlanControlScope):
    plan: RunPlan
    binding: PlanExecutionBinding
    request_id: str = Field(min_length=1, max_length=512)


class PlanLookupControl(PlanControlScope):
    run_id: str = Field(min_length=1, max_length=200, pattern=r'^[A-Za-z0-9_.:-]+$')


class PlanEventsQuery(ContractModel):
    after: int = Field(default=0, ge=0, le=2**63 - 1)
    limit: int = Field(default=100, ge=1, le=200)
    max_bytes: int = Field(default=32768, ge=2048, le=65536)


class PlanPageQuery(ContractModel):
    after: str = Field(default='', max_length=600, pattern=r'^[A-Za-z0-9_.:/-]*$')
    limit: int = Field(default=100, ge=1, le=200)
    max_bytes: int = Field(default=32768, ge=2048, le=65536)


class PlanLogsQuery(ContractModel):
    attempt_id: str = Field(min_length=1, max_length=200, pattern=r'^[A-Za-z0-9_.:-]+$')
    offset: int = Field(default=0, ge=0, le=2**63 - 1)
    max_bytes: int = Field(default=16384, ge=1, le=65536)
    encoding: Literal['text', 'base64'] = 'text'


class PlanEventsControl(PlanLookupControl, PlanEventsQuery):
    pass


class PlanPageControl(PlanLookupControl, PlanPageQuery):
    pass


class PlanLogsControl(PlanLookupControl, PlanLogsQuery):
    pass
