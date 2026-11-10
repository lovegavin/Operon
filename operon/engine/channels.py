"""Bounded streaming channels with byte credits and immutable block references.

A producer obtains credits *before* materializing a block.  Credits account for
decoded bytes plus metadata, not compressed input size.  Blocks are immutable
and reference counted; a fan-out returns physical credits only after every
required consumer acknowledges.  A slow consumer therefore applies upstream
pressure instead of growing an unbounded queue.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import threading
import time
import uuid

from .contracts import EngineError


class ChannelClosed(EngineError):
    code = 'channel_closed'
    status = 409


class JoinOverflow(EngineError):
    code = 'join_overflow'
    status = 422


class CreditError(EngineError):
    code = 'invalid_credit'
    status = 409


@dataclass(frozen=True)
class OwnedBlock:
    block_id: str
    sequence: int
    generation: int
    data: bytes
    metadata: bytes = b''
    producer: str = ''

    @property
    def decoded_bytes(self) -> int:
        return len(self.data)

    @property
    def charged_bytes(self) -> int:
        return len(self.data) + len(self.metadata)


class Credit:
    """A reserved materialization allowance; publish transfers ownership."""

    __slots__ = ('budget', 'bytes', 'blocks', 'used', 'owner', 'lock')

    def __init__(self, budget: 'ChannelBudget', bytes_: int, blocks: int, owner: str):
        self.budget = budget
        self.bytes = int(bytes_)
        self.blocks = int(blocks)
        self.used = False
        self.owner = owner
        self.lock = threading.Lock()

    def publish(self, block: OwnedBlock) -> None:
        with self.lock:
            if self.used:
                raise CreditError('This credit was already consumed')
            if block.charged_bytes > self.bytes:
                raise CreditError('The block exceeds its reserved decoded size')
            self.used = True
        self.budget.publish(self, block)

    def release(self) -> None:
        with self.lock:
            if self.used:
                return
            self.used = True
        self.budget.release_unpublished(self)


class ChannelBudget:
    """One physical byte/block budget shared by a group of channels."""

    def __init__(self, *, max_bytes: int, max_blocks: int = 8):
        if max_bytes <= 0 or max_blocks <= 0:
            raise ValueError('channel limits must be positive')
        self.max_bytes = int(max_bytes)
        self.max_blocks = int(max_blocks)
        self.condition = threading.Condition()
        self.charged_bytes = 0
        self.charged_blocks = 0
        self.peak_bytes = 0
        self.peak_blocks = 0
        self.closed = False
        self.released = 0
        self.references: dict[tuple[str, int], int] = {}

    def register(self, block: OwnedBlock, references: int) -> None:
        if references < 1:
            raise ValueError('a block requires at least one reference')
        with self.condition:
            key = (block.block_id, block.generation)
            self.references[key] = self.references.get(key, 0) + int(references)

    def reserve(self, decoded_bytes: int, *, blocks=1, owner='producer',
                timeout: float | None = None) -> Credit:
        decoded_bytes = int(decoded_bytes)
        if decoded_bytes < 0 or blocks < 1:
            raise ValueError('credit bytes must be non-negative and blocks positive')
        deadline = None if timeout is None else time.monotonic() + timeout
        with self.condition:
            while (not self.closed and
                   (self.charged_bytes + decoded_bytes > self.max_bytes or
                    self.charged_blocks + blocks > self.max_blocks)):
                remaining = None if deadline is None else deadline - time.monotonic()
                if remaining is not None and remaining <= 0:
                    raise TimeoutError('Timed out waiting for streaming credits')
                self.condition.wait(None if remaining is None else min(remaining, 0.25))
            if self.closed:
                raise ChannelClosed('The channel group is closed')
            self.charged_bytes += decoded_bytes
            self.charged_blocks += blocks
            self.peak_bytes = max(self.peak_bytes, self.charged_bytes)
            self.peak_blocks = max(self.peak_blocks, self.charged_blocks)
            return Credit(self, decoded_bytes, blocks, owner)

    def publish(self, credit: Credit, block: OwnedBlock) -> None:
        # The reservation is already charged; publishing only attaches a block.
        return None

    def release_unpublished(self, credit: Credit) -> None:
        with self.condition:
            self.charged_bytes = max(0, self.charged_bytes - credit.bytes)
            self.charged_blocks = max(0, self.charged_blocks - credit.blocks)
            self.released += credit.bytes
            self.condition.notify_all()

    def acknowledge(self, block: OwnedBlock) -> None:
        with self.condition:
            key = (block.block_id, block.generation)
            remaining = self.references.get(key, 1) - 1
            if remaining > 0:
                self.references[key] = remaining
                return
            self.references.pop(key, None)
            # The physical charge is returned only after the final consumer.
            self.charged_bytes = max(0, self.charged_bytes - block.charged_bytes)
            self.charged_blocks = max(0, self.charged_blocks - 1)
            self.released += block.charged_bytes
            self.condition.notify_all()

    def close(self):
        with self.condition:
            self.closed = True
            self.condition.notify_all()

    def stats(self) -> dict:
        with self.condition:
            return {'charged_bytes': self.charged_bytes, 'charged_blocks': self.charged_blocks,
                    'peak_bytes': self.peak_bytes, 'peak_blocks': self.peak_blocks,
                    'max_bytes': self.max_bytes, 'max_blocks': self.max_blocks,
                    'released_bytes': self.released, 'closed': self.closed}


class Channel:
    """A blocking, byte-bounded single-consumer queue."""

    def __init__(self, budget: ChannelBudget, *, name='channel', on_ack=None):
        self.budget = budget
        self.name = name
        self.on_ack = on_ack
        self.queue: list[tuple[OwnedBlock, int]] = []
        self.inflight: dict[tuple[str, int], OwnedBlock] = {}
        self.condition = threading.Condition()
        self.closed = False
        self.close_reason = ''
        self.received = 0
        self.acked = 0

    def reserve(self, decoded_bytes, *, blocks=1, timeout=None):
        return self.budget.reserve(decoded_bytes, blocks=blocks, timeout=timeout,
                                   owner=self.name)

    def publish(self, credit: Credit, block: OwnedBlock, *, subscribers=None) -> None:
        if subscribers is None:
            credit.publish(block)
            self.budget.register(block, 1)
            self._enqueue(block, 1)
            return
        # One physical charge, one immutable block, many consumer references.
        if not isinstance(subscribers, (list, tuple)) or not subscribers:
            raise ValueError('fan-out requires at least one subscriber')
        credit.publish(block)
        self.budget.register(block, len(subscribers))
        for channel in subscribers:
            channel._enqueue(block, len(subscribers))

    def _enqueue(self, block: OwnedBlock, refs: int):
        with self.condition:
            if self.closed:
                self.budget.acknowledge(block)
                return
            self.queue.append((block, refs))
            self.condition.notify_all()

    def receive(self, timeout: float | None = None) -> OwnedBlock:
        deadline = None if timeout is None else time.monotonic() + timeout
        with self.condition:
            while not self.queue and not self.closed:
                remaining = None if deadline is None else deadline - time.monotonic()
                if remaining is not None and remaining <= 0:
                    raise TimeoutError('Timed out waiting for a streaming block')
                self.condition.wait(None if remaining is None else min(remaining, 0.25))
            if not self.queue:
                raise ChannelClosed(self.close_reason or 'The channel was closed')
            block, refs = self.queue.pop(0)
            self.inflight[(block.block_id, block.generation)] = block
            self.received += 1
            return block

    def ack(self, block: OwnedBlock | tuple[str, int]) -> None:
        if isinstance(block, tuple):
            block_id, generation = block
            block = self.inflight.get((block_id, generation))
        else:
            block_id, generation = block.block_id, block.generation
        with self.condition:
            stored = self.inflight.pop((block_id, generation), None)
        if stored is None:
            # Duplicate or late ACKs are idempotent and never double-release.
            return
        self.acked += 1
        self.budget.acknowledge(stored)
        if self.on_ack:
            self.on_ack(stored)

    def close(self, reason='producer finished'):
        with self.condition:
            self.closed = True
            self.close_reason = reason
            self.condition.notify_all()

    def abort(self, reason='consumer failed'):
        """Fail the channel and return all queued/in-flight references."""
        with self.condition:
            self.closed = True
            self.close_reason = reason
            queued, self.queue = self.queue, []
            inflight, self.inflight = list(self.inflight.values()), {}
            self.condition.notify_all()
        for block, _ in queued:
            self.budget.acknowledge(block)
        for block in inflight:
            self.budget.acknowledge(block)

    def stats(self) -> dict:
        with self.condition:
            return {'name': self.name, 'buffered_blocks': len(self.queue),
                    'inflight_blocks': len(self.inflight), 'received': self.received,
                    'acked': self.acked, 'closed': self.closed,
                    'budget': self.budget.stats()}


class Fanout:
    """Publish one immutable block to several consumers with shared credits."""

    def __init__(self, budget: ChannelBudget, subscribers: list[Channel], *, name='fanout'):
        if not subscribers:
            raise ValueError('fanout requires subscribers')
        self.budget = budget
        self.subscribers = list(subscribers)
        self.name = name
        self.sequence = 0
        self.published = 0

    def publish(self, block: OwnedBlock, credit: Credit | None = None) -> None:
        if credit is None:
            credit = self.budget.reserve(block.charged_bytes)
        credit.publish(block)
        self.sequence = max(self.sequence, block.sequence)
        self.published += 1
        for channel in self.subscribers:
            channel._enqueue(block, len(self.subscribers))

    def close(self, reason='fanout finished'):
        for channel in self.subscribers:
            channel.close(reason)


class BoundedJoin:
    """Bounded keyed join; missing inputs wait for a deadline, never forever."""

    def __init__(self, inputs: list[str], budget: ChannelBudget, *, max_items=8):
        if not inputs:
            raise ValueError('join requires inputs')
        self.inputs = list(inputs)
        self.budget = budget
        self.max_items = max(1, int(max_items))
        self.queues = {name: [] for name in self.inputs}
        self.condition = threading.Condition()
        self.closed = False

    def put(self, port: str, key: str, block: OwnedBlock) -> None:
        if port not in self.queues:
            raise KeyError(f'Unknown join input {port}')
        with self.condition:
            queue = self.queues[port]
            if len(queue) >= self.max_items:
                raise JoinOverflow(f'Join input {port} exceeded its bounded buffer')
            queue.append((key, block))
            self.condition.notify_all()

    def take(self, key: str, *, timeout: float = 1.0) -> dict[str, OwnedBlock]:
        deadline = time.monotonic() + timeout
        with self.condition:
            while True:
                found = {}
                for port in self.inputs:
                    match = next((item for item in self.queues[port] if item[0] == key), None)
                    if match is None:
                        break
                    found[port] = match[1]
                if len(found) == len(self.inputs):
                    for port in self.inputs:
                        queue = self.queues[port]
                        self.queues[port] = [item for item in queue if item[0] != key]
                    return found
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError(f'Join input missing for key {key!r}')
                self.condition.wait(min(remaining, 0.25))

    def close(self):
        with self.condition:
            self.closed = True
            self.condition.notify_all()

    def stats(self) -> dict:
        with self.condition:
            return {'queues': {name: len(queue) for name, queue in self.queues.items()},
                    'max_items': self.max_items, 'closed': self.closed}


class SyntheticAdapter:
    """Test/contract adapter: produces owned copies, never borrowed views."""

    def __init__(self, chunks, *, block_bytes=None, metadata=b'{"format":"synthetic"}'):
        self.chunks = chunks
        self.block_bytes = block_bytes
        self.metadata = metadata

    def produce(self, channel: Channel, *, blocks=1):
        for sequence, value in enumerate(self.chunks):
            if not isinstance(value, (bytes, bytearray, memoryview)):
                raise TypeError('synthetic chunks must be bytes-like views')
            data = bytes(value)  # ownership copy before enqueueing
            credit = channel.reserve(len(data) + len(self.metadata))
            block = OwnedBlock(block_id=uuid.uuid4().hex, sequence=sequence, generation=1,
                               data=data, metadata=self.metadata)
            channel.publish(credit, block)
        channel.close()


def admit_group(resources, *, requests: list[tuple[str, object, dict]], owner: dict) -> list[dict]:
    """All-or-nothing admission for a streaming producer/consumer group."""
    with resources.store.transaction():
        leases = []
        for attempt_id, requirement, _ in requests:
            leases.append(resources.admit(attempt_id=attempt_id, request=requirement, owner=owner))
        return leases
