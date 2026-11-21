"""Bounded concurrent control service independent of the socket transport.

Each connection owns at most one framed request.  Handler slots and aggregate
in-flight body bytes are admitted before the body is read, every read/write has
an inactivity timeout and an absolute deadline, and a saturated server rejects
new work with a stable ``busy`` code instead of queueing without bound.

The same loop serves the private Unix socket and test TCP/socketpair transports.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from contextvars import ContextVar
from dataclasses import dataclass
import json
import os
import socket
import struct
import threading
import time

from .contracts import BusyError, EngineError
from .telemetry import METRICS, bind_correlation, correlation, new_request_id

_request_context: ContextVar[dict] = ContextVar('operon_control_request', default={})


class ControlError(EngineError):
    code = 'invalid_request'


class RequestTimeout(ControlError):
    code = 'request_timeout'


class PayloadTooLarge(ControlError):
    code = 'payload_too_large'


@dataclass(frozen=True)
class ControlLimits:
    max_handlers: int = 32
    max_reject_handlers: int = 4
    max_planning_handlers: int = 2
    max_frame_bytes: int = 128 * 1024 ** 2
    max_response_bytes: int = 64 * 1024 ** 2
    max_inflight_bytes: int = 512 * 1024 ** 2
    inactivity_seconds: float = 30.0
    absolute_seconds: float = 120.0
    busy_response_seconds: float = 2.0

    def __post_init__(self):
        for name in ('max_handlers', 'max_reject_handlers', 'max_planning_handlers', 'max_frame_bytes', 'max_response_bytes', 'max_inflight_bytes'):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                raise ValueError(f'{name} must be a positive integer')
        for name in ('inactivity_seconds', 'absolute_seconds', 'busy_response_seconds'):
            value = getattr(self, name)
            if not isinstance(value, (int, float)) or value <= 0:
                raise ValueError(f'{name} must be positive')


class ByteBudget:
    """Aggregate body-byte admission shared by all handlers."""

    def __init__(self, limit: int):
        self.limit = int(limit)
        self.used = 0
        self.lock = threading.Condition()

    def acquire(self, size: int, timeout=0.05) -> bool:
        deadline = time.monotonic() + timeout
        with self.lock:
            while self.used + size > self.limit:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return False
                self.lock.wait(remaining)
            self.used += size
            return True

    def release(self, size: int) -> None:
        with self.lock:
            self.used = max(0, self.used - size)
            self.lock.notify_all()


class ControlLoop:
    def __init__(self, dispatch, *, limits: ControlLimits | None = None, on_close=None,
                 on_error=None):
        self.dispatch = dispatch
        self.limits = limits or ControlLimits()
        self.on_close = on_close
        self.on_error = on_error
        self.budget = ByteBudget(self.limits.max_inflight_bytes)
        self.slots = threading.BoundedSemaphore(self.limits.max_handlers)
        # Parsed bulk requests cannot occupy every dispatch thread. Slow frame
        # readers remain bounded by the existing absolute/inactivity deadlines.
        self.lifecycle_handlers = min(4, self.limits.max_handlers // 4)
        self.normal_slots = threading.BoundedSemaphore(self.limits.max_handlers - self.lifecycle_handlers)
        # Keep CPU-heavy graph planning from multiplying GIL contention. Waiting
        # requests retain their already-bounded handler/byte grants and deadline.
        self.planning_slots = threading.BoundedSemaphore(self.limits.max_planning_handlers)
        self.executor = ThreadPoolExecutor(max_workers=self.limits.max_handlers,
                                           thread_name_prefix='operon-control')
        self.reject_slots = threading.BoundedSemaphore(self.limits.max_reject_handlers)
        self.reject_executor = ThreadPoolExecutor(max_workers=self.limits.max_reject_handlers,
                                                  thread_name_prefix='operon-reject')
        self.active = 0
        self.accepted = 0
        self.rejected = 0
        self.errors = 0
        self.lock = threading.Lock()
        self.closed = threading.Event()

    # -- connection handling -------------------------------------------
    def submit(self, connection, peer='') -> bool:
        if self.closed.is_set():
            connection.close()
            return False
        if not self.slots.acquire(blocking=False):
            self.rejected += 1
            METRICS.increment('control.busy_rejected')
            self._reject(connection)
            return False
        with self.lock:
            self.active += 1
            self.accepted += 1
            METRICS.gauge('control.inflight_handlers', self.active)
        try:
            self.executor.submit(self._run, connection, peer)
            return True
        except RuntimeError:
            self.slots.release()
            with self.lock:
                self.active -= 1
            self._reject(connection)
            return False

    def _reject(self, connection):
        # No socket I/O on the accept thread. Keep rejection work bounded too:
        # under a sustained flood excess connections are closed immediately.
        if not self.reject_slots.acquire(blocking=False):
            connection.close()
            return
        try:
            self.reject_executor.submit(self._reject_worker, connection)
        except RuntimeError:
            self.reject_slots.release()
            connection.close()

    def _reject_worker(self, connection):
        try:
            self._send_busy(connection)
        finally:
            self.reject_slots.release()

    def _run(self, connection, peer):
        started = time.perf_counter()
        request_id = None
        reserved = 0
        normal_slot = False
        planning_slot = False
        try:
            try:
                connection.settimeout(self.limits.inactivity_seconds)
            except (AttributeError, OSError):
                pass
            deadline = time.monotonic() + self.limits.absolute_seconds
            size = self._read_frame_size(connection, deadline)
            if size > self.limits.max_frame_bytes:
                raise PayloadTooLarge('The control frame exceeds the configured maximum')
            if not self.budget.acquire(size, timeout=0.05):
                raise BusyError('Aggregate control request bytes are at the configured limit')
            reserved = size
            raw = self._read_exact(connection, size, deadline)
            # Reserve a conservative decoded-object estimate *before* JSON parsing.
            # Counting punctuation inside strings overestimates rather than admitting
            # an unaccounted object tree. The reservation lives through dispatch.
            decoded = (len(raw) * 6 + raw.count(b'{') * 240 + raw.count(b'[') * 72
                       + raw.count(b',') * 64 + raw.count(b':') * 160 + raw.count(b'"') * 40)
            if not self.budget.acquire(decoded, timeout=0.05):
                raise BusyError('Decoded control requests exceed the aggregate byte limit')
            reserved += decoded
            try:
                request = json.loads(raw)
            except (UnicodeDecodeError, ValueError, RecursionError) as exc:
                raise ControlError('The control frame is not valid JSON') from exc
            self._validate_structure(request)
            if not isinstance(request, dict) or not isinstance(request.get('method'), str):
                raise ControlError('A control request requires a string method')
            lifecycle = request['method'] in {'status', 'cancel', 'run.cancel', 'run.details', 'run.status', 'pool.ping', 'workspace.close_session',
                'pool.status', 'cluster.plan.lookup', 'cluster.plan.status', 'cluster.plan.cancel', 'plan.details', 'plan.cancel', 'engine_status', 'session.close', 'workspace.stop', 'pool.retire'}
            if not lifecycle:
                normal_slot = self.normal_slots.acquire(blocking=False)
                if not normal_slot:
                    raise BusyError('Bulk dispatch capacity reached; lifecycle handlers are reserved')
            if request['method'] in {'compile', 'workflow.compile', 'validate', 'workflow.validate',
                                     'run', 'run.prepare', 'run.submit', 'cluster.submit', 'cluster.plan.submit', 'plan.submit', 'environment.fingerprint'}:
                planning_slot = self.planning_slots.acquire(timeout=max(0, deadline - time.monotonic()))
                if not planning_slot:
                    raise RequestTimeout('Planning admission exceeded the request deadline')
            request_id = request.get('id')
            params = request.get('params') if isinstance(request.get('params'), dict) else {}
            correlation_id = str(request_id or new_request_id())
            bind_correlation(request_id=correlation_id, method=request['method'])
            _request_context.set({'request_id': correlation_id, 'method': request['method'],
                                  'peer': peer, 'deadline': deadline})
            with _span('control.dispatch'):
                value = self.dispatch(request['method'], params)
            response = {'ok': True, 'value': value, 'id': request_id,
                        'request_id': correlation_id}
        except BaseException as exc:  # noqa: BLE001 - response must always be framed
            self.errors += 1
            METRICS.increment('control.errors')
            if self.on_error is not None:
                try:
                    self.on_error(exc, dict(_request_context.get()))
                except Exception:  # noqa: BLE001 - diagnostics must not break the response
                    pass
            response = self._error_response(exc, request_id)
        finally:
            if planning_slot:
                self.planning_slots.release()
            if normal_slot:
                self.normal_slots.release()
            _request_context.set({})
        try:
            data = json.dumps(response, ensure_ascii=False, allow_nan=False).encode('utf-8')
            if len(data) > self.limits.max_response_bytes:
                data = json.dumps(self._error_response(
                    PayloadTooLarge('The response exceeds the configured maximum'), request_id)).encode('utf-8')
            self._send_bytes(connection, data, time.monotonic() + self.limits.inactivity_seconds)
        except (OSError, ConnectionError):
            pass
        finally:
            self.budget.release(reserved)
            try:
                connection.close()
            except OSError:
                pass
            self.slots.release()
            with self.lock:
                self.active = max(0, self.active - 1)
                METRICS.gauge('control.inflight_handlers', self.active)
            METRICS.observe('control.handler_ms', (time.perf_counter() - started) * 1000)
            if self.on_close:
                try:
                    self.on_close()
                except Exception:  # noqa: BLE001 - cleanup is best effort
                    pass

    @staticmethod
    def _validate_structure(request):
        stack, count = [(request, 0)], 0
        while stack:
            value, depth = stack.pop()
            count += 1
            if depth > 64 or count > 100000:
                raise PayloadTooLarge('Control JSON exceeds the depth or item limit')
            if isinstance(value, dict):
                stack.extend((item, depth + 1) for item in value.values())
            elif isinstance(value, list):
                stack.extend((item, depth + 1) for item in value)

    @staticmethod
    def _error_response(exc, request_id):
        code = getattr(exc, 'code', None) or 'remote_error'
        message = str(exc) or type(exc).__name__
        values = {'ok': False, 'error': message, 'code': code, 'id': request_id}
        details = getattr(exc, 'details', None)
        if isinstance(exc, KeyError):
            values.update(error=f'Unknown resource: {exc}', code='not_found')
            details = None
        elif isinstance(exc, (ValueError, TypeError)) and code in ('remote_error', 'engine_error'):
            values['code'] = 'invalid_request'
        if isinstance(details, dict) and len(json.dumps(details, default=str)) <= 16384:
            values['details'] = details
        elif details is None:
            values['details'] = {'request_id': request_id}
        if isinstance(values.get('details'), dict):
            values['details'].setdefault('request_id', request_id)
        if getattr(exc, 'retry_after', None) is not None:
            values['retry_after'] = exc.retry_after
        node_id = getattr(exc, 'node_id', None)
        if node_id:
            values['node_id'] = node_id
        return values

    def _read_frame_size(self, connection, deadline) -> int:
        header = self._read_exact(connection, 8, deadline)
        size = struct.unpack('!Q', header)[0]
        if size == 0:
            raise ControlError('An empty control frame is not valid')
        return size

    def _read_exact(self, connection, size, deadline) -> bytes:
        chunks = bytearray()
        while len(chunks) < size:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise RequestTimeout('The control request exceeded its absolute deadline')
            try:
                connection.settimeout(min(self.limits.inactivity_seconds, remaining))
                block = connection.recv(min(size - len(chunks), 65536))
            except socket.timeout as exc:
                raise RequestTimeout('The control request timed out') from exc
            if not block:
                raise ConnectionError('Control connection closed before the frame completed')
            chunks.extend(block)
        return bytes(chunks)

    def _send_bytes(self, connection, data: bytes, deadline):
        payload = struct.pack('!Q', len(data)) + data
        while payload:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise RequestTimeout('The control response exceeded its deadline')
            try:
                connection.settimeout(min(self.limits.inactivity_seconds, remaining))
                sent = connection.send(payload)
            except socket.timeout as exc:
                raise RequestTimeout('The control response timed out') from exc
            if sent <= 0:
                raise ConnectionError('Control connection closed during the response')
            payload = payload[sent:]

    def _send_busy(self, connection):
        try:
            data = json.dumps({'ok': False, 'code': 'busy',
                               'error': 'The control service is at its handler limit',
                               'retry_after': 0.2}).encode('utf-8')
            self._send_bytes(connection, data, time.monotonic() + self.limits.busy_response_seconds)
            # A client that is still writing the rejected body must be able to
            # read the busy response before the socket is closed; otherwise
            # Windows reports a connection reset that hides the machine code.
            try:
                connection.shutdown(socket.SHUT_WR)
            except (AttributeError, OSError):
                pass
            drain_deadline = time.monotonic() + 0.25
            drained = 0
            while drained < 65536:
                remaining = drain_deadline - time.monotonic()
                if remaining <= 0:
                    break
                connection.settimeout(remaining)
                block = connection.recv(65536)
                if not block:
                    break
                drained += len(block)
        except (OSError, ConnectionError):
            pass
        finally:
            try:
                connection.close()
            except OSError:
                pass

    # -- accept loop ---------------------------------------------------
    def serve(self, listener, *, alive=None, idle_seconds=300.0, accept_timeout=1.0, stop_requested=None):
        """Accept connections until idle and no durable work remains."""
        listener.settimeout(accept_timeout)
        last_request = time.monotonic()
        try:
            while not self.closed.is_set():
                if callable(stop_requested) and stop_requested():
                    break
                try:
                    connection, _ = listener.accept()
                except socket.timeout:
                    if (time.monotonic() - last_request > idle_seconds and not self.busy()
                            and not (alive() if callable(alive) else False)):
                        break
                    continue
                except OSError:
                    break
                last_request = time.monotonic()
                self.submit(connection)
        finally:
            self.close()
            if callable(alive) and not alive():
                on_close = getattr(self, 'on_close', None)

    def busy(self) -> bool:
        with self.lock:
            return self.active > 0 or self.budget.used > 0

    def close(self):
        self.closed.set()
        self.executor.shutdown(wait=True)
        self.reject_executor.shutdown(wait=True)

    def stats(self) -> dict:
        with self.lock:
            active = self.active
        return {'accepted': self.accepted, 'rejected': self.rejected, 'errors': self.errors,
                'active': active, 'inflight_bytes': self.budget.used,
                'limits': {'handlers': self.limits.max_handlers,
                           'planning_handlers': self.limits.max_planning_handlers,
                           'lifecycle_handlers': self.lifecycle_handlers,
                           'inflight_bytes': self.limits.max_inflight_bytes,
                           'frame_bytes': self.limits.max_frame_bytes}}


class _span:
    """Tiny local span using telemetry without importing its decorator."""

    def __init__(self, name):
        self.name = name

    def __enter__(self):
        self.start = time.perf_counter()
        return self

    def __exit__(self, *exc):
        METRICS.observe(self.name, (time.perf_counter() - self.start) * 1000)


def limits_from_environment() -> ControlLimits:
    def integer(name, default, minimum=1):
        try:
            return max(minimum, int(os.environ.get(name, default)))
        except (TypeError, ValueError):
            return default
    return ControlLimits(
        max_handlers=integer('OPERON_CONTROL_HANDLERS', 32),
        max_planning_handlers=integer('OPERON_CONTROL_PLANNING_HANDLERS', 2),
        max_frame_bytes=integer('OPERON_CONTROL_FRAME_BYTES', 128 * 1024 ** 2),
        max_inflight_bytes=integer('OPERON_CONTROL_INFLIGHT_BYTES', 512 * 1024 ** 2),
        inactivity_seconds=float(os.environ.get('OPERON_CONTROL_INACTIVITY', 30)),
        absolute_seconds=float(os.environ.get('OPERON_CONTROL_DEADLINE', 120)),
    )
