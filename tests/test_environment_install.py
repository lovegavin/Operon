"""Isolated environment planning, state and safety checks."""
import json
from pathlib import Path

import pytest

from operon import environment_install, environments


def manifest(root: Path, entries: dict) -> Path:
    (root / 'operon').mkdir(parents=True, exist_ok=True)
    (root / 'operon' / 'environments.json').write_text(
        json.dumps({'version': 1, 'environments': entries}), encoding='utf-8')
    return root


def test_plan_marks_missing_and_used_by(tmp_path):
    source = manifest(tmp_path / 'source', {'demo': {'python': '3.11', 'imports': []}})
    plan = environment_install.plan(tmp_path / 'external', [
        {'id': 'alpha', 'resources': {'environment': 'demo'}},
        {'id': 'beta'},
    ], source=source)
    assert plan['demo']['status'] == 'missing'
    assert plan['demo']['used_by'] == ['alpha']
    assert plan['demo']['interpreter'] == ''
    assert plan['demo']['error'] == ''


def test_state_ready_and_stale_from_receipt(tmp_path):
    source = manifest(tmp_path / 'source', {'demo': {'python': '3.11', 'imports': ['json']}})
    root = tmp_path / 'external'
    entry = environments.load(source)['demo']
    python = root / 'demo' / 'bin' / 'python'
    python.parent.mkdir(parents=True)
    python.write_text('#!/bin/sh\n', encoding='utf-8')
    python.chmod(0o755)
    assert environment_install.state('demo', root, source)['status'] == 'stale'
    (root / 'demo' / 'receipt.json').write_text(
        json.dumps({'spec_sha256': environment_install.spec_sha256(entry)}), encoding='utf-8')
    ready = environment_install.state('demo', root, source)
    assert ready['status'] == 'ready'
    assert ready['interpreter'] == str(python)


def test_prepare_creates_shared_venv_environment(tmp_path):
    source = manifest(tmp_path / 'source', {'demo': {'python': '3.11', 'imports': [], 'venv_shared': True}})
    runtime = environment_install.prepare('demo', tmp_path / 'external', source)
    assert runtime['status'] == 'ready'
    assert Path(runtime['interpreter']).is_file()
    assert (tmp_path / 'external' / 'demo' / 'receipt.json').is_file()
    assert environment_install.plan(tmp_path / 'external', source=source)['demo']['status'] == 'ready'


def test_prepare_rejects_unsafe_sources_before_writing(tmp_path):
    source = manifest(tmp_path / 'source', {
        'demo': {'python': '3.11', 'requirements': ['file:///etc/passwd']}})
    root = tmp_path / 'external'
    with pytest.raises(ValueError, match='unsupported package source'):
        environment_install.prepare('demo', root, source)
    assert not (root / 'demo').exists()


def test_prepare_rejects_absolute_python(tmp_path):
    source = manifest(tmp_path / 'source', {'demo': {'python': '../3.11'}})
    with pytest.raises(ValueError, match='invalid Python version'):
        environment_install.prepare('demo', tmp_path / 'external', source)


def test_unknown_environment_is_reported(tmp_path):
    source = manifest(tmp_path / 'source', {})
    with pytest.raises(ValueError, match='unknown isolated environment'):
        environment_install.state('nope', tmp_path / 'external', source)
