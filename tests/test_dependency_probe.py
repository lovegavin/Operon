"""External tools must be looked up inside the declared environment."""
import os

from operon import dependencies


def _make_env(tmp_path, name, tool):
    base = tmp_path / name / 'bin'
    base.mkdir(parents=True)
    binary = base / tool
    binary.write_text('#!/bin/sh\n', encoding='utf-8')
    os.chmod(binary, 0o755)
    return tmp_path


def test_find_tool_searches_the_declared_environment(tmp_path, monkeypatch):
    make = _make_env(tmp_path, 'antismash', 'antismash')
    monkeypatch.setattr('operon.environments.root', lambda: tmp_path)
    monkeypatch.setattr('shutil.which', lambda name: None)

    assert dependencies.find_tool('antismash', 'antismash') == str(make / 'antismash' / 'bin' / 'antismash')


def test_probe_reports_a_missing_environment_before_missing_tools(tmp_path, monkeypatch):
    monkeypatch.setattr('operon.environments.root', lambda: tmp_path)
    entry = {'id': 'antismash_bgc', 'resources': {'environment': 'antismash', 'external_tools': ['antismash']}}

    results = dependencies.probe([entry])

    assert results['antismash_bgc']['status'] == 'failed'
    assert 'not installed' in results['antismash_bgc']['error']
