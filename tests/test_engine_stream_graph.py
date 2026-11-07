"""P13: real Reader + streaming numeric operator with branch, join and backpressure."""
from concurrent.futures import ThreadPoolExecutor
import threading
import time
from types import SimpleNamespace

import numpy as np
import pytest

from biopipe.engine.channels import Channel, ChannelBudget, ChannelClosed, OwnedBlock
from src.reader.readers.csv_reader import CsvReader
from src.task.step.steps.describe import DescribeStep


def make_table(tmp_path, rows=600, cols=12):
    rng = np.random.default_rng(11)
    data = rng.normal(size=(rows, cols))
    data[3, 2] = np.nan
    path = tmp_path / 'table.csv'
    header = ','.join(f'c{i}' for i in range(cols))
    body = '\n'.join(','.join('' if np.isnan(v) else f'{v:.6f}' for v in row) for row in data)
    path.write_text(header + '\n' + body + '\n', encoding='utf-8')
    form = CsvReader().read(path, ['sample', 'feature'],
                            {'sample': 'auto', 'feature': 'builtin'})
    return form, data


def stream_metadata(form):
    return {'dims': list(form.dims), 'labels': form.labels, 'info': form.info,
            'axis_info': form.axis_info}


def channel_chunks(channel, dtype, timeout=5):
    while True:
        try:
            block = channel.receive(timeout=timeout)
        except ChannelClosed:
            return
        try:
            yield np.frombuffer(block.data, dtype=dtype)
        finally:
            channel.ack(block)


def stream_describe(channel, form, dtype):
    step = DescribeStep()
    step.run_stream(SimpleNamespace(), {'metadata': stream_metadata(form),
                                        'shape': list(form.data.shape),
                                        'chunks': channel_chunks(channel, dtype)})
    return step.export(None)


def test_two_describe_branches_fanout_join_and_serial_equivalence(tmp_path):
    form, _ = make_table(tmp_path)
    dtype = form.data.dtype
    chunks = np.array_split(form.data, 12)
    budget = ChannelBudget(max_bytes=8192, max_blocks=4)
    producer = Channel(budget, name='producer')
    left = Channel(budget, name='left')
    right = Channel(budget, name='right')
    produced = []

    def produce():
        for index, chunk in enumerate(chunks):
            data = np.ascontiguousarray(chunk).tobytes()
            credit = producer.reserve(len(data))
            production = OwnedBlock(f'b{index}', index, 1, data)
            producer.publish(credit, production, subscribers=[left, right])
            produced.append(production)
        left.close(); right.close()

    with ThreadPoolExecutor(max_workers=3) as pool:
        producer_task = pool.submit(produce)
        left_task = pool.submit(stream_describe, left, form, dtype)
        right_task = pool.submit(stream_describe, right, form, dtype)
        left_result = left_task.result(timeout=30)
        right_result = right_task.result(timeout=30)
        producer_task.result(timeout=30)
    serial = DescribeStep(); serial.run(None, [form]); serial_result = serial.export(None)
    for branch in (left_result, right_result):
        assert branch['shape'] == serial_result['shape']
        assert branch['labels'] == serial_result['labels']
        assert branch['global']['n_missing'] == serial_result['global']['n_missing']
        assert branch['global']['mean'] == pytest.approx(serial_result['global']['mean'], rel=1e-12, abs=1e-12)
        assert branch['global']['std'] == pytest.approx(serial_result['global']['std'], rel=1e-12, abs=1e-12)
    assert budget.stats()['peak_bytes'] <= budget.max_bytes
    assert budget.charged_bytes == 0
    assert len(produced) == len(chunks)


def test_slow_required_branch_throttles_the_producer(tmp_path):
    form, _ = make_table(tmp_path)
    dtype = form.data.dtype
    chunks = np.array_split(form.data, 8)
    budget = ChannelBudget(max_bytes=16000, max_blocks=2)
    producer = Channel(budget, name='producer')
    fast = Channel(budget, name='fast')
    slow = Channel(budget, name='slow')
    produced = []

    def produce():
        for index, chunk in enumerate(chunks):
            data = np.ascontiguousarray(chunk).tobytes()
            credit = producer.reserve(len(data), timeout=10)
            block = OwnedBlock(f's{index}', index, 1, data)
            producer.publish(credit, block, subscribers=[fast, slow])
            produced.append(block)
        fast.close(); slow.close()

    def consume(channel, delay):
        results = []
        while True:
            try:
                block = channel.receive(timeout=8)
            except Exception:
                return results
            time.sleep(delay)
            results.append(len(block.data))
            channel.ack(block)

    with ThreadPoolExecutor(max_workers=3) as pool:
        producer_task = pool.submit(produce)
        fast_task = pool.submit(consume, fast, 0.0)
        slow_task = pool.submit(consume, slow, 0.05)
        fast_task.result(timeout=30); slow_task.result(timeout=30); producer_task.result(timeout=30)
    # At least one branch had to consume before all blocks existed; the peak is
    # bounded and the producer did not materialize everything immediately.
    assert budget.stats()['peak_blocks'] <= 2
    assert budget.stats()['peak_bytes'] <= budget.max_bytes
    assert budget.charged_bytes == 0


def test_failed_consumer_releases_references_and_stops_producer():
    budget = ChannelBudget(max_bytes=16, max_blocks=2)
    channel = Channel(budget, name='pipe')
    entered = threading.Event()
    failures = []

    def produce():
        for index in range(100):
            try:
                credit = channel.reserve(8, timeout=5)
            except Exception as exc:
                failures.append(exc)
                return
            channel.publish(credit, OwnedBlock(f'f{index}', index, 1, b'x' * 8))
        channel.close()

    def consume():
        block = channel.receive(timeout=2)
        entered.set()
        channel.abort('injected consumer failure')
        # A failed streaming group must stop the producer, not merely drain
        # the failed consumer's queue.
        budget.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        producer_task = pool.submit(produce)
        consumer_task = pool.submit(consume)
        consumer_task.result(timeout=5)
        producer_task.result(timeout=5)
    assert entered.is_set()
    assert failures and failures[0].code == 'channel_closed'
    assert budget.charged_bytes == 0


def test_borrowed_numpy_buffer_is_copied_before_publish():
    budget = ChannelBudget(max_bytes=32, max_blocks=2)
    channel = Channel(budget, name='pipe')
    source = np.zeros(2, dtype='float64')
    for index in range(2):
        source[:] = index
        data = source.tobytes()  # explicit ownership copy
        credit = channel.reserve(len(data))
        channel.publish(credit, OwnedBlock(f'b{index}', index, 1, data))
    first = np.frombuffer(channel.receive(timeout=1).data, dtype='float64')
    second = np.frombuffer(channel.receive(timeout=1).data, dtype='float64')
    assert first.tolist() == [0.0, 0.0]
    assert second.tolist() == [1.0, 1.0]
