import os
import stat
import sys
from pathlib import Path

from src.task.step.steps import _envpython


def _executable(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('#!/bin/sh\n', encoding='utf-8')
    path.chmod(path.stat().st_mode | stat.S_IXUSR)
    return path


def test_environment_python_prefers_the_configured_override(monkeypatch, tmp_path):
    target = _executable(tmp_path / 'python')
    monkeypatch.setenv('OPERON_ENV_ALPHAFOLD2', str(target))
    assert _envpython.environment_python('alphafold2') == str(target)


def test_environment_python_falls_back_to_a_sibling_environment(monkeypatch, tmp_path):
    root = tmp_path / 'root'
    current = root / 'current-env'
    target = _executable(root / 'alphafold2' / 'bin' / 'python')
    monkeypatch.delenv('OPERON_ENV_ALPHAFOLD2', raising=False)
    monkeypatch.setattr(sys, 'prefix', str(current))

    from operon import environments

    monkeypatch.setattr(environments, 'resolve', lambda name: None)
    assert _envpython.environment_python('alphafold2') == str(target)


def test_environment_python_returns_empty_when_nothing_matches(monkeypatch, tmp_path):
    monkeypatch.delenv('OPERON_ENV_ALPHAFOLD2', raising=False)
    monkeypatch.setattr(sys, 'prefix', str(tmp_path / 'root' / 'current'))
    from operon import environments

    monkeypatch.setattr(environments, 'resolve', lambda name: None)
    assert _envpython.environment_python('alphafold2') == ''
