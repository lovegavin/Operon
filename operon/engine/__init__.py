"""Operon execution engine: durable state, scheduling, resources and channels.

The package is transport independent.  Desktop services, the headless CLI,
MCP and the SSH server adapt to it; a scientific operator never imports a UI
server to execute.
"""
from .contracts import (  # noqa: F401
    ACTIVE_ATTEMPT_STATES, ACTIVE_RUN_STATES, ALLOWED_TRANSITIONS, AttemptState, BusyError, CorruptArtifactError,
    CommitOutcomeUnknown, CursorExpiredError, EngineError, EngineUnavailableError,
    IdempotencyConflictError, InfeasibleResourcesError, PoolSpec, ProcessIdentity,
    ResourceRequest, ResizeProposal, RunPlan, RunState, SCHEMA_VERSION, StaleAttemptError, StaleRevisionError,
    TERMINAL_ATTEMPT_STATES, TERMINAL_RUN_STATES, UnitPlan, UnauthorizedError, UnavailableStateError,
    UnsupportedOperationError, UnsupportedResizeError, canonical, digest, transition_allowed,
)
from .state import ClaimResult, StateStore  # noqa: F401
from .events import EventStream, Page, Subscription, compact_run  # noqa: F401

__all__ = [
    'ACTIVE_ATTEMPT_STATES', 'ACTIVE_RUN_STATES', 'ALLOWED_TRANSITIONS', 'AttemptState', 'BusyError',
    'ClaimResult', 'CommitOutcomeUnknown', 'CorruptArtifactError', 'CursorExpiredError', 'EngineError',
    'EngineUnavailableError', 'EventStream',
    'IdempotencyConflictError', 'InfeasibleResourcesError', 'Page', 'PoolSpec', 'ProcessIdentity',
    'ResourceRequest', 'ResizeProposal', 'RunPlan', 'RunState', 'SCHEMA_VERSION', 'StateStore',
    'StaleAttemptError', 'StaleRevisionError', 'Subscription', 'TERMINAL_ATTEMPT_STATES',
    'TERMINAL_RUN_STATES', 'UnitPlan', 'UnauthorizedError', 'UnavailableStateError',
    'UnsupportedOperationError', 'UnsupportedResizeError', 'canonical', 'compact_run', 'digest',
    'transition_allowed',
]
