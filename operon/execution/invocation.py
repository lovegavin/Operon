"""Invocation preparation records and output validation boundary."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from operon.contracts.run_plan import InvocationSpec, UnitSpec


@dataclass(frozen=True)
class InvocationContext:
    attempt_root: Path
    attempt_id: str
    run_id: str
    unit_id: str
    fence: int
    payload: dict[str, Any]
    environment: dict[str, str] = field(default_factory=dict)
    memory_bytes: int = 0
    threads: int = 1


@dataclass(frozen=True)
class ExitReceipt:
    exit_code: int | None
    state: str
    tree_alive: bool = False
    error: str | None = None


@dataclass(frozen=True)
class OutputManifest:
    status: str
    output_dir: str
    run_summary: str | None
    files: tuple[str, ...] = ()
    error: str | None = None


@dataclass(frozen=True)
class PreparedInvocation:
    spec: InvocationSpec
    context: InvocationContext
    task_dir: Path
    task_manifest_path: Path
    output_dir: Path
    command: tuple[str, ...]
    environment: dict[str, str]


class InvocationAdapter(Protocol):
    def prepare(self, invocation: InvocationSpec, context: InvocationContext) -> PreparedInvocation: ...
    def collect(self, prepared: PreparedInvocation, exit_receipt: ExitReceipt) -> OutputManifest: ...


def write_managed_invocation(directory, job, allocation):
    """Called by JobService only after its normal admission/environment gate."""
    from operon.contracts.run_plan import CodeRef, ParametersRef
    from operon.engine.fs import atomic_json
    from operon.bytecode import io_path
    marker = job['graph']['runtime']['native_invocation']
    spec = InvocationSpec(kind='native', entrypoint='operon.execution.worker_main',
                          code_ref=CodeRef(kind='workflow', ref=marker['plan_id'], digest=marker['plan_id']),
                          parameters_ref=ParametersRef(kind='task-parameters', ref='parameters.json'))
    value = {'format': 'operon.invocation', 'schema_version': 1,
             'invocation': spec.model_dump(mode='json'), 'run_id': job['id'],
             'unit_id': 'native-chain', 'attempt_id': str(job.get('coordinator_attempt') or job['id']),
             'fence': int(job.get('coordinator_fence') or 0), 'task_ref': 'task.yaml',
             'parameters_ref': spec.parameters_ref.model_dump(mode='json'),
             'environment': {}, 'memory_bytes': int(allocation.get('budget_bytes') or 0),
             'threads': int(allocation['cpu_threads']), 'output_dir': job['output_dir']}
    path = Path(directory) / 'invocation.json'
    atomic_json(io_path(path), value)
    return path


def verify_implementations(expected, catalog, *, manifest=None):
    from operon.contracts.base import ContractError
    available = {(kind, item['id']): item for kind, section in
                 (('reader', 'readers'), ('operator', 'operators')) for item in catalog.get(section, [])}
    if manifest is not None:
        from operon.planning.legacy import effective_descriptors
        from operon.planning.resolver import as_catalog
        for item in effective_descriptors(manifest, as_catalog(catalog)):
            available[(item.get('kind') or 'operator', item['id'])] = item
    for identifier, record in expected.items():
        descriptor = available.get((record.get('kind') or 'operator', identifier))
        if descriptor is None:
            raise ContractError(f'Implementation is unavailable: {identifier}', code='implementation_unavailable')
        def identity(value):
            return {key: value.get(key) for key in ('version', 'package', 'sha256', 'code_sha')}
        if identity(descriptor.get('implementation') or {}) != identity(record.get('implementation') or {}):
            raise ContractError(f'Implementation changed after compilation: {identifier}',
                                code='implementation_unavailable')
