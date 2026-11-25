import subprocess
import sys

import pytest

from operon.remote import provision


def test_cleanup_removes_previous_installations(tmp_path):
    managed = tmp_path / 'managed-v1'
    managed.mkdir()
    keep = ['code-current', 'env-current', 'setup-current.log']
    stale_files = ['source-old.tar.gz', 'install-old.sh', 'retire-old.py', 'setup-old.log']
    stale_dirs = ['code-old', 'env-old']
    untouched = ['mamba-cache', 'tools', 'environment.lock', 'publish.lock']
    for name in keep:
        if name.endswith('.log'):
            (managed / name).write_text('log')
        else:
            (managed / name).mkdir()
    for name in stale_dirs:
        (managed / name).mkdir()
        (managed / name / 'marker').write_text(name)
    for name in stale_files:
        (managed / name).write_text('x')
    for name in untouched:
        if name.endswith('.lock'):
            (managed / name).write_text('')
        else:
            (managed / name).mkdir()

    script = managed / 'cleanup-test.py'
    script.write_text(provision.CLEANUP_SCRIPT)
    result = subprocess.run(
        [sys.executable, '-I', str(script), str(managed),
         str(managed / 'code-current'), str(managed / 'env-current'),
         str(managed / 'setup-current.log')],
        capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stderr
    assert 'BP_CLEANUP_OK' in result.stdout
    remaining = sorted(p.name for p in managed.iterdir())
    assert remaining == sorted(keep + untouched + ['cleanup-test.py'])


def test_retire_script_clears_pool_directory_after_force_stop():
    script = provision.RETIRE_SCRIPT
    assert 'shutil.rmtree(pool_dir, ignore_errors=True)' in script
    assert 'import glob, hashlib, json, os, shutil, signal' in script
    # The socket directory must not be reused for the pool record directory.
    assert 'socket_dir = os.path.join(tempfile.gettempdir()' in script
    assert 'os.path.join(socket_dir, hashlib.sha256' in script
    assert 'pool_dir = os.path.dirname(record) if record else None' in script
    # A forced stop only clears the record after the pool was signalled.
    signalled = script.index('kill(pid, signal.SIGTERM)')
    cleared = script.index('shutil.rmtree(pool_dir, ignore_errors=True)', signalled)
    assert signalled < cleared

def test_retire_script_stops_the_pool_before_the_daemons():
    script = provision.RETIRE_SCRIPT
    assert script.index('def pool_pids') < script.index('if "operon.remote.server" not in joined')
    assert 'shared pool is running; stop it first or use force' in script
    assert 'pool record without a process' in script

def _idle(arguments, cwd):
    return subprocess.Popen(
        [sys.executable, '-I', '-c', 'import time; time.sleep(120)', *arguments],
        cwd=str(cwd))


def test_retire_script_survives_a_pool_found_only_through_proc(tmp_path):
    if not sys.platform.startswith('linux'):
        pytest.skip('the retire script inspects /proc')
    home = tmp_path / 'home'
    workspace = home / 'workspace'
    workspace.mkdir(parents=True)
    pool = _idle([str(home), 'operon.managed_pool'], home)
    server = _idle(['--workspace', str(workspace), 'operon.remote.server'], home)
    script = tmp_path / 'retire-test.py'
    script.write_text(provision.RETIRE_SCRIPT)
    try:
        result = subprocess.run(
            [sys.executable, '-I', str(script), str(home)],
            capture_output=True, text=True, timeout=60)
    finally:
        for process in (pool, server):
            process.kill()
            process.wait(timeout=30)
    assert result.returncode == 0, result.stderr
    assert 'BP_RETIRE_RESULT' in result.stdout
