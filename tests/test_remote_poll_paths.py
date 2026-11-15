from pathlib import Path
from operon.remote.server import _event_name


def test_poll_name_for_launcher_event(tmp_path):
    jobs = tmp_path / '.studio' / 'jobs'
    path = jobs / 'req-1' / 'launcher.events.jsonl'
    path.parent.mkdir(parents=True)
    path.write_text('', encoding='utf-8')
    assert _event_name(path, 'req-1', jobs, {}) == 'launcher.events.jsonl'


def test_poll_name_for_task_results_run_event(tmp_path):
    jobs = tmp_path / '.studio' / 'jobs'
    output = tmp_path / 'task1' / 'results' / 'req-1'
    path = output / 'runs' / '20260101T000000-abcd' / 'events.jsonl'
    path.parent.mkdir(parents=True)
    path.write_text('', encoding='utf-8')
    assert _event_name(path, 'req-1', jobs, {'output_dir': str(output)}) == 'results/runs/20260101T000000-abcd/events.jsonl'


def test_poll_name_for_external_event_is_stable(tmp_path):
    path = tmp_path / 'elsewhere' / 'events.jsonl'
    path.parent.mkdir(parents=True)
    path.write_text('', encoding='utf-8')
    first = _event_name(path, 'req-1', tmp_path / '.studio' / 'jobs', {})
    second = _event_name(path, 'req-1', tmp_path / '.studio' / 'jobs', {})
    assert first == second
    assert first.startswith('external/')