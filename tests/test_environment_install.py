"""Isolated environment planning, state and safety checks."""
import json
import sys
import threading
from pathlib import Path

import pytest

from operon import environment_install, environments


def manifest(root: Path, entries: dict) -> Path:
    (root / 'operon').mkdir(parents=True, exist_ok=True)
    (root / 'operon' / 'environments.json').write_text(
        json.dumps({'version': 1, 'environments': entries}), encoding='utf-8')
    return root


def test_plan_marks_missing_and_used_by(tmp_path):
    source = manifest(tmp_path / 'source', {'demo': {'python': '3.11', 'imports': []}})
    plan = environment_install.plan(tmp_path / 'external', [
        {'id': 'alpha', 'resources': {'environment': 'demo'}},
        {'id': 'beta'},
    ], source=source)
    assert plan['demo']['status'] == 'missing'
    assert plan['demo']['used_by'] == ['alpha']
    assert plan['demo']['interpreter'] == ''
    assert plan['demo']['error'] == ''


def test_state_ready_and_stale_from_receipt(tmp_path):
    source = manifest(tmp_path / 'source', {'demo': {'python': '3.11', 'imports': ['json']}})
    root = tmp_path / 'external'
    entry = environments.load(source)['demo']
    python = root / 'demo' / 'bin' / 'python'
    python.parent.mkdir(parents=True)
    python.write_text('#!/bin/sh\n', encoding='utf-8')
    python.chmod(0o755)
    assert environment_install.state('demo', root, source)['status'] == 'stale'
    (root / 'demo' / 'receipt.json').write_text(
        json.dumps({'spec_sha256': environment_install.spec_sha256(entry)}), encoding='utf-8')
    ready = environment_install.state('demo', root, source)
    assert ready['status'] == 'ready'
    assert ready['interpreter'] == str(python)


def test_prepare_creates_shared_venv_environment(tmp_path):
    source = manifest(tmp_path / 'source', {'demo': {'python': '3.11', 'imports': [], 'venv_shared': True}})
    runtime = environment_install.prepare('demo', tmp_path / 'external', source)
    assert runtime['status'] == 'ready'
    assert Path(runtime['interpreter']).is_file()
    assert (tmp_path / 'external' / 'demo' / 'receipt.json').is_file()
    assert environment_install.plan(tmp_path / 'external', source=source)['demo']['status'] == 'ready'


def test_prepare_rejects_unsafe_sources_before_writing(tmp_path):
    source = manifest(tmp_path / 'source', {
        'demo': {'python': '3.11', 'requirements': ['file:///etc/passwd']}})
    root = tmp_path / 'external'
    with pytest.raises(ValueError, match='unsupported package source'):
        environment_install.prepare('demo', root, source)
    assert not (root / 'demo').exists()


def test_prepare_rejects_absolute_python(tmp_path):
    source = manifest(tmp_path / 'source', {'demo': {'python': '../3.11'}})
    with pytest.raises(ValueError, match='invalid Python version'):
        environment_install.prepare('demo', tmp_path / 'external', source)


def test_unknown_environment_is_reported(tmp_path):
    source = manifest(tmp_path / 'source', {})
    with pytest.raises(ValueError, match='unknown isolated environment'):
        environment_install.state('nope', tmp_path / 'external', source)


def test_control_reports_cancellation():
    stop = threading.Event()
    control = environment_install._Control(stop)
    control.check()
    assert control.stopped is False
    stop.set()
    assert control.stopped is True
    with pytest.raises(environment_install.Cancelled):
        control.check()


def test_run_kills_the_child_when_cancelled():
    control = environment_install._Control()
    timer = threading.Timer(0.5, control.stop)
    timer.start()
    try:
        with pytest.raises(environment_install.Cancelled):
            environment_install._run(
                [sys.executable, '-c', 'import time; time.sleep(30)'], log=None, control=control)
    finally:
        timer.cancel()


def test_run_reports_cancellation_even_when_the_kill_lands_first():
    control = environment_install._Control()
    timer = threading.Timer(0.2, control.stop)
    timer.start()
    try:
        with pytest.raises(environment_install.Cancelled):
            environment_install._run(
                [sys.executable, '-c', 'import time; time.sleep(30)'], log=None, control=control)
    finally:
        timer.cancel()


def test_prepare_stops_early_without_recording_a_failure(tmp_path):
    source = manifest(tmp_path / 'source', {'demo': {'python': '3.11', 'imports': []}})
    control = environment_install._Control()
    control.stop()
    with pytest.raises(environment_install.Cancelled):
        environment_install.prepare('demo', tmp_path / 'external', source, control=control)
    progress = environment_install.read_progress('demo', tmp_path / 'external')
    assert progress['phase'] == 'cancelled'
    assert 'error' not in progress
    assert not (tmp_path / 'external' / '.operon-environment-errors' / 'demo.json').exists()

def test_mark_cancelled_reports_a_stalled_preparation(tmp_path, monkeypatch):
    monkeypatch.setattr(environment_install.environments, 'root', lambda: tmp_path)
    environment_install._write_progress('openfold', tmp_path,
                                        {'name': 'openfold', 'phase': 'creating', 'detail': 'download'})
    environment_install.mark_cancelled('openfold')
    progress = environment_install.read_progress('openfold')
    assert progress['phase'] == 'cancelled'
    assert progress['detail'] == 'cancelled by user'
    environment_install.mark_cancelled('openfold')
    assert environment_install.read_progress('openfold')['phase'] == 'cancelled'


def test_progress_writes_from_several_threads_do_not_collide(tmp_path, monkeypatch):
    monkeypatch.setattr(environment_install.environments, 'root', lambda: tmp_path)
    errors = []

    def worker(index):
        try:
            for step in range(20):
                environment_install._write_progress(
                    'openfold', None,
                    {'name': 'openfold', 'phase': 'installing', 'step': step, 'writer': index},
                )
        except BaseException as error:  # noqa: BLE001 - the test reports what escaped
            errors.append(error)

    threads = [threading.Thread(target=worker, args=(index,)) for index in range(6)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert errors == []
    recorded = environment_install.read_progress('openfold', None)
    assert recorded['name'] == 'openfold'
    assert recorded['phase'] == 'installing'


def test_a_worker_failure_does_not_overwrite_a_recorded_cancellation(tmp_path, monkeypatch):
    monkeypatch.setattr(environment_install.environments, 'root', lambda: tmp_path)
    environment_install._write_progress('openfold', None, {'name': 'openfold', 'phase': 'installing'})
    environment_install.mark_cancelled('openfold', None)
    environment_install._write_progress('openfold', None, {'name': 'openfold', 'phase': 'failed', 'error': 'boom'})
    assert environment_install.read_progress('openfold', None)['phase'] == 'cancelled'
