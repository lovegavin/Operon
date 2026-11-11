"""ExecutionService resume: completed units are not re-executed on retry."""
from types import SimpleNamespace
import threading

from src.web.execution import ExecutionService


class FakeService:
    def __init__(self, directory):
        self.directory = directory
        self.root = directory

    def history(self):
        return []


def make_job(directory, key='exec-' + 'a' * 32):
    service = FakeService(directory)
    executions = ExecutionService(service)
    folder = executions.path(key)
    folder.mkdir(parents=True)
    units = [
        {'id': 'stage_1', 'node_ids': ['a'], 'target': {'kind': 'local'}, 'depends_on': []},
        {'id': 'stage_2', 'node_ids': ['b'], 'target': {'kind': 'local'}, 'depends_on': ['stage_1']},
    ]
    job = {'id': key, 'name': 'resume', 'status': 'preparing', 'created_at': 'now',
           'finished_at': None, 'error': None,
           'graph': {'schema_version': 2, 'name': 'resume', 'nodes': [], 'edges': []},
           'execution_plan': {'units': units},
           'owner': executions.owner, 'children': [], 'completed_units': ['stage_1'],
           'receipts': {}, 'logs_complete': False, 'order': ['a', 'b'],
           'progress': {'phase': 'preparing', 'completed': 1, 'total': 2}}
    import json
    (folder / 'job.json').write_text(json.dumps(job), encoding='utf-8')
    executions.cancels[key] = threading.Event()
    executions.stopping.clear()
    return executions, key


def test_retry_skips_completed_units_and_runs_only_the_remaining_node(tmp_path):
    executions, key = make_job(tmp_path)
    calls = []
    failed = {'done': False}

    def stage(key_value, unit, graph, plan):
        calls.append(unit['id'])
        if unit['id'] == 'stage_2' and not failed['done']:
            failed['done'] = True
            raise RuntimeError('injected stage failure')
        executions._update(key_value, completed_units=sorted(set(
            executions._read(key_value)['completed_units']) | {unit['id']}))

    executions._stage = stage
    executions._run(key)
    assert calls == ['stage_2']
    assert executions._read(key)['status'] == 'failed'
    # Retry the same durable record: stage_1 is already committed and must not
    # run again; stage_2 runs once and completes.
    executions._update(key, status='preparing', error=None, logs_complete=False)
    executions.cancels[key].clear()
    calls.clear()
    executions._run(key)
    assert calls == ['stage_2']
    record = executions._read(key)
    assert record['status'] == 'complete'
    assert record['completed_units'] == ['stage_1', 'stage_2']
