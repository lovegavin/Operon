"""Durable engine state on local SQLite WAL.

One writer owns every transition.  State changes, durable events and outbox
commands commit in the same transaction; process launches never happen inside
one.  The database is intentionally local-only: network workspaces may hold
data, not the coordinator journal.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import threading
import uuid
from typing import Iterable

from .contracts import (
    ACTIVE_ATTEMPT_STATES, ACTIVE_RUN_STATES, AttemptState, BusyError, CommitOutcomeUnknown,
    CorruptArtifactError, CursorExpiredError,
    IdempotencyConflictError, InfeasibleResourcesError, PoolSpec, ResourceRequest, ResizeProposal,
    RunState, SCHEMA_VERSION, StaleAttemptError, StaleRevisionError, TERMINAL_ATTEMPT_STATES,
    TERMINAL_RUN_STATES, UnavailableStateError, transition_allowed,
)

SCHEMA = """
CREATE TABLE IF NOT EXISTS schema_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS pools (
    pool_id TEXT PRIMARY KEY,
    spec_json TEXT NOT NULL,
    epoch INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS workspaces (
    workspace_id TEXT PRIMARY KEY,
    pool_id TEXT NOT NULL REFERENCES pools(pool_id),
    root TEXT NOT NULL,
    principal TEXT NOT NULL,
    project TEXT NOT NULL DEFAULT 'default',
    created_at TEXT NOT NULL,
    UNIQUE(pool_id, root)
);
CREATE TABLE IF NOT EXISTS requests (
    id TEXT PRIMARY KEY,
    principal TEXT NOT NULL,
    request_key TEXT NOT NULL,
    digest TEXT NOT NULL,
    operation TEXT NOT NULL,
    state TEXT NOT NULL,
    run_id TEXT,
    receipt_json TEXT NOT NULL DEFAULT '{}',
    owner_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(principal, request_key)
);
CREATE TABLE IF NOT EXISTS runs (
    id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL,
    principal TEXT NOT NULL,
    project TEXT NOT NULL,
    plan_key TEXT NOT NULL,
    plan_digest TEXT NOT NULL,
    plan_json TEXT NOT NULL,
    status TEXT NOT NULL,
    revision INTEGER NOT NULL DEFAULT 1,
    cancel_requested INTEGER NOT NULL DEFAULT 0,
    cancel_state TEXT,
    error TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    finished_at TEXT
);
CREATE INDEX IF NOT EXISTS runs_status ON runs(status, created_at);
CREATE INDEX IF NOT EXISTS runs_principal ON runs(principal, project, created_at);
CREATE TABLE IF NOT EXISTS units (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
    local_id TEXT NOT NULL,
    ordinal INTEGER NOT NULL,
    node_ids_json TEXT NOT NULL,
    depends_on_json TEXT NOT NULL,
    target_json TEXT NOT NULL,
    requirement_json TEXT NOT NULL,
    capability TEXT NOT NULL,
    group_id TEXT,
    state TEXT NOT NULL,
    attempts INTEGER NOT NULL DEFAULT 0,
    retry_limit INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(run_id, local_id)
);
CREATE INDEX IF NOT EXISTS units_run ON units(run_id, ordinal);
CREATE TABLE IF NOT EXISTS attempts (
    id TEXT PRIMARY KEY,
    unit_id TEXT NOT NULL REFERENCES units(id) ON DELETE CASCADE,
    ordinal INTEGER NOT NULL,
    epoch INTEGER NOT NULL,
    fence INTEGER NOT NULL,
    state TEXT NOT NULL,
    revision INTEGER NOT NULL DEFAULT 1,
    process_json TEXT NOT NULL DEFAULT '{}',
    exit_code INTEGER,
    error_code TEXT,
    error TEXT,
    started_at TEXT,
    finished_at TEXT,
    receipt_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(unit_id, ordinal)
);
CREATE INDEX IF NOT EXISTS attempts_state ON attempts(state);
CREATE TABLE IF NOT EXISTS leases (
    id TEXT PRIMARY KEY,
    attempt_id TEXT NOT NULL,
    pool_id TEXT NOT NULL,
    owner_json TEXT NOT NULL,
    request_json TEXT NOT NULL,
    committed_json TEXT NOT NULL,
    target_json TEXT NOT NULL,
    revision INTEGER NOT NULL DEFAULT 1,
    state TEXT NOT NULL,
    resize_id TEXT,
    resize_state TEXT,
    resize_json TEXT,
    heartbeat_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS leases_state ON leases(pool_id, state);
CREATE TABLE IF NOT EXISTS artifacts (
    id TEXT PRIMARY KEY,
    attempt_id TEXT NOT NULL,
    fence INTEGER NOT NULL,
    manifest_json TEXT NOT NULL,
    digest TEXT NOT NULL,
    size_bytes INTEGER NOT NULL,
    state TEXT NOT NULL,
    location TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS artifacts_state ON artifacts(state);
CREATE TABLE IF NOT EXISTS artifact_refs (
    id TEXT PRIMARY KEY,
    artifact_id TEXT NOT NULL,
    owner TEXT NOT NULL,
    reason TEXT NOT NULL,
    state TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE(artifact_id, owner, reason)
);
CREATE TABLE IF NOT EXISTS events (
    cursor INTEGER PRIMARY KEY AUTOINCREMENT,
    kind TEXT NOT NULL,
    principal TEXT NOT NULL,
    workspace_id TEXT,
    run_id TEXT,
    unit_id TEXT,
    attempt_id TEXT,
    revision INTEGER NOT NULL DEFAULT 0,
    payload_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS events_run ON events(run_id, cursor);
CREATE TABLE IF NOT EXISTS outbox (
    id TEXT PRIMARY KEY,
    attempt_id TEXT,
    run_id TEXT,
    command TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    state TEXT NOT NULL,
    attempts INTEGER NOT NULL DEFAULT 0,
    available_at REAL NOT NULL DEFAULT 0,
    last_error TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS outbox_state ON outbox(state, available_at);
CREATE TABLE IF NOT EXISTS transitions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entity TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    before_state TEXT,
    after_state TEXT NOT NULL,
    revision INTEGER NOT NULL,
    actor TEXT NOT NULL DEFAULT '',
    reason TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS transitions_entity ON transitions(entity, entity_id, id);
CREATE TABLE IF NOT EXISTS coordinators (
    pool_id TEXT PRIMARY KEY REFERENCES pools(pool_id),
    owner_json TEXT NOT NULL,
    owner_id TEXT NOT NULL,
    heartbeat REAL NOT NULL,
    epoch INTEGER NOT NULL,
    claimed_at TEXT NOT NULL
);
"""


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_id(prefix: str) -> str:
    return prefix + uuid.uuid4().hex


def _json(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def _load(value, default=None):
    if value is None:
        return default
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return default


class ClaimResult:
    __slots__ = ('created', 'record', 'status')

    def __init__(self, *, created: bool, status: str, record: dict):
        self.created, self.status, self.record = created, status, record

    @property
    def reused(self) -> bool:
        return not self.created

    def __repr__(self):
        return f'ClaimResult(created={self.created!r}, status={self.status!r}, run_id={self.record.get("run_id")!r})'


class StateStore:
    """Transactional repository for runs, attempts, leases, artifacts and events."""

    def __init__(self, path, *, create=True, timeout=30.0, backup=None):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self.local = threading.local()
        self._condition = threading.Condition()
        self.timeout = timeout
        self._closed = False
        exists = self.path.is_file()
        if not exists and not create:
            raise UnavailableStateError(f'Engine state does not exist: {self.path}')
        try:
            self.connection = sqlite3.connect(str(self.path), timeout=timeout, check_same_thread=False,
                                              isolation_level=None)
        except sqlite3.Error as exc:
            raise UnavailableStateError(f'Cannot open engine state {self.path}: {exc}') from exc
        self.connection.row_factory = sqlite3.Row
        try:
            self.connection.execute('PRAGMA busy_timeout = %d' % int(timeout * 1000))
            self.connection.execute('PRAGMA foreign_keys = ON')
            self.connection.execute('PRAGMA journal_mode = WAL')
            self.connection.execute('PRAGMA synchronous = FULL')
            self._verify_integrity()
            # executescript commits any open transaction, so schema creation is
            # deliberately run in autocommit mode before the migration check.
            self.connection.executescript(SCHEMA)
            with self.transaction():
                self._migrate()
        except UnavailableStateError:
            self.connection.close()
            raise
        except (sqlite3.Error, OSError) as exc:
            self.connection.close()
            raise UnavailableStateError(f'Engine state {self.path} is unavailable: {exc}') from exc
        if backup is not None:
            self.backup(backup)

    # -- lifecycle -----------------------------------------------------
    def _verify_integrity(self):
        try:
            rows = self.connection.execute('PRAGMA quick_check').fetchall()
        except sqlite3.DatabaseError as exc:
            raise UnavailableStateError(f'Engine state is corrupt: {exc}') from exc
        if not rows or any(str(row[0]).lower() != 'ok' for row in rows):
            raise UnavailableStateError(f'Engine state failed its integrity check: {rows}')

    def _migrate(self):
        row = self.connection.execute("SELECT value FROM schema_meta WHERE key='schema_version'").fetchone()
        if row is None:
            self.connection.execute("INSERT INTO schema_meta(key, value) VALUES('schema_version', ?)",
                                    (str(SCHEMA_VERSION),))
            self.connection.execute("INSERT INTO schema_meta(key, value) VALUES('engine_version', '1')")
            return
        version = int(row['value'])
        if version > SCHEMA_VERSION:
            raise UnavailableStateError(
                f'Engine state schema {version} is newer than this application supports ({SCHEMA_VERSION}); '
                'refusing to recreate or silently downgrade the durable queue')
        if version < SCHEMA_VERSION:
            raise UnavailableStateError(
                f'Engine state schema {version} requires an explicit migration; this build cannot read it safely')

    def close(self):
        with self.lock:
            if not self._closed:
                self.connection.close()
                self._closed = True

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    @contextmanager
    def transaction(self):
        """Hold the single writer; nested calls join the outer transaction."""
        with self.lock:
            depth = getattr(self.local, 'depth', 0)
            events = getattr(self.local, 'events', 0)
            if depth:
                self.local.depth = depth + 1
                try:
                    yield self
                finally:
                    self.local.depth = depth
                return
            try:
                self.connection.execute('BEGIN IMMEDIATE')
            except sqlite3.Error as exc:
                raise UnavailableStateError(f'Cannot start an engine transaction: {exc}') from exc
            self.local.depth = 1
            self.local.events = 0
            try:
                yield self
            except BaseException:
                self.connection.rollback()
                self.local.depth = 0
                raise
            else:
                try:
                    self.connection.commit()
                except BaseException as exc:
                    # Any failure at COMMIT can leave the durable outcome
                    # unknown (for example the server committed before the
                    # acknowledgement was lost).  Callers must probe, not
                    # blindly retry a side effect.
                    try:
                        self.connection.rollback()
                    except Exception:  # noqa: BLE001 - preserve the original failure
                        pass
                    self.local.depth = 0
                    raise CommitOutcomeUnknown(
                        'The engine transaction failed while committing; its durable outcome is unknown',
                        details={'error': f'{type(exc).__name__}: {exc}'}) from exc
                self.local.depth = 0
                if self.local.events:
                    self.local.events = 0
                    with self._condition:
                        self._condition.notify_all()
            finally:
                self.local.depth = 0

    def backup(self, target):
        target = Path(target)
        target.parent.mkdir(parents=True, exist_ok=True)
        with self.lock:
            try:
                destination = sqlite3.connect(str(target))
                try:
                    self.connection.backup(destination)
                finally:
                    destination.close()
            except sqlite3.Error as exc:
                raise UnavailableStateError(f'Cannot back up engine state to {target}: {exc}') from exc
        return target

    # -- pools and workspaces ------------------------------------------
    def ensure_pool(self, spec: PoolSpec, *, actor='engine') -> tuple[PoolSpec, int]:
        with self.transaction():
            row = self.connection.execute('SELECT * FROM pools WHERE pool_id=?', (spec.pool_id,)).fetchone()
            if row is None:
                self.connection.execute(
                    'INSERT INTO pools(pool_id, spec_json, epoch, created_at, updated_at) VALUES(?,?,?,?,?)',
                    (spec.pool_id, _json(spec.to_json()), 1, now_iso(), now_iso()))
                self._event('pool_registered', principal=spec.principal, revision=1,
                            payload={'pool_id': spec.pool_id, 'spec': spec.to_json(), 'epoch': 1})
                return spec, 1
            stored = PoolSpec.from_json(_load(row['spec_json'], {}))
            epoch = int(row['epoch'])
            active = self._active_lease_totals(spec.pool_id)
            changed = stored.to_json() != spec.to_json()
            if changed and (active['leases'] or active['attempts']):
                raise UnavailableStateError(
                    'The durable pool snapshot differs from the current startup capacity while attempts are active; '
                    'drain or explicitly migrate the pool before changing its ceiling')
            if changed:
                epoch += 1
                self.connection.execute('UPDATE pools SET spec_json=?, epoch=?, updated_at=? WHERE pool_id=?',
                                        (_json(spec.to_json()), epoch, now_iso(), spec.pool_id))
                self._event('pool_reconfigured', principal=spec.principal, revision=epoch,
                            payload={'pool_id': spec.pool_id, 'spec': spec.to_json(), 'epoch': epoch})
            return PoolSpec.from_json(_load(row['spec_json'], {})) if not changed else spec, epoch

    def pool(self, pool_id: str) -> tuple[PoolSpec, int]:
        with self.lock:
            row = self.connection.execute('SELECT * FROM pools WHERE pool_id=?', (pool_id,)).fetchone()
            if row is None:
                raise UnavailableStateError(f'Unknown execution pool {pool_id}')
            return PoolSpec.from_json(_load(row['spec_json'], {})), int(row['epoch'])

    def advance_epoch(self, pool_id: str, *, actor='supervisor') -> int:
        with self.transaction():
            row = self.connection.execute('SELECT epoch, spec_json FROM pools WHERE pool_id=?', (pool_id,)).fetchone()
            if row is None:
                raise UnavailableStateError(f'Unknown execution pool {pool_id}')
            epoch = int(row['epoch']) + 1
            self.connection.execute('UPDATE pools SET epoch=?, updated_at=? WHERE pool_id=?',
                                    (epoch, now_iso(), pool_id))
            spec = PoolSpec.from_json(_load(row['spec_json'], {}))
            self._event('epoch_advanced', principal=spec.principal, revision=epoch,
                        payload={'pool_id': pool_id, 'epoch': epoch, 'actor': actor})
            return epoch

    def coordinator(self, pool_id: str) -> dict | None:
        with self.lock:
            row = self.connection.execute('SELECT * FROM coordinators WHERE pool_id=?', (pool_id,)).fetchone()
            if row is None:
                return None
            value = dict(row)
            value['owner'] = _load(value.pop('owner_json'), {})
            return value

    def claim_coordinator(self, pool_id: str, *, owner: dict, owner_id: str,
                          owner_alive=None, stale_after=60.0) -> int:
        """Acquire exclusive pool ownership and advance the epoch.

        A live coordinator with a fresh heartbeat is never displaced.  An
        uncertain owner is treated as live; operators must drain it explicitly.
        """
        import time as _time
        now = _time.time()
        with self.transaction():
            row = self.connection.execute('SELECT * FROM coordinators WHERE pool_id=?', (pool_id,)).fetchone()
            spec, current_epoch = self.pool(pool_id)
            if row is not None:
                if row['owner_id'] == owner_id:
                    self.connection.execute('UPDATE coordinators SET heartbeat=?, owner_json=? WHERE pool_id=?',
                                            (now, _json(owner), pool_id))
                    return int(row['epoch'])
                previous = _load(row['owner_json'], {})
                fresh = now - float(row['heartbeat'] or 0) <= stale_after
                alive = owner_alive(previous) if callable(owner_alive) else fresh
                if fresh and alive:
                    raise BusyError('Another coordinator owns this execution pool')
                if not fresh and alive and callable(owner_alive):
                    # Live process but stale heartbeat: do not steal a slow
                    # coordinator's ownership automatically.
                    raise BusyError('A coordinator process may still own this execution pool; drain it explicitly')
            epoch = current_epoch + 1
            self.connection.execute('UPDATE pools SET epoch=?, updated_at=? WHERE pool_id=?',
                                    (epoch, now_iso(), pool_id))
            self.connection.execute(
                'INSERT INTO coordinators(pool_id, owner_json, owner_id, heartbeat, epoch, claimed_at) '
                'VALUES(?,?,?,?,?,?) ON CONFLICT(pool_id) DO UPDATE SET owner_json=excluded.owner_json, '
                'owner_id=excluded.owner_id, heartbeat=excluded.heartbeat, epoch=excluded.epoch, '
                'claimed_at=excluded.claimed_at',
                (pool_id, _json(owner), owner_id, now, epoch, now_iso()))
            self._event('coordinator_claimed', principal=spec.principal, revision=epoch,
                        payload={'pool_id': pool_id, 'owner_id': owner_id, 'epoch': epoch})
            return epoch

    def heartbeat_coordinator(self, pool_id: str, owner_id: str) -> bool:
        import time as _time
        with self.transaction():
            row = self.connection.execute('SELECT owner_id FROM coordinators WHERE pool_id=?', (pool_id,)).fetchone()
            if row is None or row['owner_id'] != owner_id:
                return False
            self.connection.execute('UPDATE coordinators SET heartbeat=? WHERE pool_id=?',
                                    (_time.time(), pool_id))
            return True

    def release_coordinator(self, pool_id: str, owner_id: str) -> bool:
        with self.transaction():
            row = self.connection.execute('SELECT owner_id FROM coordinators WHERE pool_id=?', (pool_id,)).fetchone()
            if row is None or row['owner_id'] != owner_id:
                return False
            self.connection.execute('DELETE FROM coordinators WHERE pool_id=?', (pool_id,))
            return True

    def register_workspace(self, workspace_id: str, pool_id: str, root: str, principal: str,
                           project: str = 'default') -> dict:
        with self.transaction():
            row = self.connection.execute('SELECT * FROM workspaces WHERE workspace_id=?', (workspace_id,)).fetchone()
            if row is not None:
                return dict(row)
            self.connection.execute(
                'INSERT INTO workspaces(workspace_id, pool_id, root, principal, project, created_at) '
                'VALUES(?,?,?,?,?,?)', (workspace_id, pool_id, root, principal, project, now_iso()))
            return dict(self.connection.execute('SELECT * FROM workspaces WHERE workspace_id=?',
                                                (workspace_id,)).fetchone())

    def workspace(self, workspace_id: str) -> dict:
        row = self.connection.execute('SELECT * FROM workspaces WHERE workspace_id=?', (workspace_id,)).fetchone()
        if row is None:
            raise KeyError(f'Unknown workspace {workspace_id}')
        return dict(row)

    # -- requests and submissions --------------------------------------
    def request(self, principal: str, key: str) -> dict | None:
        with self.lock:
            row = self.connection.execute('SELECT * FROM requests WHERE principal=? AND request_key=?',
                                          (principal, key)).fetchone()
            return self._request_row(row) if row else None

    def _request_row(self, row) -> dict:
        value = dict(row)
        value['receipt'] = _load(value.pop('receipt_json'), {})
        value['owner'] = _load(value.pop('owner_json'), {})
        return value

    def claim_request(self, *, principal: str, key: str, digest: str, operation: str,
                      owner: dict | None = None, receipt: dict | None = None) -> ClaimResult:
        """Atomically claim an idempotency key without creating an engine run.

        Used by adapters that keep their existing scientific job directory as
        the execution record while the engine supplies the durable request
        index.  Reuse with different content is a conflict.
        """
        stamp = now_iso()
        with self.transaction():
            row = self.connection.execute('SELECT * FROM requests WHERE principal=? AND request_key=?',
                                          (principal, key)).fetchone()
            if row is not None:
                existing = self._request_row(row)
                if existing['digest'] != digest:
                    raise IdempotencyConflictError(
                        'request_id was already used for a different payload',
                        details={'request_id': key, 'existing_operation': existing['operation']})
                return ClaimResult(created=False, status='reused', record=existing)
            request_id = new_id('req-')
            self.connection.execute(
                'INSERT INTO requests(id, principal, request_key, digest, operation, state, run_id, receipt_json, '
                'owner_json, created_at, updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)',
                (request_id, principal, key, digest, operation, 'claimed', None,
                 _json(receipt or {}), _json(owner or {}), stamp, stamp))
            self._event('request_claimed', principal=principal, revision=1,
                        payload={'request_id': key, 'operation': operation})
            row = self.connection.execute('SELECT * FROM requests WHERE id=?', (request_id,)).fetchone()
            return ClaimResult(created=True, status='created', record=self._request_row(row))

    def claim_submission(self, *, principal: str, key: str, digest: str, operation: str,
                         run: dict, units: list[dict], owner: dict | None = None,
                         receipt: dict | None = None) -> ClaimResult:
        """Atomically claim one request identity and create its durable run."""
        stamp = now_iso()
        with self.transaction():
            row = self.connection.execute('SELECT * FROM requests WHERE principal=? AND request_key=?',
                                          (principal, key)).fetchone()
            if row is not None:
                existing = self._request_row(row)
                if existing['digest'] != digest:
                    raise IdempotencyConflictError(
                        'request_id was already used for a different payload',
                        details={'request_id': key, 'existing_operation': existing['operation']})
                return ClaimResult(created=False, status='reused', record=existing)
            request_id = new_id('req-')
            self.connection.execute(
                'INSERT INTO requests(id, principal, request_key, digest, operation, state, run_id, receipt_json, '
                'owner_json, created_at, updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)',
                (request_id, principal, key, digest, operation, 'claimed', run['id'],
                 _json(receipt or {}), _json(owner or {}), stamp, stamp))
            self.connection.execute(
                'INSERT INTO runs(id, workspace_id, principal, project, plan_key, plan_digest, plan_json, status, '
                'revision, cancel_requested, created_at, updated_at) VALUES(?,?,?,?,?,?,?,?,1,0,?,?)',
                (run['id'], run['workspace_id'], principal, run['project'], run['plan_key'],
                 run['plan_digest'], _json(run['plan']), RunState.QUEUED.value, stamp, stamp))
            for ordinal, unit in enumerate(units):
                dependencies = list(unit.get('depends_on', ()))
                initial = AttemptState.READY.value if not dependencies else AttemptState.BLOCKED.value
                self.connection.execute(
                    'INSERT INTO units(id, run_id, local_id, ordinal, node_ids_json, depends_on_json, target_json, '
                    'requirement_json, capability, group_id, state, attempts, retry_limit, created_at, updated_at) '
                    'VALUES(?,?,?,?,?,?,?,?,?,?,?,0,?,?,?)',
                    (new_id('unit-'), run['id'], unit['unit_id'], ordinal,
                     _json(list(unit.get('node_ids', ()))), _json(dependencies),
                     _json(dict(unit.get('target') or {'kind': 'local'})),
                     _json(ResourceRequest.from_json(unit.get('requirement')).to_json()),
                     unit.get('capability', 'legacy-sequential'), unit.get('group'),
                     initial, int(unit.get('retry_limit', 1)), stamp, stamp))
            self.connection.execute(
                'INSERT OR IGNORE INTO outbox(id, attempt_id, run_id, command, payload_json, state, created_at, updated_at) '
                'VALUES(?,?,?,?,?,?,?,?)',
                (f'dispatch:{run["id"]}', None, run['id'], 'dispatch',
                 _json({'run_id': run['id']}), 'pending', stamp, stamp))
            self._event('run_submitted', principal=principal, workspace_id=run['workspace_id'], run_id=run['id'],
                        revision=1, payload={'plan_key': run['plan_key'], 'operation': operation,
                                             'request_id': key})
            row = self.connection.execute('SELECT * FROM requests WHERE principal=? AND request_key=?',
                                          (principal, key)).fetchone()
            return ClaimResult(created=True, status='created', record=self._request_row(row))

    def update_request(self, principal: str, key: str, *, state: str | None = None, run_id: str | None = None,                       receipt: dict | None = None, error: str | None = None) -> dict:
        with self.transaction():
            row = self.connection.execute('SELECT * FROM requests WHERE principal=? AND request_key=?',
                                          (principal, key)).fetchone()
            if row is None:
                raise KeyError('Unknown engine request')
            request_id = row['id']
            changes = {'updated_at': now_iso()}
            if state is not None:
                changes['state'] = state
            if run_id is not None:
                changes['run_id'] = run_id
            if receipt is not None:
                changes['receipt_json'] = _json(receipt)
            assignments = ', '.join(f'{name}=?' for name in changes)
            self.connection.execute(f'UPDATE requests SET {assignments} WHERE id=?',
                                    (*changes.values(), request_id))
            if error is not None:
                receipt_value = _load(row['receipt_json'], {})
                receipt_value['error'] = error
                self.connection.execute('UPDATE requests SET receipt_json=? WHERE id=?',
                                        (_json(receipt_value), request_id))
            return self._request_row(self.connection.execute('SELECT * FROM requests WHERE id=?',
                                                            (request_id,)).fetchone())

    # -- runs and units ------------------------------------------------
    def run(self, run_id: str) -> dict:
        with self.lock:
            row = self.connection.execute('SELECT * FROM runs WHERE id=?', (run_id,)).fetchone()
            if row is None:
                raise KeyError(f'Unknown run {run_id}')
            value = dict(row)
            value['plan'] = _load(value.pop('plan_json'), {})
            value['cancel_requested'] = bool(value['cancel_requested'])
            return value

    def run_plan(self, run_id: str) -> dict:
        return self.run(run_id)['plan']

    def units(self, run_id: str) -> list[dict]:
        with self.lock:
            rows = self.connection.execute('SELECT * FROM units WHERE run_id=? ORDER BY ordinal',
                                           (run_id,)).fetchall()
            return [self._unit_row(row) for row in rows]

    def _unit_row(self, row) -> dict:
        value = dict(row)
        for source in ('node_ids_json', 'depends_on_json', 'target_json', 'requirement_json'):
            value[source[:-5]] = _load(value.pop(source), [] if source.endswith('s_json') else {})
        value['local_id'] = value.pop('local_id')
        return value

    def unit(self, unit_id: str) -> dict:
        with self.lock:
            row = self.connection.execute('SELECT * FROM units WHERE id=?', (unit_id,)).fetchone()
            if row is None:
                raise KeyError(f'Unknown unit {unit_id}')
            return self._unit_row(row)

    def transition_run(self, run_id: str, to: RunState | str, *, expected_revision: int | None = None,
                       actor='engine', reason='', error: str | None = None,
                       cancel_requested: bool | None = None) -> dict:
        to = RunState(to)
        stamp = now_iso()
        with self.transaction():
            row = self.connection.execute('SELECT * FROM runs WHERE id=?', (run_id,)).fetchone()
            if row is None:
                raise KeyError(f'Unknown run {run_id}')
            if expected_revision is not None and int(row['revision']) != expected_revision:
                raise StaleRevisionError(
                    'The run changed before this command was applied',
                    details={'run_id': run_id, 'expected_revision': expected_revision,
                             'actual_revision': int(row['revision'])})
            before = RunState(row['status'])
            revision = int(row['revision']) + 1
            values = {'status': to.value, 'revision': revision, 'updated_at': stamp}
            if to in TERMINAL_RUN_STATES:
                values['finished_at'] = stamp
            if error is not None:
                values['error'] = error
            if cancel_requested is not None:
                values['cancel_requested'] = int(bool(cancel_requested))
                values['cancel_state'] = 'requested' if cancel_requested else None
            assignments = ', '.join(f'{name}=?' for name in values)
            self.connection.execute(f'UPDATE runs SET {assignments} WHERE id=?', (*values.values(), run_id))
            self.connection.execute(
                'INSERT INTO transitions(entity, entity_id, before_state, after_state, revision, actor, reason, created_at) '
                'VALUES(?,?,?,?,?,?,?,?)',
                ('run', run_id, before.value, to.value, revision, actor, reason, stamp))
            self._event(f'run_{to.value}', principal=row['principal'], workspace_id=row['workspace_id'],
                        run_id=run_id, revision=revision,
                        payload={'status': to.value, 'error': error, 'actor': actor, 'reason': reason})
            return self.run(run_id)

    def request_cancel(self, run_id: str, *, expected_revision: int | None = None, reason: str = '',
                       actor='client') -> dict:
        stamp = now_iso()
        with self.transaction():
            row = self.connection.execute('SELECT * FROM runs WHERE id=?', (run_id,)).fetchone()
            if row is None:
                raise KeyError(f'Unknown run {run_id}')
            if expected_revision is not None and int(row['revision']) != expected_revision:
                raise StaleRevisionError('The run changed before cancellation was accepted',
                                         details={'run_id': run_id, 'expected_revision': expected_revision,
                                                  'actual_revision': int(row['revision'])})
            if bool(row['cancel_requested']):
                return self.run(run_id)
            if RunState(row['status']) in TERMINAL_RUN_STATES:
                raise StaleRevisionError('The run already reached a terminal state',
                                         code='stale_revision',
                                         details={'run_id': run_id, 'status': row['status']})
            revision = int(row['revision']) + 1
            self.connection.execute(
                "UPDATE runs SET cancel_requested=1, cancel_state='requested', revision=?, updated_at=? WHERE id=?",
                (revision, stamp, run_id))
            self.connection.execute(
                'INSERT INTO transitions(entity, entity_id, before_state, after_state, revision, actor, reason, created_at) '
                'VALUES(?,?,?,?,?,?,?,?)',
                ('run', run_id, row['status'], row['status'], revision, actor, 'cancel: ' + reason, stamp))
            self._event('run_cancel_requested', principal=row['principal'], workspace_id=row['workspace_id'],
                        run_id=run_id, revision=revision, payload={'reason': reason, 'actor': actor})
            return self.run(run_id)

    def mark_cancel_stopped(self, run_id: str, *, actor='supervisor', error: str | None = None) -> dict:
        current = self.run(run_id)
        if RunState(current['status']) in TERMINAL_RUN_STATES:
            # A committed success must never be rewritten by a late cancel.
            self.update_run_cancel_state(run_id, 'late' if current['status'] != RunState.CANCELLED.value else 'stopped')
            return self.run(run_id)
        result = self.transition_run(run_id, RunState.CANCELLED, actor=actor,
                                     reason='process tree stopped', error=error)
        with self.transaction():
            self.connection.execute("UPDATE runs SET cancel_state='stopped' WHERE id=?", (run_id,))
        return result

    def update_run_cancel_state(self, run_id: str, state: str) -> None:
        with self.transaction():
            self.connection.execute('UPDATE runs SET cancel_state=?, updated_at=? WHERE id=?',
                                    (state, now_iso(), run_id))

    def update_unit(self, unit_id: str, *, state: str | None = None, increment_attempts=False) -> dict:
        with self.transaction():
            row = self.connection.execute('SELECT * FROM units WHERE id=?', (unit_id,)).fetchone()
            if row is None:
                raise KeyError(f'Unknown unit {unit_id}')
            values = {'updated_at': now_iso()}
            if state is not None:
                values['state'] = state
            if increment_attempts:
                values['attempts'] = int(row['attempts']) + 1
            assignments = ', '.join(f'{name}=?' for name in values)
            self.connection.execute(f'UPDATE units SET {assignments} WHERE id=?', (*values.values(), unit_id))
            return self.unit(unit_id)

    def set_unit_state_for_dependencies(self, run_id: str) -> int:
        """Mark blocked units ready when every dependency has succeeded."""
        with self.transaction():
            rows = self.connection.execute('SELECT * FROM units WHERE run_id=? ORDER BY ordinal',
                                           (run_id,)).fetchall()
            state = {row['local_id']: row['state'] for row in rows}
            changed = 0
            for row in rows:
                if row['state'] not in (RunState.QUEUED.value, AttemptState.BLOCKED.value):
                    continue
                dependencies = _load(row['depends_on_json'], [])
                if all(state.get(item) == AttemptState.SUCCEEDED.value for item in dependencies):
                    self.connection.execute('UPDATE units SET state=?, updated_at=? WHERE id=?',
                                            (AttemptState.READY.value, now_iso(), row['id']))
                    changed += 1
            return changed

    # -- attempts ------------------------------------------------------
    def attempts(self, run_id: str | None = None, *, state: str | None = None) -> list[dict]:
        query = 'SELECT a.* FROM attempts a'
        clauses, values = [], []
        if run_id is not None:
            query += ' JOIN units u ON u.id=a.unit_id'
            clauses.append('u.run_id=?')
            values.append(run_id)
        if state is not None:
            clauses.append('a.state=?')
            values.append(state)
        if clauses:
            query += ' WHERE ' + ' AND '.join(clauses)
        query += ' ORDER BY a.created_at'
        with self.lock:
            return [self._attempt_row(row) for row in self.connection.execute(query, values).fetchall()]

    def attempt(self, attempt_id: str) -> dict:
        with self.lock:
            row = self.connection.execute('SELECT * FROM attempts WHERE id=?', (attempt_id,)).fetchone()
            if row is None:
                raise KeyError(f'Unknown attempt {attempt_id}')
            return self._attempt_row(row)

    def _attempt_row(self, row) -> dict:
        value = dict(row)
        value['process'] = _load(value.pop('process_json'), {})
        value['receipt'] = _load(value.pop('receipt_json'), {})
        return value

    def create_attempt(self, unit_id: str, *, epoch: int, actor='coordinator') -> dict:
        stamp = now_iso()
        with self.transaction():
            row = self.connection.execute('SELECT * FROM units WHERE id=?', (unit_id,)).fetchone()
            if row is None:
                raise KeyError(f'Unknown unit {unit_id}')
            ordinal = int(row['attempts']) + 1
            attempt_id = new_id('attempt-')
            fence = int(epoch) * 1_000_000 + ordinal
            self.connection.execute(
                'INSERT INTO attempts(id, unit_id, ordinal, epoch, fence, state, revision, created_at, updated_at) '
                'VALUES(?,?,?,?,?,?,1,?,?)',
                (attempt_id, unit_id, ordinal, int(epoch), fence, AttemptState.ADMITTED.value, stamp, stamp))
            self.connection.execute('UPDATE units SET attempts=?, state=?, updated_at=? WHERE id=?',
                                    (ordinal, AttemptState.ADMITTED.value, stamp, unit_id))
            self.connection.execute(
                'INSERT INTO transitions(entity, entity_id, before_state, after_state, revision, actor, reason, created_at) '
                'VALUES(?,?,?,?,?,?,?,?)',
                ('attempt', attempt_id, None, AttemptState.ADMITTED.value, 1, actor, 'admitted', stamp))
            self._event('attempt_admitted', principal=self._run_principal(unit_id), run_id=self._unit_run(unit_id),
                        unit_id=unit_id, attempt_id=attempt_id, revision=1,
                        payload={'ordinal': ordinal, 'epoch': int(epoch), 'fence': fence})
            return self.attempt(attempt_id)

    def _unit_run(self, unit_id):
        row = self.connection.execute('SELECT run_id FROM units WHERE id=?', (unit_id,)).fetchone()
        return row['run_id'] if row else None

    def _run_principal(self, unit_id):
        row = self.connection.execute('SELECT r.principal FROM units u JOIN runs r ON r.id=u.run_id WHERE u.id=?',
                                      (unit_id,)).fetchone()
        return row['principal'] if row else ''

    def transition_attempt(self, attempt_id: str, to: AttemptState | str, *, expected_revision: int | None = None,
                           actor='coordinator', reason='', process: dict | None = None,
                           exit_code: int | None = None, error: str | None = None,
                           error_code: str | None = None, receipt: dict | None = None,
                           expected_epoch: int | None = None, expected_fence: int | None = None) -> dict:
        to = AttemptState(to)
        stamp = now_iso()
        with self.transaction():
            row = self.connection.execute('SELECT * FROM attempts WHERE id=?', (attempt_id,)).fetchone()
            if row is None:
                raise KeyError(f'Unknown attempt {attempt_id}')
            if expected_revision is not None and int(row['revision']) != expected_revision:
                raise StaleAttemptError('The attempt changed before this command was applied',
                                        details={'attempt_id': attempt_id, 'expected_revision': expected_revision,
                                                 'actual_revision': int(row['revision'])})
            if expected_epoch is not None and int(row['epoch']) != expected_epoch:
                raise StaleAttemptError('The attempt belongs to a stale coordinator epoch',
                                        details={'attempt_id': attempt_id, 'expected_epoch': expected_epoch,
                                                 'actual_epoch': int(row['epoch'])})
            if expected_fence is not None and int(row['fence']) != expected_fence:
                raise StaleAttemptError('The attempt fence is stale', details={'attempt_id': attempt_id})
            before = AttemptState(row['state'])
            if before != to and not transition_allowed(before, to):
                raise StaleAttemptError(f'Illegal attempt transition {before.value} -> {to.value}',
                                        details={'attempt_id': attempt_id, 'before': before.value, 'after': to.value})
            revision = int(row['revision']) + 1
            values = {'state': to.value, 'revision': revision, 'updated_at': stamp}
            if process is not None:
                values['process_json'] = _json(process)
            if exit_code is not None:
                values['exit_code'] = exit_code
            if error is not None:
                values['error'] = error
            if error_code is not None:
                values['error_code'] = error_code
            if receipt is not None:
                values['receipt_json'] = _json(receipt)
            if to in (AttemptState.RUNNING, AttemptState.STARTING) and not row['started_at']:
                values['started_at'] = stamp
            if to in TERMINAL_ATTEMPT_STATES:
                values['finished_at'] = stamp
            assignments = ', '.join(f'{name}=?' for name in values)
            self.connection.execute(f'UPDATE attempts SET {assignments} WHERE id=?', (*values.values(), attempt_id))
            unit = self.connection.execute('SELECT * FROM units WHERE id=?', (row['unit_id'],)).fetchone()
            run = self.connection.execute('SELECT * FROM runs WHERE id=?', (unit['run_id'],)).fetchone()
            self.connection.execute(
                'INSERT INTO transitions(entity, entity_id, before_state, after_state, revision, actor, reason, created_at) '
                'VALUES(?,?,?,?,?,?,?,?)',
                ('attempt', attempt_id, before.value, to.value, revision, actor, reason, stamp))
            self._event(f'attempt_{to.value}', principal=run['principal'], workspace_id=run['workspace_id'],
                        run_id=run['id'], unit_id=row['unit_id'], attempt_id=attempt_id, revision=revision,
                        payload={'ordinal': int(row['ordinal']), 'error': error, 'exit_code': exit_code,
                                 'error_code': error_code})
            if to in TERMINAL_ATTEMPT_STATES:
                self._finish_unit(unit, to, stamp)
            return self.attempt(attempt_id)

    def _finish_unit(self, unit, attempt_state: AttemptState, stamp: str):
        final = {AttemptState.SUCCEEDED: AttemptState.SUCCEEDED,
                 AttemptState.FAILED: AttemptState.FAILED,
                 AttemptState.CANCELLED: AttemptState.CANCELLED}[attempt_state]
        self.connection.execute('UPDATE units SET state=?, updated_at=? WHERE id=?',
                                (final.value, stamp, unit['id']))
        if final != AttemptState.SUCCEEDED:
            return
        rows = self.connection.execute('SELECT * FROM units WHERE run_id=?', (unit['run_id'],)).fetchall()
        states = {row['local_id']: row['state'] for row in rows}
        for row in rows:
            if row['state'] in (RunState.QUEUED.value, AttemptState.BLOCKED.value) and all(
                    states.get(item) == AttemptState.SUCCEEDED.value for item in _load(row['depends_on_json'], [])):
                self.connection.execute('UPDATE units SET state=?, updated_at=? WHERE id=?',
                                        (AttemptState.READY.value, stamp, row['id']))
        if rows and all(row['state'] == AttemptState.SUCCEEDED.value for row in rows):
            run = self.connection.execute('SELECT * FROM runs WHERE id=?', (unit['run_id'],)).fetchone()
            if run is None or RunState(run['status']) in TERMINAL_RUN_STATES:
                return
            revision = int(run['revision']) + 1
            self.connection.execute('UPDATE runs SET status=?, revision=?, updated_at=?, finished_at=? WHERE id=?',
                                    (RunState.COMPLETE.value, revision, stamp, stamp, unit['run_id']))
            self.connection.execute(
                'INSERT INTO transitions(entity, entity_id, before_state, after_state, revision, actor, reason, created_at) '
                'VALUES(?,?,?,?,?,?,?,?)',
                ('run', unit['run_id'], run['status'], RunState.COMPLETE.value, revision, 'engine',
                 'all units succeeded', stamp))
            self._event('run_complete', principal=run['principal'], workspace_id=run['workspace_id'],
                        run_id=unit['run_id'], revision=revision, payload={'status': RunState.COMPLETE.value})

    def active_attempts(self) -> list[dict]:
        states = tuple(item.value for item in ACTIVE_ATTEMPT_STATES)
        rows = self.connection.execute(
            f'SELECT * FROM attempts WHERE state IN ({",".join("?" * len(states))}) ORDER BY created_at',
            states).fetchall()
        return [self._attempt_row(row) for row in rows]

    def attempts_for_pool(self, pool_id: str, *, states: Iterable[str] | None = None) -> list[dict]:
        values = [pool_id]
        clause = ''
        if states:
            listed = [str(item) for item in states]
            clause = f' AND a.state IN ({",".join("?" * len(listed))})'
            values.extend(listed)
        query = ('SELECT a.*, u.run_id AS run_id, u.local_id AS unit_local_id, r.principal AS principal, '
                 'r.project AS project, r.plan_json AS plan_json, r.workspace_id AS workspace_id '
                 'FROM attempts a JOIN units u ON u.id=a.unit_id JOIN runs r ON r.id=u.run_id '
                 'JOIN workspaces w ON w.workspace_id=r.workspace_id '
                 'WHERE w.pool_id=?' + clause + ' ORDER BY a.created_at')
        with self.lock:
            rows = self.connection.execute(query, values).fetchall()
        result = []
        for row in rows:
            value = self._attempt_row(row)
            value['run_id'] = row['run_id']
            value['unit_local_id'] = row['unit_local_id']
            value['principal'] = row['principal']
            value['project'] = row['project']
            value['plan'] = _load(row['plan_json'], {})
            value['workspace_id'] = row['workspace_id']
            result.append(value)
        return result

    def ready_units(self, pool_id: str, *, limit=256) -> list[dict]:
        query = ('SELECT u.*, r.id AS run_id, r.principal AS principal, r.project AS project, '
                 'r.created_at AS run_created, r.status AS run_status, r.plan_json AS plan_json, '
                 'r.workspace_id AS workspace_id '
                 'FROM units u JOIN runs r ON r.id=u.run_id JOIN workspaces w ON w.workspace_id=r.workspace_id '
                 "WHERE w.pool_id=? AND u.state='ready' AND r.status IN ('queued','running') "
                 "AND r.cancel_requested=0 ORDER BY r.created_at, u.ordinal LIMIT ?")
        with self.lock:
            rows = self.connection.execute(query, (pool_id, max(1, int(limit)))).fetchall()
        result = []
        for row in rows:
            value = self._unit_row(row)
            value['run_id'] = row['run_id']
            value['principal'] = row['principal']
            value['project'] = row['project']
            value['run_created'] = row['run_created']
            value['run_status'] = row['run_status']
            value['plan'] = _load(row['plan_json'], {})
            value['workspace_id'] = row['workspace_id']
            result.append(value)
        return result

    def incomplete_runs(self) -> list[dict]:
        states = tuple(item.value for item in ACTIVE_RUN_STATES)
        rows = self.connection.execute(
            f'SELECT * FROM runs WHERE status IN ({",".join("?" * len(states))}) ORDER BY created_at',
            states).fetchall()
        return [self.run(row['id']) for row in rows]

    def list_runs(self, *, principal: str | None = None, workspace_id: str | None = None,
                  states: Iterable[str] | None = None, limit: int = 200) -> list[dict]:
        query = 'SELECT * FROM runs'
        clauses, values = [], []
        if principal is not None:
            clauses.append('principal=?')
            values.append(principal)
        if workspace_id is not None:
            clauses.append('workspace_id=?')
            values.append(workspace_id)
        if states:
            values_states = [str(item) for item in states]
            clauses.append(f'status IN ({",".join("?" * len(values_states))})')
            values.extend(values_states)
        if clauses:
            query += ' WHERE ' + ' AND '.join(clauses)
        query += ' ORDER BY created_at DESC LIMIT ?'
        values.append(max(1, min(int(limit), 1000)))
        with self.lock:
            rows = self.connection.execute(query, values).fetchall()
        return [self.run(row['id']) for row in rows]

    # -- leases --------------------------------------------------------
    def _active_lease_totals(self, pool_id: str | None = None) -> dict:
        query = ("SELECT * FROM leases WHERE state IN ('granted','resize_pending','release_pending')")
        values = []
        if pool_id is not None:
            query += ' AND pool_id=?'
            values.append(pool_id)
        used_ram = used_cpu = used_scratch = used_transport = used_shared = 0
        leases = []
        attempts = 0
        with self.lock:
            rows = self.connection.execute(query, values).fetchall()
        for row in rows:
            committed = ResourceRequest.from_json(_load(row['committed_json'], {}))
            used_ram += committed.ram_bytes
            used_cpu += committed.cpu_threads
            used_scratch += committed.scratch_reserved_bytes
            used_transport += committed.transport_reserved_bytes
            used_shared += committed.shared_buffer_bytes
            if row['state'] == 'resize_pending':
                # Growth is reserved before the worker is allowed to raise its
                # managed budget; a pending target therefore consumes capacity
                # even though committed credits have not moved yet.
                target = ResourceRequest.from_json(_load(row['target_json'], {}))
                used_ram += max(0, target.process_reservation_bytes - committed.process_reservation_bytes)
                used_ram += max(0, target.transport_reserved_bytes - committed.transport_reserved_bytes)
                used_ram += max(0, target.shared_buffer_bytes - committed.shared_buffer_bytes)
                used_cpu += max(0, target.cpu_threads - committed.cpu_threads)
                used_scratch += max(0, target.scratch_reserved_bytes - committed.scratch_reserved_bytes)
                used_transport += max(0, target.transport_reserved_bytes - committed.transport_reserved_bytes)
                used_shared += max(0, target.shared_buffer_bytes - committed.shared_buffer_bytes)
            leases.append(dict(row))
        attempts = len(leases)
        return {'leases': leases, 'ram': used_ram, 'cpu': used_cpu, 'scratch': used_scratch,
                'transport': used_transport, 'shared': used_shared, 'attempts': attempts}

    def lease_by_id(self, lease_id: str) -> dict | None:
        with self.lock:
            row = self.connection.execute('SELECT * FROM leases WHERE id=?', (lease_id,)).fetchone()
            return self._lease_row(row) if row else None

    def lease(self, attempt_id: str) -> dict | None:
        with self.lock:
            row = self.connection.execute('SELECT * FROM leases WHERE attempt_id=?',
                                          (attempt_id,)).fetchone()
            return self._lease_row(row) if row else None

    def _lease_row(self, row) -> dict:
        value = dict(row)
        value['owner'] = _load(value.pop('owner_json'), {})
        value['request'] = ResourceRequest.from_json(_load(value.pop('request_json'), {}))
        value['committed'] = ResourceRequest.from_json(_load(value.pop('committed_json'), {}))
        value['target'] = ResourceRequest.from_json(_load(value.pop('target_json'), {}))
        value['resize'] = _load(value.pop('resize_json'), None)
        return value

    def active_leases(self, pool_id: str | None = None) -> list[dict]:
        return self._active_lease_totals(pool_id)['leases']

    def lease_details(self, pool_id: str) -> list[dict]:
        """Active leases joined to their run/owner for diagnostics and policy."""
        with self.lock:
            rows = self.connection.execute(
                "SELECT l.*, r.id AS run_id, r.principal AS principal, r.project AS project, "
                "u.local_id AS unit_local_id, a.state AS attempt_state "
                "FROM leases l LEFT JOIN attempts a ON a.id=l.attempt_id "
                "LEFT JOIN units u ON u.id=a.unit_id LEFT JOIN runs r ON r.id=u.run_id "
                "WHERE l.pool_id=? AND l.state IN ('granted','resize_pending','release_pending') "
                "ORDER BY l.created_at", (pool_id,)).fetchall()
            result = []
            for row in rows:
                value = self._lease_row(row)
                value['run_id'] = row['run_id']
                value['principal'] = row['principal']
                value['project'] = row['project']
                value['unit_local_id'] = row['unit_local_id']
                value['attempt_state'] = row['attempt_state']
                result.append(value)
            return result

    def record_external_lease(self, *, lease_id: str, pool_id: str, owner: dict,
                              request: ResourceRequest, reason: str = 'legacy') -> dict:
        """Charge a legacy reservation that the engine did not grant.

        Coordinator mode imports these charges before becoming authoritative;
        they are released only when the legacy owner confirms termination.
        """
        with self.transaction():
            row = self.connection.execute('SELECT * FROM leases WHERE id=?', (lease_id,)).fetchone()
            if row is not None:
                return self.lease_by_id(lease_id)
            stamp = now_iso()
            attempt_id = 'external:' + lease_id
            self.connection.execute(
                'INSERT INTO leases(id, attempt_id, pool_id, owner_json, request_json, committed_json, '
                'target_json, revision, state, heartbeat_at, created_at, updated_at) '
                'VALUES(?,?,?,?,?,?,?,1,?,?,?,?)',
                (lease_id, attempt_id, pool_id, _json(owner), _json(request.to_json()),
                 _json(request.to_json()), _json(request.to_json()), 'granted', stamp, stamp, stamp))
            spec, _ = self.pool(pool_id)
            self._event('legacy_lease_imported', principal=spec.principal, revision=1,
                        payload={'lease_id': lease_id, 'request': request.to_json(), 'reason': reason})
            return self.lease_by_id(lease_id)

    def transport_lease(self, *, pool_id, lease_id, owner, size=None, release=False):
        """Byte credits for control/transfer adapters, under the pool transaction.

        Explicit release means the caller has relinquished its buffers. A lost
        client never returns credits merely because a timeout elapsed.
        """
        with self.transaction():
            spec, _ = self.pool(pool_id)
            old = self.lease_by_id(lease_id)
            if old and (old['pool_id'] != pool_id or old['owner'] != owner
                        or old['attempt_id'] != 'transport:' + lease_id):
                raise ValueError('Transport lease belongs to another owner')
            if release:
                if old:
                    self.connection.execute("UPDATE leases SET state='released', updated_at=? WHERE id=?",
                                            (now_iso(), lease_id))
                return True
            if type(size) is not int or size <= 0:
                raise ValueError('Transport byte budget must be positive')
            if old and old['state'] != 'released':
                if old['committed'].transport_reserved_bytes != size:
                    raise ValueError('Transport retry changed its byte budget')
                return True
            used = self._active_lease_totals(pool_id)
            if size > spec.schedulable_bytes - used['ram']:
                return False
            if spec.transport_reserve_bytes and size > spec.transport_reserve_bytes - used['transport']:
                return False
            stamp = now_iso()
            value = _json(ResourceRequest(cpu_threads=0, transport_reserved_bytes=size).to_json())
            self.connection.execute(
                "INSERT OR REPLACE INTO leases(id,attempt_id,pool_id,owner_json,request_json,committed_json,"
                "target_json,revision,state,heartbeat_at,created_at,updated_at) VALUES(?,?,?,?,?,?,?,1,'granted',?,?,?)",
                (lease_id, 'transport:' + lease_id, pool_id, _json(owner), value, value, value, stamp, stamp, stamp))
            return True

    def reconcile_transport_leases(self, pool_id):
        from .supervisor import identity_alive
        for raw in self.active_leases(pool_id):
            if not raw['attempt_id'].startswith('transport:'):
                continue
            owner = _load(raw['owner_json'], {})
            # An incomplete identity is uncertainty, not evidence of death.
            if owner.get('pid') and owner.get('created') and owner.get('boot_id') and not identity_alive(owner):
                self.transport_lease(pool_id=pool_id, lease_id=raw['id'], owner=owner, release=True)

    def acquire_lease(self, *, attempt_id: str, pool_id: str, owner: dict,
                      request: ResourceRequest, lease_id: str | None = None,
                      actor='coordinator') -> dict:
        """All-or-nothing RAM/CPU/device/scratch reservation inside one transaction."""
        with self.transaction():
            spec, epoch = self.pool(pool_id)
            if not self.connection.execute('SELECT 1 FROM attempts WHERE id=?', (attempt_id,)).fetchone():
                raise KeyError(f'Unknown attempt {attempt_id}')
            used = self._active_lease_totals(pool_id)
            free_ram = spec.schedulable_bytes - used['ram']
            free_cpu = spec.cpu_threads - used['cpu']
            free_scratch = (spec.scratch_bytes - used['scratch']) if spec.scratch_bytes else None
            details = {'pool_id': pool_id, 'requested': request.to_json(),
                       'free_ram_bytes': max(0, free_ram), 'free_cpu_threads': max(0, free_cpu),
                       'free_scratch_bytes': free_scratch, 'epoch': epoch}
            if request.ram_bytes > free_ram or request.cpu_threads > free_cpu:
                raise InfeasibleResourcesError('The requested resources do not fit the frozen pool',
                                               details=details)
            if free_scratch is not None and request.scratch_reserved_bytes > free_scratch:
                raise InfeasibleResourcesError('The requested scratch reservation does not fit the frozen pool',
                                               details=details)
            if (spec.transport_reserve_bytes and
                    used['transport'] + request.transport_reserved_bytes > spec.transport_reserve_bytes):
                raise InfeasibleResourcesError('The requested transport allowance exceeds the pool reserve',
                                               details=details)
            if (spec.shared_buffer_reserve_bytes and
                    used['shared'] + request.shared_buffer_bytes > spec.shared_buffer_reserve_bytes):
                raise InfeasibleResourcesError('The requested shared-buffer allowance exceeds the pool reserve',
                                               details=details)
            if request.devices:
                held = {device for item in used['leases']
                        for device in ResourceRequest.from_json(_load(item['committed_json'], {})).devices}
                if held & set(request.devices):
                    raise InfeasibleResourcesError('A requested device is already leased',
                                                   details={**details, 'device_conflict': sorted(held & set(request.devices))})
            lease_id = lease_id or new_id('lease-')
            stamp = now_iso()
            self.connection.execute(
                'INSERT INTO leases(id, attempt_id, pool_id, owner_json, request_json, committed_json, target_json, '
                'revision, state, heartbeat_at, created_at, updated_at) VALUES(?,?,?,?,?,?,?,1,?,?,?,?)',
                (lease_id, attempt_id, pool_id, _json(owner), _json(request.to_json()), _json(request.to_json()),
                 _json(request.to_json()), 'granted', stamp, stamp, stamp))
            attempt = self.attempt(attempt_id)
            unit = self.unit(attempt['unit_id'])
            run = self.run(unit['run_id'])
            self._event('lease_granted', principal=run['principal'], workspace_id=run['workspace_id'],
                        run_id=run['id'], unit_id=unit['id'], attempt_id=attempt_id, revision=1,
                        payload={'lease_id': lease_id, 'request': request.to_json(), 'epoch': epoch,
                                 'committed': request.to_json()})
            return self.lease(attempt_id)

    def release_lease(self, lease_id: str, *, expected_revision: int | None = None, reason='released',
                      actor='supervisor', released_process_bytes: int | None = None) -> dict:
        with self.transaction():
            row = self.connection.execute('SELECT * FROM leases WHERE id=?', (lease_id,)).fetchone()
            if row is None:
                raise KeyError(f'Unknown lease {lease_id}')
            if expected_revision is not None and int(row['revision']) != expected_revision:
                raise StaleRevisionError('The lease changed before release was applied',
                                         details={'lease_id': lease_id})
            if row['state'] == 'released':
                return self.lease_by_id(lease_id)
            committed = ResourceRequest.from_json(_load(row['committed_json'], {}))
            revision = int(row['revision']) + 1
            self.connection.execute(
                "UPDATE leases SET state='released', revision=?, updated_at=?, resize_json=? WHERE id=?",
                (revision, now_iso(), _json({'reason': reason, 'committed': committed.to_json(),
                                             'released_process_bytes': released_process_bytes}), lease_id))
            attempt = self.attempt(row['attempt_id'])
            unit = self.unit(attempt['unit_id'])
            run = self.run(unit['run_id'])
            self._event('lease_released', principal=run['principal'], workspace_id=run['workspace_id'],
                        run_id=run['id'], unit_id=unit['id'], attempt_id=row['attempt_id'], revision=revision,
                        payload={'lease_id': lease_id, 'reason': reason, 'committed': committed.to_json(),
                                 'released_process_bytes': released_process_bytes})
            return self.lease_by_id(lease_id)

    def heartbeat_lease(self, lease_id: str) -> None:
        with self.transaction():
            self.connection.execute('UPDATE leases SET heartbeat_at=?, updated_at=? WHERE id=? AND state != ?',
                                    (now_iso(), now_iso(), lease_id, 'released'))

    def propose_resize(self, *, lease_id: str, fence: int, resize_id: str, target: ResourceRequest,
                       requested_process_release: int = 0, actor='coordinator') -> dict:
        """Persist a revisioned target.  Committed grants stay charged until ACK."""
        with self.transaction():
            row = self.connection.execute('SELECT * FROM leases WHERE id=?', (lease_id,)).fetchone()
            if row is None:
                raise KeyError(f'Unknown lease {lease_id}')
            attempt = self.attempt(row['attempt_id'])
            if int(attempt['fence']) != int(fence):
                raise StaleAttemptError('The lease fence is stale', details={'lease_id': lease_id})
            current = ResourceRequest.from_json(_load(row['committed_json'], {}))
            if requested_process_release < 0 or requested_process_release > current.process_reservation_bytes:
                raise ValueError('requested_process_release is outside the committed process grant')
            spec, _ = self.pool(row['pool_id'])
            if target.ram_bytes > current.ram_bytes:
                # Reserve growth before the worker is permitted to raise its
                # limit; otherwise an ACK could overcommit the pool.
                totals = self._active_lease_totals(row['pool_id'])
                increase = target.ram_bytes - current.ram_bytes
                free = spec.schedulable_bytes - totals['ram']
                if increase > free:
                    raise InfeasibleResourcesError('No free pool capacity for this growth proposal',
                                                   details={'pool_id': row['pool_id'],
                                                             'requested_increase_bytes': increase,
                                                             'free_bytes': max(0, free)})
            revision = int(row['revision']) + 1
            payload = {'lease_id': lease_id, 'attempt_id': row['attempt_id'], 'fence': fence,
                       'resize_id': resize_id, 'revision': revision, 'state': 'pending',
                       'current': current.to_json(), 'target': target.to_json(),
                       'requested_process_release': requested_process_release,
                       'acknowledged_process_release': 0, 'ack_state': 'pending',
                       'created_at': now_iso(), 'updated_at': now_iso()}
            self.connection.execute(
                "UPDATE leases SET target_json=?, revision=?, state='resize_pending', resize_id=?, "
                "resize_state='pending', resize_json=?, updated_at=? WHERE id=?",
                (_json(target.to_json()), revision, resize_id, _json(payload), now_iso(), lease_id))
            unit = self.unit(attempt['unit_id'])
            run = self.run(unit['run_id'])
            self._event('lease_resize_proposed', principal=run['principal'], workspace_id=run['workspace_id'],
                        run_id=run['id'], unit_id=unit['id'], attempt_id=row['attempt_id'], revision=revision,
                        payload=payload)
            return self.lease_by_id(lease_id)

    def ack_resize(self, *, lease_id: str, resize_id: str, fence: int,
                   acknowledged_process_release: int = 0, actor='worker') -> dict:
        with self.transaction():
            row = self.connection.execute('SELECT * FROM leases WHERE id=?', (lease_id,)).fetchone()
            if row is None:
                raise KeyError(f'Unknown lease {lease_id}')
            payload = _load(row['resize_json'], None)
            if not payload or payload.get('resize_id') != resize_id:
                raise StaleRevisionError('The resize proposal is stale', details={'lease_id': lease_id})
            attempt = self.attempt(row['attempt_id'])
            if int(attempt['fence']) != int(fence):
                raise StaleAttemptError('The resize fence is stale', details={'lease_id': lease_id})
            if payload.get('ack_state') == 'acknowledged':
                return self.lease_by_id(lease_id)
            current = ResourceRequest.from_json(_load(row['committed_json'], {}))
            target = ResourceRequest.from_json(_load(row['target_json'], {}))
            if target.process_reservation_bytes >= current.process_reservation_bytes:
                # Growth was reserved by the coordinator before this ACK.
                released = 0
                process = target.process_reservation_bytes
            else:
                released = min(int(acknowledged_process_release),
                               max(0, current.process_reservation_bytes - target.process_reservation_bytes))
                process = current.process_reservation_bytes - released
            managed = min(target.managed_budget_bytes, process)
            committed = ResourceRequest(
                managed_budget_bytes=managed,
                process_reservation_bytes=process,
                cpu_threads=target.cpu_threads,
                scratch_reserved_bytes=target.scratch_reserved_bytes,
                transport_reserved_bytes=target.transport_reserved_bytes,
                shared_buffer_bytes=target.shared_buffer_bytes,
                devices=target.devices)
            revision = int(row['revision']) + 1
            payload.update(state='acknowledged', ack_state='acknowledged', revision=revision,
                           acknowledged_process_release=released,
                           updated_at=now_iso())
            self.connection.execute(
                "UPDATE leases SET committed_json=?, revision=?, state='granted', resize_state='acknowledged', "
                "resize_json=?, updated_at=? WHERE id=?",
                (_json(committed.to_json()), revision, _json(payload), now_iso(), lease_id))
            unit = self.unit(attempt['unit_id'])
            run = self.run(unit['run_id'])
            self._event('lease_resize_acknowledged', principal=run['principal'], workspace_id=run['workspace_id'],
                        run_id=run['id'], unit_id=unit['id'], attempt_id=row['attempt_id'], revision=revision,
                        payload=payload)
            return self.lease_by_id(lease_id)

    def reject_resize(self, *, lease_id: str, resize_id: str, reason: str, actor='coordinator') -> dict:
        with self.transaction():
            row = self.connection.execute('SELECT * FROM leases WHERE id=?', (lease_id,)).fetchone()
            if row is None:
                raise KeyError(f'Unknown lease {lease_id}')
            payload = _load(row['resize_json'], None)
            if payload and payload.get('resize_id') == resize_id:
                payload.update(state='rejected', ack_state='rejected', reason=reason, updated_at=now_iso())
                revision = int(row['revision']) + 1
                self.connection.execute(
                    "UPDATE leases SET revision=?, state='granted', resize_state='rejected', resize_json=?, "
                    "updated_at=? WHERE id=?", (revision, _json(payload), now_iso(), lease_id))
                return self.lease_by_id(lease_id)
            return self.lease_by_id(lease_id)

    # -- artifacts -----------------------------------------------------
    def record_artifact(self, *, artifact_id: str, attempt_id: str, fence: int, manifest: dict,
                        digest: str, size_bytes: int, state: str, location: str) -> dict:
        with self.transaction():
            row = self.connection.execute('SELECT * FROM artifacts WHERE id=?', (artifact_id,)).fetchone()
            if row is not None:
                if row['digest'] != digest or row['fence'] != int(fence):
                    raise CorruptArtifactError('An immutable artifact id was reused with different content',
                                               details={'artifact_id': artifact_id})
                return dict(row)
            self.connection.execute(
                'INSERT INTO artifacts(id, attempt_id, fence, manifest_json, digest, size_bytes, state, location, '
                'created_at, updated_at) VALUES(?,?,?,?,?,?,?,?,?,?)',
                (artifact_id, attempt_id, int(fence), _json(manifest), digest, int(size_bytes), state, location,
                 now_iso(), now_iso()))
            return dict(self.connection.execute('SELECT * FROM artifacts WHERE id=?', (artifact_id,)).fetchone())

    def artifact(self, artifact_id: str) -> dict | None:
        with self.lock:
            row = self.connection.execute('SELECT * FROM artifacts WHERE id=?', (artifact_id,)).fetchone()
            if row is None:
                return None
            value = dict(row)
            value['manifest'] = _load(value.pop('manifest_json'), {})
            return value

    def update_artifact(self, artifact_id: str, *, state: str, location: str | None = None) -> dict:
        with self.transaction():
            values = {'state': state, 'updated_at': now_iso()}
            if location is not None:
                values['location'] = location
            assignments = ', '.join(f'{name}=?' for name in values)
            self.connection.execute(f'UPDATE artifacts SET {assignments} WHERE id=?',
                                    (*values.values(), artifact_id))
            row = self.connection.execute('SELECT * FROM artifacts WHERE id=?', (artifact_id,)).fetchone()
            if row is None:
                raise KeyError(f'Unknown artifact {artifact_id}')
            return dict(row)

    def add_reference(self, artifact_id: str, *, owner: str, reason: str) -> dict:
        with self.transaction():
            token = hashlib.sha256(f'{artifact_id}\0{owner}\0{reason}'.encode()).hexdigest()[:32]
            reference_id = f'ref-{token}'
            self.connection.execute(
                'INSERT OR IGNORE INTO artifact_refs(id, artifact_id, owner, reason, state, created_at) '
                'VALUES(?,?,?,?,?,?)', (reference_id, artifact_id, owner, reason, 'pinned', now_iso()))
            return dict(self.connection.execute('SELECT * FROM artifact_refs WHERE id=?',
                                                (reference_id,)).fetchone())

    def references(self, artifact_id: str) -> list[dict]:
        with self.lock:
            return [dict(row) for row in self.connection.execute(
                'SELECT * FROM artifact_refs WHERE artifact_id=? AND state=?',
                (artifact_id, 'pinned')).fetchall()]

    def release_reference(self, reference_id: str) -> None:
        with self.transaction():
            self.connection.execute("UPDATE artifact_refs SET state='released' WHERE id=?", (reference_id,))

    # -- events --------------------------------------------------------
    def _event(self, kind: str, *, principal: str, workspace_id=None, run_id=None, unit_id=None,
               attempt_id=None, revision=0, payload=None) -> int:
        current = self.connection.execute('INSERT INTO events(kind, principal, workspace_id, run_id, unit_id, '
                                          'attempt_id, revision, payload_json, created_at) '
                                          'VALUES(?,?,?,?,?,?,?,?,?)',
                                          (kind, principal, workspace_id, run_id, unit_id, attempt_id,
                                           int(revision), _json(payload or {}), now_iso()))
        self.local.events = getattr(self.local, 'events', 0) + 1
        return int(current.lastrowid)

    def append_event(self, kind: str, *, principal: str, **kwargs) -> int:
        with self.transaction():
            return self._event(kind, principal=principal, **kwargs)

    def event_bounds(self) -> tuple[int, int]:
        with self.lock:
            row = self.connection.execute('SELECT MIN(cursor) AS first, MAX(cursor) AS last FROM events').fetchone()
            return int(row['first'] or 0), int(row['last'] or 0)

    def _event_floor(self) -> int:
        row = self.connection.execute("SELECT value FROM schema_meta WHERE key='min_event_cursor'").fetchone()
        return int(row['value']) if row else 0

    def events_after(self, cursor: int, *, limit=200, run_id=None, principal=None, workspace_id=None,
                     kinds=None, max_bytes=256 * 1024) -> dict:
        floor = self._event_floor()
        if cursor < floor:
            raise CursorExpiredError('The requested event cursor has expired; request a snapshot first',
                                     details={'cursor': cursor, 'floor': floor})
        query = 'SELECT * FROM events WHERE cursor>?'
        values: list = [int(cursor)]
        for column, value in (('run_id', run_id), ('principal', principal), ('workspace_id', workspace_id)):
            if value is not None:
                query += f' AND {column}=?'
                values.append(value)
        if kinds:
            query += f' AND kind IN ({",".join("?" * len(kinds))})'
            values.extend(list(kinds))
        query += ' ORDER BY cursor LIMIT ?'
        values.append(max(1, min(int(limit), 1000)))
        with self.lock:
            rows = self.connection.execute(query, values).fetchall()
        events, used = [], 0
        for row in rows:
            payload = _load(row['payload_json'], {})
            item = {'cursor': int(row['cursor']), 'kind': row['kind'], 'principal': row['principal'],
                    'workspace_id': row['workspace_id'], 'run_id': row['run_id'], 'unit_id': row['unit_id'],
                    'attempt_id': row['attempt_id'], 'revision': int(row['revision']),
                    'payload': payload, 'created_at': row['created_at']}
            size = len(_json(item).encode('utf-8'))
            if used + size > max_bytes and events:
                break
            events.append(item)
            used += size
        next_cursor = events[-1]['cursor'] if events else int(cursor)
        has_more = False
        if events:
            probe = 'SELECT 1 FROM events WHERE cursor>?'
            probe_values: list = [next_cursor]
            for column, value in (('run_id', run_id), ('principal', principal), ('workspace_id', workspace_id)):
                if value is not None:
                    probe += f' AND {column}=?'
                    probe_values.append(value)
            if kinds:
                probe += f' AND kind IN ({",".join("?" * len(kinds))})'
                probe_values.extend(list(kinds))
            probe += ' LIMIT 1'
            with self.lock:
                has_more = bool(self.connection.execute(probe, probe_values).fetchone())
        first, last = self.event_bounds()
        return {'events': events, 'cursor': next_cursor, 'floor': floor, 'has_more': has_more,
                'bytes': used, 'first_cursor': first, 'last_cursor': last}

    def prune_events(self, *, keep=20000) -> dict:
        with self.transaction():
            maximum = self.connection.execute('SELECT MAX(cursor) FROM events').fetchone()[0] or 0
            cutoff = maximum - int(keep)
            if cutoff <= 0:
                return {'deleted': 0, 'floor': self._event_floor()}
            row = self.connection.execute('SELECT MIN(cursor) FROM events WHERE cursor<=?', (cutoff,)).fetchone()
            floor = int(row[0] or maximum)
            deleted = self.connection.execute('DELETE FROM events WHERE cursor<=?', (cutoff,)).rowcount
            self.connection.execute(
                "INSERT INTO schema_meta(key, value) VALUES('min_event_cursor', ?) "
                'ON CONFLICT(key) DO UPDATE SET value=excluded.value', (str(floor),))
            return {'deleted': deleted, 'floor': floor}

    def wait_events(self, cursor: int, timeout: float) -> bool:
        """Wait for a local append; cross-process writers are caught by polling."""
        import time as _time
        deadline = _time.monotonic() + max(0.0, timeout)
        while True:
            first, last = self.event_bounds()
            if last > cursor:
                return True
            remaining = deadline - _time.monotonic()
            if remaining <= 0:
                return False
            with self._condition:
                self._condition.wait(min(remaining, 0.25))

    # -- outbox --------------------------------------------------------
    def add_outbox(self, *, command: str, attempt_id: str | None = None, run_id: str | None = None,
                   payload: dict | None = None, outbox_id: str | None = None) -> dict:
        stamp = now_iso()
        outbox_id = outbox_id or new_id('outbox-')
        with self.transaction():
            self.connection.execute(
                'INSERT OR IGNORE INTO outbox(id, attempt_id, run_id, command, payload_json, state, created_at, '
                'updated_at) VALUES(?,?,?,?,?,?,?,?)',
                (outbox_id, attempt_id, run_id, command, _json(payload or {}), 'pending', stamp, stamp))
            return self.outbox(outbox_id)

    def outbox(self, outbox_id: str) -> dict:
        with self.lock:
            row = self.connection.execute('SELECT * FROM outbox WHERE id=?', (outbox_id,)).fetchone()
            if row is None:
                raise KeyError(f'Unknown outbox command {outbox_id}')
            value = dict(row)
            value['payload'] = _load(value.pop('payload_json'), {})
            return value

    def pending_outbox(self, *, limit=64, now: float | None = None) -> list[dict]:
        import time as _time
        now = _time.monotonic() if now is None else now
        with self.lock:
            rows = self.connection.execute(
                "SELECT * FROM outbox WHERE state IN ('pending','retry') AND available_at<=? "
                'ORDER BY created_at LIMIT ?', (now, max(1, int(limit)))).fetchall()
        result = []
        for row in rows:
            value = dict(row)
            value['payload'] = _load(value.pop('payload_json'), {})
            result.append(value)
        return result

    def claim_outbox(self, outbox_id: str) -> dict:
        with self.transaction():
            row = self.connection.execute('SELECT * FROM outbox WHERE id=?', (outbox_id,)).fetchone()
            if row is None:
                raise KeyError(f'Unknown outbox command {outbox_id}')
            if row['state'] in ('acked', 'dispatched'):
                return self.outbox(outbox_id)
            self.connection.execute(
                "UPDATE outbox SET state='dispatched', attempts=attempts+1, updated_at=? WHERE id=?",
                (now_iso(), outbox_id))
            return self.outbox(outbox_id)

    def ack_outbox(self, outbox_id: str, *, result: dict | None = None) -> dict:
        with self.transaction():
            self.connection.execute(
                "UPDATE outbox SET state='acked', last_error=NULL, payload_json=?, updated_at=? WHERE id=?",
                (_json(result or {}), now_iso(), outbox_id))
            return self.outbox(outbox_id)

    def retry_outbox(self, outbox_id: str, *, error: str, delay=1.0) -> dict:
        import time as _time
        with self.transaction():
            self.connection.execute(
                "UPDATE outbox SET state='retry', available_at=?, last_error=?, updated_at=? WHERE id=?",
                (_time.monotonic() + max(0.0, delay), error[:1000], now_iso(), outbox_id))
            return self.outbox(outbox_id)

    # -- operational queries -------------------------------------------
    def operational_snapshot(self) -> dict:
        current = self._active_lease_totals()
        with self.transaction():
            queued = self.connection.execute("SELECT COUNT(*) AS n FROM runs WHERE status IN ('queued','running')").fetchone()['n']
            attempts = self.connection.execute('SELECT COUNT(*) AS n FROM attempts WHERE state IN (?,?,?,?)',
                                               (AttemptState.ADMITTED.value, AttemptState.STARTING.value,
                                                AttemptState.RUNNING.value, AttemptState.COMMITTING.value)).fetchone()['n']
            outbox = self.connection.execute("SELECT COUNT(*) AS n FROM outbox WHERE state IN ('pending','retry')").fetchone()['n']
            first, last = self.event_bounds()
            floor = self._event_floor()
        return {'active_leases': current['attempts'], 'charged_ram_bytes': current['ram'],
                'charged_cpu_threads': current['cpu'], 'queued_runs': int(queued),
                'active_attempts': int(attempts), 'pending_outbox': int(outbox),
                'event_bounds': [first, last], 'event_floor': floor,
                'schema_version': SCHEMA_VERSION, 'path': str(self.path)}

    def transition_history(self, entity: str, entity_id: str) -> list[dict]:
        with self.lock:
            return [dict(row) for row in self.connection.execute(
                'SELECT * FROM transitions WHERE entity=? AND entity_id=? ORDER BY id',
                (entity, entity_id)).fetchall()]
