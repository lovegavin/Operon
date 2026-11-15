"""Bounded read projections of the host's durable invocation records.

The pool authorizes the run before constructing this reader. It neither opens
an executor nor trusts a worker manifest, receipt path or caller-selected file.
"""
from __future__ import annotations

import base64
from contextlib import contextmanager
import json
import os
from pathlib import Path
import stat

from operon.bytecode import io_path
from operon.contracts.plan_operations import PlanEventsQuery, PlanLogsQuery, PlanPageQuery
from operon.engine.contracts import CursorExpiredError, EngineError


def _size(value):
    # ASCII escaping is the worst-case serialization used by the pool framing.
    return len(json.dumps(value, ensure_ascii=True).encode('utf-8'))


def _page(run, name, records, *, after, limit, max_bytes, extra=None):
    page = {'run_id': run['id'], 'revision': run['revision'], name: [],
            'next_cursor': after, 'has_more': False, **(extra or {})}
    for record in records[:limit]:
        item = dict(record)
        cursor = item.pop('page_key')
        candidate = {**page, name: [*page[name], item], 'next_cursor': cursor}
        if _size(candidate) > max_bytes:
            if not page[name]:
                raise EngineError('A result record exceeds the requested page budget',
                                  code='result_record_too_large', status=413)
            break
        page = candidate
    page['has_more'] = len(page[name]) < len(records)
    return page


def _reject_links(root, relative):
    path = root
    for part in relative.parts:
        if part in ('', '.', '..') or ':' in part or '/' in part or '\\' in part:
            raise EngineError('Invalid owned log location', code='plan_log_unavailable', status=409)
        path = path / part
        attrs = io_path(path).lstat()
        if stat.S_ISLNK(attrs.st_mode) or getattr(attrs, 'st_file_attributes', 0) & 0x400:
            raise EngineError('Owned log location contains a link', code='plan_log_unavailable', status=409)
    return path


@contextmanager
def _open_owned(root, relative):
    """Pin POSIX components / verify the opened Windows handle before reading."""
    path = _reject_links(root, relative)
    descriptor = None
    try:
        if os.open in os.supports_dir_fd and hasattr(os, 'O_NOFOLLOW'):
            descriptor = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            for index, part in enumerate(relative.parts):
                flags = os.O_RDONLY | os.O_NOFOLLOW | getattr(os, 'O_NONBLOCK', 0)
                if index < len(relative.parts) - 1:
                    flags |= os.O_DIRECTORY
                child = os.open(part, flags, dir_fd=descriptor)
                os.close(descriptor)
                descriptor = child
        else:
            descriptor = os.open(io_path(path), os.O_RDONLY | getattr(os, 'O_BINARY', 0)
                                 | getattr(os, 'O_NONBLOCK', 0))
        opened = os.fstat(descriptor)
        if not stat.S_ISREG(opened.st_mode) or opened.st_nlink != 1:
            raise EngineError('Owned log is not a single-link regular file', code='plan_log_unavailable', status=409)
        if os.name == 'nt':
            import ctypes
            from ctypes import wintypes
            import msvcrt
            final_path = ctypes.WinDLL('kernel32', use_last_error=True).GetFinalPathNameByHandleW
            final_path.argtypes = [wintypes.HANDLE, wintypes.LPWSTR, wintypes.DWORD, wintypes.DWORD]
            final_path.restype = wintypes.DWORD
            buffer = ctypes.create_unicode_buffer(32768)
            length = final_path(msvcrt.get_osfhandle(descriptor), buffer, len(buffer), 0)
            actual = buffer.value
            if actual.startswith('\\\\?\\UNC\\'):
                actual = '\\\\' + actual[8:]
            elif actual.startswith('\\\\?\\'):
                actual = actual[4:]
            if not length or length >= len(buffer) or Path(actual) != path:
                raise EngineError('Owned log changed before reading', code='plan_log_unavailable', status=409)
        current = io_path(_reject_links(root, relative)).stat()
        if (opened.st_dev, opened.st_ino) != (current.st_dev, current.st_ino):
            raise EngineError('Owned log changed before reading', code='plan_log_unavailable', status=409)
        yield descriptor, opened
    finally:
        if descriptor is not None:
            os.close(descriptor)


def _read_log(root, relative, offset, limit):
    with _open_owned(root, relative) as (descriptor, opened):
        if offset > opened.st_size:
            raise EngineError('Log offset is beyond the current log; restart at zero',
                              code='plan_log_offset', status=409, details={'size_bytes': opened.st_size})
        os.lseek(descriptor, offset, os.SEEK_SET)
        return os.read(descriptor, limit), os.fstat(descriptor).st_size


class PlanResults:
    def __init__(self, store, service_directory, run):
        self.store, self.root, self.run = store, Path(service_directory).resolve(), run

    def events(self, **values):
        query = PlanEventsQuery.model_validate(values)
        with self.store.lock:
            row = self.store.connection.execute(
                "SELECT value FROM schema_meta WHERE key='min_event_cursor'").fetchone()
            floor = int(row['value']) if row else 0
            first = self.store.connection.execute('SELECT MIN(cursor) FROM events').fetchone()[0]
            if first is not None:
                # Older journals may save the first deleted cursor as their
                # floor. Do not silently skip the rest of that deleted range.
                floor = max(floor, int(first) - 1)
            elif floor:
                sequence = self.store.connection.execute(
                    "SELECT seq FROM sqlite_sequence WHERE name='events'").fetchone()
                floor = max(floor, int(sequence[0]) if sequence else 0)
            if query.after < floor:
                raise CursorExpiredError('Plan event cursor expired; restart from the retained floor',
                                         details={'floor': floor, 'cursor': query.after})
            rows = self.store.connection.execute(
                'SELECT cursor AS page_key,cursor,kind,unit_id,attempt_id,revision,created_at '
                'FROM events WHERE run_id=? AND principal=? AND (workspace_id=? OR workspace_id IS NULL) AND cursor>? '
                'ORDER BY cursor LIMIT ?', (self.run['id'], self.run['principal'], self.run['workspace_id'],
                                            query.after, query.limit + 1)).fetchall()
        return _page(self.run, 'events', rows, **query.model_dump(), extra={'floor': floor})

    def attempts(self, **values):
        query = PlanPageQuery.model_validate(values)
        if query.after and (not query.after.isascii() or not query.after.isdecimal() or len(query.after) > 19
                            or int(query.after) > 2**63 - 1):
            raise EngineError('Invalid attempt page cursor', code='invalid_plan_cursor', status=422)
        with self.store.lock:
            rows = self.store.connection.execute(
                'SELECT CAST(a.rowid AS TEXT) AS page_key,a.id AS attempt_id,u.local_id AS unit_id,a.ordinal,a.state,'
                'a.exit_code,a.error_code,a.started_at,a.finished_at FROM attempts a '
                'JOIN units u ON u.id=a.unit_id WHERE u.run_id=? AND a.rowid>? ORDER BY a.rowid LIMIT ?',
                (self.run['id'], int(query.after or 0), query.limit + 1)).fetchall()
        return _page(self.run, 'attempts', rows, **query.model_dump())

    def artifacts(self, **values):
        query = PlanPageQuery.model_validate(values)
        # Reuse is an explicit durable reference owned by this run; neither
        # mutable published/*.json nor a caller's artifact ID grants authority.
        projection = ("u.id || '/' || a.id AS page_key,a.id AS artifact_id,u.local_id AS unit_id,"
                      'a.attempt_id,a.digest AS sha256,a.size_bytes,a.created_at')
        with self.store.lock:
            rows = self.store.connection.execute(
                'SELECT * FROM (SELECT ' + projection + ',0 AS reused FROM units u '
                'JOIN attempts t ON t.unit_id=u.id JOIN artifacts a ON a.attempt_id=t.id '
                'WHERE u.run_id=? AND a.state=\'committed\' UNION ALL SELECT ' + projection +
                ',1 AS reused FROM units u JOIN unit_reuses x ON x.unit_id=u.id '
                'JOIN artifacts a ON a.id=x.artifact_id WHERE u.run_id=? AND a.state=\'committed\') '
                'WHERE page_key>? ORDER BY page_key LIMIT ?',
                (self.run['id'], self.run['id'], query.after, query.limit + 1)).fetchall()
        return _page(self.run, 'artifacts', rows, **query.model_dump())

    def artifact_files(self, **values):
        from .plan_artifacts import PlanArtifactReader
        return PlanArtifactReader(self.store, self.root, self.run).files(**values)

    def artifact_preview(self, **values):
        from .plan_artifacts import PlanArtifactReader
        return PlanArtifactReader(self.store, self.root, self.run).preview(**values)

    def artifact_file(self, **values):
        from .plan_artifacts import PlanArtifactReader
        return PlanArtifactReader(self.store, self.root, self.run).descriptor(**values)

    def logs(self, **values):
        query = PlanLogsQuery.model_validate(values)
        with self.store.lock:
            row = self.store.connection.execute(
                'SELECT a.state,u.local_id FROM attempts a JOIN units u ON u.id=a.unit_id '
                'WHERE a.id=? AND u.run_id=?', (query.attempt_id, self.run['id'])).fetchone()
        if row is None:
            raise EngineError('Attempt is not owned by this plan', code='plan_attempt_not_found', status=404)
        prefix = Path('invocations') / 'runs' / self.run['id']
        current = prefix / 'attempts' / query.attempt_id / 'logs' / 'worker.log'
        previous = prefix / 'nodes' / row['local_id'] / 'attempts' / query.attempt_id / 'logs' / 'worker.log'
        data, size, available = b'', 0, False
        # Both fixed layouts are host-owned. The older one supports attempts
        # prepared before the executor's short Windows path migration.
        try:
            for relative in (current, previous):
                try:
                    data, size = _read_log(self.root, relative, query.offset, query.max_bytes)
                    available = True
                    break
                except FileNotFoundError:
                    continue
        except OSError as exc:
            raise EngineError('Owned log is unavailable', code='plan_log_unavailable', status=409) from exc
        content = base64.b64encode(data).decode('ascii') if query.encoding == 'base64' else data.decode('utf-8', errors='replace')
        return {'run_id': self.run['id'], 'attempt_id': query.attempt_id, 'state': row['state'],
                'available': available, 'encoding': query.encoding, 'data': content,
                'offset': query.offset, 'next_offset': query.offset + len(data), 'bytes_read': len(data),
                'size_bytes': size, 'eof': query.offset + len(data) >= size}
