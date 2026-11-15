"""Explicit RunPlan export requests, separate from legacy graph export."""
from typing import Any, Literal

from pydantic import Field, field_validator

from .base import ContractModel
from .plan_operations import BoundEnvironment, binding_path
from .run_plan import RunPlan


class ExportFile(ContractModel):
    path: str = Field(min_length=1, max_length=2048)
    sha256: str = Field(pattern=r'^[a-f0-9]{64}$')
    role: str = Field(default='resource', min_length=1, max_length=80)
    _path = field_validator('path')(binding_path)


class ExportImplementation(ContractModel):
    implementation: dict[str, Any]
    files: dict[str, ExportFile] = Field(min_length=1, max_length=10000)

    @field_validator('files')
    @classmethod
    def destinations(cls, value):
        for name in value:
            if binding_path(name) != name:
                raise ValueError('Export destination names must be normalized relative paths')
        return value


class PlanExportRequest(ContractModel):
    plan: RunPlan
    request_id: str = Field(min_length=1, max_length=512)
    source_root: str = Field(min_length=1, max_length=2048)
    environment_store: str = Field(min_length=1, max_length=2048)
    output: str = Field(min_length=1, max_length=2048)
    implementations: dict[str, ExportImplementation] = Field(default_factory=dict, max_length=4096)
    environments: dict[str, BoundEnvironment] = Field(min_length=1, max_length=128)
    extra_files: dict[str, ExportFile] = Field(default_factory=dict, max_length=10000)
    management_environment: str | None = Field(default=None, min_length=1, max_length=200)
    input_bindings: dict[str, str] = Field(default_factory=dict, max_length=4096)
    input_formats: dict[str, Literal['form', 'file', 'table', 'json', 'npy', 'report', 'figure']] = Field(default_factory=dict, max_length=4096)
    _paths = field_validator('source_root', 'environment_store', 'output')(binding_path)

    @field_validator('extra_files')
    @classmethod
    def extra_destinations(cls, value):
        for name in value:
            if binding_path(name) != name:
                raise ValueError('Export destination names must be normalized relative paths')
        return value

    @field_validator('input_bindings')
    @classmethod
    def input_paths(cls, value):
        return {name: binding_path(path) for name, path in value.items()}
