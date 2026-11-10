"""Transfer admission adapter. Never creates a second host allocator."""
import hashlib
import threading

from .facade import owner_identity

_adapter_lock = threading.Lock()


class PoolTransportAdmission:
    def __init__(self, service):
        self.service = service
        self.owner = owner_identity()

    @property
    def capacity(self):
        if self.service.pool_remote:
            self.service._ensure_pool_session()
            return self.service.pool_client.request('transport.capacity', {})['bytes']
        spec = self.service.engine.spec
        return min(spec.schedulable_bytes, spec.transport_reserve_bytes or spec.schedulable_bytes)

    def _call(self, ticket, *, size=None, release=False):
        lease_id = 'transport-' + hashlib.sha256(
            (self.owner['service_id'] + ':' + ticket).encode()).hexdigest()
        params = {'lease_id': lease_id, 'owner': self.owner, 'size': size, 'release': release}
        if self.service.pool_remote:
            self.service._ensure_pool_session()
            return self.service.pool_client.request('transport.lease', params)['reserved']
        engine = self.service.engine
        return engine.store.transport_lease(pool_id=engine.spec.pool_id, **params)

    def reserve(self, ticket, allocation):
        if allocation.get('kind') != 'transport' or allocation.get('cpu_threads', 0):
            raise ValueError('This adapter only grants transfer bytes')
        return self._call(ticket, size=allocation['reserved_bytes'])

    def release(self, ticket):
        return self._call(ticket, release=True)


def transport_admission(service):
    if getattr(service, 'pool_remote', False) or getattr(service, 'coordinator', None) is not None or getattr(service, 'pool', None) is not None:
        with _adapter_lock:
            if not hasattr(service, '_transport_admission'):
                service._transport_admission = PoolTransportAdmission(service)
            return service._transport_admission
    return service.admission
