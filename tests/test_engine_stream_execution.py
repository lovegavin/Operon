"""Internal streaming adapter wired through a real JobService worker process.

The adapter is test-only.  It uses the real CsvReader and real DescribeStep
streaming implementation plus the product bounded channels; it is not a claim
that a production Reader advertises streaming.
"""
import json
import os
from pathlib import Path
import time

import pytest

from biopipe.pool_service import PoolService
from src.web.models import Graph

ROOT = Path(__file__).resolve().parents[1]
MIB = 1024 ** 2


def wait_until(check, timeout=40):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        value = check()
        if value:
            return value
        time.sleep(.05)
    pytest.fail('Timed out waiting for streaming worker')


def test_bounded_channels_run_inside_a_real_worker(tmp_path, monkeypatch):
    workspace = tmp_path / 'workspace'; workspace.mkdir()
    source = workspace / 'input.csv'
    source.write_text('a,b,c,d\n1,2,4,8\n2,5,7,3\n3,8,1,6\n7,2,9,4\n4,6,3,5\n8,1,6,2\n',
                      encoding='utf-8')
    code = tmp_path / 'code'; (code / 'scripts').mkdir(parents=True)
    (code / 'scripts/run.py').write_text('''import json, os, sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
sys.path.insert(0, os.environ['BIOPIPE_ACCEPTANCE_ROOT'])
import numpy as np
from biopipe.engine.channels import ChannelBudget, Channel, OwnedBlock, ChannelClosed
from src.reader.readers.csv_reader import CsvReader
from src.task.step.steps.describe import DescribeStep
import yaml

task = Path(sys.argv[1]); output = task / 'output'; output.mkdir(parents=True, exist_ok=True)
form = CsvReader().read(Path(os.environ['BIOPIPE_STREAM_INPUT']), ['sample', 'feature'],
                        {'sample': 'auto', 'feature': 'builtin'})
data = form.data
chunks = np.array_split(data, 6)
budget = ChannelBudget(max_bytes=max(chunk.nbytes for chunk in chunks) + 1, max_blocks=2)
producer = Channel(budget, name='producer')
left = Channel(budget, name='left'); right = Channel(budget, name='right')
def produce():
    for index, chunk in enumerate(chunks):
        payload = np.ascontiguousarray(chunk).tobytes()
        credit = producer.reserve(len(payload))
        producer.publish(credit, OwnedBlock(f'b{index}', index, 1, payload), subscribers=[left, right])
    left.close(); right.close()
def consume(channel):
    step = DescribeStep()
    def blocks():
        while True:
            try:
                block = channel.receive(timeout=10)
            except ChannelClosed:
                return
            try:
                yield np.frombuffer(block.data, dtype=data.dtype)
            finally:
                channel.ack(block)
    step.run_stream(None, {'metadata': {'dims': list(form.dims), 'labels': form.labels,
                                        'info': form.info, 'axis_info': form.axis_info},
                            'shape': list(data.shape), 'chunks': blocks()})
    return step.export(None)
with ThreadPoolExecutor(max_workers=3) as pool:
    p = pool.submit(produce); a = pool.submit(consume, left); b = pool.submit(consume, right)
    p.result(timeout=20); left_result = a.result(timeout=20); right_result = b.result(timeout=20)
summary = {'status': 'complete', 'branches_equal':
           abs(left_result['global']['mean'] - right_result['global']['mean']) <= 1e-12,
           'mean': left_result['global']['mean'], 'n_valid': left_result['global']['n_valid']}
(output / 'run_summary.json').write_text(json.dumps(summary))
''', encoding='utf-8')
    monkeypatch.setenv('BIOPIPE_STREAM_INPUT', str(source))
    monkeypatch.setenv('BIOPIPE_ACCEPTANCE_ROOT', str(ROOT))
    monkeypatch.setenv('PYTHONPATH', str(ROOT) + os.pathsep + os.environ.get('PYTHONPATH', ''))
    graph = Graph.model_validate({
        'schema_version': 2, 'name': 'stream adapter', 'base_dir': str(workspace),
        'memory': {'enabled': True, 'auto_spill': True, 'budget_mb': 16, 'process_limit_mb': 64},
        'runtime': {'execution': {'mode': 'manual', 'max_parallel_tasks': 1}},
        'nodes': [{'id': 'input', 'kind': 'source', 'position': {'x': 0, 'y': 0},
                   'source': {'path': 'input.csv', 'dims': ['sample', 'feature'],
                              'labels': {'sample': 'auto', 'feature': 'builtin'}}},
                  {'id': 'summary', 'kind': 'operator', 'operator': 'describe',
                   'position': {'x': 1, 'y': 0}, 'params': {}}],
        'edges': [{'id': 'e1', 'source': 'input', 'target': 'summary'}]})
    pool = PoolService(root=tmp_path / 'pool', admission_dir=tmp_path / 'admission',
                       workspaces=[{'root': workspace, 'principal': 'alice'}],
                       code_root=code, capacity_bytes=256 * MIB, cpu_threads=2)
    try:
        job = pool.launch(workspace, graph, request_id='stream-adapter', principal='alice')
        wait_until(lambda: pool.details(workspace, job['id'], principal='alice')['status']
                   in ('complete', 'failed'))
        result = pool.details(workspace, job['id'], principal='alice')
        assert result['status'] == 'complete', result.get('error') or result.get('console')
        summary = json.loads((pool.resolve(workspace).jobs_dir / job['id'] /
                              'output/run_summary.json').read_text())
        assert summary['status'] == 'complete' and summary['branches_equal'] is True
        assert summary['n_valid'] == 24
        wait_until(lambda: pool.details(workspace, job['id'], principal='alice')['lifecycle']
                   ['artifact_committed'])
        assert pool.details(workspace, job['id'], principal='alice')['lifecycle']['tree_exited']
    finally:
        pool.shutdown()
