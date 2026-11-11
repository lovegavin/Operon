"""Bounded streaming channels: credits, fan-out, join, cancellation and group admission."""
from concurrent.futures import ThreadPoolExecutor
import threading
import time

import pytest

from operon.engine.channels import (
    BoundedJoin, Channel, ChannelBudget, SyntheticAdapter, admit_group,
)
from operon.engine.contracts import InfeasibleResourcesError, PoolSpec, ResourceRequest
from operon.engine.resources import PoolResources
from operon.engine.state import StateStore


def test_producer_blocks_at_the_byte_ceiling_and_consumer_ack_releases(tmp_path):
    budget = ChannelBudget(max_bytes=8, max_blocks=2)
    channel = Channel(budget, name='pipe')
    adapter = SyntheticAdapter([b'a' * 4, b'a' * 4, b'a' * 4], metadata=b'')
    produced = []

    def produce():
        for chunk in adapter.chunks:
            credit = channel.reserve(len(chunk) + len(adapter.metadata))
            from operon.engine.channels import OwnedBlock
            block = OwnedBlock(block_id=f'b{len(produced)}', sequence=len(produced), generation=1,
                               data=chunk, metadata=adapter.metadata)
            channel.publish(credit, block)
            produced.append(block)

    with ThreadPoolExecutor(max_workers=1) as pool:
        task = pool.submit(produce)
        first = channel.receive(timeout=2)
        second = channel.receive(timeout=2)
        # Two blocks are buffered/in flight; the third publish is blocked by
        # credits, so no data exists beyond the configured bound.
        time.sleep(0.2)
        assert len(produced) == 2, len(produced)
        assert budget.stats()['charged_bytes'] == 8
        channel.ack(first)
        time.sleep(0.2)
        assert len(produced) == 3
        third = channel.receive(timeout=1)
        channel.ack(second)
        channel.ack(third)
        task.result(timeout=2)
    assert budget.charged_bytes == 0 and budget.released > 0


def test_credit_is_reserved_before_value_materialization():
    budget = ChannelBudget(max_bytes=4, max_blocks=1)
    channel = Channel(budget, name='pipe')
    adapter = SyntheticAdapter([b'abcd'], metadata=b'')
    materialized = []

    def allocate(data):
        materialized.append(bytes(data))
        return materialized[-1]

    credit = channel.reserve(len(b'abcd') + len(adapter.metadata))
    assert not materialized
    data = allocate(b'abcd')
    from operon.engine.channels import OwnedBlock
    channel.publish(credit, OwnedBlock('b1', 0, 1, data, adapter.metadata))
    assert materialized == [b'abcd']


def test_fanout_returns_physical_credits_only_after_every_consumer_acks():
    budget = ChannelBudget(max_bytes=8, max_blocks=2)
    first = Channel(budget, name='branch-a')
    second = Channel(budget, name='branch-b')
    producer = Channel(budget, name='producer')
    from operon.engine.channels import OwnedBlock
    block = OwnedBlock('shared', 0, 1, b'data', b'meta')
    credit = producer.reserve(block.charged_bytes)
    producer.publish(credit, block, subscribers=[first, second])
    assert budget.charged_bytes == block.charged_bytes
    one = first.receive(timeout=1)
    first.ack(one)
    assert budget.charged_bytes == block.charged_bytes, 'one branch still owns the block'
    two = second.receive(timeout=1)
    second.ack(two)
    assert budget.charged_bytes == 0


def test_duplicate_or_delayed_ack_never_double_releases():
    budget = ChannelBudget(max_bytes=4, max_blocks=1)
    channel = Channel(budget, name='pipe')
    credit = channel.reserve(1)
    from operon.engine.channels import OwnedBlock
    block = OwnedBlock('b', 0, 1, b'x')
    channel.publish(credit, block)
    received = channel.receive(timeout=1)
    channel.ack(received)
    channel.ack((received.block_id, received.generation))
    channel.ack((received.block_id, received.generation))
    assert budget.charged_bytes == 0


def test_join_waits_with_a_deadline_and_enforces_bounded_buffers():
    budget = ChannelBudget(max_bytes=64, max_blocks=8)
    join = BoundedJoin(['left', 'right'], budget, max_items=2)
    from operon.engine.channels import OwnedBlock
    join.put('left', 'k1', OwnedBlock('l1', 0, 1, b'a'))
    with pytest.raises(TimeoutError):
        join.take('k1', timeout=0.1)
    join.put('right', 'k1', OwnedBlock('r1', 0, 1, b'b'))
    found = join.take('k1', timeout=0.2)
    assert set(found) == {'left', 'right'}
    join.put('left', 'x', OwnedBlock('l2', 1, 1, b'a'))
    join.put('left', 'y', OwnedBlock('l3', 2, 1, b'a'))
    with pytest.raises(Exception):
        join.put('left', 'z', OwnedBlock('l4', 3, 1, b'a'))


def test_closed_channel_releases_reservations_and_fails_fast():
    budget = ChannelBudget(max_bytes=4, max_blocks=1)
    channel = Channel(budget, name='pipe')
    channel.reserve(4)
    channel.close('consumer failed')
    with pytest.raises(Exception):
        channel.receive(timeout=0.1)
    budget.close()
    with pytest.raises(Exception):
        budget.reserve(1)


def test_borrowed_views_are_copied_before_enqueue():
    budget = ChannelBudget(max_bytes=32, max_blocks=4)
    channel = Channel(budget, name='pipe')
    buffer = bytearray(b'abcd')
    adapter = SyntheticAdapter([bytes(buffer)], metadata=b'')
    adapter.produce(channel)
    buffer[:] = b'zzzz'
    block = channel.receive(timeout=1)
    assert block.data == b'abcd'
    channel.ack(block)


def test_group_admission_is_all_or_nothing(tmp_path):
    store = StateStore(tmp_path / 'state.sqlite3')
    spec = PoolSpec('pool-group', 'tester', 'host', 100, 0, 4)
    store.ensure_pool(spec)
    store.register_workspace('ws', 'pool-group', str(tmp_path), 'tester')
    store.claim_submission(principal='tester', key='k', digest='d', operation='run',
                           run={'id': 'run-1', 'workspace_id': 'ws', 'project': 'p',
                                'plan_key': 'p', 'plan_digest': 'd', 'plan': {}},
                           units=[{'unit_id': 'p', 'node_ids': ['p'], 'depends_on': [],
                                   'target': {'kind': 'local'},
                                   'requirement': {'managed_budget_bytes': 50,
                                                   'process_reservation_bytes': 50, 'cpu_threads': 1}},
                                  {'unit_id': 'c', 'node_ids': ['c'], 'depends_on': ['p'],
                                   'target': {'kind': 'local'},
                                   'requirement': {'managed_budget_bytes': 60,
                                                   'process_reservation_bytes': 60, 'cpu_threads': 1}}])
    units = {unit['local_id']: unit for unit in store.units('run-1')}
    attempts = {key: store.create_attempt(unit['id'], epoch=1) for key, unit in units.items()}
    resources = PoolResources(store, *store.pool('pool-group'))
    with pytest.raises(InfeasibleResourcesError):
        admit_group(resources, requests=[
            (attempts['p']['id'], ResourceRequest(managed_budget_bytes=50,
                                                  process_reservation_bytes=50, cpu_threads=1), {}),
            (attempts['c']['id'], ResourceRequest(managed_budget_bytes=60,
                                                  process_reservation_bytes=60, cpu_threads=1), {}),
        ], owner={})
    assert store.lease_details('pool-group') == []
    leases = admit_group(resources, requests=[
        (attempts['p']['id'], ResourceRequest(managed_budget_bytes=40,
                                              process_reservation_bytes=40, cpu_threads=1), {}),
        (attempts['c']['id'], ResourceRequest(managed_budget_bytes=40,
                                              process_reservation_bytes=40, cpu_threads=1), {}),
    ], owner={})
    assert len(leases) == 2 and resources.snapshot().used.ram == 80
