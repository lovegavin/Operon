"""Attempt layout preserves ownership without embedding unbounded node labels."""
from types import SimpleNamespace
from pathlib import Path
import os

from operon.bytecode import executable_path, io_path
from operon.execution.unit_executor import RunPlanExecutor


def test_attempt_layout_is_run_scoped_and_adopts_an_existing_preparation(tmp_path):
    executor = RunPlanExecutor(tmp_path, environment_store=None, package_root=tmp_path, bindings={})
    context = SimpleNamespace(run={'id': 'run-123'}, unit={'local_id': 'node-' + 'n' * 160}, attempt_id='attempt-456')
    first = executor.directory(context)
    assert first == io_path(tmp_path / 'runs/run-123/attempts/attempt-456')
    assert context.unit['local_id'] not in str(first)
    # An existing attempt is adopted in place; no data movement or new attempt.
    previous = tmp_path / 'runs/run-123/nodes' / context.unit['local_id'] / 'attempts/attempt-456'
    io_path(previous).mkdir(parents=True)
    io_path(previous / 'prepared.json').write_text('{}')
    assert executor.directory(context) == previous


def test_short_executable_uses_normal_spelling_without_resolving_launch_alias(tmp_path):
    path = tmp_path / 'alias/runtime.exe'
    assert executable_path(io_path(path)) == str(path)
    if os.name == 'nt':
        deep = tmp_path / ('segment-' * 35) / 'runtime.exe'
        assert executable_path(deep).startswith('\\\\?\\')
