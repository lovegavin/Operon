"""Bounded service offload hooks for the existing async application adapter."""
from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
import threading

from operon.engine.contracts import BusyError


class BoundedExecutor:
    """Acquire before submit; the executor's unbounded queue is never admission."""

    def __init__(self, lanes, *, name):
        if not lanes or any(type(value) is not int or value <= 0 for value in lanes.values()):
            raise ValueError('Executor lanes must be positive integer capacities')
        self.capacity = dict(lanes)
        self._slots = {lane: threading.BoundedSemaphore(count) for lane, count in lanes.items()}
        self._executor = ThreadPoolExecutor(max_workers=sum(lanes.values()), thread_name_prefix=name)

    def submit(self, lane, function, *args, **kwargs):
        slot = self._slots[lane]
        if not slot.acquire(blocking=False):
            raise BusyError('Cluster executor lane is full', details={'lane': lane})
        try:
            future = self._executor.submit(function, *args, **kwargs)
        except BaseException:
            slot.release()
            raise
        future.add_done_callback(lambda _: slot.release())
        return future

    def close(self, *, wait=True):
        self._executor.shutdown(wait=wait, cancel_futures=True)


class ClusterService:
    """No web imports or hidden controller startup; authenticated principal is supplied."""

    def __init__(self, repository, *, controller=None):
        self.repository, self.controller = repository, controller
        self.database_work = (controller.database_work if controller is not None else
                              BoundedExecutor({'ordinary': 6, 'scheduler': 1, 'lifecycle': 1}, name='cluster-db'))

    async def submit(self, *, principal, request_id, plan, preparations=0):
        result = await asyncio.wrap_future(self.database_work.submit('ordinary', self.repository.submit,
            principal=principal, request_id=request_id, plan=plan, preparations=preparations))
        if self.controller:
            self.controller.wake()
        return result

    async def status(self, *, principal, run_id):
        return await asyncio.wrap_future(self.database_work.submit('lifecycle', self.repository.status, principal, run_id))

    async def cancel(self, *, principal, run_id):
        result = await asyncio.wrap_future(self.database_work.submit('lifecycle', self.repository.cancel, principal, run_id))
        if self.controller:
            self.controller.wake()
        return result

    async def lookup(self, *, principal, request_id):
        return await asyncio.wrap_future(self.database_work.submit('lifecycle', self.repository.request, principal, request_id))

    async def events(self, *, principal, after='0', limit=200):
        return await asyncio.wrap_future(self.database_work.submit('lifecycle', self.repository.events,
            principal, after=after, limit=limit))

    def close(self):
        if self.controller:
            self.controller.stop()
        else:
            self.database_work.close()
