"""The portable interpreter falls back to the newest patch of one minor."""
import json
from pathlib import Path

import pytest

from operon.contracts.base import ContractError
from operon.environment_store import acquisition


def details(version=(3, 11, 18)):
    return {'version': list(version), 'os': 'linux', 'arch': 'x86_64',
            'base_prefix': '/usr', 'prefix': '/usr'}


def harness(monkeypatch, tmp_path, downloadable, installed):
    """Pretend uv offers `downloadable` and records what it selected."""
    monkeypatch.setattr(acquisition.shutil, 'which', lambda name: '/usr/bin/uv')
    state = {'selected': None}

    def run_process(command, **kwargs):
        if command[1:3] == ['-I', '-c']:
            version = state['selected']
            return json.dumps({'version': list(version), 'os': 'linux', 'arch': 'x86_64',
                               'base_prefix': str(tmp_path / 'portable-python' / version_text(version)),
                               'prefix': str(tmp_path / 'portable-python' / version_text(version))})
        if 'install' in command:
            name = command[-1]
            if name not in downloadable:
                raise ContractError('uv failed', code='tool_failed')
            state['selected'] = installed[name]
            return ''
        if 'find' in command:
            if state['selected'] is None:
                raise ContractError('not installed', code='tool_failed')
            return str(tmp_path / 'portable-python' / version_text(state['selected']) / 'bin' / 'python3')
        raise AssertionError(command)

    monkeypatch.setattr(acquisition, 'run_process', run_process)
    return state


def version_text(version):
    return '.'.join(str(part) for part in version)


def test_exact_patch_is_preferred(monkeypatch, tmp_path):
    state = harness(monkeypatch, tmp_path, downloadable={'3.11.18', '3.11'},
                    installed={'3.11.18': (3, 11, 18), '3.11': (3, 11, 14)})
    actual = acquisition.standalone_python(tmp_path, details())
    assert actual['version'] == [3, 11, 18]
    assert state['selected'] == (3, 11, 18)


def test_missing_patch_falls_back_to_the_same_minor(monkeypatch, tmp_path):
    state = harness(monkeypatch, tmp_path, downloadable={'3.11'},
                    installed={'3.11': (3, 11, 14)})
    actual = acquisition.standalone_python(tmp_path, details())
    assert actual['version'] == [3, 11, 14]
    assert state['selected'] == (3, 11, 14)


def test_a_different_minor_is_never_accepted(monkeypatch, tmp_path):
    harness(monkeypatch, tmp_path, downloadable={'3.11'}, installed={'3.11': (3, 12, 0)})
    with pytest.raises(ContractError) as excinfo:
        acquisition.standalone_python(tmp_path, details())
    assert excinfo.value.code == 'environment_unverified'


def test_nothing_downloadable_is_reported(monkeypatch, tmp_path):
    harness(monkeypatch, tmp_path, downloadable=set(), installed={})
    with pytest.raises(ContractError) as excinfo:
        acquisition.standalone_python(tmp_path, details())
    assert excinfo.value.code == 'environment_preparation_required'
    assert '3.11.18' in str(excinfo.value)
