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


def test_state_ready_and_stale_from_receipt(tmp_path, monkeypatch):
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
    monkeypatch.setattr(environment_install, 'dependency_status', lambda entry, location: (1, 1, []))
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


def test_cpu_fallback_drops_cuda_torch_pins() -> None:
    from operon.environment_install import _cpu_entry

    entry = {'requirements': ['torch==2.6.0', 'esm==3.2.0', 'torchvision==0.21.0'],
             'pip_wheels': ['torchaudio==2.6.0'], 'torch_cuda': True}
    updated = _cpu_entry(entry)
    assert updated['torch_cpu'] is True
    assert updated['torch_cuda'] is False
    assert updated['requirements'] == ['esm==3.2.0']
    assert updated['pip_wheels'] == []
    assert entry['requirements'][0] == 'torch==2.6.0'


def test_mark_cancelled_reports_terminal_state(tmp_path: Path) -> None:
    environment_install._write_progress('core', tmp_path, {'phase': 'ready', 'detail': 'done', 'bytes': 10})
    assert environment_install.mark_cancelled('core', tmp_path) is False
    assert environment_install.read_progress('core', tmp_path)['phase'] == 'ready'

    environment_install._write_progress('core', tmp_path, {'phase': 'installing', 'detail': 'pip'})
    assert environment_install.mark_cancelled('core', tmp_path) is True
    assert environment_install.read_progress('core', tmp_path)['phase'] == 'cancelled'


def test_track_line_keeps_download_bytes_ahead_of_disk_usage() -> None:
    progress: dict = {}
    environment_install._track_line(
        'Downloading torch-2.15.0+cpu-cp311-cp311-win_amd64.whl (201.4 MB)', progress)
    assert progress['fetched'] == int(201.4 * 1024 ** 2)
    assert progress['bytes'] == progress['fetched']
    assert progress['stage'] == 'downloading'


def test_run_waits_for_the_first_line_before_the_stall_limit(tmp_path, monkeypatch):
    monkeypatch.setattr(environment_install, 'STARTUP_SECONDS', 10.0)
    code = 'import time; time.sleep(1.2); print("done")'
    output = environment_install._run([sys.executable, '-c', code], log=lambda line: None,
                                      timeout=30, stall=0.4)
    assert 'done' in output


def test_run_aborts_when_the_command_never_starts_talking(tmp_path, monkeypatch):
    monkeypatch.setattr(environment_install, 'STARTUP_SECONDS', 0.6)
    code = 'import time; time.sleep(3)'
    with pytest.raises(RuntimeError, match='printed nothing'):
        environment_install._run([sys.executable, '-c', code], log=lambda line: None,
                                 timeout=30, stall=0.4)


def test_probe_announces_each_import_and_gets_the_full_timeout_as_grace(tmp_path, monkeypatch):
    from operon import environment_install

    calls = []

    def fake_run(argv, **kwargs):
        calls.append((argv, kwargs))
        return ''

    monkeypatch.setattr(environment_install, '_run', fake_run)
    monkeypatch.setattr(environment_install, '_probe_environment', lambda python: {'PATH': ''})
    python = tmp_path / 'bin' / 'python'
    python.parent.mkdir(parents=True)
    python.write_text('', encoding='utf-8')

    script = environment_install._probe(
        python, {'imports': ['json', 'math']}, lambda line: None)

    assert script == 'import json;import math'
    argv, kwargs = calls[0]
    code = argv[-1]
    assert code.count('sys.stdout.write') == 2
    assert code.index('sys.stdout.write("import json') < code.index('import json')
    assert code.index('sys.stdout.write("import math') < code.index('import math')
    assert kwargs['startup'] == kwargs['timeout'] == 600


def test_pip_runs_unbuffered_so_a_quiet_resolve_is_not_a_stall(tmp_path, monkeypatch):
    calls = []

    def fake_run(argv, **kwargs):
        calls.append((argv, kwargs))
        return ''

    monkeypatch.setattr(environment_install, '_run', fake_run)
    monkeypatch.setattr(environment_install, '_python', lambda staging: Path(sys.executable))
    monkeypatch.setattr(environment_install, '_pip_prefix', lambda staging: [])
    environment_install._install({'requirements': ['demo==1']}, tmp_path / 'staging',
                                 lambda line: None)

    assert calls
    for argv, kwargs in calls:
        assert 'pip' in argv
        assert kwargs['env']['PYTHONUNBUFFERED'] == '1'
        assert kwargs['startup'] == environment_install.PIP_STARTUP_SECONDS

def test_prepare_keeps_an_unsupported_platform_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(environment_install, 'PLATFORM', 'windows')
    source = manifest(tmp_path / 'source', {'gated': {'python': '3.11', 'imports': [],
                                                     'platforms': ['linux'], 'platform_note': 'linux only'}})
    root = tmp_path / 'external'
    with pytest.raises(RuntimeError, match='linux'):
        environment_install.prepare('gated', root, source)
    assert environment_install.state('gated', root, source)['status'] == 'missing'
    assert (root / '.operon-environment-errors' / 'gated.json').is_file()

def test_repair_rewrites_stale_staging_shebangs(tmp_path, monkeypatch):
    from operon import environment_install

    root = tmp_path / 'environments'
    target = root / 'demo'
    nested = target / 'bin' / 'nested'
    nested.mkdir(parents=True)
    top = target / 'bin' / 'tool'
    deep = nested / 'deep_tool'
    top.write_text('#!/tmp/.staging-demo-abcd1234/bin/python\nprint(1)\n', encoding='utf-8')
    deep.write_text('#!/tmp/.staging-demo-abcd1234/bin/python3\nprint(2)\n', encoding='utf-8')

    monkeypatch.setattr(environment_install.environments, 'root', lambda: root)
    result = environment_install.repair('demo')

    assert result['rewritten'] == 2
    expected = f'#!{target}/bin/python'
    assert top.read_text(encoding='utf-8').splitlines()[0] == expected
    assert deep.read_text(encoding='utf-8').splitlines()[0] == f'#!{target}/bin/python3'
    # a second run is a no-op
    assert environment_install.repair('demo')['rewritten'] == 0


def test_repair_rejects_an_unknown_environment(tmp_path, monkeypatch):
    from operon import environment_install

    monkeypatch.setattr(environment_install.environments, 'root', lambda: tmp_path)
    try:
        environment_install.repair('missing')
    except ValueError as error:
        assert 'not installed' in str(error)
    else:  # pragma: no cover - defensive
        raise AssertionError('repair should reject an unknown environment')
