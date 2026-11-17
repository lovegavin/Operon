"""Real CreateProcess regression: long cwd, relative I/O and owned cancellation."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time

import pytest

from operon.bytecode import io_path
from operon.process_paths import ProcessDirectory
from operon.processes import owned_process

pytestmark = pytest.mark.skipif(os.name != 'nt', reason='Windows CreateProcess boundary')


def long_directory(tmp_path):
    result = tmp_path
    while len(str(result)) < 300:
        result /= 'long directory with spaces 123456789'
    result = io_path(result)
    result.mkdir(parents=True)
    (result / 'input.txt').write_text('relative input', encoding='utf-8')
    return result


def test_owned_process_long_cwd_relative_io_and_cleanup(tmp_path):
    directory = long_directory(tmp_path)
    code = "from pathlib import Path; Path('out.txt').write_text(Path('input.txt').read_text())"
    with owned_process([sys.executable, '-I', '-c', code], cwd=directory,
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE) as child:
        out, err = child.communicate(timeout=15)
        assert child.returncode == 0, err
    assert (directory / 'out.txt').read_text() == 'relative input'


def test_aliases_are_per_launch_and_never_delete_target(tmp_path):
    directory = long_directory(tmp_path)
    first, second = ProcessDirectory(directory), ProcessDirectory(directory)
    try:
        assert first.path != second.path
        assert Path(first.path).samefile(directory)
        alias = Path(first.path)
        first.finish(confirmed=True)
        assert not alias.exists()
        assert (Path(second.path) / 'input.txt').read_text() == 'relative input'
    finally:
        first.finish(confirmed=True)
        second.finish(confirmed=True)
    assert directory.is_dir()


def test_uncertain_tree_retains_alias_and_journal(tmp_path):
    directory = long_directory(tmp_path)
    owner = ProcessDirectory(directory)
    owner.finish(confirmed=False)
    assert Path(owner.path).samefile(directory)
    assert json.loads((owner.directory / 'owner.json').read_text())['state'] == 'recovery_required'
    owner.finish(confirmed=True)


def test_exception_stops_long_cwd_process(tmp_path):
    import psutil
    directory = long_directory(tmp_path)
    with pytest.raises(RuntimeError, match='cancel'):
        with owned_process([sys.executable, '-I', '-c', 'import time; time.sleep(60)'],
                           cwd=directory) as child:
            pid = child.pid
            raise RuntimeError('cancel')
    assert not psutil.pid_exists(pid)


def test_spawn_failure_releases_alias(tmp_path, monkeypatch):
    directory = long_directory(tmp_path)
    created = []
    original = ProcessDirectory.__init__
    def capture(self, *args, **kwargs):
        original(self, *args, **kwargs)
        created.append(Path(self.path))
    monkeypatch.setattr(ProcessDirectory, '__init__', capture)
    with pytest.raises(OSError):
        with owned_process([str(tmp_path / 'missing.exe')], cwd=directory):
            pass
    assert created and all(not item.exists() for item in created)


def test_script_adapter_uses_common_path_layer_and_export_collects_it(tmp_path):
    from operon.script_operators import inspect_script, execute_script
    from operon.export.collector import kernel_files
    directory = long_directory(tmp_path)
    script = tmp_path / 'generator.py'
    script.write_text('# output: result file.txt\nimport argparse\nfrom pathlib import Path\n'
        'p=argparse.ArgumentParser(); p.add_argument("--out-result"); a=p.parse_args()\n'
        'Path("relative.txt").write_text("42")\n'
        'Path(a.out_result).write_text(Path("relative.txt").read_text())\n')
    result = execute_script(inspect_script(script), {}, {}, directory / 'script output')
    assert Path(result['files']['result']).read_text() == '42'
    files = kernel_files(Path(__file__).resolve().parents[1])
    assert 'operon/process_paths.py' in files


def test_external_tool_runner_uses_same_cwd_boundary(tmp_path):
    from operon.tool_runner import ToolRunner
    directory = long_directory(tmp_path)
    events = []
    class Context:
        task_dir = directory
        metadata = {}
        def artifact_path(self, name):
            return directory / name
        def event(self, name, **values):
            events.append(name)
    runner = ToolRunner(Context(), {'executor': 'native', 'memory_mb': 256})
    output = runner.run([sys.executable, '-I', '-c',
        'from pathlib import Path; Path("relative.txt").write_text("ok"); print("tool ok")'])
    assert 'tool ok' in output.read_text()
    assert (runner.directory / 'relative.txt').read_text() == 'ok'
    assert 'external_exit' in events


def test_redirected_task_temp_does_not_become_alias_metadata_root(tmp_path, monkeypatch):
    import tempfile
    import operon.process_paths as paths
    directory = long_directory(tmp_path)
    local = tmp_path / 'user-local'
    local.mkdir()
    monkeypatch.setattr(paths, '_windows_local_app_data', lambda: local)
    monkeypatch.setattr(tempfile, 'tempdir', str(directory))
    for name in ('TEMP', 'TMP', 'TMPDIR'):
        monkeypatch.setenv(name, str(directory))
    code = ('import json,tempfile; from pathlib import Path; '
            'Path("out.txt").write_text(Path("input.txt").read_text()); '
            'print(json.dumps({"temp":tempfile.gettempdir()}))')
    with owned_process([sys.executable, '-I', '-c', code], cwd=directory,
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE) as child:
        out, err = child.communicate(timeout=15)
        assert child.returncode == 0, err
    assert Path(json.loads(out)['temp']).samefile(directory)
    assert (directory / 'out.txt').read_text() == 'relative input'
    assert list((local / 'Operon' / 'ProcessCwd').iterdir()) == []
    assert tempfile.gettempdir() == str(directory)


def test_windows_metadata_root_ignores_environment_folder_spoofing(tmp_path, monkeypatch):
    import operon.process_paths as paths
    actual = paths._windows_local_app_data()
    monkeypatch.setenv('LOCALAPPDATA', str(tmp_path / 'untrusted-placeholder'))
    assert paths._windows_local_app_data() == actual
    assert actual.is_dir()
