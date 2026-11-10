"""Revisioned elastic-budget commands at safe step boundaries.

Managed-store budget and process reservation are separate.  Shrinking the
managed budget never returns process credits: native allocators may retain RSS.
Process credits are returned only after a verified release capability succeeds
or the process tree is confirmed gone.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import time
import uuid

from .contracts import EngineError, ResourceRequest, StaleAttemptError, StaleRevisionError, UnsupportedResizeError

REQUEST_NAME = 'resize.request.json'
ACK_NAME = 'resize.ack.json'
STATE_NAME = 'resize.state.json'


class ResizeError(EngineError):
    code = 'resize_failed'
    status = 409


def _read(path):
    try:
        return json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return None


def _write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.tmp-' + uuid.uuid4().hex[:8])
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True), encoding='utf-8')
    os.replace(temporary, path)


@dataclass(frozen=True)
class ResizeCommand:
    lease_id: str
    attempt_id: str
    fence: int
    resize_id: str
    revision: int
    managed_budget_bytes: int
    process_reservation_bytes: int
    release_process_bytes: int = 0

    def to_json(self) -> dict:
        return {'lease_id': self.lease_id, 'attempt_id': self.attempt_id, 'fence': self.fence,
                'resize_id': self.resize_id, 'revision': self.revision,
                'managed_budget_bytes': self.managed_budget_bytes,
                'process_reservation_bytes': self.process_reservation_bytes,
                'release_process_bytes': self.release_process_bytes}


def write_command(task_dir, command: ResizeCommand) -> Path:
    path = Path(task_dir) / REQUEST_NAME
    _write(path, command.to_json())
    return path


def read_ack(task_dir) -> dict | None:
    return _read(Path(task_dir) / ACK_NAME)


def step_boundary_resize(task_dir, memory) -> dict | None:
    """Apply a pending resize at a task boundary; duplicate commands are idempotent.

    Returns the acknowledgement (existing or new), or ``None`` when no resize
    was requested.  A failed managed shrink leaves the previous budget in place
    and reports the failure without corrupting the scientific run.
    """
    task_dir = Path(task_dir)
    request = _read(task_dir / REQUEST_NAME)
    if not request:
        return None
    ack_path = task_dir / ACK_NAME
    previous = _read(ack_path)
    if previous and previous.get('resize_id') == request.get('resize_id') and \
            previous.get('revision') == request.get('revision'):
        return previous
    if previous and int(previous.get('revision', -1)) > int(request.get('revision', 0)):
        # A delayed old command must never overwrite a newer applied budget.
        old = dict(previous)
        old['stale_command'] = True
        return old
    acknowledged = 0
    state = 'acknowledged'
    error = None
    try:
        if memory is None:
            raise ResizeError('The attempt has no managed memory runtime to resize')
        if hasattr(memory, 'update_budget'):
            memory.update_budget(int(request['managed_budget_bytes']))
        else:
            raise ResizeError('This worker does not expose a safe step-boundary resize hook')
    except Exception as exc:  # noqa: BLE001 - the old committed grant remains charged
        state = 'failed'
        error = f'{type(exc).__name__}: {exc}'
    ack = {'resize_id': request.get('resize_id'), 'revision': int(request.get('revision', 0)),
           'lease_id': request.get('lease_id'), 'attempt_id': request.get('attempt_id'),
           'fence': int(request.get('fence', 0)), 'state': state,
           'ack_state': 'acknowledged' if state == 'acknowledged' else 'failed',
           'managed_budget_bytes': int(request.get('managed_budget_bytes', 0)),
           'acknowledged_process_release': 0,
           'error': error, 'applied_at': time.time()}
    _write(ack_path, ack)
    _write(task_dir / STATE_NAME, {'last_applied': ack})
    return ack


class ResizeController:
    """Coordinator-side proposal/ack protocol with process-release verification."""

    def __init__(self, resources, store, *, process_release_verifier=None):
        self.resources = resources
        self.store = store
        # Conservative default: a managed shrink never returns process credits.
        self.process_release_verifier = process_release_verifier or (lambda *args, **kwargs: False)

    def propose(self, attempt_id: str, *, managed_budget_bytes: int,
                release_process_bytes: int = 0, process_reservation_bytes: int | None = None,
                resize_id: str | None = None) -> dict:
        attempt = self.store.attempt(attempt_id)
        unit = self.store.unit(attempt['unit_id'])
        capability = unit.get('capability') or 'legacy-sequential'
        if capability not in ('cooperative-resize-step', 'cooperative-resize-chunk'):
            raise UnsupportedResizeError(
                'This attempt did not declare a cooperative resize capability',
                details={'attempt_id': attempt_id, 'capability': capability})
        if attempt['state'] != 'running':
            raise ResizeError('Resize proposals are accepted only for a running attempt',
                              details={'attempt_id': attempt_id, 'state': attempt['state']})
        lease = self.store.lease(attempt_id)
        if lease is None or lease['state'] == 'released':
            raise ResizeError('The attempt has no active lease')
        current = lease['committed']
        if managed_budget_bytes <= 0 or managed_budget_bytes > max(current.process_reservation_bytes,
                                                                    process_reservation_bytes or 0):
            raise ResizeError('The managed budget must be positive and within the requested process grant')
        release_process_bytes = int(release_process_bytes)
        if release_process_bytes < 0 or release_process_bytes > current.process_reservation_bytes:
            raise ResizeError('release_process_bytes is outside the committed process grant')
        if process_reservation_bytes is not None:
            if release_process_bytes:
                raise ResizeError('A growth proposal cannot also request a process release')
            target_process = max(int(managed_budget_bytes), int(process_reservation_bytes))
        else:
            target_process = max(managed_budget_bytes,
                                 current.process_reservation_bytes - release_process_bytes)
        target = ResourceRequest(
            managed_budget_bytes=int(managed_budget_bytes),
            process_reservation_bytes=target_process,
            cpu_threads=current.cpu_threads,
            scratch_reserved_bytes=current.scratch_reserved_bytes,
            transport_reserved_bytes=current.transport_reserved_bytes,
            shared_buffer_bytes=current.shared_buffer_bytes,
            devices=current.devices)
        self.resources.verify_growth(lease=lease, target=target)
        return self.resources.resize(lease_id=lease['id'], fence=int(attempt['fence']),
                                     resize_id=resize_id or uuid.uuid4().hex,
                                     target=target, requested_process_release=release_process_bytes)

    def acknowledge(self, attempt_id: str, ack: dict) -> dict:
        attempt = self.store.attempt(attempt_id)
        lease = self.store.lease(attempt_id)
        if lease is None:
            raise ResizeError('The attempt has no lease')
        if ack.get('state') != 'acknowledged':
            # Failed shrink keeps the old global grant; never infer release.
            return self.store.reject_resize(lease_id=lease['id'],
                                            resize_id=str(ack.get('resize_id')),
                                            reason=str(ack.get('error') or 'worker refused resize'))
        proposal = lease.get('resize') or {}
        if proposal.get('resize_id') != ack.get('resize_id'):
            raise StaleRevisionError('The resize acknowledgement does not match the current proposal')
        requested = int(proposal.get('requested_process_release', 0) or 0)
        verified = 0
        if requested:
            verifier = self.process_release_verifier
            if verifier(attempt_id, lease, requested):
                verified = requested
            else:
                verified = 0
        return self.resources.acknowledge(lease_id=lease['id'],
                                          resize_id=str(ack['resize_id']),
                                          fence=int(attempt['fence']),
                                          acknowledged_process_release=verified)

    def reject(self, attempt_id: str, *, resize_id: str, reason: str) -> dict:
        lease = self.store.lease(attempt_id)
        if lease is None:
            raise ResizeError('The attempt has no lease')
        return self.store.reject_resize(lease_id=lease['id'], resize_id=resize_id, reason=reason)
