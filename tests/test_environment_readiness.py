"""Readiness must reflect whether the declared dependencies are present."""
import os

import pytest

from operon import environment_install


def _prepare(tmp_path, monkeypatch, status):
    entry = {'name': 'demo', 'python': '3.11', 'requirements': [], 'dependencies': []}
    target = tmp_path / 'demo'
    (target / 'Scripts').mkdir(parents=True)
    python = target / 'Scripts' / 'python.exe'
    python.write_text('', encoding='utf-8')
    os.chmod(python, 0o755)

    monkeypatch.setattr(environment_install.environments, 'describe', lambda name, source=None: entry)
    monkeypatch.setattr(environment_install, 'target', lambda name, root=None: target)
    monkeypatch.setattr(environment_install, 'spec_sha256', lambda value: 'spec')
    monkeypatch.setattr(environment_install, 'receipt', lambda name, root=None: {'spec_sha256': 'spec'})
    monkeypatch.setattr(environment_install, '_read', lambda path: {})
    monkeypatch.setattr(environment_install, 'platform_supported', lambda value: True)
    monkeypatch.setattr(environment_install, 'dependency_status', lambda value, location=None: status)
    return environment_install.state('demo')


def test_ready_requires_every_declared_dependency(tmp_path, monkeypatch):
    rows = [{'kind': 'requirements', 'name': 'pandas', 'installed': True},
            {'kind': 'requirements', 'name': 'scipy', 'installed': False}]
    result = _prepare(tmp_path, monkeypatch, (1, 2, rows))

    assert result['status'] == 'incomplete'
    assert result['dependency_installed'] == 1
    assert result['dependency_total'] == 2
    assert result['missing_dependencies'] == ['scipy']
    assert 'scipy' in result['error']


def test_ready_when_dependencies_are_complete(tmp_path, monkeypatch):
    rows = [{'kind': 'requirements', 'name': 'pandas', 'installed': True}]
    result = _prepare(tmp_path, monkeypatch, (1, 1, rows))

    assert result['status'] == 'ready'
    assert result['dependency_installed'] == 1
    assert result['missing_dependencies'] == []
