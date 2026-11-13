"""Regression: every isolated environment is committed and probed safely.

The Windows commit bug was not OpenMM-specific: any environment whose directory
was held open by a readiness probe could fail to rename. These tests use
non-OpenMM names to prove the shared code path is generic.
"""
import sys

from operon import dependencies, environment_install


def test_probe_blocks_while_any_environment_is_installing(monkeypatch):
    calls = []
    monkeypatch.setattr(environment_install, 'state', lambda name, root=None, source=None: {'status': 'installing'})
    monkeypatch.setattr(dependencies.subprocess, 'run', lambda *a, **k: calls.append(a))
    monkeypatch.setattr('operon.environments.resolve', lambda name: sys.executable)

    for name in ('esm3', 'boltz', 'antifold', 'openmm81'):
        result = dependencies.probe_environment('operator', name, ['json'])
        assert result['status'] == 'failed'
        assert 'still being installed' in result['error']
    assert calls == []


def test_commit_keeps_working_environment_for_generic_name(monkeypatch, tmp_path):
    final = tmp_path / 'esm3'
    final.mkdir()
    (final / 'marker').write_text('old', encoding='utf-8')
    staging = tmp_path / '.staging-esm3'
    staging.mkdir()
    (staging / 'marker').write_text('new', encoding='utf-8')

    environment_install._commit('esm3', staging, final)

    assert (final / 'marker').read_text(encoding='utf-8') == 'new'
    assert not list(tmp_path.glob('.previous-esm3-*'))


def test_commit_restores_previous_on_failure(monkeypatch, tmp_path):
    import os as _os
    final = tmp_path / 'boltz'
    final.mkdir()
    (final / 'marker').write_text('old', encoding='utf-8')
    staging = tmp_path / '.staging-boltz'
    staging.mkdir()
    real_rename = type(staging).rename
    calls = {'n': 0}

    def flaky(self, target):
        if self == staging:
            calls['n'] += 1
            raise PermissionError(5, 'Access is denied', str(self))
        return real_rename(self, target)

    monkeypatch.setattr(type(staging), 'rename', flaky)
    monkeypatch.setattr(environment_install.time, 'sleep', lambda seconds: None)

    try:
        environment_install._commit('boltz', staging, final)
    except RuntimeError as error:
        assert 'could not commit environment boltz' in str(error)
    else:
        raise AssertionError('commit should have failed')
    assert final.is_dir()
    assert (final / 'marker').read_text(encoding='utf-8') == 'old'
