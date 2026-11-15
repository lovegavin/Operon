"""Explicit PostgreSQL 17 connection lanes, migrations and leadership.

No SQL is retried after an uncertain commit. Retryable deadlocks and
serialization failures are retried only while executing a pure DB callback.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field
import hashlib
import math
from pathlib import Path
import re
import threading

from operon.engine.contracts import BusyError, CommitOutcomeUnknown
from .receipts import ClusterError, LeadershipLost

MIGRATION_LOCK = 72840317001
LEADERSHIP_LOCK = 72840317002


@dataclass(frozen=True)
class DatabaseConfig:
    dsn: str = field(repr=False)
    schema: str = 'public'
    connect_timeout: int = 5
    statement_timeout_ms: int = 5000
    lock_timeout_ms: int = 1000
    acquire_timeout: float = 2.0

    def __post_init__(self):
        if not re.fullmatch(r'[a-z_][a-z0-9_]{0,62}', self.schema):
            raise ValueError('Database schema must be a safe lowercase identifier')
        if not self.dsn or any(not math.isfinite(v) or v <= 0 for v in (self.connect_timeout,
                self.statement_timeout_ms, self.lock_timeout_ms, self.acquire_timeout)):
            raise ValueError('A DSN and positive finite timeouts are required')


class Postgres:
    """Six ordinary, one scheduler, one lifecycle connection; no overflow."""

    def __init__(self, config: DatabaseConfig):
        try:
            import psycopg
            from psycopg.rows import dict_row
            from psycopg_pool import ConnectionPool
        except ImportError as exc:
            raise ClusterError('Cluster service requires the pinned psycopg 3 and psycopg_pool extras',
                               code='cluster_dependency_unavailable') from exc
        self.config, self.psycopg = config, psycopg
        self._pools = {}
        self._slots = {name: threading.BoundedSemaphore(size)
                       for name, size in (('ordinary', 6), ('scheduler', 1), ('lifecycle', 1))}
        kwargs = self.connection_kwargs()
        kwargs['row_factory'] = dict_row
        try:
            for name, size in (('ordinary', 6), ('scheduler', 1), ('lifecycle', 1)):
                pool = ConnectionPool(config.dsn, min_size=0, max_size=size, max_waiting=size,
                                      timeout=config.acquire_timeout, kwargs=kwargs, open=False,
                                      name='operon-cluster-' + name)
                pool.open()
                self._pools[name] = pool
            with self.connection() as connection:
                self.require_version(connection)
        except BaseException:
            self.close()
            raise

    def connection_kwargs(self):
        return {'autocommit': True, 'connect_timeout': self.config.connect_timeout,
                'options': f'-c statement_timeout={self.config.statement_timeout_ms} '
                           f'-c lock_timeout={self.config.lock_timeout_ms} '
                           '-c idle_in_transaction_session_timeout=10000 '
                           f'-c search_path={self.config.schema}'}

    @staticmethod
    def require_version(connection):
        if connection.info.server_version // 10000 != 17:
            raise ClusterError('Cluster persistence requires PostgreSQL 17',
                               code='cluster_database_version')

    @contextmanager
    def connection(self, lane='ordinary'):
        slot = self._slots[lane]
        if not slot.acquire(blocking=False):
            raise BusyError('Cluster database lane is full', details={'lane': lane})
        try:
            with self._pools[lane].connection(timeout=self.config.acquire_timeout) as connection:
                yield connection
        except self.psycopg.Error as exc:
            raise ClusterError('Database connection lane is unavailable', code='database_unavailable',
                               details={'lane': lane, 'sqlstate': exc.sqlstate}) from exc
        finally:
            slot.release()

    def transaction(self, callback, *, lane='ordinary', retries=2):
        """Callback MUST contain only SQL/local work, never network or launch."""
        for attempt in range(retries + 1):
            with self.connection(lane) as connection:
                body_done = False
                try:
                    with connection.transaction():
                        connection.execute('SET TRANSACTION ISOLATION LEVEL READ COMMITTED')
                        result = callback(connection)
                        body_done = True
                    return result
                except (self.psycopg.errors.DeadlockDetected,
                        self.psycopg.errors.SerializationFailure):
                    if attempt == retries:
                        raise ClusterError('Database transaction retry limit reached', code='database_retry_exhausted')
                except self.psycopg.Error as exc:
                    if body_done:
                        raise CommitOutcomeUnknown('Cluster commit outcome is unknown; look up the original request key') from exc
                    raise ClusterError('Cluster transaction did not complete',
                                       code='database_unavailable',
                                       details={'sqlstate': exc.sqlstate}) from exc

    def migrate(self, directory=None):
        directory = Path(directory or Path(__file__).with_name('migrations'))
        files = sorted(directory.glob('[0-9][0-9][0-9][0-9]_*.sql'))
        migrations = [(int(path.name[:4]), path.name, hashlib.sha256(path.read_bytes()).hexdigest(),
                       path.read_text(encoding='utf-8')) for path in files]
        if len({item[0] for item in migrations}) != len(migrations):
            raise ClusterError('Duplicate migration number', code='migration_conflict')

        def apply(connection):
            connection.execute('SELECT pg_advisory_xact_lock(%s)', (MIGRATION_LOCK,))
            connection.execute('CREATE TABLE IF NOT EXISTS schema_migrations '
                               '(version integer PRIMARY KEY, name text NOT NULL, checksum text NOT NULL, '
                               'applied_at timestamptz NOT NULL DEFAULT now())')
            existing = {row['version']: row for row in connection.execute('SELECT * FROM schema_migrations')}
            known = {item[0] for item in migrations}
            if set(existing) - known:
                raise ClusterError('Database schema is newer than this controller', code='migration_newer_schema')
            for version, name, checksum, sql in migrations:
                if version in existing:
                    if existing[version]['checksum'] != checksum or existing[version]['name'] != name:
                        raise ClusterError('Applied migration checksum mismatch', code='migration_checksum_mismatch')
                    continue
                # Trusted, packaged migrations are the only non-parameter SQL input.
                connection.execute(sql, prepare=False)
                connection.execute('INSERT INTO schema_migrations(version,name,checksum) VALUES (%s,%s,%s)',
                                   (version, name, checksum))
            return tuple(item[1] for item in migrations)
        return self.transaction(apply, lane='scheduler')

    def close(self):
        for pool in self._pools.values():
            pool.close()


class Leadership:
    """Dedicated advisory-lock connection, never borrowed for request work."""

    def __init__(self, database: Postgres, *, cluster_id: str, owner_id: str):
        self.database, self.cluster_id, self.owner_id = database, cluster_id, owner_id
        self.epoch = 0
        self._connection = None
        self._mutex = threading.RLock()
        self._lost = threading.Event()
        self._reconciled = False

    def acquire(self):
        with self._mutex:
            self.close()
            connection = self.database.psycopg.connect(self.database.config.dsn,
                                                       **self.database.connection_kwargs())
            try:
                self.database.require_version(connection)
                if not connection.execute('SELECT pg_try_advisory_lock(%s)', (LEADERSHIP_LOCK,)).fetchone()[0]:
                    raise LeadershipLost('Another controller owns the cluster')
                with connection.transaction():
                    row = connection.execute(
                        'INSERT INTO controller_owner(singleton,cluster_id,epoch,owner_id) VALUES (true,%s,1,%s) '
                        'ON CONFLICT(singleton) DO UPDATE SET epoch=controller_owner.epoch+1, '
                        'owner_id=EXCLUDED.owner_id, acquired_at=now() '
                        'WHERE controller_owner.cluster_id=EXCLUDED.cluster_id RETURNING epoch',
                        (self.cluster_id, self.owner_id)).fetchone()
                    if row is None:
                        raise LeadershipLost('Database belongs to a different cluster')
                    self.epoch = row[0]
                self._connection = connection
                self._lost.clear()
                self._reconciled = False
                return self.epoch
            except BaseException:
                connection.close()
                raise

    def assert_current(self, *, dispatch=True):
        with self._mutex:
            if self._lost.is_set() or self._connection is None or (dispatch and not self._reconciled):
                raise LeadershipLost('Controller must acquire leadership and reconcile before dispatch')
            try:
                # A live dedicated session retains its advisory lock until close.
                row = self._connection.execute('SELECT epoch,owner_id FROM controller_owner WHERE singleton=true').fetchone()
                if not row or row != (self.epoch, self.owner_id):
                    raise LeadershipLost('Controller epoch was superseded')
            except BaseException as exc:
                self._lost.set()
                if isinstance(exc, LeadershipLost):
                    raise
                raise LeadershipLost('Leadership connection lost; dispatch stopped') from exc

    def reconciled(self):
        self.assert_current(dispatch=False)
        self._reconciled = True

    def close(self):
        with self._mutex:
            self._lost.set()
            self._reconciled = False
            if self._connection is not None:
                self._connection.close()
                self._connection = None
