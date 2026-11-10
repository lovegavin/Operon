"""One exclusive resource authority per authorized execution pool.

The pool snapshot is frozen at startup.  Admission decisions are transactional
and all-or-nothing; resize targets are proposals until the worker acknowledges
a verified release.  Managed-store eviction never returns process credits by
itself.
"""
from __future__ import annotations

from dataclasses import dataclass
import time

from .contracts import (
    InfeasibleResourcesError, PoolSpec, ResourceRequest, StaleAttemptError, UnsupportedResizeError,
)
from .policy import Usage
from .telemetry import METRICS


@dataclass(frozen=True)
class PoolSnapshot:
    spec: PoolSpec
    epoch: int
    used: Usage
    free: Usage
    active: int
    transport: int = 0
    shared: int = 0
    reserved: int = 0

    @property
    def capacity(self) -> int:
        return self.spec.schedulable_bytes

    def to_json(self) -> dict:
        return {'pool': self.spec.to_json(), 'epoch': self.epoch,
                'capacity_bytes': self.capacity,
                'used': {'ram': self.used.ram, 'cpu': self.used.cpu, 'scratch': self.used.scratch},
                'free': {'ram': self.free.ram, 'cpu': self.free.cpu, 'scratch': self.free.scratch},
                'transport_bytes': self.transport, 'shared_buffer_bytes': self.shared,
                'active_leases': self.active, 'reserved_process_bytes': self.reserved}


class PoolResources:
    def __init__(self, store, spec: PoolSpec, epoch: int):
        self.store, self.spec, self.epoch = store, spec, epoch

    @property
    def pool_id(self) -> str:
        return self.spec.pool_id

    def snapshot(self) -> PoolSnapshot:
        totals = self.store._active_lease_totals(self.pool_id)
        used = Usage(ram=totals['ram'], cpu=totals['cpu'], scratch=totals['scratch'])
        free = Usage(ram=max(0, self.spec.schedulable_bytes - used.ram),
                     cpu=max(0, self.spec.cpu_threads - used.cpu),
                     scratch=max(0, self.spec.scratch_bytes - used.scratch) if self.spec.scratch_bytes else 0)
        return PoolSnapshot(spec=self.spec, epoch=self.epoch, used=used, free=free,
                            active=len(totals['leases']), transport=totals['transport'],
                            shared=totals['shared'],
                            reserved=max(0, used.ram - totals['transport'] - totals['shared']))

    def admit(self, *, attempt_id: str, request: ResourceRequest, owner: dict,
              lease_id: str | None = None) -> dict:
        start = time.perf_counter()
        try:
            lease = self.store.acquire_lease(attempt_id=attempt_id, pool_id=self.pool_id,
                                             owner=owner, request=request, lease_id=lease_id)
        finally:
            METRICS.observe('pool.admit_ms', (time.perf_counter() - start) * 1000)
        METRICS.increment('pool.leases_granted')
        METRICS.gauge('pool.charged_ram_bytes', self.snapshot().used.ram)
        return lease

    def release(self, lease_id: str, *, reason='released', actor='supervisor',
                released_process_bytes: int | None = None) -> dict:
        lease = self.store.release_lease(lease_id, reason=reason, actor=actor,
                                         released_process_bytes=released_process_bytes)
        METRICS.increment('pool.leases_released')
        METRICS.gauge('pool.charged_ram_bytes', self.snapshot().used.ram)
        return lease

    def resize(self, *, lease_id: str, fence: int, resize_id: str, target: ResourceRequest,
               requested_process_release: int = 0) -> dict:
        """Persist a shrink/grow proposal; committed credits stay charged."""
        lease = self.store.lease_by_id(lease_id)
        if lease is None:
            raise KeyError(f'Unknown lease {lease_id}')
        current = lease['committed']
        if target.ram_bytes < current.ram_bytes and not requested_process_release:
            # A managed-budget reduction is legitimate, but it cannot return
            # process credits.  The proposal must say so explicitly.
            requested_process_release = 0
        return self.store.propose_resize(lease_id=lease_id, fence=fence, resize_id=resize_id,
                                         target=target, requested_process_release=requested_process_release)

    def acknowledge(self, *, lease_id: str, resize_id: str, fence: int,
                    acknowledged_process_release: int = 0) -> dict:
        return self.store.ack_resize(lease_id=lease_id, resize_id=resize_id, fence=fence,
                                     acknowledged_process_release=acknowledged_process_release)

    def reject(self, *, lease_id: str, resize_id: str, reason: str) -> dict:
        return self.store.reject_resize(lease_id=lease_id, resize_id=resize_id, reason=reason)

    def verify_growth(self, *, lease: dict, target: ResourceRequest) -> None:
        """Growth must reserve pool credits before the worker raises its limit."""
        if target.ram_bytes <= lease['committed'].ram_bytes:
            return
        snapshot = self.snapshot()
        increase = target.ram_bytes - lease['committed'].ram_bytes
        if increase > snapshot.free.ram:
            raise InfeasibleResourcesError('There is no free pool capacity for this growth',
                                           details={'requested_increase_bytes': increase,
                                                    'free_bytes': snapshot.free.ram})

    @staticmethod
    def require_resizable(adapter_capability: str) -> None:
        if adapter_capability not in ('cooperative-resize-step', 'cooperative-resize-chunk'):
            raise UnsupportedResizeError(
                'This execution adapter did not declare a cooperative resize capability')
