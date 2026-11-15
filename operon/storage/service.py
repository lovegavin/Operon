"""Bounded storage browsing behind one application-service interface."""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field
import io
import posixpath
import secrets
import threading
import time

from operon.contracts.storage import StorageRef
from .browsing import BrowseLimits, BrowsePage, BrowseRequest, Preview, PreviewRequest
from .references import StorageError, reference, restart


def _cancelled(cancel):
    return cancel is not None and (cancel() if callable(cancel) else cancel.is_set())


def _check_cancel(cancel):
    if _cancelled(cancel):
        raise StorageError('Storage operation was cancelled', code='storage_cancelled')


@contextmanager
def _errors():
    try:
        yield
    except StorageError:
        raise
    except FileNotFoundError as exc:
        raise StorageError('Storage entry does not exist', code='storage_not_found') from exc
    except PermissionError as exc:
        raise StorageError('Storage access was denied', code='storage_forbidden') from exc
    except (TimeoutError, OSError, EOFError) as exc:
        raise StorageError('Storage I/O is unavailable; retry the operation',
                           code='storage_unavailable') from exc


@dataclass
class _Listing:
    principal: str
    session_id: str
    mount: object
    request: BrowseRequest
    touched: float
    guard: object = field(default_factory=threading.Lock)
    cancelled: object = field(default_factory=threading.Event)
    session: object = None
    names: object = None
    revision: str = ''

    def close(self):
        iterator, self.names = self.names, None
        session, self.session = self.session, None
        if iterator is not None:
            try:
                iterator.close()
            except Exception:
                pass
        if session is not None:
            session.close()


class StorageService:
    """Synchronous bounded work for the application's bounded I/O executor.

    Principal/session IDs are supplied by authentication, never request JSON.
    A cursor leases an enumeration handle, not a scientific execution lease.
    """

    def __init__(self, mounts, *, limits=None, clock=time.monotonic):
        self.mounts = mounts
        self.limits = BrowseLimits.model_validate(limits if limits is not None else {})
        self.clock = clock
        self._lock = threading.RLock()
        self._handles = {}
        self._active = {}
        self._closed = False

    @contextmanager
    def _io(self, principal):
        self.expire_idle()
        with self._lock:
            if self._closed:
                raise StorageError('Storage service is closed', code='storage_unavailable')
            count = self._active.get(principal, 0)
            if count >= self.limits.io_slots_per_principal or sum(self._active.values()) >= self.limits.io_slots:
                raise StorageError('Storage I/O capacity is occupied', code='storage_busy',
                                   details={'per_principal': self.limits.io_slots_per_principal,
                                            'global': self.limits.io_slots})
            self._active[principal] = count + 1
        try:
            with _errors():
                yield
        finally:
            with self._lock:
                remaining = self._active[principal] - 1
                if remaining:
                    self._active[principal] = remaining
                else:
                    del self._active[principal]

    def _retire(self, token, state):
        with self._lock:
            if self._handles.get(token) is state:
                del self._handles[token]
            state.cancelled.set()
        if state.guard.acquire(blocking=False):
            try:
                state.close()
            finally:
                state.guard.release()
        elif state.session is not None:
            try:
                state.session.abort()
            except Exception:
                pass

    def expire_idle(self):
        """Also callable from the application's regular maintenance tick."""
        expired = []
        with self._lock:
            now = self.clock()
            for token, state in tuple(self._handles.items()):
                if now - state.touched < self.limits.cursor_idle_seconds:
                    continue
                if state.guard.acquire(blocking=False):
                    del self._handles[token]
                    state.cancelled.set()
                    expired.append(state)
        for state in expired:
            try:
                state.close()
            finally:
                state.guard.release()
        return len(expired)

    def _listing(self, request, principal, session_id):
        mount = self.mounts.resolve(request.storage_id, principal)
        with self._lock:
            if self._closed:
                raise StorageError('Storage service is closed', code='storage_unavailable')
            if request.cursor:
                token = request.cursor
                state = self._handles.get(token)
                if state is None:
                    raise restart('browse_cursor_expired', 'Browse cursor expired or was closed; restart the listing')
                scope = (principal, session_id, request.storage_id, request.relative_path, request.hidden, request.order)
                expected = (state.principal, state.session_id, state.request.storage_id,
                            state.request.relative_path, state.request.hidden, state.request.order)
                if scope != expected:
                    raise restart('browse_cursor_scope', 'Browse cursor belongs to another request scope')
                if not state.guard.acquire(blocking=False):
                    raise StorageError('A page is already being read for this cursor', code='storage_busy')
                return token, state
            total = len(self._handles)
            count = sum(state.principal == principal for state in self._handles.values())
            if total >= self.limits.max_handles or count >= self.limits.handles_per_principal:
                raise StorageError('Browse handle capacity is occupied; close a listing or retry after expiry',
                                   code='storage_busy', details={'max_handles': self.limits.max_handles,
                                                               'per_principal': self.limits.handles_per_principal})
            token = secrets.token_urlsafe(32)
            state = _Listing(principal, session_id, mount, request, self.clock())
            state.guard.acquire()
            self._handles[token] = state
            return token, state

    def list(self, request, *, principal, session_id='', cancel=None):
        request = BrowseRequest.model_validate(request)
        size = request.page_size or self.limits.default_page_size
        if size > self.limits.max_page_size:
            raise StorageError('Requested page exceeds the configured limit', code='storage_limit',
                               details={'max_page_size': self.limits.max_page_size})
        with self._io(principal):
            _check_cancel(cancel)
            token, state = self._listing(request, principal, session_id)
            retire = False
            try:
                _check_cancel(state.cancelled)
                if state.mount is not self.mounts.resolve(request.storage_id, principal):
                    raise restart('browse_changed', 'Storage binding changed; restart the listing')
                if state.session is None:
                    state.session = state.mount.backend.open()
                    _check_cancel(state.cancelled)
                    state.revision = state.session.revision(request.relative_path)
                    state.names = iter(state.session.names(request.relative_path))
                if state.session.revision(request.relative_path) != state.revision:
                    raise restart('browse_changed', 'Directory changed; restart the listing')
                entries, scanned, complete = [], 0, False
                started = self.clock()
                while len(entries) < size and scanned < self.limits.max_scan_entries:
                    _check_cancel(cancel)
                    _check_cancel(state.cancelled)
                    if scanned and self.clock() - started >= self.limits.page_work_seconds:
                        break
                    try:
                        name, attrs = next(state.names)
                    except StopIteration:
                        complete = True
                        break
                    scanned += 1
                    if not request.hidden and name.startswith('.'):
                        continue
                    path = posixpath.join(request.relative_path, name)
                    entries.append(state.session.listing_entry(request.storage_id, path, attrs))
                _check_cancel(cancel)
                _check_cancel(state.cancelled)
                if state.session.revision(request.relative_path) != state.revision:
                    raise restart('browse_changed', 'Directory changed while browsing; restart the listing')
                state.touched = self.clock()
                retire = complete
                return BrowsePage(tuple(entries), None if complete else token, state.revision,
                                  complete, scanned=scanned)
            except BaseException as exc:
                retire = True
                if state.cancelled.is_set() or _cancelled(cancel):
                    raise StorageError('Storage operation was cancelled', code='storage_cancelled') from exc
                if isinstance(exc, FileNotFoundError):
                    raise restart('browse_changed', 'Directory entry changed; restart the listing') from exc
                raise
            finally:
                if retire or state.cancelled.is_set():
                    with self._lock:
                        self._handles.pop(token, None)
                    try:
                        state.close()
                    finally:
                        state.guard.release()
                else:
                    state.guard.release()

    def stat(self, ref, *, principal, cancel=None):
        ref = StorageRef.model_validate(ref)
        ref = reference(ref.storage_id, ref.relative_path, version=ref.version, digest=ref.digest)
        with self._io(principal):
            _check_cancel(cancel)
            session = self.mounts.resolve(ref.storage_id, principal).backend.open()
            try:
                entry = session.stat(ref.storage_id, ref.relative_path)
                _check_cancel(cancel)
                if ref.version is not None and entry.ref.version != ref.version:
                    raise StorageError('Storage metadata version changed', code='storage_changed')
                return entry
            finally:
                session.close()

    def preview(self, request, *, principal, cancel=None):
        request = PreviewRequest.model_validate(request)
        amount = request.byte_limit or self.limits.default_preview_bytes
        rows = request.row_limit or self.limits.default_preview_rows
        if amount > self.limits.max_preview_bytes or rows > self.limits.max_preview_rows:
            raise StorageError('Preview exceeds the configured limit', code='storage_limit', details={
                'max_preview_bytes': self.limits.max_preview_bytes, 'max_preview_rows': self.limits.max_preview_rows})
        with self._io(principal):
            _check_cancel(cancel)
            session = self.mounts.resolve(request.storage_id, principal).backend.open()
            try:
                entry = session.stat(request.storage_id, request.relative_path)
                if entry.kind != 'file':
                    raise StorageError('Preview requires a regular file', code='storage_not_file')
                raw = session.read(request.relative_path, amount)
                _check_cancel(cancel)
                if session.stat(request.storage_id, request.relative_path).ref.version != entry.ref.version:
                    raise StorageError('File changed during preview', code='storage_changed')
                # Stop row enumeration at the display bound, even for a binary
                # file containing a million newline bytes.
                lines = []
                stream = io.BytesIO(raw)
                for _ in range(rows):
                    line = stream.readline()
                    if not line:
                        break
                    lines.append(line)
                shown = b''.join(lines)
                try:
                    text = shown.decode('utf-8')
                    errors = False
                except UnicodeDecodeError:
                    text, errors = shown.decode('utf-8', errors='replace'), True
                return Preview(entry, text, len(raw), len(lines),
                               len(shown) < entry.size_bytes, decoding_errors=errors)
            finally:
                session.close()

    def cancel(self, cursor, *, principal, session_id=''):
        with self._lock:
            state = self._handles.get(cursor)
            if state is None:
                return False
            if (state.principal, state.session_id) != (principal, session_id):
                raise StorageError('Browse cursor belongs to another session', code='browse_cursor_scope')
        self._retire(cursor, state)
        return True

    def cancel_session(self, *, principal, session_id=''):
        with self._lock:
            owned = [(token, state) for token, state in self._handles.items()
                     if (state.principal, state.session_id) == (principal, session_id)]
        for token, state in owned:
            self._retire(token, state)
        return len(owned)

    def cancel_connection(self, *, principal, connection_id):
        """Detach all UI-session namespaces under one authenticated connection."""
        with self._lock:
            owned = [(token, state) for token, state in self._handles.items()
                     if state.principal == principal and (state.session_id == connection_id
                     or state.session_id.startswith(connection_id + ':'))]
        for token, state in owned:
            self._retire(token, state)
        return len(owned)

    def close(self):
        with self._lock:
            self._closed = True
            owned = tuple(self._handles.items())
        for token, state in owned:
            self._retire(token, state)

    def status(self):
        self.expire_idle()
        with self._lock:
            return {'limits': self.limits.model_dump(mode='json'),
                    'browse_handles': len(self._handles), 'active_io': sum(self._active.values())}
