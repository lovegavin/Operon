"""Bounded durable admission and authenticated control dispatch.

Limits stop new work, never cancellation/recovery of already accepted work.
They are admission watermarks, not filesystem quotas for scientific outputs.
"""
from contextlib import contextmanager
from dataclasses import dataclass, fields
import os
import math
import threading
import time

from .contracts import BusyError


@dataclass(frozen=True)
class QueueLimits:
    active_runs: int = 10000
    principal_active_runs: int = 1000
    retained_requests: int = 100000
    principal_retained_requests: int = 10000
    submission_bytes: int = 16 * 1024 ** 2
    submission_units: int = 4096
    state_bytes: int = 4 * 1024 ** 3
    free_disk_bytes: int = 256 * 1024 ** 2

    def __post_init__(self):
        for item in fields(self):
            value = getattr(self, item.name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                raise ValueError(f'{item.name} must be a positive integer')

    @classmethod
    def from_environment(cls):
        defaults = cls()
        return cls(**{f.name: int(os.environ.get('OPERON_QUEUE_' + f.name.upper(),
                                                getattr(defaults, f.name))) for f in fields(cls)})


class PrincipalLimiter:
    """Token buckets plus concurrent dispatch slots, with bounded identity state.

    Call only AFTER authentication and resolve the key from trusted workspace /
    session records. Client-supplied arbitrary principal strings are not keys.
    """
    def __init__(self, *, rate=20.0, burst=40, concurrent=8, max_keys=4096, clock=time.monotonic):
        if (isinstance(rate, bool) or not isinstance(rate, (float, int)) or not math.isfinite(rate) or rate <= 0
                or any(isinstance(v, bool) or not isinstance(v, int) or v < 1
                       for v in (burst, concurrent, max_keys))):
            raise ValueError('Request limits must be positive')
        self.rate, self.burst = float(rate), int(burst)
        self.concurrent, self.max_keys, self.clock = int(concurrent), int(max_keys), clock
        self.lock = threading.Lock()
        self.buckets = {}

    @contextmanager
    def admit(self, principal, *, lane='normal'):
        if lane not in ('normal', 'lifecycle'):
            raise ValueError('Unknown control lane')
        key = (principal, lane)
        with self.lock:
            now = self.clock()
            if key not in self.buckets and sum(other[1] == lane for other in self.buckets) >= self.max_keys:
                # Only evict idle, fully replenished buckets; churn cannot reset
                # an exhausted bucket or steal another principal's active slot.
                for other, item in list(self.buckets.items()):
                    if other[1] == lane and not item[2] and now - item[1] >= self.burst / self.rate:
                        del self.buckets[other]
                if sum(other[1] == lane for other in self.buckets) >= self.max_keys:
                    raise BusyError('Control identity capacity reached', code='rate_limited')
            bucket = self.buckets.setdefault(key, [float(self.burst), now, 0])
            bucket[0] = min(self.burst, bucket[0] + max(0, now - bucket[1]) * self.rate)
            bucket[1] = now
            if bucket[0] < 1 or bucket[2] >= self.concurrent:
                raise BusyError('Control request limit reached for this principal', code='rate_limited',
                                retry_after=max(0.05, (1 - bucket[0]) / self.rate),
                                details={'lane': lane})
            bucket[0] -= 1
            bucket[2] += 1
        try:
            yield
        finally:
            with self.lock:
                bucket[2] -= 1
