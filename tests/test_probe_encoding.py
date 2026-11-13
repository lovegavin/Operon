"""Regression: probes must not decode child output with the OS locale.

On a Chinese Windows host the default ``subprocess`` text encoding is GBK even
when the child writes UTF-8 diagnostic paths, which raised UnicodeDecodeError
inside readiness checks and then crashed while slicing ``stderr``.
"""
import sys
from types import SimpleNamespace

from operon import dependencies, environments


def test_probe_decodes_utf8_and_never_crashes(monkeypatch):
    seen = {}

    def fake_run(argv, **kwargs):
        seen.update(kwargs)
        seen['argv'] = list(argv)
        return SimpleNamespace(returncode=1, stdout='', stderr='import failed: 路径')

    monkeypatch.setattr(dependencies.subprocess, 'run', fake_run)
    monkeypatch.setattr(environments, 'resolve', lambda name: sys.executable)

    result = dependencies.probe_environment('operator', 'fake-env', ['missing_module'])

    assert seen['encoding'] == 'utf-8'
    assert '-X' in seen['argv'] and 'utf8' in seen['argv']
    assert seen['errors'] == 'replace'
    assert result['status'] == 'failed'
    assert result['stderr'] == 'import failed: 路径'


def test_probe_tolerates_missing_stderr(monkeypatch):
    monkeypatch.setattr(dependencies.subprocess, 'run',
                        lambda argv, **kwargs: SimpleNamespace(returncode=1, stdout='boom', stderr=None))
    monkeypatch.setattr(environments, 'resolve', lambda name: sys.executable)

    result = dependencies.probe_environment('operator', 'fake-env', ['missing_module'])

    assert result['status'] == 'failed'
    assert 'boom' in result['error']
    assert result['stderr'] == ''


def test_environment_probe_forces_utf8_child(monkeypatch, tmp_path):
    seen = {}

    def fake_run(argv, **kwargs):
        seen['argv'] = list(argv)
        return SimpleNamespace(returncode=0, stdout='', stderr='')

    monkeypatch.setattr(environments.subprocess, 'run', fake_run)
    monkeypatch.setattr(environments, 'resolve', lambda name: sys.executable)
    monkeypatch.setattr(environments, 'describe', lambda name, root=None: {'imports': ['json']})
    monkeypatch.setattr(environments, 'root', lambda: tmp_path)

    ok, python, error = environments.probe('fake-env')

    assert ok is True and error == ''
    assert '-X' in seen['argv'] and 'utf8' in seen['argv']
