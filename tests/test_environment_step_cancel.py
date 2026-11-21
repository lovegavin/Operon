"""Regression tests for bridged step execution.

Two failures were observed on the remote host:

* ``sequence_stats`` + ``FastqReader`` raised
  ``'Context' object has no attribute 'task_dir'`` because the bridge context
  did not expose the attribute the in-process worker provides;
* a long bridged step could not be cancelled: ``_run_step`` used
  ``subprocess.run`` and only noticed the cancellation marker after the step
  finished (an ``annotation_overlap_check`` step ran for 830 s).
"""

from __future__ import annotations

import pathlib
import sys
import threading
import time

import pytest

from operon import environments, env_worker


def test_bridge_context_exposes_task_dir(tmp_path):
    context = env_worker.Context({}, tmp_path)
    assert context.task_dir == tmp_path
    assert (context.task_dir / "cancel.requested") == tmp_path / "cancel.requested"


def test_execute_honours_cancel(tmp_path):
    states = {"cancel": False}
    started = threading.Event()
    result = {}

    def cancel():
        started.set()
        return states["cancel"]

    def run():
        try:
            environments._execute([sys.executable, "-c", "import time; time.sleep(30)"],
                                  tmp_path, pathlib.Path(sys.executable), (), timeout=60, cancel=cancel)
        except Exception as exc:  # noqa: BLE001 - the message is the assertion
            result["error"] = exc

    worker = threading.Thread(target=run, daemon=True)
    worker.start()
    assert started.wait(20), "cancellation callback was never polled"
    states["cancel"] = True
    worker.join(20)
    assert not worker.is_alive()
    assert "Run cancelled by user" in str(result.get("error"))


def test_execute_without_cancel_returns_output(tmp_path):
    completed = environments._execute([sys.executable, "-c", "print('bridge-ok')"],
                                      tmp_path, pathlib.Path(sys.executable), (), timeout=60)
    assert completed.returncode == 0
    assert completed.stdout.strip() == "bridge-ok"


def test_run_step_accepts_cancel_keyword(tmp_path):
    import inspect

    signature = inspect.signature(environments.run_step)
    assert "cancel" in signature.parameters
    assert "cancel" in inspect.signature(environments._run_step).parameters
