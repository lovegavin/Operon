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

def test_dependency_rows_does_not_count_the_bootstrap_wheel_twice():
    entry = {'requirements': ['wheel', 'setuptools>=68,<81'],
             'pip_wheels': ['setuptools>=68,<81', 'wheel']}
    rows = environment_install.dependency_rows(entry)

    assert [(row['kind'], row['name']) for row in rows] == [
        ('requirements', 'wheel'),
        ('requirements', 'setuptools>=68,<81'),
    ]


def test_dependency_rows_keeps_import_and_binary_checks():
    entry = {'requirements': ['wheel'], 'pip_wheels': ['wheel'],
             'imports': ['wheel'], 'binaries': ['wheel']}
    rows = environment_install.dependency_rows(entry)

    assert [row['kind'] for row in rows] == ['requirements', 'import', 'binary']


def _shared_venv(tmp_path, inherited: bool):
    base = tmp_path / 'base'
    site = base / 'lib' / 'python3.11' / 'site-packages'
    (site / 'wheel-0.48.0.dist-info').mkdir(parents=True)
    (site / 'wheel-0.48.0.dist-info' / 'METADATA').write_text('', encoding='utf-8')
    venv = tmp_path / 'env'
    (venv / 'bin').mkdir(parents=True)
    flag = 'true' if inherited else 'false'
    (venv / 'pyvenv.cfg').write_text(
        f'home = {base / "bin"}\ninclude-system-site-packages = {flag}\nversion = 3.11.18\n',
        encoding='utf-8')
    return venv


def test_installed_index_sees_packages_inherited_from_the_base_interpreter(tmp_path):
    venv = _shared_venv(tmp_path, inherited=True)

    assert environment_install.dependency_installed(
        {'kind': 'requirements', 'name': 'wheel'}, str(venv)) is True


def test_installed_index_ignores_the_base_interpreter_when_isolation_is_off(tmp_path):
    venv = _shared_venv(tmp_path, inherited=False)

    assert environment_install.dependency_installed(
        {'kind': 'requirements', 'name': 'wheel'}, str(venv)) is False
