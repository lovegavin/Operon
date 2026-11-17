"""Forced worker exit must not strand scoped cwd aliases or touch user data."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from types import SimpleNamespace

import pytest

from operon.bytecode import io_path
from operon.process_paths import ProcessDirectory
from operon.process_path_scopes import prepare_scope, release_scope, SCOPE_ENV
from operon.processes import owned_process
from test_process_long_cwd import long_directory

pytestmark = pytest.mark.skipif(os.name != 'nt', reason='Windows junction recovery')
ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def scoped(tmp_path, monkeypatch):
    import operon.process_paths as paths
    local = tmp_path / 'local'; local.mkdir()
    monkeypatch.setattr(paths, '_windows_local_app_data', lambda: local)
    root = tmp_path / 'attempt'; root.mkdir()
    env = prepare_scope(root, attempt_id='attempt-one', fence=3)
    monkeypatch.setenv(SCOPE_ENV, env[SCOPE_ENV])
    return root, local, env


def test_scope_reclaims_after_forced_worker_kill(scoped):
    root, local, env = scoped
    directory = long_directory(root)
    ready = root / 'ready.json'
    # Outer Job Object contains worker and child. Killing it bypasses the
    # worker finally block, reproducing Studio cancellation rather than a
    # cooperative exception in owned_process.
    source = (
        "import sys,json,time,subprocess; from pathlib import Path; "
        "sys.path.insert(0,sys.argv[1]); import operon.process_paths as pp; "
        "pp._windows_local_app_data=lambda:Path(sys.argv[2]); "
        "from operon.processes import owned_process; "
        "\nwith owned_process([sys.executable,'-I','-c','import time; time.sleep(90)'],cwd=sys.argv[3]) as child:"
        "\n Path(sys.argv[4]).write_text(json.dumps({'pid':child.pid}))"
        "\n time.sleep(90)\n")
    import psutil
    with owned_process([sys.executable, '-I', '-c', source, str(ROOT), str(local),
                        str(directory), str(ready)], cwd=root,
                       env={**os.environ, **env}, stdout=subprocess.PIPE, stderr=subprocess.PIPE) as worker:
        deadline = time.monotonic() + 20
        while not ready.exists() and worker.poll() is None and time.monotonic() < deadline:
            time.sleep(.05)
        if not ready.exists():
            worker.kill()
            raise AssertionError(worker.communicate(timeout=5))
        child_pid = json.loads(ready.read_text())['pid']
    assert not psutil.pid_exists(child_pid)
    alias_parent = next((local / 'Operon/ProcessCwd').glob('scope-*'))
    assert list(alias_parent.glob('operon-cwd-*'))
    # A fresh observer uses the durable scope + authoritative stop proof, not
    # worker PID guesses or process-local state.
    report = release_scope(root, attempt_id='attempt-one', fence=3, confirmed=True)
    assert report['state'] == 'cleaned' and len(report['removed']) == 1
    assert not alias_parent.exists()
    assert (directory / 'input.txt').read_text() == 'relative input'
    assert release_scope(root, attempt_id='attempt-one', fence=3, confirmed=True) == report


def test_uncertain_stop_and_wrong_fence_never_delete(scoped):
    root, local, _ = scoped
    owner = ProcessDirectory(long_directory(root))
    try:
        report = release_scope(root, attempt_id='attempt-one', fence=3, confirmed=False)
        assert report['state'] == 'recovery_required'
        assert Path(owner.path).exists()
        with pytest.raises(ValueError, match='fence'):
            release_scope(root, attempt_id='attempt-one', fence=4, confirmed=True)
        assert Path(owner.path).exists()
    finally:
        owner.finish(confirmed=True)
        release_scope(root, attempt_id='attempt-one', fence=3, confirmed=True)


def test_tampered_alias_preserved_and_other_scope_untouched(scoped, monkeypatch):
    root, local, env = scoped
    owner = ProcessDirectory(long_directory(root))
    owner.handles.close()  # simulate killed worker after containment is empty
    journal = owner.directory / 'owner.json'
    original = json.loads(journal.read_text())
    forged = {**original, 'alias': str(local / 'foreign')}
    journal.write_text(json.dumps(forged))
    other = root.parent / 'other'; other.mkdir()
    other_env = prepare_scope(other, attempt_id='other', fence=1)
    monkeypatch.setenv(SCOPE_ENV, other_env[SCOPE_ENV])
    second = ProcessDirectory(long_directory(other))
    try:
        report = release_scope(root, attempt_id='attempt-one', fence=3, confirmed=True)
        assert report['state'] == 'recovery_required' and report['errors']
        assert Path(owner.path).exists() and Path(second.path).exists()
    finally:
        journal.write_text(json.dumps(original))
        release_scope(root, attempt_id='attempt-one', fence=3, confirmed=True)
        second.finish(confirmed=True)
        release_scope(other, attempt_id='other', fence=1, confirmed=True)


def test_executor_requires_containment_proof_and_records_recovery(scoped):
    from operon.execution.unit_executor import RunPlanExecutor
    from operon.engine.executor import ExecutionResult
    root, _, _ = scoped
    owner = ProcessDirectory(long_directory(root)); owner.handles.close()
    executor = object.__new__(RunPlanExecutor)
    executor.directory = lambda context: root
    executor.supervisor = SimpleNamespace(generation_tree_exit=lambda *a, **kw: False)
    context = SimpleNamespace(attempt_id='attempt-one', fence=3)
    executor._release_scratch(context, ExecutionResult('cancelled', tree_alive=False))
    report = json.loads((root / 'process-cwd-cleanup.json').read_text())
    assert report['state'] == 'recovery_required' and Path(owner.path).exists()
    from operon.engine.supervisor import SupervisorError
    def stale_proof(*args, **kwargs):
        raise SupervisorError('Tree proof differs', code='recovery_required')
    executor.supervisor.generation_tree_exit = stale_proof
    executor._release_scratch(context, ExecutionResult('cancelled', tree_alive=False))
    report = json.loads((root / 'process-cwd-cleanup.json').read_text())
    assert report['state'] == 'recovery_required' and Path(owner.path).exists()
    executor.supervisor.generation_tree_exit = lambda *a, **kw: True
    executor._release_scratch(context, ExecutionResult('cancelled', tree_alive=False))
    assert not Path(owner.path).exists()
    assert json.loads((root / 'process-cwd-cleanup.json').read_text())['state'] == 'cleaned'


def test_external_cwd_data_is_not_owned_or_removed(scoped):
    root, local, _ = scoped
    external = root.parent / 'external-input'; external.mkdir()
    target = long_directory(external)
    owner = ProcessDirectory(target); owner.handles.close()
    report = release_scope(root, attempt_id='attempt-one', fence=3, confirmed=True)
    assert report['state'] == 'cleaned' and not Path(owner.path).exists()
    assert (target / 'input.txt').read_text() == 'relative input'
