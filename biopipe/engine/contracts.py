"""Immutable contracts shared by local, headless and remote execution.

The engine deliberately keeps its internal records independent from the desktop
models: a scientific worker must not import a UI server to use the execution
engine.  Records are frozen dataclasses; every mutation replaces the value and
is persisted through :mod:`biopipe.engine.state`.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import Enum
import hashlib
import json
import re
from typing import Any, Iterable, Mapping, Sequence

SCHEMA_VERSION = 1
ENGINE_VERSION = 1

PRINCIPAL_PATTERN = re.compile(r'^[A-Za-z0-9_.:@-]{1,128}$')
POOL_PATTERN = re.compile(r'^[A-Za-z0-9_.:-]{1,160}$')


class EngineError(Exception):
    """Stable machine-readable engine failure.

    Adapters translate the code into the existing user-facing message; agents
    never have to parse prose.
    """

    code = 'engine_error'
    status = 400

    def __init__(self, message: str, *, code: str | None = None, status: int | None = None,
                 retry_after: float | None = None, details: Mapping[str, Any] | None = None):
        super().__init__(message)
        if code:
            self.code = code
        if status is not None:
            self.status = status
        self.retry_after = retry_after
        self.details = dict(details or {})


class BusyError(EngineError):
    code = 'busy'
    status = 429

    def __init__(self, message='The engine is at its configured concurrency limit', **kwargs):
        kwargs.setdefault('retry_after', 0.2)
        super().__init__(message, **kwargs)


class UnauthorizedError(EngineError):
    code = 'unauthorized'
    status = 403


class StaleRevisionError(EngineError):
    code = 'stale_revision'
    status = 409


class IdempotencyConflictError(EngineError):
    code = 'idempotency_conflict'
    status = 409


class UnsupportedOperationError(EngineError):
    code = 'capability_unavailable'
    status = 409


class InfeasibleResourcesError(EngineError):
    code = 'infeasible_resources'
    status = 422


class UnsupportedResizeError(EngineError):
    code = 'unsupported_resize'
    status = 409


class StaleAttemptError(EngineError):
    code = 'stale_attempt'
    status = 409


class CorruptArtifactError(EngineError):
    code = 'corrupt_artifact'
    status = 422


class UnavailableStateError(EngineError):
    code = 'unrecoverable_state'
    status = 503


class CommitOutcomeUnknown(EngineError):
    """A transaction commit raised; the durable outcome is not knowable here."""

    code = 'commit_outcome_unknown'
    status = 503

    def __init__(self, message='The durable transaction outcome is unknown', **kwargs):
        super().__init__(message, **kwargs)


class EngineUnavailableError(EngineError):
    """The transaction was definitely not committed; retry is safe."""

    code = 'engine_unavailable'
    status = 503

    def __init__(self, message='The durable engine is temporarily unavailable', **kwargs):
        super().__init__(message, **kwargs)


class CursorExpiredError(EngineError):
    code = 'cursor_expired'
    status = 410

    def __init__(self, *args, snapshot_required=True, **kwargs):
        super().__init__(*args, **kwargs)
        self.snapshot_required = snapshot_required


def canonical(value: Any) -> str:
    """Stable JSON encoding used for digests and idempotency."""
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False,
                      allow_nan=False, default=_json_default)


def _json_default(value: Any):
    if hasattr(value, 'model_dump'):
        return value.model_dump(mode='json')
    if isinstance(value, (set, tuple)):
        return list(value)
    raise TypeError(f'{type(value).__name__} is not JSON serializable')


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value).encode('utf-8')).hexdigest()


@dataclass(frozen=True)
class ResourceRequest:
    """A resource envelope.

    ``managed_budget_bytes`` is the local managed-store/workspace planning limit.
    ``process_reservation_bytes`` covers the interpreter, native allocators and
    owned child processes and is the quantity charged against the RAM pool.
    Scratch is charged against a separate disk capacity, never silently to RAM.
    """

    managed_budget_bytes: int = 0
    process_reservation_bytes: int = 0
    cpu_threads: int = 1
    scratch_reserved_bytes: int = 0
    transport_reserved_bytes: int = 0
    shared_buffer_bytes: int = 0
    devices: tuple[str, ...] = ()

    def __post_init__(self):
        for name in ('managed_budget_bytes', 'process_reservation_bytes', 'scratch_reserved_bytes',
                     'transport_reserved_bytes', 'shared_buffer_bytes'):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(f'{name} must be a non-negative integer')
        if isinstance(self.cpu_threads, bool) or not isinstance(self.cpu_threads, int) or self.cpu_threads < 0:
            raise ValueError('cpu_threads must be a non-negative integer')
        if any(not isinstance(item, str) or not item for item in self.devices):
            raise ValueError('device ids must be nonempty strings')
        if self.managed_budget_bytes and self.process_reservation_bytes < self.managed_budget_bytes:
            # The process reservation must cover the managed budget it protects.
            raise ValueError('process_reservation_bytes cannot be smaller than managed_budget_bytes')

    @property
    def ram_bytes(self) -> int:
        """Physical pool charge.  The managed budget is a sub-limit, not extra RAM."""
        return self.process_reservation_bytes + self.transport_reserved_bytes + self.shared_buffer_bytes

    def scaled(self, *, managed_budget_bytes: int | None = None,
               process_reservation_bytes: int | None = None) -> 'ResourceRequest':
        return replace(self,
                       managed_budget_bytes=self.managed_budget_bytes if managed_budget_bytes is None else managed_budget_bytes,
                       process_reservation_bytes=self.process_reservation_bytes if process_reservation_bytes is None else process_reservation_bytes)

    def with_transport(self, value: int) -> 'ResourceRequest':
        return replace(self, transport_reserved_bytes=value)

    def to_json(self) -> dict:
        return {
            'managed_budget_bytes': self.managed_budget_bytes,
            'process_reservation_bytes': self.process_reservation_bytes,
            'cpu_threads': self.cpu_threads,
            'scratch_reserved_bytes': self.scratch_reserved_bytes,
            'transport_reserved_bytes': self.transport_reserved_bytes,
            'shared_buffer_bytes': self.shared_buffer_bytes,
            'devices': list(self.devices),
        }

    @classmethod
    def from_json(cls, value: Mapping[str, Any] | None) -> 'ResourceRequest':
        value = dict(value or {})
        return cls(
            managed_budget_bytes=int(value.get('managed_budget_bytes', 0)),
            process_reservation_bytes=int(value.get('process_reservation_bytes', 0)),
            cpu_threads=int(value.get('cpu_threads', 1)),
            scratch_reserved_bytes=int(value.get('scratch_reserved_bytes', 0)),
            transport_reserved_bytes=int(value.get('transport_reserved_bytes', 0)),
            shared_buffer_bytes=int(value.get('shared_buffer_bytes', 0)),
            devices=tuple(str(item) for item in value.get('devices', ())),
        )


@dataclass(frozen=True)
class PoolSpec:
    """Startup-frozen capacity for one OS principal and capacity domain.

    The ceiling and reserves are computed once, from the existing host
    admission snapshot.  Scheduling only redistributes capacity inside them.
    """

    pool_id: str
    principal: str
    capacity_domain: str
    ceiling_bytes: int
    management_reserve_bytes: int
    cpu_threads: int
    scratch_bytes: int = 0
    transport_reserve_bytes: int = 0
    shared_buffer_reserve_bytes: int = 0
    device_ids: tuple[str, ...] = ()
    policy_revision: str = 'fair-v1'
    mode: str = 'legacy'

    def __post_init__(self):
        if not POOL_PATTERN.match(self.pool_id or ''):
            raise ValueError('pool_id must be a stable identifier')
        if not PRINCIPAL_PATTERN.match(self.principal or ''):
            raise ValueError('principal must be a stable identifier')
        if not self.capacity_domain:
            raise ValueError('capacity_domain is required')
        for name in ('ceiling_bytes', 'management_reserve_bytes', 'cpu_threads', 'scratch_bytes',
                     'transport_reserve_bytes', 'shared_buffer_reserve_bytes'):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(f'{name} must be a non-negative integer')
        if self.ceiling_bytes <= self.management_reserve_bytes:
            raise ValueError('the pool ceiling must exceed the management reserve')
        if self.cpu_threads < 1:
            raise ValueError('cpu_threads must be at least one')
        if self.mode not in ('legacy', 'shadow', 'coordinator'):
            raise ValueError('mode must be legacy, shadow or coordinator')

    @property
    def schedulable_bytes(self) -> int:
        return self.ceiling_bytes - self.management_reserve_bytes

    def to_json(self) -> dict:
        return {
            'pool_id': self.pool_id, 'principal': self.principal, 'capacity_domain': self.capacity_domain,
            'ceiling_bytes': self.ceiling_bytes, 'management_reserve_bytes': self.management_reserve_bytes,
            'cpu_threads': self.cpu_threads, 'scratch_bytes': self.scratch_bytes,
            'transport_reserve_bytes': self.transport_reserve_bytes,
            'shared_buffer_reserve_bytes': self.shared_buffer_reserve_bytes,
            'device_ids': list(self.device_ids), 'policy_revision': self.policy_revision, 'mode': self.mode,
        }

    @classmethod
    def from_json(cls, value: Mapping[str, Any]) -> 'PoolSpec':
        return cls(pool_id=value['pool_id'], principal=value['principal'],
                   capacity_domain=value['capacity_domain'], ceiling_bytes=int(value['ceiling_bytes']),
                   management_reserve_bytes=int(value['management_reserve_bytes']),
                   cpu_threads=int(value['cpu_threads']),
                   scratch_bytes=int(value.get('scratch_bytes', 0)),
                   transport_reserve_bytes=int(value.get('transport_reserve_bytes', 0)),
                   shared_buffer_reserve_bytes=int(value.get('shared_buffer_reserve_bytes', 0)),
                   device_ids=tuple(str(item) for item in value.get('device_ids', ())),
                   policy_revision=value.get('policy_revision', 'fair-v1'),
                   mode=value.get('mode', 'legacy'))


class RunState(str, Enum):
    SUBMITTED = 'submitted'
    QUEUED = 'queued'
    RUNNING = 'running'
    COMPLETE = 'complete'
    FAILED = 'failed'
    CANCELLED = 'cancelled'
    RECOVERY_REQUIRED = 'recovery_required'


ACTIVE_RUN_STATES = frozenset({RunState.SUBMITTED, RunState.QUEUED, RunState.RUNNING, RunState.RECOVERY_REQUIRED})
TERMINAL_RUN_STATES = frozenset({RunState.COMPLETE, RunState.FAILED, RunState.CANCELLED})


class AttemptState(str, Enum):
    BLOCKED = 'blocked'
    READY = 'ready'
    ADMITTED = 'admitted'
    STARTING = 'starting'
    RUNNING = 'running'
    COMMITTING = 'committing'
    SUCCEEDED = 'succeeded'
    FAILED = 'failed'
    CANCELLED = 'cancelled'
    RECOVERY_REQUIRED = 'recovery_required'


ACTIVE_ATTEMPT_STATES = frozenset({AttemptState.ADMITTED, AttemptState.STARTING, AttemptState.RUNNING,
                                   AttemptState.COMMITTING, AttemptState.RECOVERY_REQUIRED})
TERMINAL_ATTEMPT_STATES = frozenset({AttemptState.SUCCEEDED, AttemptState.FAILED, AttemptState.CANCELLED})

ALLOWED_TRANSITIONS: Mapping[AttemptState, frozenset[AttemptState]] = {
    AttemptState.BLOCKED: frozenset({AttemptState.READY, AttemptState.FAILED, AttemptState.CANCELLED}),
    AttemptState.READY: frozenset({AttemptState.ADMITTED, AttemptState.FAILED, AttemptState.CANCELLED}),
    AttemptState.ADMITTED: frozenset({AttemptState.STARTING, AttemptState.RUNNING, AttemptState.FAILED,
                                     AttemptState.CANCELLED, AttemptState.RECOVERY_REQUIRED}),
    AttemptState.STARTING: frozenset({AttemptState.RUNNING, AttemptState.FAILED, AttemptState.CANCELLED,
                                     AttemptState.RECOVERY_REQUIRED}),
    AttemptState.RUNNING: frozenset({AttemptState.COMMITTING, AttemptState.SUCCEEDED, AttemptState.FAILED,
                                    AttemptState.CANCELLED, AttemptState.RECOVERY_REQUIRED}),
    AttemptState.COMMITTING: frozenset({AttemptState.SUCCEEDED, AttemptState.FAILED, AttemptState.CANCELLED,
                                       AttemptState.RECOVERY_REQUIRED}),
    AttemptState.RECOVERY_REQUIRED: frozenset({AttemptState.SUCCEEDED, AttemptState.FAILED, AttemptState.CANCELLED,
                                              AttemptState.RUNNING, AttemptState.READY}),
    AttemptState.SUCCEEDED: frozenset(),
    AttemptState.FAILED: frozenset(),
    AttemptState.CANCELLED: frozenset(),
}


def transition_allowed(before: AttemptState | str, after: AttemptState | str) -> bool:
    """Central transition table.  Completion/cancel races use this check."""
    before, after = AttemptState(before), AttemptState(after)
    return after in ALLOWED_TRANSITIONS[before]


@dataclass(frozen=True)
class ProcessIdentity:
    pid: int
    created: float
    boot_id: str | None = None
    host: str | None = None

    @property
    def stable(self) -> str:
        return f'{self.host or "local"}:{self.boot_id or "session"}:{self.pid}:{self.created:.6f}'

    def to_json(self) -> dict:
        return {'pid': self.pid, 'created': self.created, 'boot_id': self.boot_id, 'host': self.host}

    @classmethod
    def from_json(cls, value: Mapping[str, Any] | None) -> 'ProcessIdentity | None':
        if not value:
            return None
        try:
            return cls(pid=int(value['pid']), created=float(value['created']),
                       boot_id=value.get('boot_id'), host=value.get('host'))
        except (KeyError, TypeError, ValueError):
            return None


@dataclass(frozen=True)
class UnitPlan:
    """One schedulable execution unit (a whole stage or an independent branch)."""

    unit_id: str
    node_ids: tuple[str, ...]
    depends_on: tuple[str, ...] = ()
    target: Mapping[str, Any] = field(default_factory=lambda: {'kind': 'local'})
    requirement: ResourceRequest = field(default_factory=ResourceRequest)
    capability: str = 'legacy-sequential'
    group: str | None = None
    retry_limit: int = 1

    def to_json(self) -> dict:
        return {'unit_id': self.unit_id, 'node_ids': list(self.node_ids),
                'depends_on': list(self.depends_on), 'target': dict(self.target),
                'requirement': self.requirement.to_json(), 'capability': self.capability,
                'group': self.group, 'retry_limit': self.retry_limit}


@dataclass(frozen=True)
class RunPlan:
    """Frozen submission plan.  The digest is the cache/resume identity base."""

    run_id: str
    workspace_id: str
    principal: str
    project: str
    plan_key: str
    graph: Mapping[str, Any]
    parameters: Mapping[str, Any]
    execution: Mapping[str, Any]
    units: tuple[UnitPlan, ...]
    inputs: tuple[Mapping[str, Any], ...] = ()
    created_at: str = ''

    def to_json(self) -> dict:
        return {'run_id': self.run_id, 'workspace_id': self.workspace_id, 'principal': self.principal,
                'project': self.project, 'plan_key': self.plan_key, 'graph': dict(self.graph),
                'parameters': dict(self.parameters), 'execution': dict(self.execution),
                'units': [unit.to_json() for unit in self.units], 'inputs': [dict(item) for item in self.inputs],
                'created_at': self.created_at}

    @property
    def digest(self) -> str:
        return digest({'plan_key': self.plan_key, 'graph': self.graph, 'parameters': self.parameters,
                       'execution': self.execution, 'units': [unit.to_json() for unit in self.units],
                       'inputs': list(self.inputs)})


@dataclass(frozen=True)
class ResizeProposal:
    """A revisioned resize intent; targets are never free memory."""

    lease_id: str
    attempt_id: str
    fence: int
    resize_id: str
    revision: int
    state: str
    current: ResourceRequest
    target: ResourceRequest
    requested_process_release: int = 0
    acknowledged_process_release: int = 0
    ack_state: str = 'pending'
    created_at: str = ''
    updated_at: str = ''

    def to_json(self) -> dict:
        return {'lease_id': self.lease_id, 'attempt_id': self.attempt_id, 'fence': self.fence,
                'resize_id': self.resize_id, 'revision': self.revision, 'state': self.state,
                'current': self.current.to_json(), 'target': self.target.to_json(),
                'requested_process_release': self.requested_process_release,
                'acknowledged_process_release': self.acknowledged_process_release,
                'ack_state': self.ack_state, 'created_at': self.created_at, 'updated_at': self.updated_at}


@dataclass(frozen=True)
class EventRecord:
    cursor: int
    kind: str
    principal: str
    workspace_id: str | None
    run_id: str | None
    unit_id: str | None
    attempt_id: str | None
    revision: int
    payload: Mapping[str, Any]
    created_at: str

    def to_json(self) -> dict:
        return {'cursor': self.cursor, 'kind': self.kind, 'principal': self.principal,
                'workspace_id': self.workspace_id, 'run_id': self.run_id, 'unit_id': self.unit_id,
                'attempt_id': self.attempt_id, 'revision': self.revision,
                'payload': dict(self.payload), 'created_at': self.created_at}


def normalize_principal(value: str) -> str:
    value = str(value or '').strip()
    if not PRINCIPAL_PATTERN.match(value):
        raise UnauthorizedError('A stable authenticated principal is required')
    return value


def to_bytes(value: float, unit: str) -> int:
    """Convert operator/UI units to integer bytes without silent rounding."""
    scale = {'b': 1, 'kb': 1024, 'mb': 1024 ** 2, 'gb': 1024 ** 3, 'tb': 1024 ** 4}[unit.lower()]
    result = value * scale
    if result < 0 or int(result) != result:
        raise ValueError('resource values must be non-negative whole bytes at this precision')
    return int(result)
