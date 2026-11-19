"""The bridge context must expose the run directory to step code."""

from pathlib import Path

from operon.env_worker import Context


def test_context_exposes_the_run_directory(tmp_path):
    context = Context({'note': 'report'}, tmp_path)
    assert context.out_dir == tmp_path
    assert context.memory is not None
    assert Path(context.memory.run_dir) == tmp_path


def test_context_defaults_to_the_working_directory():
    context = Context({})
    assert context.out_dir == Path.cwd()
