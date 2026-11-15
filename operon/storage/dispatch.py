"""Admission before asynchronous offload; the executor queue is not a quota."""
from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
import threading

from .references import StorageError


class StorageDispatch:
    def __init__(self, limits):
        self.limits = limits
        self._executor = ThreadPoolExecutor(max_workers=limits.io_slots, thread_name_prefix='storage-io')
        self._lifecycle = ThreadPoolExecutor(max_workers=limits.lifecycle_slots, thread_name_prefix='storage-lifecycle')
        self._lock = threading.Lock()
        self._active = {}
        self._lifecycle_active = {}
        self._closed = False

    async def run(self, function, *, principal, lifecycle=False, **kwargs):
        active = self._lifecycle_active if lifecycle else self._active
        total_limit = self.limits.lifecycle_slots if lifecycle else self.limits.io_slots
        owner_limit = total_limit if lifecycle else self.limits.io_slots_per_principal
        with self._lock:
            count = active.get(principal, 0)
            if self._closed:
                raise StorageError('Storage dispatch is closed', code='storage_unavailable')
            if sum(active.values()) >= total_limit or count >= owner_limit:
                raise StorageError('Storage dispatch capacity is occupied', code='storage_busy')
            active[principal] = count + 1

        def release(_=None):
            with self._lock:
                count = active[principal] - 1
                if count:
                    active[principal] = count
                else:
                    del active[principal]
        try:
            future = (self._lifecycle if lifecycle else self._executor).submit(function, **kwargs)
        except BaseException:
            release()
            raise
        # Releasing on the actual Future's completion keeps cancelled HTTP
        # requests accounted for while their synchronous I/O is still running.
        future.add_done_callback(release)
        return await asyncio.wrap_future(future)

    def close(self):
        with self._lock:
            self._closed = True
        self._executor.shutdown(wait=False, cancel_futures=True)
        self._lifecycle.shutdown(wait=False, cancel_futures=True)
