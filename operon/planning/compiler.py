"""Shared metadata-only workflow compiler.

All callers use the existing route/converter graph compiler through a lazy
compatibility boundary. There is one DAG implementation and one RunPlan identity;
importing this package does not import scientific implementations.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import os
from pathlib import Path
import platform
import sys
from typing import Any, Callable, Mapping

from operon.contracts.base import ContractError, sha256_hex
from operon.contracts.run_plan import (
    CacheContract, CodeRef, EnvironmentRequirement, InvocationSpec, OutputContract,
    ParametersRef, PlacementPolicy, ResourceRequestSpec, RetryPolicy, RunPlan,
    StorageBinding, TargetSpec, UnitSpec,
)
from operon.contracts.workflow import FrozenParameters, WorkflowSpec
from .identity import parameters_digest, workflow_revision
from .resolver import CatalogSnapshot, as_catalog, resolve_workflow, selected_descriptors

COMPILER_VERSION = 'operon-planning/1'


@dataclass(frozen=True)
class CompiledWorkflow:
    spec: WorkflowSpec
    values: FrozenParameters
    manifest: dict[str, Any]
    step_ids: tuple[str, ...]
    graph: dict[str, Any] | None = None
    descriptors: tuple[dict[str, Any], ...] = ()


def _target() -> TargetSpec:
    system = platform.system().lower()
    system = {'win32': 'windows'}.get(system, system)
    machine = platform.machine().lower()
    machine = {'amd64': 'x86_64', 'arm64': 'aarch64'}.get(machine, machine)
    return TargetSpec(os=system or 'unknown', arch=machine or 'unknown',
                      python_abi=f'cpython-{sys.version_info.major}.{sys.version_info.minor}',
                      capabilities=())


def _bytes_from_mb(value: Any, default: int = 0) -> int:
    if value is None:
        return default
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
        raise ContractError('Memory limits must be non-negative numbers', code='invalid_resource')
    return int(value * 1024 * 1024)


def _resource_request(manifest: Mapping[str, Any]) -> ResourceRequestSpec:
    memory = (manifest.get('runtime') or {}).get('memory') or {}
    managed = _bytes_from_mb(memory.get('budget_mb'))
    process = _bytes_from_mb(memory.get('process_limit_mb'), managed)
    if process < managed:
        process = managed
    cpu = memory.get('threads', 1)
    if isinstance(cpu, bool) or not isinstance(cpu, int) or cpu < 0:
        cpu = 1
    scratch = _bytes_from_mb(memory.get('disk_limit_mb'))
    return ResourceRequestSpec(managed_budget_bytes=managed, process_reservation_bytes=process,
                               cpu_threads=max(0, cpu), scratch_reserved_bytes=scratch)


def _dependency_closure(descriptors) -> tuple[list[str], dict[str, Any]]:
    dependencies, resources = set(), {}
    for descriptor in descriptors:
        dependencies.update(str(item) for item in (descriptor.get('dependencies') or ()))
        if descriptor.get('resources'):
            resources[descriptor['id']] = deepcopy(descriptor['resources'])
        implementation = descriptor.get('implementation') or {}
        lock = descriptor.get('dependency_lock') or implementation.get('dependency_lock')
        if isinstance(lock, dict):
            resources.setdefault('dependency_locks', {}).update(deepcopy(lock))
    return sorted(dependencies), resources


def _implementations(descriptors) -> dict[str, dict[str, Any]]:
    from .descriptor_snapshot import IDENTITY_FIELDS
    result = {}
    for descriptor in descriptors:
        key = str(descriptor.get('id'))
        result[key] = {
            'kind': descriptor.get('kind'),
            **({'origin': descriptor['origin']} if descriptor.get('origin') is not None else {}),
            'distribution': descriptor.get('distribution') or descriptor.get('package'),
            'version': descriptor.get('version') or (descriptor.get('implementation') or {}).get('version'),
            'implementation': {field: deepcopy(value) for field, value in
                               (descriptor.get('implementation') or {}).items() if field in IDENTITY_FIELDS},
        }
    return result


def _storage_bindings(spec: WorkflowSpec, root: Path | None) -> tuple[StorageBinding, ...]:
    bindings = []
    for node in spec.nodes:
        if node.kind != 'source' or node.source is None:
            continue
        if node.source.storage_ref is not None:
            ref = node.source.storage_ref
            bindings.append(StorageBinding(storage_id=ref.storage_id, relative_path=ref.relative_path,
                                           version=ref.version, digest=ref.digest, access='read'))
            continue
        path = Path(node.source.path)
        storage_id = 'workflow'
        relative = path.as_posix()
        if root is not None or path.is_absolute():
            absolute = (root / path).resolve() if root is not None else path.resolve()
            try:
                if root is None:
                    raise ValueError('No workflow root binding')
                relative = absolute.relative_to(root.resolve()).as_posix()
            except ValueError:
                # Separate external source roots even when basenames coincide.
                # K02 resolves this through the frozen compatibility payload;
                # portable export must supply the explicit root binding.
                storage_id, relative = 'source:' + node.id, absolute.name
        bindings.append(StorageBinding(storage_id=storage_id, relative_path=relative,
                                       access='read'))
    return tuple(bindings)


def _plan_from_compiled(compiled: CompiledWorkflow, catalog: CatalogSnapshot,
                        root: Path | None, *, diagnostics: dict[str, Any] | None = None) -> RunPlan:
    manifest = deepcopy(compiled.manifest)
    task_steps = manifest.get('steps') or []
    step_ids = list(compiled.step_ids)
    if len(step_ids) != len(task_steps):
        raise ContractError('Compiler step identity count does not match the manifest',
                            code='compiler_identity_mismatch')
    target = _target()
    descriptors = compiled.descriptors or selected_descriptors(compiled.spec, catalog)
    from .descriptor_snapshot import execution_descriptor
    dependencies, resources = _dependency_closure(descriptors)
    memory = deepcopy((manifest.get('runtime') or {}).get('memory') or {})
    invocation = InvocationSpec(
        kind='native', entrypoint='operon.execution.worker_main', argv=(),
        code_ref=CodeRef(kind='workflow', ref=compiled.spec.name,
                         digest=workflow_revision(compiled.spec)),
        parameters_ref=ParametersRef(kind='task-parameters', ref='unit.payload.task_manifest'),
        environment_ref='cpython',
        output_manifest='output_manifest.json')
    payload = {'task_manifest': deepcopy(manifest), 'step_ids': step_ids,
               'graph': deepcopy(compiled.graph) if compiled.graph else compiled.spec.to_legacy_dict(),
               'native_descriptors': [execution_descriptor(item) for item in descriptors],
               'native_implementations': _implementations(descriptors)}
    storage_inputs = []
    def lower_storage(graph, *, embedded=False):
        for node in graph.get('nodes', ()):
            source = node.get('source')
            if source and source.get('storage_ref') is not None:
                ref = source.pop('storage_ref')
                if not embedded:
                    storage_inputs.append(ref)
            if node.get('route'):
                lower_storage(node['route']['graph'], embedded=True)
    lower_storage(payload['graph'])
    unit = UnitSpec(
        unit_id='native-chain', node_ids=tuple(step_ids) or tuple(
            node.id for node in compiled.spec.nodes if node.kind != 'source'),
        invocation=invocation,
        input_bindings={name: source.get('path', '') for name, source in (manifest.get('sources') or {}).items()},
        output_contracts=tuple(OutputContract(name=str(step.get('name')), representation='form')
                               for step in task_steps),
        resource_request=_resource_request(manifest),
        placement=PlacementPolicy(executor='local', target=target),
        retry_policy=RetryPolicy(),
        cache_contract=CacheContract(eligible=False, reason='generic native plan has no explicit cache contract'),
        payload=payload,
    )
    environment = EnvironmentRequirement(
        target=target,
        runtime=f'cpython-{sys.version_info.major}.{sys.version_info.minor}',
        dependency_lock={'requirements': dependencies},
        resources_manifest=resources,
        required_capabilities=(),
        recipe_digest=sha256_hex({'requirements': dependencies, 'resources': resources}),
    )
    edges = tuple({'id': edge.id, 'source': edge.source, 'target': edge.target,
                   'source_handle': edge.source_handle, 'target_handle': edge.target_handle}
                  for edge in compiled.spec.edges)
    plan = RunPlan(
        plan_id='pending', workflow_revision=workflow_revision(compiled.spec),
        units=(unit,), edges=edges,
        parameters_digest=parameters_digest(compiled.values),
        implementations=_implementations(descriptors),
        environment_requirements=(environment,),
        storage_bindings=_storage_bindings(compiled.spec, root),
        execution_policy={'memory': memory, 'target': target.model_dump(mode='json'),
                          'admission': 'host-pool', 'environment_refs': {'cpython': sha256_hex(environment)},
                          **({'storage_input_refs': storage_inputs} if storage_inputs else {})},
        compiler_version=COMPILER_VERSION,
        diagnostics={**deepcopy(diagnostics or {}),
                     'native_descriptor_audit': {item['id']: deepcopy(item) for item in descriptors}},
    )
    return plan.with_identity()


class WorkflowCompiler:
    """Compile metadata into one canonical RunPlan.

    All public callers use the same lazy compatibility compiler. The optional
    callable is retained for adapter tests, not an alternative DAG algorithm.
    """

    def __init__(self, legacy_compile: Callable[..., CompiledWorkflow] | None = None,
                 compiler_version: str = COMPILER_VERSION):
        self.legacy_compile = legacy_compile
        self.compiler_version = compiler_version

    def compile_authoring(self, normalized, catalog=None, *, root=None, require_files=False) -> RunPlan:
        """One application facade for native graphs and static foreign units."""
        from .authoring_v2 import NormalizedWorkflow
        from .invocation_lowering import NormalizedForeignWorkflow, NormalizedMixedWorkflow, lower_foreign, lower_mixed
        if isinstance(normalized, NormalizedMixedWorkflow):
            return lower_mixed(normalized, self, catalog, root=root, require_files=require_files)
        if isinstance(normalized, NormalizedForeignWorkflow):
            return lower_foreign(normalized, compiler_version=self.compiler_version, require_files=require_files)
        if not isinstance(normalized, NormalizedWorkflow):
            raise ContractError('Authoring must be normalized before compilation', code='invalid_workflow')
        if any(normalized.document.processes[step.process].environment
               for step in normalized.document.workflow.steps.values()):
            from .invocation_lowering import lower_native_authoring
            return lower_native_authoring(normalized, self, catalog, root=root, require_files=require_files)
        normalized._check_compilation_policy()
        plan = self.compile(normalized.spec, None, catalog, root=root or normalized.spec.base_dir,
                            require_files=require_files, freeze_defaults=False)
        from operon.execution.native_bootstrap import validate_native_descriptors
        for unit in plan.units:
            validate_native_descriptors(unit.payload['native_descriptors'], plan.implementations,
                                        unit.payload['task_manifest'])
        return plan

    def compile(self, spec: WorkflowSpec | Mapping[str, Any],
                values: FrozenParameters | Mapping[str, Any] | None,
                catalog: Mapping[str, Any] | CatalogSnapshot | None,
                *, root: str | Path | None = None,
                require_files: bool = False, freeze_defaults: bool = True) -> RunPlan:
        catalog_snapshot = as_catalog(catalog)
        workflow, frozen, catalog_snapshot = resolve_workflow(spec, values, catalog_snapshot)
        root_path = Path(root).resolve() if root is not None else None
        from .legacy import compile_legacy, freeze_spec
        if freeze_defaults:
            workflow = freeze_spec(workflow, catalog_snapshot, root_path)
        compile_graph = self.legacy_compile or compile_legacy
        options = {'require_files': require_files}
        if not freeze_defaults:
            options['freeze_defaults'] = False
        compiled = compile_graph(workflow, frozen, catalog_snapshot, root_path, **options)
        if not isinstance(compiled, CompiledWorkflow):
            raise ContractError('The compatibility compiler returned an invalid result',
                                code='compiler_adapter_error')
        if compiled.spec != workflow:
            raise ContractError('The compatibility compiler changed the frozen workflow',
                                code='compiler_frozen_mismatch')
        return _plan_from_compiled(compiled, catalog_snapshot, root_path,
                                   diagnostics={'compiler': 'shared-graph-compiler'})
