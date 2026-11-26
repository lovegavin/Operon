"""Isolated interpreter bridge for operators with conflicting runtimes."""

import json
from pathlib import Path

import numpy as np
import pytest

from operon import environments


def _descriptor(name="structure_interface_core", environment="fake"):
    registry = json.loads((Path(__file__).resolve().parents[1] / "library/seed/operon/builtin_packages.json").read_text(encoding="utf-8"))
    descriptor = next(e for p in registry["packages"] for e in p["descriptors"] if e["id"] == name)
    return {**descriptor, "resources": {**descriptor["resources"], "environment": environment}}


def _form():
    from src.core.forms import Form
    from src.reader.readers._encoder import LabelEncoder

    columns = ("x", "y", "z", "residue_number", "resname", "chain", "atom_name", "element")
    raw = [
        (0, 0, 0, 1, "ALA", "A", "CA", "C"),
        (4, 0, 0, 1, "ALA", "A", "CA", "C"),
        (0, 0, 5, 2, "GLY", "B", "CA", "C"),
        (4, 0, 5, 2, "GLY", "B", "CA", "C"),
    ]
    encoders, data = {}, []
    for column in ("resname", "chain", "atom_name", "element"):
        index = columns.index(column)
        values = [row[index] for row in raw]
        encoder = LabelEncoder()
        encoder.fit_transform(values)
        encoders[column] = encoder
    for row in raw:
        values = []
        for index, (column, value) in enumerate(zip(columns, row)):
            values.append(float(encoders[column].mapping[value]) if column in encoders else float(value))
        data.append(values)
    return Form(
        data=np.asarray(data, dtype=np.float32),
        dims=["atom", "field"],
        labels={"atom": {f"atom{i}": i for i in range(len(raw))},
                "field": {name: index for index, name in enumerate(columns)}},
        info={"missing_code": np.nan, "encoders": {"field": encoders}},
    )


def _host_worker_environment(monkeypatch):
    """The host interpreter keeps numpy in the user site; the bridge hides it."""
    import os
    import site

    real = environments.worker_environment

    def wrapper(python, paths=(), tools=None):
        env = real(python, paths, tools)
        user = site.getusersitepackages()
        env['PYTHONPATH'] = os.pathsep.join([env.get('PYTHONPATH', ''), user])
        return env

    monkeypatch.setattr(environments, 'worker_environment', wrapper)


def test_bridge_runs_a_step_in_the_environment_interpreter(monkeypatch, tmp_path):
    import sys

    monkeypatch.setattr(environments, "resolve", lambda name: Path(sys.executable))
    monkeypatch.setattr(environments, "code_root", lambda: Path(__file__).resolve().parents[1])
    _host_worker_environment(monkeypatch)

    step = environments.proxy_step(_descriptor())()

    class Ctx(dict):
        step_params = {"output": "core", "binder_chains": "A", "target_chains": "B"}
        metadata = {}

    ctx = Ctx()
    step.run(ctx, [_form()])
    result = ctx["core"]
    assert result.dims == ["residue", "statistic"]
    assert result.data.shape[1] == 4
    assert "n_core" in result.info and "n_rim" in result.info
    assert isinstance(step.export(ctx), dict)


def test_bridge_reports_a_missing_environment():
    from src.core.errors import StepError

    step = environments.proxy_step(_descriptor(environment="absent"))()

    class Ctx(dict):
        step_params = {"output": "core"}
        metadata = {}

    with pytest.raises(StepError, match="is not installed"):
        step.run(Ctx(), [_form()])


def test_bridge_preserves_axis_metadata_missing_values_and_cleans_files(monkeypatch, tmp_path):
    import sys
    from src.core.forms import Form
    _host_worker_environment(monkeypatch)
    monkeypatch.setattr(environments.tempfile, 'tempdir', str(tmp_path))
    form = Form(data=np.array([[3.0, np.nan]]), dims=['sample', 'feature'],
                labels={'sample': {'s': 0}, 'feature': {'a': 0, 'b': 1}},
                info={'missing_code': np.nan, 'group': ['control']},
                axis_info={'sample': ['group']})
    result, _, _ = environments.run_step(_descriptor('log_transform'), [form],
                                         {'output': 'log', 'base': 2, 'pseudocount': 1}, Path(sys.executable))
    assert result.axis_info == form.axis_info
    assert result.info['group'] == ['control']
    assert np.isnan(result.info['missing_code'])
    np.testing.assert_allclose(result.data, [[2, np.nan]], equal_nan=True)
    assert not list(tmp_path.glob('envbridge-*'))
    with pytest.raises(Exception):
        environments.run_step(_descriptor('log_transform'), [form],
                              {'output': 'log', 'pseudocount': -1}, Path(sys.executable))
    assert not list(tmp_path.glob('envbridge-*'))


def test_bridge_uses_portable_interpreter_and_process_environment(monkeypatch, tmp_path):
    import os
    executable = tmp_path / 'example/python.exe'
    executable.parent.mkdir()
    executable.touch()
    executable.chmod(0o755)
    monkeypatch.setenv('OPERON_ENVIRONMENTS_ROOT', str(tmp_path))
    monkeypatch.setenv('SystemRoot', 'windows-system-location')
    monkeypatch.setenv('PYTHONHOME', 'unrelated-python')
    monkeypatch.setenv('PYTHONPATH', 'unrelated-modules')
    monkeypatch.setenv('HF_ENDPOINT', 'https://example.invalid/models')
    assert environments.resolve('example') == executable
    env = environments.worker_environment(executable)
    assert {key.upper(): value for key, value in env.items()}['SYSTEMROOT'] == 'windows-system-location'
    assert 'PYTHONHOME' not in env
    assert env['PYTHONPATH'] == str(environments.code_root())
    assert env['PATH'].split(os.pathsep)[0] == str(executable.parent)
    assert env['HF_ENDPOINT'] == 'https://example.invalid/models'


def test_openmm81_manifest_uses_bundled_pdbfixer():
    manifest = json.loads(
        (Path(__file__).resolve().parents[1] / "library/seed/operon/environments.json").read_text(encoding="utf-8")
    )
    entry = manifest["environments"]["openmm81"]
    assert entry["imports"] == ["openmm", "numpy"]
    assert "pdbfixer" not in entry["imports"]
    assert "no_build_isolation" not in entry
    assert "setuptools>=68,<81" in entry["requirements"]
    assert entry.get("venv_shared") is True
    assert entry["python"] == "3.11"


def test_bridge_runs_a_report_only_step_without_an_output_parameter(monkeypatch):
    import sys

    monkeypatch.setattr(environments, 'resolve', lambda name: Path(sys.executable))
    monkeypatch.setattr(environments, 'code_root', lambda: Path(__file__).resolve().parents[1])
    monkeypatch.setattr(environments, 'run_step', lambda *args, **kwargs: (None, {'rows': 3}, ''))

    step = environments.proxy_step(_descriptor())()
    seen = {}

    class Ctx(dict):
        step_params = {'note': 'report'}
        metadata = {}

        def __setitem__(self, key, value):
            seen[key] = value

    step.run(Ctx(), [_form()])
    assert seen == {}
    assert step.export(Ctx()) == {'rows': 3}
"""Wiring tests: the plugin lock has to reach the isolated step worker."""
import json
from pathlib import Path
from types import SimpleNamespace


def test_bridge_publishes_the_plugin_lock_for_worker(monkeypatch, tmp_path):
    from operon import environments

    seen = {}

    def fake_run(command, **kwargs):
        directory = Path(kwargs['cwd'])
        seen['command'] = command
        seen['readers'] = json.loads((directory / 'readers.json').read_text(encoding='utf-8'))
        (directory / 'result.json').write_text(json.dumps({'kind': 'none', 'export': {}}), encoding='utf-8')
        return SimpleNamespace(returncode=0, stdout='', stderr='')

    monkeypatch.setattr(environments.subprocess, 'run', fake_run)
    import operon.bytecode
    monkeypatch.setattr(operon.bytecode, 'executable_path', lambda value: value)
    monkeypatch.setattr(environments, 'worker_environment', lambda python, paths=(), tools=None: {})

    lock = {'protocol_version': 3, 'packages': [], 'descriptors': [{'id': 'PdbReader'}]}
    environments._run_step(tmp_path, {'entry_point': 'x:Y'}, [], {}, Path('python'),
                           timeout=30, lock=lock)

    assert seen['command'][1:] == ['-m', 'operon.env_worker', str(tmp_path)]
    assert seen['readers'] == lock


def test_bridge_omits_the_lock_when_the_caller_has_none(monkeypatch, tmp_path):
    from operon import environments

    seen = {}

    def fake_run(command, **kwargs):
        directory = Path(kwargs['cwd'])
        seen['readers'] = (directory / 'readers.json').exists()
        (directory / 'result.json').write_text(json.dumps({'kind': 'none', 'export': {}}), encoding='utf-8')
        return SimpleNamespace(returncode=0, stdout='', stderr='')

    monkeypatch.setattr(environments.subprocess, 'run', fake_run)
    import operon.bytecode
    monkeypatch.setattr(operon.bytecode, 'executable_path', lambda value: value)
    monkeypatch.setattr(environments, 'worker_environment', lambda python, paths=(), tools=None: {})

    environments._run_step(tmp_path, {'entry_point': 'x:Y'}, [], {}, Path('python'), timeout=30)

    assert seen['readers'] is False


def test_proxy_step_forwards_the_lock_to_run_step(monkeypatch):
    from operon import environments

    seen = {}

    def fake_run_step(descriptor, inputs, params, python, *, timeout, paths, outputs=None, lock=None,
                      tools=None, cancel=None, artifacts_root=None):
        seen['lock'] = lock
        seen['paths'] = paths
        return None, {}, ''

    monkeypatch.setattr(environments, 'run_step', fake_run_step)
    monkeypatch.setattr(environments, 'resolve', lambda environment: Path('python'))

    descriptor = {'id': 'demo', 'entry_point': 'x:Y', 'version': '1.0.0', 'inputs_arity': 0,
                  'outputs': [], 'contracts': {'inputs': [], 'output': {}},
                  'resources': {'environment': 'demo'}}
    lock = {'protocol_version': 3}
    step = environments.proxy_step(descriptor, [], lock=lock)()

    class Ctx(dict):
        step_params = {}
        metadata = {}

    step.run(Ctx(), [])

    assert seen['lock'] == lock

def test_revive_uses_the_label_encoder_the_library_ships():
    from operon.env_worker import _revive

    try:
        from src.reader.readers._encoder import LabelEncoder
    except Exception:
        import pytest
        pytest.skip('the installed library is not importable here')

    revived = _revive({'encoders': {'field': {'atom_name': {'__labelencoder__': {'N': 0, 'CA': 1}}}}})
    encoder = revived['encoders']['field']['atom_name']
    assert isinstance(encoder, LabelEncoder)
    assert encoder.inverse_transform([1.0]) == ['CA']


def test_worker_environment_publishes_resolved_tools(monkeypatch, tmp_path):
    from operon import environments

    monkeypatch.delenv('OPERON_PACKED_TOOLS', raising=False)
    monkeypatch.setattr(environments, 'code_root', lambda: tmp_path)
    env = environments.worker_environment(Path('python'), (), {'mkdssp': '/opt/dssp/bin/mkdssp', 'gone': None})
    assert json.loads(env['OPERON_PACKED_TOOLS']) == {'mkdssp': '/opt/dssp/bin/mkdssp'}
    env = environments.worker_environment(Path('python'), (), None)
    assert 'OPERON_PACKED_TOOLS' not in env


def test_worker_environment_publishes_the_environments_root(monkeypatch, tmp_path):
    from operon import environments

    monkeypatch.delenv('OPERON_ENVIRONMENTS_ROOT', raising=False)
    monkeypatch.setattr(environments, 'root', lambda: tmp_path / 'environments')
    env = environments.worker_environment(Path('python'))
    assert env['OPERON_ENVIRONMENTS_ROOT'] == str(tmp_path / 'environments')

    monkeypatch.setenv('OPERON_ENVIRONMENTS_ROOT', '/explicit/root')
    env = environments.worker_environment(Path('python'))
    assert env['OPERON_ENVIRONMENTS_ROOT'] == '/explicit/root'
