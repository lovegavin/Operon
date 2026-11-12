import subprocess
import sys

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
    assert 'shutil.rmtree(os.path.dirname(path), ignore_errors=True)' in provision.RETIRE_SCRIPT
    assert 'import glob, hashlib, json, os, shutil, signal' in provision.RETIRE_SCRIPT
