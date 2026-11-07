"""Process-tree ownership: launch receipts, adoption, confirmed stop and fences."""
import os
import sys
import time
from pathlib import Path

import psutil
import pytest

from biopipe.engine.supervisor import (
    LaunchSpec, ProcessSupervisor, SupervisorError, identity_alive,
)


def spec_for(tmp_path, code, *, name='worker.py'):
    script = tmp_path / name
    script.write_text(code, encoding='utf-8')
    return LaunchSpec(argv=(sys.executable, str(script)), cwd=str(tmp_path),
                      environment=dict(os.environ), stdout_path=str(tmp_path / 'logs' / 'worker.log'))


def test_launch_receipt_is_idempotent_and_adoptable(tmp_path):
    supervisor = ProcessSupervisor(tmp_path / 'super')
    spec = spec_for(tmp_path, 'import time\ntime.sleep(30)\n')
    receipt = supervisor.launch('attempt-1', fence=7, spec=spec)
    assert identity_alive(receipt.identity)
    # A lost launch reply must adopt the recorded process, never spawn a second.
    again = supervisor.launch('attempt-1', fence=7, spec=spec)
    assert again.adopted and again.identity.pid == receipt.identity.pid
    assert supervisor.poll_status('attempt-1')[0] == 'running'
    stopped = supervisor.stop('attempt-1', fence=7)
    assert stopped.confirmed and not identity_alive(receipt.identity)
    # Repeated stop is idempotent.
    assert supervisor.stop('attempt-1', fence=7).confirmed


def test_stale_fence_cannot_stop_or_adopt_another_attempt(tmp_path):
    supervisor = ProcessSupervisor(tmp_path / 'super')
    receipt = supervisor.launch('attempt-1', fence=7,
                                spec=spec_for(tmp_path, 'import time\ntime.sleep(30)\n'))
    with pytest.raises(SupervisorError):
        supervisor.launch('attempt-1', fence=8, spec=LaunchSpec((sys.executable, '-c', 'pass'),
                                                                str(tmp_path), dict(os.environ), ''))
    with pytest.raises(SupervisorError):
        supervisor.stop('attempt-1', fence=8)
    supervisor.stop('attempt-1', fence=7)


def test_owned_child_tree_is_stopped_and_confirmed(tmp_path):
    code = """
import subprocess, sys, time
child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)'])
open('child.pid', 'w').write(str(child.pid))
time.sleep(30)
"""
    supervisor = ProcessSupervisor(tmp_path / 'super')
    receipt = supervisor.launch('attempt-tree', fence=1, spec=spec_for(tmp_path, code))
    deadline = time.monotonic() + 5
    while not (tmp_path / 'child.pid').exists() and time.monotonic() < deadline:
        time.sleep(0.02)
    child_pid = int((tmp_path / 'child.pid').read_text())
    assert psutil.pid_exists(child_pid)
    stopped = supervisor.stop('attempt-tree', fence=1)
    assert stopped.confirmed
    assert not identity_alive(receipt.identity)
    deadline = time.monotonic() + 3
    while psutil.pid_exists(child_pid) and time.monotonic() < deadline:
        try:
            if psutil.Process(child_pid).status() == psutil.STATUS_ZOMBIE:
                break
        except psutil.NoSuchProcess:
            break
        time.sleep(0.02)
    assert not psutil.pid_exists(child_pid) or psutil.Process(child_pid).status() == psutil.STATUS_ZOMBIE


def test_launch_failure_keeps_a_failed_receipt_and_never_adopts(tmp_path):
    supervisor = ProcessSupervisor(tmp_path / 'super')
    spec = LaunchSpec(argv=(str(tmp_path / 'missing.exe'),), cwd=str(tmp_path),
                      environment=dict(os.environ), stdout_path=str(tmp_path / 'logs' / 'x.log'))
    with pytest.raises(SupervisorError):
        supervisor.launch('attempt-bad', fence=1, spec=spec)
    receipt = supervisor.read_receipt('attempt-bad')
    assert receipt.state == 'failed'
    with pytest.raises(SupervisorError):
        supervisor.launch('attempt-bad', fence=1, spec=spec)


def test_new_supervisor_instance_adopts_a_live_receipt(tmp_path):
    first = ProcessSupervisor(tmp_path / 'super')
    receipt = first.launch('attempt-adopt', fence=3,
                           spec=spec_for(tmp_path, 'import time\ntime.sleep(30)\n'))
    restarted = ProcessSupervisor(tmp_path / 'super')
    reconciled = restarted.reconcile('attempt-adopt', fence=3)
    assert reconciled is not None and reconciled.identity.pid == receipt.identity.pid
    assert restarted.stop('attempt-adopt', fence=3).confirmed
