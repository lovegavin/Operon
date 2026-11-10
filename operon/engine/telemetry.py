"""Low-overhead local metrics, spans and correlation identifiers.

Diagnostics are local by default.  Collection starts only when
``OPERON_ENGINE_METRICS`` is a truthy value, so existing deployments pay a
dictionary lookup per observation.  No payload, credential or whole scientific
input is ever recorded.
"""
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timezone
import math
import os
import threading
import time
import uuid

_TRUE = {'1', 'true', 'yes', 'on'}


def enabled() -> bool:
    return os.environ.get('OPERON_ENGINE_METRICS', '').strip().lower() in _TRUE


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class Histogram:
    """Bounded exact sample set for small local workloads.

    Percentiles use nearest-rank over retained samples.  Once the reservoir is
    full, new observations replace a deterministic slot and the sample count is
    reported separately, so a p95 is never presented as a population estimate.
    """

    __slots__ = ('values', 'count', 'total', 'minimum', 'maximum', 'limit', 'dropped')

    def __init__(self, limit=4096):
        self.values = []
        self.count = 0
        self.total = 0.0
        self.minimum = None
        self.maximum = None
        self.limit = limit
        self.dropped = 0

    def observe(self, value: float) -> None:
        if not math.isfinite(value):
            return
        self.count += 1
        self.total += value
        self.minimum = value if self.minimum is None else min(self.minimum, value)
        self.maximum = value if self.maximum is None else max(self.maximum, value)
        if len(self.values) < self.limit:
            self.values.append(value)
        else:
            self.dropped += 1
            self.values[self.count % self.limit] = value

    def summary(self) -> dict:
        values = sorted(self.values)
        def rank(percent):
            if not values:
                return None
            index = max(0, min(len(values) - 1, int(math.ceil(percent / 100 * len(values))) - 1))
            return values[index]
        return {'count': self.count, 'retained': len(values), 'dropped': self.dropped,
                'min': self.minimum, 'max': self.maximum,
                'mean': (self.total / self.count) if self.count else None,
                'p50': rank(50), 'p95': rank(95), 'p99': rank(99)}


class Metrics:
    def __init__(self, limit=4096):
        self.lock = threading.Lock()
        self.histograms: dict[str, Histogram] = {}
        self.counters: dict[str, int] = {}
        self.gauges: dict[str, float] = {}
        self.started_at = now_iso()
        self.limit = limit
        self.enabled = enabled()

    def observe(self, name: str, milliseconds: float) -> None:
        if not (self.enabled or enabled()):
            return
        with self.lock:
            histogram = self.histograms.get(name)
            if histogram is None:
                histogram = self.histograms[name] = Histogram(self.limit)
            histogram.observe(milliseconds)

    def increment(self, name: str, value: int = 1) -> None:
        if not (self.enabled or enabled()):
            return
        with self.lock:
            self.counters[name] = self.counters.get(name, 0) + value

    def gauge(self, name: str, value: float) -> None:
        if not (self.enabled or enabled()):
            return
        with self.lock:
            self.gauges[name] = value

    def snapshot(self, *, reset=False) -> dict:
        with self.lock:
            value = {'started_at': self.started_at,
                     'histograms': {name: item.summary() for name, item in sorted(self.histograms.items())},
                     'counters': dict(sorted(self.counters.items())),
                     'gauges': dict(sorted(self.gauges.items()))}
            if reset:
                self.histograms.clear()
                self.counters.clear()
                self.gauges.clear()
        return value

    def reset(self) -> None:
        self.snapshot(reset=True)


METRICS = Metrics()

_correlation: ContextVar[dict] = ContextVar('operon_engine_correlation', default={})


def correlation() -> dict:
    return dict(_correlation.get())


def bind_correlation(**values) -> dict:
    current = dict(_correlation.get())
    current.update({key: value for key, value in values.items() if value is not None})
    _correlation.set(current)
    return current


def new_request_id() -> str:
    return uuid.uuid4().hex


@contextmanager
def span(name: str, **fields):
    """Time one bounded operation and attach correlation fields."""
    start = time.perf_counter()
    token = None
    if fields:
        token = _correlation.set({**_correlation.get(), **{k: v for k, v in fields.items() if v is not None}})
    try:
        yield
    finally:
        METRICS.observe(name, (time.perf_counter() - start) * 1000)
        if token is not None:
            _correlation.reset(token)


def timed(name: str):
    """Decorator form of :func:`span` for adapter methods."""
    def decorate(function):
        def wrapper(*args, **kwargs):
            with span(name):
                return function(*args, **kwargs)
        wrapper.__name__ = getattr(function, '__name__', 'timed')
        wrapper.__doc__ = function.__doc__
        return wrapper
    return decorate


def redact(value, *, keys=('password', 'passphrase', 'token', 'secret', 'key_path')):
    """Copy diagnostics without credential-like values."""
    if isinstance(value, dict):
        return {key: ('<redacted>' if str(key).lower() in keys else redact(item, keys=keys))
                for key, item in value.items()}
    if isinstance(value, list):
        return [redact(item, keys=keys) for item in value]
    return value
